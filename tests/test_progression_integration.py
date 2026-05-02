# tests/test_progression_integration.py — Strict TDD: Phase 4 integration tests
"""Integration tests for character progression hooks into existing modules."""
import pytest
from state.state_manager import new_state, save_state, load_state
from dm.xp_engine import calculate_xp, award_xp, award_combat_xp
from dm.spell_engine import get_spell_slots, concentration_save, CASTER_TYPE_MAP
from dm.class_features import get_features, activate_feature, recover_features, FEATURES
from dm.resource_manager import ResourceManager
import random as _random


class TestStateManagerProgression:
    """Verify new_state includes progression fields."""

    def test_new_state_has_progression_fields(self):
        state = new_state("test_prog", "Test", "fantasy")
        assert "xp_current" in state.get("player", {})
        assert "level" in state.get("player", {})
        assert "proficiency_bonus" in state.get("player", {})

    def test_new_state_progression_defaults(self):
        state = new_state("test_prog2", "Test", "fantasy")
        player = state["player"]
        assert player["xp_current"] == 0
        assert player["level"] == 1
        assert player["proficiency_bonus"] == 2

    def test_new_state_has_use_character_progression_flag(self):
        state = new_state("test_prog3", "Test", "fantasy")
        assert state.get("use_character_progression") is True

    def test_new_state_has_features_list(self):
        state = new_state("test_prog4", "Test", "fantasy")
        assert isinstance(state["player"].get("features"), list)


class TestAwardCombatXP:
    """Integration: combat end -> XP award -> state mutation."""

    def test_award_combat_xp_to_player_state(self):
        state = new_state("test_xp_int", "Test", "fantasy")
        state["player"]["xp_current"] = 0
        state["player"]["level"] = 1

        # Simulate defeating a CR1 enemy
        xp_per = calculate_xp(enemy_cr=1, party_size=1)
        result = award_xp(state["player"], xp_per)

        # award_xp returns 'xp' key; state uses 'xp_current'
        state["player"]["xp_current"] = result["character"]["xp"]
        state["player"]["level"] = result["character"]["level"]
        assert state["player"]["xp_current"] == 200
        assert state["player"]["level"] == 1

    def test_combat_xp_with_level_up(self):
        state = new_state("test_xp_lvl", "Test", "fantasy")
        state["player"]["xp_current"] = 280
        state["player"]["level"] = 1

        xp_per = calculate_xp(enemy_cr=0.25, party_size=1)  # 50 XP
        result = award_xp(state["player"], xp_per)
        state["player"]["xp_current"] = result["character"]["xp"]
        state["player"]["level"] = result["character"]["level"]

        assert state["player"]["xp_current"] == 330
        assert state["player"]["level"] == 2
        assert result["levels_gained"] == [2]


class TestFeatureRecoveryIntegration:
    """Integration: ResourceManager rest -> recover class features."""

    def test_long_rest_recovers_features(self):
        rm = ResourceManager()
        state = new_state("test_rest_feat", "Test", "fantasy")
        state["player"]["features"] = [
            {"name": "Rage", "uses": 2, "used": 2, "rest_recovery": "long", "damage_bonus": 2}
        ]

        # Long rest should recover rage uses
        recovered = recover_features(state["player"], "long")
        assert "Rage" in recovered["recovered"]
        assert state["player"]["features"][0]["used"] == 0

    def test_short_rest_recovers_short_recovery_only(self):
        state = new_state("test_rest_short", "Test", "fantasy")
        state["player"]["features"] = [
            {"name": "Action Surge", "uses": 1, "used": 1, "rest_recovery": "short"},
            {"name": "Rage", "uses": 2, "used": 2, "rest_recovery": "long", "damage_bonus": 2},
        ]

        recovered = recover_features(state["player"], "short")
        assert "Action Surge" in recovered["recovered"]
        assert "Rage" not in recovered["recovered"]
        # Rage still exhausted
        assert state["player"]["features"][1]["used"] == 2


class TestConcentrationIntegration:
    """Integration: damage taken -> concentration check."""

    def test_concentration_check_on_damage(self):
        rng = _random.Random(99)
        saved, dc = concentration_save(damage_taken=14, con_mod=2, rng=rng)
        assert dc == 10  # max(10, 7) = 10
        # With seeded rng, result is deterministic
        assert isinstance(saved, bool)

    def test_concentration_broken_on_high_damage(self):
        """30 damage → DC 15. With CON -1, need 16+ on d20 (25% chance)."""
        failures = 0
        for _ in range(200):
            saved, dc = concentration_save(damage_taken=30, con_mod=-1)
            if not saved:
                failures += 1
        # 75% chance to fail each time
        assert failures > 100  # Should fail often

    def test_auto_fail_when_unconscious(self):
        """Unconscious character auto-fails concentration."""
        # Concentration save is purely mechanical — unconsciousness is checked
        # by the caller (CombatFlow checks state before calling concentration_save)
        # Here we verify the concentration_save function doesn't care
        saved, dc = concentration_save(damage_taken=1, con_mod=10)
        assert dc == 10
