"""
tests/test_combat_gate.py — Tests for Combat Gate (Phase 1: Narrative Progression Gates).

Tests the combat validation layer:
  - Attacks blocked when combat is inactive
  - Attacks blocked when target doesn't exist in scene
  - Attacks allowed when combat is active and target is present
"""

from unittest.mock import MagicMock

import pytest

from adapters.mode_b.action_router import ActionRouter, ActionResult


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def router_no_combat():
    """Router with state where combat is NOT active."""
    state = {
        "combat": {
            "active": False,
            "round": 0,
            "initiative_order": [],
            "current_turn": None,
        },
        "npcs": {},
        "campaign": {"name": "Test", "current_location": "Tavern"},
    }
    return ActionRouter(state=state)


@pytest.fixture
def router_combat_active():
    """Router with state where combat IS active and a goblin is present."""
    state = {
        "combat": {
            "active": True,
            "round": 1,
            "initiative_order": [
                {"name": "Goblin", "initiative": 15},
                {"name": "Valdric", "initiative": 10},
            ],
            "current_turn": "Valdric",
        },
        "npcs": {
            "goblin": {"name": "Goblin", "location": "Dungeon", "hp": 20},
        },
        "campaign": {"name": "Test", "current_location": "Dungeon"},
    }
    char = MagicMock()
    char.name = "Valdric"
    char.mod = MagicMock(return_value=2)
    char.proficiency_bonus = 2
    return ActionRouter(state=state, character=char)


# ------------------------------------------------------------------
# Combat Gate — Validation Tests
# ------------------------------------------------------------------

class TestCombatGateAttackBlocked:
    """Tests for attack rejection when combat is inactive."""

    def test_attack_blocked_when_combat_inactive(self, router_no_combat):
        """
        RED (Task 1.1): route() must return a blocked ActionResult when
        state["combat"]["active"]=False and action_type is attack.

        Expected: route() detects combat is inactive and returns an ActionResult
        that indicates the action was blocked, with a clear Spanish message.
        """
        mock_update = MagicMock()
        result = router_no_combat.route(mock_update, "ataco al goblin")

        assert isinstance(result, ActionResult)
        assert result.action_type == "blocked", (
            f"Expected action_type='blocked', got '{result.action_type}'."
        )
        assert "combate" in result.narrative.lower(), (
            f"Expected narrative to mention combat, got: {result.narrative[:100]}"
        )
        assert result.mechanic_inline is None, (
            f"Expected mechanic_inline=None (no dice rolled), got: {result.mechanic_inline}"
        )

    def test_attack_blocked_no_target_string(self, router_no_combat):
        """
        RED (Task 1.1 edge case): Even with an empty target, attack should
        be blocked when combat is inactive.
        """
        mock_update = MagicMock()
        result = router_no_combat.route(mock_update, "ataco")

        assert isinstance(result, ActionResult)
        assert result.action_type == "blocked", (
            f"Expected action_type='blocked', got '{result.action_type}'"
        )


class TestCombatGateTargetValidation:
    """Tests for target existence validation."""

    def test_attack_blocked_when_target_not_in_scene(self, router_combat_active):
        """
        RED (Task 1.5): Attack should be blocked when combat is active
        but the target doesn't exist in the scene.
        """
        mock_update = MagicMock()
        result = router_combat_active.route(mock_update, "ataco al dragon")

        assert isinstance(result, ActionResult)
        assert result.action_type == "blocked", (
            f"Expected action_type='blocked', got '{result.action_type}'"
        )
        assert "dragon" in result.narrative.lower(), (
            f"Expected narrative to reference 'dragon', got: {result.narrative[:100]}"
        )

    def test_attack_allowed_when_valid(self, router_combat_active):
        """
        RED (Task 1.7): Attack should proceed normally when combat is active
        and target exists in the scene/initiative_order.
        """
        mock_update = MagicMock()
        result = router_combat_active.route(mock_update, "ataco al goblin")

        assert isinstance(result, ActionResult)
        assert result.action_type != "blocked", (
            f"Expected action_type != 'blocked', got '{result.action_type}'."
        )
        assert result.action_type == "attack", (
            f"Expected action_type='attack', got '{result.action_type}'"
        )
        assert result.mechanic_inline is not None
        assert len(result.mechanic_inline) > 0


class TestActionResultBlockedFields:
    """Tests for the blocked fields on ActionResult."""

    def test_action_result_blocked_default(self):
        """
        Backward compat: Existing ActionResult construction still works
        without blocked/block_reason fields.
        """
        result = ActionResult(
            narrative="Test narrative",
            mechanic_inline="8 damage",
            action_type="attack",
        )
        assert result.narrative == "Test narrative"
        assert result.mechanic_inline == "8 damage"
        assert result.action_type == "attack"


class TestCombatGateNonAttackPassthrough:
    """Tests that non-attack actions are not affected by the combat gate."""

    def test_dialogue_not_blocked_by_combat_gate(self, router_no_combat):
        """Dialogue should never be blocked by combat gate."""
        mock_update = MagicMock()
        result = router_no_combat.route(mock_update, "le digo hola al guardia")

        assert isinstance(result, ActionResult)
        assert result.action_type != "blocked", (
            f"Dialogue should not be blocked. Got action_type='{result.action_type}'"
        )

    def test_explore_not_blocked_by_combat_gate(self, router_no_combat):
        """Exploration should never be blocked by combat gate."""
        mock_update = MagicMock()
        result = router_no_combat.route(mock_update, "exploro la cueva")

        assert isinstance(result, ActionResult)
        assert result.action_type != "blocked", (
            f"Explore should not be blocked. Got action_type='{result.action_type}'"
        )

    def test_rest_not_blocked_by_combat_gate(self, router_no_combat):
        """Rest should never be blocked by combat gate."""
        mock_update = MagicMock()
        result = router_no_combat.route(mock_update, "descanso")

        assert isinstance(result, ActionResult)
        assert result.action_type != "blocked", (
            f"Rest should not be blocked. Got action_type='{result.action_type}'"
        )


class TestValidateCombatTarget:
    """Tests for _validate_combat_target helper method."""

    def test_validate_combat_target_returns_false_for_none(self, router_combat_active):
        """_validate_combat_target(None) should return False."""
        result = router_combat_active._validate_combat_target(None)
        assert result is False, f"Expected False for None target, got {result}"

    def test_validate_combat_target_returns_false_for_empty(self, router_combat_active):
        """_validate_combat_target('') should return False."""
        result = router_combat_active._validate_combat_target("")
        assert result is False, f"Expected False for empty target, got {result}"

    def test_validate_combat_target_returns_true_for_valid(self, router_combat_active):
        """_validate_combat_target('Goblin') should return True."""
        result = router_combat_active._validate_combat_target("Goblin")
        assert result is True, f"Expected True for 'Goblin', got {result}"

    def test_validate_combat_target_case_insensitive(self, router_combat_active):
        """_validate_combat_target should be case-insensitive."""
        result = router_combat_active._validate_combat_target("goblin")
        assert result is True, f"Expected True for 'goblin' (case-insensitive), got {result}"

    def test_validate_combat_target_false_for_absent(self, router_combat_active):
        """_validate_combat_target('Dragon') should return False."""
        result = router_combat_active._validate_combat_target("Dragon")
        assert result is False, f"Expected False for 'Dragon', got {result}"

    def test_validate_combat_target_false_no_combat(self, router_no_combat):
        """_validate_combat_target should return False when combat is inactive."""
        result = router_no_combat._validate_combat_target("Goblin")
        assert result is False, f"Expected False when combat inactive, got {result}"
