"""
dm/provider_client.py — Provider-agnostic LLM client interface for HermesDM.

Define LLMClient como abstracción. Cada provider (MiniMax, GLM, OpenAI,
Anthropic, etc.) implementa esta interfaz.

Uso:
    from dm.provider_client import LLMClient, MiniMaxProvider

    # MiniMax
    client = MiniMaxProvider(api_key="...")
    ng = NarrativeGenerator(llm_client=client)

    # Otro provider — solo implementa LLMClient
    client = TuProviderGLM(api_key="...")
    ng = NarrativeGenerator(llm_client=client)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Standard response from an LLM client."""
    text: str
    raw: Any = None
    model: str | None = None
    usage: dict | None = None
    latency_ms: float | None = None


class LLMClient(ABC):
    """
    Abstract base class for LLM providers.

    Implement this interface to add a new provider:
        class TuProvider(LLMClient):
            def text(self, prompt, system=None, max_tokens=256, temperature=0.8) -> LLMResponse:
                # Tu implementación
                pass
    """

    @abstractmethod
    def text(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 256,
        temperature: float = 0.8,
    ) -> LLMResponse:
        """
        Send a text prompt and return the LLM response.

        Args:
            prompt: The user prompt
            system: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            LLMResponse with the generated text
        """
        ...

    def close(self) -> None:
        """Cleanup resources. Override if needed."""
        pass


# ── MiniMax Provider (default for HermesDM) ──────────────────────────────────

class MiniMaxProvider(LLMClient):
    """
    MiniMax provider implementation via OpenRouter.

    Requires OPENROUTER_API_KEY env var.
    Falls back to MINIMAX_API_KEY for direct MiniMax API.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "minimax/minimax-m2.7",
    ) -> None:
        import os
        # Try OpenRouter first, then fallback to direct MiniMax
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "") or os.getenv("MINIMAX_API_KEY", "")
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.model = model or os.getenv("MINIMAX_MODEL", "minimax/minimax-m2.7")

    def text(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 256,
        temperature: float = 0.8,
    ) -> LLMResponse:
        import json
        import time
        import urllib.request

        # ── Audit: start timing ──────────────────────────────────────────
        start_ts = time.perf_counter()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.load(resp)
        except Exception as exc:
            # ── Audit: log error ───────────────────────────────────────
            self._log_llm(
                prompt=prompt,
                system=system,
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                latency_ms=(time.perf_counter() - start_ts) * 1000,
                error=str(exc),
            )
            raise

        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage")
        latency_ms = (time.perf_counter() - start_ts) * 1000

        # ── Audit: log success ───────────────────────────────────────────
        self._log_llm(
            prompt=prompt,
            system=system,
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_text=content,
            usage=usage,
            latency_ms=latency_ms,
        )

        return LLMResponse(
            text=content,
            raw=result,
            model=self.model,
            usage=usage,
            latency_ms=latency_ms,
        )

    def _log_llm(
        self,
        *,
        prompt: str,
        system: str | None,
        model: str,
        max_tokens: int,
        temperature: float,
        response_text: str | None = None,
        usage: dict | None = None,
        latency_ms: float | None = None,
        error: str | None = None,
    ) -> None:
        """Write an llm_call event to the audit log."""
        try:
            import sys
            from pathlib import Path

            # Add project root to path so audit_logger can be imported
            project_root = Path(__file__).parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            from bot.audit_logger import get_audit_logger

            audit = get_audit_logger()

            # Truncate very large payloads to keep logs manageable
            max_prompt_len = 8000
            max_response_len = 8000

            prompt_snip = prompt[:max_prompt_len] + ("..." if len(prompt) > max_prompt_len else "")
            system_snip = (system[:max_prompt_len] + ("..." if len(system) > max_prompt_len else "")) if system else None
            response_snip = (response_text[:max_response_len] + ("..." if len(response_text) > max_response_len else "")) if response_text else None

            metadata: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
            }

            if usage:
                metadata["usage"] = usage
            if error:
                metadata["error"] = error

            audit.log_event(
                event_type="llm_call",
                input=prompt_snip,
                output=response_snip,
                metadata=metadata,
            )
        except Exception:
            # Never let audit logging break the actual LLM call
            pass


# ── Gemini Provider ──────────────────────────────────────────────────────────

class GeminiProvider(LLMClient):
    """
    Google Gemini provider via the REST API.

    Requires GEMINI_API_KEY env var.
    Model: gemini-2.0-flash (default).
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
    ) -> None:
        import os
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model

    def text(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 256,
        temperature: float = 0.8,
    ) -> LLMResponse:
        import json
        import time
        import urllib.request
        import urllib.error

        start_ts = time.perf_counter()

        # Build contents: user prompt only (system instruction goes in systemInstruction)
        contents = [
            {"role": "user", "parts": [{"text": prompt}]},
        ]

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
                # Disable extended thinking — use all output tokens for actual content
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }

        # Gemini uses systemInstruction for system prompts, not a role in contents
        if system:
            payload["systemInstruction"] = {
                "role": "user",
                "parts": [{"text": system}],
            }

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}"
            f":generateContent?key={self.api_key}"
        )

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.load(resp)
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Gemini API error {exc.code}: {error_body[:500]}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

        latency_ms = (time.perf_counter() - start_ts) * 1000

        try:
            content = result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise RuntimeError(f"Unexpected Gemini response structure: {result}")

        usage = result.get("usageMetadata", {})

        return LLMResponse(
            text=content,
            raw=result,
            model=self.model,
            usage=usage,
            latency_ms=latency_ms,
        )


# ── Provider factory ─────────────────────────────────────────────────────────

def get_provider(name: str, **kwargs) -> LLMClient:
    """
    Get an LLM provider by name.

    Args:
        name: Provider name (e.g. "minimax", "openai", "glm")
        **kwargs: Additional arguments passed to the provider constructor

    Returns:
        LLMClient instance

    Raises:
        ValueError: If provider is not supported
    """
    name = name.lower()
    if name == "minimax":
        return MiniMaxProvider(**kwargs)
    if name == "gemini":
        return GeminiProvider(**kwargs)
    # Agregar otros providers aquí
    # elif name == "openai":
    #     return OpenAIProvider(**kwargs)
    # elif name == "glm":
    #     return GLMProvider(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {name}. Supported: minimax, gemini")
