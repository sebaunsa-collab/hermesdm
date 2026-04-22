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
    MiniMax provider implementation.

    Requires MINIMAX_API_KEY and optionally MINIMAX_BASE_URL in environment
    or constructor.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.minimax.io/v1",
        model: str = "MiniMax-M2.7",
    ) -> None:
        import os
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
        self.base_url = base_url or os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
        self.model = model

    def text(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 256,
        temperature: float = 0.8,
    ) -> LLMResponse:
        import json
        import urllib.request

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

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.load(resp)

        content = result["choices"][0]["message"]["content"]
        return LLMResponse(
            text=content,
            raw=result,
            model=self.model,
            usage=result.get("usage"),
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
    # Agregar otros providers aquí
    # elif name == "openai":
    #     return OpenAIProvider(**kwargs)
    # elif name == "glm":
    #     return GLMProvider(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {name}. Supported: minimax")
