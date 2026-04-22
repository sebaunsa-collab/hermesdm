"""
dm/image_provider.py — Image generation providers.

Abstraction layer for image generation APIs.
All providers return a local PNG/JPG path.

Usage:
    from dm.image_provider import get_provider, PollinationsProvider
    provider = get_provider("pollinations")
    path = await provider.generate("a dragon in a cave", "combat_climax")
"""
import os
import time
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ImageGenerationError(Exception):
    """Raised when image generation fails."""


# ── Genre → style suffix for better prompts ──────────────────────────────────

GENRE_STYLE = {
    "fantasy": "fantasy art medieval cinematic 4k",
    "cyberpunk": "cyberpunk neon dystopian cinematic 4k",
    "horror": "dark horror cinematic 4k",
    "zombie": "post-apocalyptic zombie survival dark 4k",
    "romance": "romantic cinematic soft lighting 4k",
    "scifi": "science fiction cinematic 4k",
    "historical": "historical cinematic 4k",
    "viking": "viking nordic dark fantasy cinematic 4k",
    "western": "western cinematic vintage 4k",
    "noir": "film noir black and white cinematic",
    "default": "cinematic 4k",
}


@dataclass
class ImageResult:
    """Result of an image generation call."""
    path: str           # Absolute local path to the generated image
    provider: str       # Provider name used
    elapsed_seconds: float
    prompt_used: str     # Prompt that was actually sent to the provider


class SceneType(Enum):
    """Types of narrative scenes that can trigger image generation."""
    NAT_20 = "nat_20"
    NAT_1 = "nat_1"
    PLAYER_DEATH = "player_death"
    NPC_DEATH = "npc_death"
    BOSS_INTRO = "boss_intro"
    BOSS_DEATH = "boss_death"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    DISCOVERY = "discovery"
    CRITICAL_WOUND = "critical_wound"
    DRAMATIC_VICTORY = "dramatic_victory"
    NORMAL_TURN = "normal_turn"
    OTHER = "other"


# ── Prompt Builder ─────────────────────────────────────────────────────────────

def build_scene_prompt(
    narrative: str,
    scene_type: str,
    genre: str = "fantasy",
    characters: list[str] | None = None,
    mood: str = "dramatic",
    max_chars: int = 380,
) -> str:
    """
    Convert narrative context into a concise image generation prompt.

    Keeps prompt < max_chars to avoid 404 on Pollinations.
    """
    # Add style suffix
    style = GENRE_STYLE.get(genre.lower(), GENRE_STYLE["default"])

    # Core action from narrative (first sentence, trimmed)
    core = narrative.strip().split("\n")[0]
    if len(core) > 200:
        core = core[:200].rsplit(" ", 1)[0] + "..."

    # Build final prompt — genre + scene_type hint + core + style
    type_hints = {
        SceneType.NAT_20: "epic critical hit",
        SceneType.NAT_1: "disaster comedic moment",
        SceneType.PLAYER_DEATH: "character death dark",
        SceneType.NPC_DEATH: "npc death dramatic",
        SceneType.BOSS_INTRO: "epic boss entrance",
        SceneType.BOSS_DEATH: "epic victory",
        SceneType.SESSION_START: "adventure beginning",
        SceneType.SESSION_END: "dramatic conclusion",
        SceneType.DISCOVERY: "mysterious discovery",
        SceneType.CRITICAL_WOUND: "danger close combat",
        SceneType.DRAMATIC_VICTORY: "epic triumphant victory",
        SceneType.NORMAL_TURN: "action scene",
        SceneType.OTHER: "cinematic scene",
    }
    # Normalize scene_type to enum
    try:
        st = SceneType(scene_type)
    except ValueError:
        st = SceneType.OTHER
    hint = type_hints.get(st, "cinematic scene")
    prompt = f"{core}, {hint}, {style}"

    # Truncate to max_chars safely
    if len(prompt) > max_chars:
        # Cut at last space before limit
        prompt = prompt[:max_chars].rsplit(" ", 1)[0]

    return prompt


# ── ImageProvider ABC ─────────────────────────────────────────────────────────

class ImageProvider(ABC):
    """Abstract base for image generation providers."""

    name: str = "base"

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        scene_type: str,
        **kwargs: Any,
    ) -> ImageResult:
        """
        Generate an image from a text prompt.

        Args:
            prompt: The image prompt (should be < 400 chars)
            scene_type: Semantic type of scene (e.g. "nat_20", "boss_death")
            **kwargs: Provider-specific options

        Returns:
            ImageResult with local path to the generated image

        Raises:
            ImageGenerationError: If generation fails
        """

    def _result(self, path: str, prompt: str, elapsed: float) -> ImageResult:
        return ImageResult(path=path, provider=self.name, elapsed_seconds=elapsed, prompt_used=prompt)


