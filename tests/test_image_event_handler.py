"""
Tests for dm/image_event_handler.py — auto image generation triggers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from dm.image_event_handler import (
    DEFAULT_AUTO_IMAGE_TRIGGERS,
    ImageContext,
    ImageEventHandler,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_provider():
    """Mock ImageProvider that returns a successful result."""
    provider = MagicMock()
    provider.generate = AsyncMock()
    provider.generate.return_value = MagicMock()
    provider.generate.return_value.path = "/tmp/test.png"
    return provider


@pytest.fixture
def handler(mock_provider):
    """Fresh ImageEventHandler for each test."""
    return ImageEventHandler(provider=mock_provider)


@pytest.fixture
def basic_ctx():
    """Basic ImageContext for trigger testing."""
    return ImageContext(
        scene_type="nat_20",
        narrative="The hero lands a devastating blow!",
    )


# ── Tests: should_generate ──────────────────────────────────────────────────

class TestShouldGenerate:
    """should_generate returns True/False based on trigger config."""

    def test_disabled_handler_returns_false(self, handler, basic_ctx):
        """Disabled handler never generates."""
        handler.set_enabled(False)
        assert handler.should_generate(basic_ctx) is False

    def test_matching_trigger_returns_true(self, handler, basic_ctx):
        """Enabled handler with matching trigger returns True."""
        basic_ctx.scene_type = "nat_20"
        handler.triggers["nat_20"] = True
        assert handler.should_generate(basic_ctx) is True

    def test_non_matching_trigger_returns_false(self, handler, basic_ctx):
        """Non-matching trigger returns False."""
        basic_ctx.scene_type = "normal_turn"
        handler.triggers["normal_turn"] = False
        assert handler.should_generate(basic_ctx) is False

    def test_unknown_trigger_uses_other_default(self, handler):
        """Unknown scene_type uses 'other' default trigger."""
        ctx = ImageContext(scene_type="weird_event", narrative="...")
        handler.triggers["other"] = False
        assert handler.should_generate(ctx) is False

    def test_cooldown_active_returns_false(self, handler, basic_ctx):
        """Active cooldown prevents generation."""
        import time
        handler._last_image_time = time.time()  # Set to now
        handler.cooldown_seconds = 60.0
        assert handler.should_generate(basic_ctx) is False


# ── Tests: maybe_generate ───────────────────────────────────────────────────

class TestMaybeGenerate:
    """maybe_generate orchestrates the full generation flow."""

    @pytest.mark.asyncio
    async def test_no_trigger_returns_none(self, handler, basic_ctx):
        """When trigger doesn't match, returns None."""
        basic_ctx.scene_type = "normal_turn"
        handler.triggers["normal_turn"] = False
        result = await handler.maybe_generate(basic_ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_successful_generation_returns_result(self, handler, basic_ctx):
        """Matching trigger + successful generation returns ImageResult."""
        basic_ctx.scene_type = "nat_20"
        handler.triggers["nat_20"] = True
        result = await handler.maybe_generate(basic_ctx)
        assert result is not None
        handler.provider.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_provider_error_returns_none(self, handler, basic_ctx):
        """Provider error returns None (doesn't crash)."""
        from dm.image_provider import ImageGenerationError
        handler.provider.generate.side_effect = ImageGenerationError("API error")
        basic_ctx.scene_type = "nat_20"
        handler.triggers["nat_20"] = True
        result = await handler.maybe_generate(basic_ctx)
        assert result is None




class TestSetTriggers:
    """set_triggers updates the trigger configuration."""

    def test_set_triggers_updates_dict(self, handler):
        """Calling set_triggers replaces the trigger dict."""
        new_triggers = {"nat_20": True, "other": False}
        handler.set_triggers(new_triggers)
        assert handler.triggers == new_triggers

    def test_none_triggers_uses_default(self, mock_provider):
        """Handler with triggers=None uses DEFAULT_AUTO_IMAGE_TRIGGERS."""
        h = ImageEventHandler(provider=mock_provider, triggers=None)
        assert h.triggers == DEFAULT_AUTO_IMAGE_TRIGGERS

    @pytest.mark.asyncio
    async def test_maybe_generate_combat_limit(self, handler, basic_ctx):
        """When combat image count exceeds max, generation is skipped."""
        handler.triggers["nat_20"] = True
        basic_ctx.scene_type = "nat_20"
        basic_ctx.combat_state = True
        handler._combat_image_count = 10  # exceeds max_per_combat=5
        result = await handler.maybe_generate(basic_ctx)
        assert result is None

    def test_combat_count_reset(self, handler):
        """reset_combat_count sets counter to 0."""
        handler._combat_image_count = 10
        handler.reset_combat_count()
        assert handler._combat_image_count == 0

# ── Tests: _infer_scene_type ────────────────────────────────────────────────

class TestInferSceneType:
    """_infer_scene_type maps ActionResult fields to scene types."""

    def test_nat_20_returns_nat_20(self):
        """Nat 20 result → 'nat_20' scene type."""
        class FakeResult:
            nat_20 = True
            nat_1 = False
        assert ImageEventHandler._infer_scene_type(FakeResult()) == "nat_20"

    def test_nat_1_returns_nat_1(self):
        """Nat 1 result → 'nat_1' scene type."""
        class FakeResult:
            nat_20 = False
            nat_1 = True
        assert ImageEventHandler._infer_scene_type(FakeResult()) == "nat_1"

    def test_normal_returns_other(self):
        """Normal result → 'other' scene type."""
        class FakeResult:
            nat_20 = False
            nat_1 = False
        assert ImageEventHandler._infer_scene_type(FakeResult()) == "other"


# ── Tests: from_action_result ───────────────────────────────────────────────

class TestFromActionResult:
    """from_action_result creates ImageContext from ActionResult."""

    def test_creates_context_with_scene_type(self):
        """Factory creates ImageContext with inferred scene type."""
        class FakeResult:
            narrative = "Critical hit!"
            nat_20 = True
            nat_1 = False

        handler = ImageEventHandler(provider=MagicMock())
        ctx = handler.from_action_result(
            MagicMock(),
            FakeResult(),
            genre="dark fantasy",
        )
        assert ctx.scene_type == "nat_20"
        assert ctx.narrative == "Critical hit!"
        assert ctx.genre == "dark fantasy"
        assert ctx.is_critical is True
        assert ctx.is_fumble is False
