"""
tests/test_world_flags.py — Tests for World State Flags (Phase 3: Narrative Progression Gates).

Tests world_flags persistence and querying:
  - new_state() initializes world_flags
  - set_world_flag() persists flag values
  - check_world_flag() reads flag values
  - Immutability guard: True→False rejected
"""

import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from state import state_manager
from state.state_manager import (
    new_state,
    save_state,
    load_state,
    set_world_flag,
    check_world_flag,
    CAMPAIGNS_DIR,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def temp_campaigns_dir():
    """Temporary campaigns directory for isolated tests."""
    tmp = tempfile.mkdtemp()
    old = state_manager.CAMPAIGNS_DIR
    state_manager.CAMPAIGNS_DIR = Path(tmp)
    yield tmp
    state_manager.CAMPAIGNS_DIR = old
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def campaign_state(temp_campaigns_dir):
    """Create a fresh campaign state for testing."""
    cid = "test_flags_001"
    state = new_state(cid, "Test Flags", "fantasy")
    save_state(cid, state)
    yield cid
    # Cleanup
    from state.state_manager import _state_path
    p = Path(temp_campaigns_dir) / cid / "state.json"
    if p.exists():
        p.unlink()


# ------------------------------------------------------------------
# new_state() world_flags initialization
# ------------------------------------------------------------------

class TestNewStateWorldFlags:
    """Tests for world_flags initialization in new_state()."""

    def test_new_state_has_world_flags_key(self):
        """new_state() should include a world_flags dict."""
        state = new_state("test_f1", "Test", "fantasy")
        assert "world_flags" in state, (
            "state must contain 'world_flags' key"
        )

    def test_world_flags_is_empty_dict(self):
        """world_flags should start as an empty dict."""
        state = new_state("test_f2", "Test", "fantasy")
        assert state["world_flags"] == {}
        assert isinstance(state["world_flags"], dict)

    def test_new_state_compatible_with_existing_keys(self):
        """Other state keys should still be present."""
        state = new_state("test_f3", "Test", "fantasy")
        assert "campaign" in state
        assert "combat" in state
        assert "npcs" in state
        assert "world" in state
        assert "quests" in state
        assert "history" in state


# ------------------------------------------------------------------
# set_world_flag / check_world_flag
# ------------------------------------------------------------------

class TestSetAndCheckWorldFlag:
    """Tests for set_world_flag() and check_world_flag()."""

    def test_set_world_flag_true(self, campaign_state):
        """set_world_flag should persist True value."""
        cid = campaign_state
        set_world_flag(cid, "boss_defeated", True)
        assert check_world_flag(cid, "boss_defeated") is True

    def test_check_world_flag_default_false(self, campaign_state):
        """check_world_flag should return False for unset flags."""
        cid = campaign_state
        assert check_world_flag(cid, "nonexistent") is False

    def test_set_world_flag_persists_across_loads(self, campaign_state):
        """set_world_flag should persist to JSON and survive reload."""
        cid = campaign_state
        set_world_flag(cid, "bridge_repaired", True)

        # Reload state
        state = load_state(cid)
        assert state["world_flags"]["bridge_repaired"] is True

    def test_set_world_flag_multiple_flags(self, campaign_state):
        """Multiple flags can be set independently."""
        cid = campaign_state
        set_world_flag(cid, "flag_a", True)
        set_world_flag(cid, "flag_b", True)
        set_world_flag(cid, "flag_c", False)

        assert check_world_flag(cid, "flag_a") is True
        assert check_world_flag(cid, "flag_b") is True
        assert check_world_flag(cid, "flag_c") is False

    def test_check_world_flag_default_value_default_false(self, campaign_state):
        """Default return for missing flags should be False."""
        cid = campaign_state
        # Set boss_defeated = True first
        set_world_flag(cid, "boss_defeated", True)
        # Now check a different key
        assert check_world_flag(cid, "castle_conquered") is False


# ------------------------------------------------------------------
# Immutability Guard
# ------------------------------------------------------------------

class TestImmutabilityGuard:
    """Tests for the immutability guard: True→False should be rejected."""

    def test_cannot_flip_true_to_false(self, campaign_state):
        """Once a flag is True, it cannot be set back to False."""
        cid = campaign_state
        set_world_flag(cid, "immutable_test", True)

        # Attempt to flip back
        result = set_world_flag(cid, "immutable_test", False)
        assert result is False, "Setting True→False should return False"

        # Verify it's still True
        assert check_world_flag(cid, "immutable_test") is True

    def test_false_to_true_is_allowed(self, campaign_state):
        """False → True should always be allowed."""
        cid = campaign_state
        set_world_flag(cid, "rising_test", False)
        ok = set_world_flag(cid, "rising_test", True)
        assert ok is True
        assert check_world_flag(cid, "rising_test") is True

    def test_false_to_false_is_noop(self, campaign_state):
        """False → False is a no-op, should succeed."""
        cid = campaign_state
        ok = set_world_flag(cid, "noop_test", False)
        assert ok is True
        assert check_world_flag(cid, "noop_test") is False

    def test_true_to_true_is_noop(self, campaign_state):
        """True → True should succeed (no-op)."""
        cid = campaign_state
        set_world_flag(cid, "true_test", True)
        ok = set_world_flag(cid, "true_test", True)
        assert ok is True
        assert check_world_flag(cid, "true_test") is True


# ------------------------------------------------------------------
# Backward Compatibility
# ------------------------------------------------------------------

class TestWorldFlagsBackwardCompat:
    """Tests for backward compatibility with campaigns that lack world_flags."""

    def test_check_world_flag_missing_key(self, temp_campaigns_dir, campaign_state):
        """check_world_flag should return False when state has no world_flags key."""
        cid = campaign_state
        # Directly write state without world_flags key
        state = load_state(cid)
        del state["world_flags"]
        save_state(cid, state)

        # Should return False, not crash
        assert check_world_flag(cid, "any_flag") is False

    def test_set_world_flag_initializes_missing_key(self, temp_campaigns_dir, campaign_state):
        """set_world_flag should initialize world_flags if missing."""
        cid = campaign_state
        # Remove world_flags from state
        state = load_state(cid)
        del state["world_flags"]
        save_state(cid, state)

        # Set should work even when key is missing
        ok = set_world_flag(cid, "new_flag", True)
        assert ok is True

        # Verify it persisted
        state = load_state(cid)
        assert state["world_flags"]["new_flag"] is True


# ------------------------------------------------------------------
# Integration: flag in narrative context
# ------------------------------------------------------------------

class TestFlagsInNarrativeContext:
    """Tests that world_flags are available in narrative context."""

    def test_world_flags_present_in_state_after_set(self, campaign_state):
        """After setting a flag, state should have it."""
        cid = campaign_state
        set_world_flag(cid, "dark_ritual_done", True)

        state = load_state(cid)
        world_flags = state.get("world_flags", {})
        assert world_flags.get("dark_ritual_done") is True
        assert isinstance(world_flags, dict)
