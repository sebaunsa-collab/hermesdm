# tests/test_class_features.py — Strict TDD: Phase 3 tests for dm.class_features
"""8 tests covering rage activation, action surge, sneak attack,
   resource binding, and feature recovery."""
import pytest
from dm.class_features import (
    FEATURES,
    get_features,
    activate_feature,
    recover_features,
)


# ── Feature registry tests ────────────────────────────────────────────────

class TestFeatureRegistry:
    def test_barbarian_level_1_has_rage(self):
        features = get_features({"player_class": "barbarian", "level": 1})
        assert len(features) >= 1
        rage = [f for f in features if f["name"].lower() == "rage"][0]
        assert rage["uses"] == 2
        assert rage["rest_recovery"] == "long"
        assert "damage_bonus" in rage
        assert rage["damage_bonus"] == 2

    def test_fighter_level_2_has_action_surge(self):
        features = get_features({"player_class": "fighter", "level": 2})
        assert len(features) >= 1
        surge = [f for f in features if "action surge" in f["name"].lower()][0]
        assert surge["uses"] == 1
        assert surge["rest_recovery"] == "short"

    def test_rogue_level_1_has_sneak_attack(self):
        features = get_features({"player_class": "rogue", "level": 1})
        assert len(features) >= 1
        sa = [f for f in features if "sneak attack" in f["name"].lower()][0]
        assert sa["passive"] is True
        assert sa["damage_dice"] == "1d6"

    def test_fighter_level_1_has_no_action_surge(self):
        features = get_features({"player_class": "fighter", "level": 1})
        # Fighter L1 has Second Wind (or similar), NOT Action Surge (L2)
        surge_features = [f for f in features if "action surge" in f["name"].lower()]
        assert len(surge_features) == 0

    def test_level_10_barbarian_has_multiple_features(self):
        features = get_features({"player_class": "barbarian", "level": 10})
        # Should have Rage (L1) + additional features at higher levels
        assert len(features) >= 2  # At least rage + another feature


# ── Feature activation tests ──────────────────────────────────────────────

class TestActivateFeature:
    def test_activate_rage_consumes_charge(self):
        char = {
            "player_class": "barbarian",
            "level": 1,
            "features": [
                {"name": "Rage", "uses": 2, "used": 0, "rest_recovery": "long",
                 "damage_bonus": 2, "resistances": ["bludgeoning", "piercing", "slashing"]}
            ]
        }
        result = activate_feature(char, "Rage")
        assert result["success"] is True
        assert result["effect"]["damage_bonus"] == 2
        assert result["effect"]["active"] is True
        # One use consumed
        rage_feat = [f for f in char["features"] if f["name"] == "Rage"][0]
        assert rage_feat["used"] == 1

    def test_activate_rage_when_exhausted_fails(self):
        char = {
            "player_class": "barbarian",
            "level": 1,
            "features": [
                {"name": "Rage", "uses": 2, "used": 2, "rest_recovery": "long",
                 "damage_bonus": 2}
            ]
        }
        result = activate_feature(char, "Rage")
        assert result["success"] is False
        assert "exhausted" in result.get("reason", "") or "agotado" in result.get("reason", "")

    def test_activate_action_surge_consumes_charge(self):
        char = {
            "player_class": "fighter",
            "level": 2,
            "features": [
                {"name": "Action Surge", "uses": 1, "used": 0, "rest_recovery": "short"}
            ]
        }
        result = activate_feature(char, "Action Surge")
        assert result["success"] is True
        surge = [f for f in char["features"] if f["name"] == "Action Surge"][0]
        assert surge["used"] == 1

    def test_activate_nonexistent_feature_fails(self):
        char = {"player_class": "fighter", "level": 1, "features": []}
        result = activate_feature(char, "Magic Missile")
        assert result["success"] is False


# ── Feature recovery tests ────────────────────────────────────────────────

class TestRecoverFeatures:
    def test_long_rest_recovers_rage_uses(self):
        char = {
            "player_class": "barbarian",
            "level": 1,
            "features": [
                {"name": "Rage", "uses": 2, "used": 2, "rest_recovery": "long",
                 "damage_bonus": 2}
            ]
        }
        result = recover_features(char, "long")
        rage = [f for f in char["features"] if f["name"] == "Rage"][0]
        assert rage["used"] == 0
        assert "Rage" in str(result.get("recovered", []))

    def test_short_rest_recovers_action_surge(self):
        char = {
            "player_class": "fighter",
            "level": 2,
            "features": [
                {"name": "Action Surge", "uses": 1, "used": 1, "rest_recovery": "short"}
            ]
        }
        result = recover_features(char, "short")
        surge = [f for f in char["features"] if f["name"] == "Action Surge"][0]
        assert surge["used"] == 0

    def test_short_rest_does_not_recover_long_rest_feature(self):
        char = {
            "player_class": "barbarian",
            "level": 1,
            "features": [
                {"name": "Rage", "uses": 2, "used": 2, "rest_recovery": "long",
                 "damage_bonus": 2}
            ]
        }
        result = recover_features(char, "short")
        rage = [f for f in char["features"] if f["name"] == "Rage"][0]
        # Rage is long rest recovery — should NOT recover on short rest
        assert rage["used"] == 2  # STAYS exhausted