# ── PollinationsProvider (DEFAULT) ────────────────────────────────────────────

class PollinationsProvider(ImageProvider):
    """
    Pollinations.ai — free, fast, no API key required.
    Uses Stable Diffusion via https://image.pollinations.ai/

    Pros: Free, fast (0.5-3s), unlimited
    Cons: Quality is good-not-great, long prompts cause 404
    """

    name = "pollinations"
    BASE_URL = "https://image.pollinations.ai/prompt/{prompt_encoded}"
    DEFAULT_SIZE = (1024, 1024)

    def __init__(
        self,
        width: int = 1024,
        height: int = 1024,
        model: str = "flux",
        seed: int | None = None,
        timeout: int = 60,
    ):
        self.width = width
        self.height = height
        self.model = model
        self.seed = seed
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        scene_type: str,
        **kwargs: Any,
    ) -> ImageResult:
        width = kwargs.get("width", self.width)
        height = kwargs.get("height", self.height)
        model = kwargs.get("model", self.model)
        seed = kwargs.get("seed", self.seed)

        encoded_prompt = urllib.parse.quote(prompt.strip(), safe="")
        params = f"width={width}&height={height}&model={model}&nologo=true"
        if seed is not None:
            params += f"&seed={seed}"
        url = f"{self.BASE_URL.format(prompt_encoded=encoded_prompt)}?{params}"

        output_path = f"/tmp/hermes_img_{int(time.time())}_{seed or 42}.png"

        headers = {"User-Agent": "Mozilla/5.0 (compatible; HermesDM/1.0)"}
        req = urllib.request.Request(url, headers=headers)

        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
        except Exception as e:
            raise ImageGenerationError(f"Pollinations failed: {e}") from e

        elapsed = time.time() - start

        if len(data) < 1000:
            raise ImageGenerationError(
                f"Response too small ({len(data)} bytes) — server error or 404"
            )

        os.makedirs(os.path.dirname(output_path) or "/tmp", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(data)

        return self._result(output_path, prompt, elapsed)


# ── MiniMaxProvider ────────────────────────────────────────────────────────────

class MiniMaxProvider(ImageProvider):
    """
    MiniMax image generation API — high quality, paid.

    Requires MINIMAX_API_KEY env var.
    Cost: ~$0.02-0.05 per image, ~60-90s generation time.
    """

    name = "minimax"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "image-01",
        aspect_ratio: str = "1:1",
        timeout: int = 120,
    ):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.model = model
        self.aspect_ratio = aspect_ratio
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        scene_type: str,
        **kwargs: Any,
    ) -> ImageResult:
        if not self.api_key:
            raise ImageGenerationError(
                "MiniMax API key not set. Set MINIMAX_API_KEY env var."
            )

        import json

        model = kwargs.get("model", self.model)
        ratio = kwargs.get("aspect_ratio", self.aspect_ratio)

        url = "https://api.minimax.io/v1/image_generation"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": ratio,
        }

        import urllib.request

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )

        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read())
        except Exception as e:
            raise ImageGenerationError(f"MiniMax API error: {e}") from e

        elapsed = time.time() - start

        # MiniMax returns a URL to the image
        image_url = result.get("data", [{}])[0].get("url", "")
        if not image_url:
            raise ImageGenerationError(f"No image URL in MiniMax response: {result}")

        # Download the image
        output_path = f"/tmp/hermes_img_minimax_{int(time.time())}.png"
        img_req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(img_req, timeout=30) as resp:
            data = resp.read()

        os.makedirs(os.path.dirname(output_path) or "/tmp", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(data)

        return self._result(output_path, prompt, elapsed)


# ── FluxProvider ──────────────────────────────────────────────────────────────

class FluxProvider(ImageProvider):
    """
    Flux (via local Stable Diffusion or HF Inference API).

    Can point to:
    - Local oobabooga/comfyUI (localhost:7860)
    - Hugging Face Inference API (hf.co/models)
    - Any FLUX.1-compatible API endpoint

    Requires FLUX_ENDPOINT and optionally FLUX_API_KEY env vars.
    """

    name = "flux"

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        timeout: int = 120,
    ):
        self.endpoint = endpoint or os.environ.get("FLUX_ENDPOINT", "http://localhost:7860")
        self.api_key = api_key or os.environ.get("FLUX_API_KEY", "")
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        scene_type: str,
        **kwargs: Any,
    ) -> ImageResult:
        import json
        import urllib.request

        output_path = f"/tmp/hermes_img_flux_{int(time.time())}.png"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {"prompt": prompt, "width": 1024, "height": 1024}
        payload.update(kwargs)

        req = urllib.request.Request(
            self.endpoint.rstrip("/") + "/v1/generate",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )

        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read())
        except Exception as e:
            raise ImageGenerationError(f"Flux API error: {e}") from e

        elapsed = time.time() - start

        # Try to extract image from result (varies by endpoint)
        image_data = result.get("images", [{}])[0].get("data") or result.get("image", "")
        if isinstance(image_data, str):
            # base64 encoded
            import base64
            image_data = base64.b64decode(image_data)

        if not image_data or len(image_data) < 1000:
            raise ImageGenerationError(f"No valid image in Flux response: {result}")

        os.makedirs(os.path.dirname(output_path) or "/tmp", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(image_data)

        return self._result(output_path, prompt, elapsed)


# ── NanoBananaProvider ─────────────────────────────────────────────────────────

class NanoBananaProvider(ImageProvider):
    """
    Generic REST provider for any image gen API that accepts JSON {prompt} and returns an image.

    Configure via env vars:
    - NANOBANANA_ENDPOINT: Full URL to POST /generate
    - NANOBANANA_API_KEY: Optional auth header
    - NANOBANANA_FIELD: Field name for prompt (default: "prompt")
    """

    name = "nanobanana"

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        prompt_field: str = "prompt",
        timeout: int = 120,
    ):
        self.endpoint = endpoint or os.environ.get("NANOBANANA_ENDPOINT", "")
        self.api_key = api_key or os.environ.get("NANOBANANA_API_KEY", "")
        self.prompt_field = prompt_field
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        scene_type: str,
        **kwargs: Any,
    ) -> ImageResult:
        if not self.endpoint:
            raise ImageGenerationError(
                "NanoBanana endpoint not set. Set NANOBANANA_ENDPOINT env var."
            )

        import json
        import urllib.request

        output_path = f"/tmp/hermes_img_nanobanana_{int(time.time())}.png"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {self.prompt_field: prompt, **kwargs}

        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )

        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                content_type = resp.headers.get("Content-Type", "")
                data = resp.read()
        except Exception as e:
            raise ImageGenerationError(f"NanoBanana API error: {e}") from e

        elapsed = time.time() - start

        # If response is JSON, try to extract image URL or base64
        if "application/json" in content_type:
            result = json.loads(data)
            image_url = result.get("url") or result.get("image_url") or result.get("data", {}).get("url")
            if image_url:
                img_req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(img_req, timeout=30) as resp:
                    data = resp.read()
            else:
                # Try base64
                b64 = result.get("image") or result.get("data", "")
                if b64:
                    import base64
                    data = base64.b64decode(b64)

        if len(data) < 1000:
            raise ImageGenerationError(f"Invalid NanoBanana response ({len(data)} bytes)")

        os.makedirs(os.path.dirname(output_path) or "/tmp", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(data)

        return self._result(output_path, prompt, elapsed)


# ── Factory ───────────────────────────────────────────────────────────────────

_PROVIDER_CLASSES: dict[str, type[ImageProvider]] = {
    "pollinations": PollinationsProvider,
    "minimax": MiniMaxProvider,
    "flux": FluxProvider,
    "nanobanana": NanoBananaProvider,
}


def get_provider(
    provider_name: str = "pollinations",
    **kwargs: Any,
) -> ImageProvider:
    """
    Factory: return an ImageProvider instance by name.

    Usage:
        provider = get_provider("pollinations")
        provider = get_provider("minimax", api_key="sk-...")
        provider = get_provider("flux", endpoint="http://localhost:7860")
    """
    cls = _PROVIDER_CLASSES.get(provider_name.lower())
    if cls is None:
        available = ", ".join(_PROVIDER_CLASSES.keys())
        raise ValueError(
            f"Unknown image provider '{provider_name}'. "
            f"Available: {available}"
        )
    return cls(**kwargs)


def list_providers() -> list[str]:
    """Return names of all available providers."""
    return list(_PROVIDER_CLASSES.keys())
