"""
tests/test_image_provider.py — Tests for image generation providers.
"""
import json
import os
import time
import unittest
from unittest.mock import MagicMock, patch

import pytest

from dm.image_provider import (
    FalProvider,
    FluxProvider,
    ImageGenerationError,
    ImageProvider,
    MiniMaxProvider,
    NanoBananaProvider,
    PollinationsProvider,
    build_scene_prompt,
    get_provider,
    list_providers,
)


# ── Provider Factory Tests ────────────────────────────────────────────────────


class TestFactory(unittest.TestCase):
    def test_list_providers_includes_all(self):
        providers = list_providers()
        assert "pollinations" in providers
        assert "minimax" in providers
        assert "flux" in providers
        assert "nanobanana" in providers
        assert "fal" in providers

    def test_get_provider_pollinations(self):
        p = get_provider("pollinations")
        assert isinstance(p, PollinationsProvider)
        assert p.name == "pollinations"

    def test_get_provider_fal(self):
        p = get_provider("fal", api_key="test_key")
        assert isinstance(p, FalProvider)
        assert p.name == "fal"
        assert p.api_key == "test_key"

    def test_get_provider_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown image provider"):
            get_provider("nonexistent")


# ── FalProvider Tests ─────────────────────────────────────────────────────────


class TestFalProvider(unittest.TestCase):
    def test_init_reads_env_var(self):
        with patch.dict(os.environ, {"FAL_KEY": "env_key_123"}):
            p = FalProvider()
            assert p.api_key == "env_key_123"
            assert p.model == "fal-ai/flux/dev"
            assert p.timeout == 120

    def test_init_accepts_params(self):
        p = FalProvider(api_key="param_key", model="fal-ai/flux/schnell", timeout=60)
        assert p.api_key == "param_key"
        assert p.model == "fal-ai/flux/schnell"
        assert p.timeout == 60

    def test_generate_no_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            p = FalProvider()
            with pytest.raises(ImageGenerationError, match="fal.ai API key not set"):
                # Use asyncio.run for async method
                import asyncio
                asyncio.run(p.generate("a dragon", "combat"))

    @patch("dm.image_provider.urllib.request.urlopen")
    def test_generate_success(self, mock_urlopen):
        """Test that generate() returns ImageResult on successful response."""
        # Mock the API response
        api_resp = MagicMock()
        api_resp.read.return_value = json.dumps({
            "images": [{"url": "https://fal.ai/cdn/test_image.png"}]
        }).encode()
        api_resp.__enter__ = MagicMock(return_value=api_resp)
        api_resp.__exit__ = MagicMock(return_value=False)

        # Mock the image download response
        img_resp = MagicMock()
        img_resp.read.return_value = b"PNGFAKEIMAGEDATA" * 100
        img_resp.__enter__ = MagicMock(return_value=img_resp)
        img_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [api_resp, img_resp]

        import asyncio
        p = FalProvider(api_key="test_key")
        result = asyncio.run(p.generate("a wizard casting fireball", "combat"))

        assert result.provider == "fal"
        assert result.prompt_used == "a wizard casting fireball"
        assert result.path.startswith("/tmp/hermes_img_fal_")
        assert result.elapsed_seconds >= 0

        # Verify the API request
        calls = mock_urlopen.call_args_list
        assert len(calls) == 2

        # First call: POST to fal.run
        req = calls[0][0][0]
        assert req.get_full_url() == "https://fal.run/fal-ai/flux/dev"
        assert req.get_method() == "POST"
        assert req.get_header("Authorization") == "Bearer test_key"
        body = json.loads(req.data)
        assert body["prompt"] == "a wizard casting fireball"
        assert body["image_size"] == "1024x1024"
        assert body["num_inference_steps"] == 28

    @patch("dm.image_provider.urllib.request.urlopen")
    def test_generate_custom_model_and_size(self, mock_urlopen):
        """Test that kwargs override defaults."""
        api_resp = MagicMock()
        api_resp.read.return_value = json.dumps({
            "images": [{"url": "https://fal.ai/cdn/test.png"}]
        }).encode()
        api_resp.__enter__ = MagicMock(return_value=api_resp)
        api_resp.__exit__ = MagicMock(return_value=False)

        img_resp = MagicMock()
        img_resp.read.return_value = b"PNGFAKEIMAGEDATA" * 100
        img_resp.__enter__ = MagicMock(return_value=img_resp)
        img_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [api_resp, img_resp]

        import asyncio
        p = FalProvider(api_key="test_key")
        result = asyncio.run(p.generate(
            "a dragon",
            "combat",
            model="fal-ai/flux/schnell",
            image_size="512x512",
            num_inference_steps=4,
            seed=42,
        ))

        assert result.provider == "fal"
        calls = mock_urlopen.call_args_list
        req = calls[0][0][0]
        assert req.get_full_url() == "https://fal.run/fal-ai/flux/schnell"
        body = json.loads(req.data)
        assert body["image_size"] == "512x512"
        assert body["num_inference_steps"] == 4
        assert body["seed"] == 42

    @patch("dm.image_provider.urllib.request.urlopen")
    def test_generate_401_error(self, mock_urlopen):
        """Test that 401 returns clear error message."""
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            "https://fal.run/fal-ai/flux/dev",
            401,
            "Unauthorized",
            {},
            None,
        )

        import asyncio
        p = FalProvider(api_key="bad_key")
        with pytest.raises(ImageGenerationError, match=r"fal\.ai auth failed \(401\)"):
            asyncio.run(p.generate("test", "combat"))

    @patch("dm.image_provider.urllib.request.urlopen")
    def test_generate_404_error(self, mock_urlopen):
        """Test that 404 returns clear error message."""
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            "https://fal.run/fal-ai/flux/nonexistent",
            404,
            "Not Found",
            {},
            None,
        )

        import asyncio
        p = FalProvider(api_key="test_key", model="fal-ai/flux/nonexistent")
        with pytest.raises(ImageGenerationError, match=r"fal\.ai model not found \(404\)"):
            asyncio.run(p.generate("test", "combat"))

    @patch("dm.image_provider.urllib.request.urlopen")
    def test_generate_no_images_in_response(self, mock_urlopen):
        """Test error when response has no images array."""
        api_resp = MagicMock()
        api_resp.read.return_value = json.dumps({"detail": "Some error"}).encode()
        api_resp.__enter__ = MagicMock(return_value=api_resp)
        api_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.return_value = api_resp

        import asyncio
        p = FalProvider(api_key="test_key")
        with pytest.raises(ImageGenerationError, match="No images in fal.ai response"):
            asyncio.run(p.generate("test", "combat"))

    @patch("dm.image_provider.urllib.request.urlopen")
    def test_generate_empty_image_url(self, mock_urlopen):
        """Test error when image URL is empty."""
        api_resp = MagicMock()
        api_resp.read.return_value = json.dumps({
            "images": [{"url": ""}]
        }).encode()
        api_resp.__enter__ = MagicMock(return_value=api_resp)
        api_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.return_value = api_resp

        import asyncio
        p = FalProvider(api_key="test_key")
        with pytest.raises(ImageGenerationError, match="No image URL in fal.ai response"):
            asyncio.run(p.generate("test", "combat"))

    @patch("dm.image_provider.urllib.request.urlopen")
    def test_generate_image_too_small(self, mock_urlopen):
        """Test error when downloaded image is too small."""
        api_resp = MagicMock()
        api_resp.read.return_value = json.dumps({
            "images": [{"url": "https://fal.ai/cdn/tiny.png"}]
        }).encode()
        api_resp.__enter__ = MagicMock(return_value=api_resp)
        api_resp.__exit__ = MagicMock(return_value=False)

        img_resp = MagicMock()
        img_resp.read.return_value = b"tiny"  # < 1000 bytes
        img_resp.__enter__ = MagicMock(return_value=img_resp)
        img_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [api_resp, img_resp]

        import asyncio
        p = FalProvider(api_key="test_key")
        with pytest.raises(ImageGenerationError, match="fal.ai image too small"):
            asyncio.run(p.generate("test", "combat"))


# ── Prompt Builder Tests ─────────────────────────────────────────────────────


class TestBuildScenePrompt(unittest.TestCase):
    def test_basic_prompt(self):
        prompt = build_scene_prompt(
            "The dragon breathes fire",
            "boss_intro",
            genre="fantasy",
        )
        assert "dragon breathes fire" in prompt
        assert "epic boss entrance" in prompt
        assert "fantasy art medieval cinematic 4k" in prompt

    def test_truncate_long_prompt(self):
        long_narrative = "A" * 500
        prompt = build_scene_prompt(long_narrative, "normal_turn", max_chars=200)
        assert len(prompt) <= 200

    def test_unknown_scene_type(self):
        prompt = build_scene_prompt("Something happens", "unknown_type")
        assert "cinematic scene" in prompt

    def test_genre_suffix(self):
        prompt = build_scene_prompt("A city", "discovery", genre="cyberpunk")
        assert "cyberpunk neon dystopian cinematic 4k" in prompt


if __name__ == "__main__":
    unittest.main()
