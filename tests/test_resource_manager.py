"""
test_resource_manager.py — Tests for ResourceManager module.

Covers:
- HP tracking, damage application
- Death saves: 3 failures → dead, nat1=2fail, nat20=1HP
- Spell slot management (full 5e table)
- Hit dice tracking
- Short rest (spend hit dice)
- Long rest (full recovery)
- HP critical detection
"""

import pytest
from dm.resource_manager import (
    ResourceManager, SPELL_SLOT_TABLE, DEATH_SAVE_THRESHOLD,
)


# ── HP ────────────────────────────────────────────────────────────────────


class TestHP:
    """HP tracking and damage application."""

    def test_apply_damage(self):
        """Damage reduces HP."""
        rm = ResourceManager()
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
        }
        result = rm.apply_damage(state, 10)
        assert result["damage_applied"] == 10
        assert state["player"]["hp_current"] == 20

    def test_apply_damage_to_zero(self):
        """Damage to 0 HP triggers unconscious and death saves."""
        rm = ResourceManager()
        state = {
            "player": {"hp_current": 5, "hp_max": 40},
        }
        result = rm.apply_damage(state, 10)
        assert state["player"]["hp_current"] == 0
        assert result["triggered_unconscious"] is True
        assert result["death_saves_active"] is True
        assert "death_saves" in state["player"]

    def test_heal(self):
        """Healing restores HP up to max."""
        rm = ResourceManager()
        state = {
            "player": {"hp_current": 10, "hp_max": 40},
        }
        result = rm.heal(state, 15)
        assert result["healed"] == 15
        assert state["player"]["hp_current"] == 25

    def test_heal_caps_at_max(self):
        """Healing cannot exceed max HP."""
        rm = ResourceManager()
        state = {
            "player": {"hp_current": 35, "hp_max": 40},
        }
        result = rm.heal(state, 20)
        assert result["healed"] == 5  # Capped
        assert state["player"]["hp_current"] == 40

    def test_cannot_heal_unconscious(self):
        """Cannot heal an unconscious character."""
        rm = ResourceManager()
        state = {
            "player": {"hp_current": 0, "hp_max": 40},
        }
        result = rm.heal(state, 20)
        assert result["healed"] == 0


# ── 4.3-4.5 Death Saves ──────────────────────────────────────────────────


class TestDeathSaves:
    """Task 4.3-4.5: death save mechanics."""

    def test_death_save_success(self):
        """A roll >= 10 adds a success."""
        rm = ResourceManager()
        state = {"player": {"death_saves": {"successes": 0, "failures": 0}}}
        result = rm.roll_death_save(state, 15)
        assert result["successes"] == 1
        assert result["failures"] == 0
        assert result["stabilized"] is False
        assert result["dead"] is False

    def test_death_save_failure(self):
        """A roll < 10 adds a failure."""
        rm = ResourceManager()
        state = {"player": {"death_saves": {"successes": 0, "failures": 0}}}
        result = rm.roll_death_save(state, 8)
        assert result["failures"] == 1
        assert result["successes"] == 0

    def test_three_successes_stabilize(self):
        """3 successes = stabilized."""
        rm = ResourceManager()
        state = {"player": {"death_saves": {"successes": 2, "failures": 0}}}
        result = rm.roll_death_save(state, 15)
        assert result["successes"] == 3
        assert result["stabilized"] is True

    def test_three_failures_dead(self):
        """3 failures = dead, world flag set."""
        rm = ResourceManager()
        state = {"player": {"death_saves": {"successes": 0, "failures": 2}}}
        result = rm.roll_death_save(state, 5)
        assert result["failures"] == 3
        assert result["dead"] is True
        assert state["world_flags"].get("player_dead") is True

    def test_nat1_adds_two_failures(self):
        """Natural 1 adds 2 failures."""
        rm = ResourceManager()
        state = {"player": {"death_saves": {"successes": 0, "failures": 1}}}
        result = rm.roll_death_save(state, 1)
        assert result["failures"] == 3  # 1 + 2 = 3
        assert result["nat1"] is True
        assert result["dead"] is True

    def test_nat20_restores_1hp(self):
        """Natural 20 restores 1 HP and stabilizes."""
        rm = ResourceManager()
        state = {
            "player": {
                "death_saves": {"successes": 0, "failures": 2},
                "hp_current": 0,
                "hp_max": 40,
                "is_unconscious": True,
            },
        }
        result = rm.roll_death_save(state, 20)
        assert result["nat20"] is True
        assert result["hp_restored"] == 1
        assert state["player"]["hp_current"] == 1
        assert state["player"].get("is_unconscious") is False

    def test_reset_death_saves(self):
        """Reset death saves clears all death state."""
        rm = ResourceManager()
        state = {
            "player": {
                "death_saves": {"successes": 2, "failures": 2},
                "is_unconscious": True,
                "is_dead": True,
            },
        }
        rm.reset_death_saves(state)
        assert state["player"]["death_saves"] == {"successes": 0, "failures": 0}
        assert "is_unconscious" not in state["player"]
        assert "is_dead" not in state["player"]


# ── Spell Slots ───────────────────────────────────────────────────────────


class TestSpellSlots:
    """Spell slot management with full 5e table."""

    def test_init_spell_slots_level1(self):
        """Level 1 character gets spell slots per 5e table."""
        rm = ResourceManager()
        state = {}
        slots = rm.init_spell_slots(state, 1)
        # Level 1: 2 level-1 slots
        assert slots["max"][0] == 2
        assert slots["used"][0] == 0
        assert state["player"]["spell_slots"] == slots

    def test_init_spell_slots_level5(self):
        """Level 5 character gets 4/3/2 slots."""
        rm = ResourceManager()
        state = {}
        slots = rm.init_spell_slots(state, 5)
        assert slots["max"][0] == 4  # L1
        assert slots["max"][1] == 3  # L2
        assert slots["max"][2] == 2  # L3
        assert slots["max"][3] == 0  # L4 (none at level 5)

    def test_use_spell_slot(self):
        """Using a spell slot decrements available."""
        rm = ResourceManager()
        state = {}
        rm.init_spell_slots(state, 1)
        assert rm.use_spell_slot(state, 1) is True
        assert rm.available_spell_slots(state, 1) == 1

    def test_use_all_slots(self):
        """Using all slots returns False when depleted."""
        rm = ResourceManager()
        state = {}
        rm.init_spell_slots(state, 1)
        assert rm.use_spell_slot(state, 1) is True
        assert rm.use_spell_slot(state, 1) is True  # Last slot
        assert rm.use_spell_slot(state, 1) is False  # No more

    def test_spell_slot_table_coverage(self):
        """SPELL_SLOT_TABLE covers levels 1-20."""
        for level in range(1, 21):
            assert level in SPELL_SLOT_TABLE
            slots = SPELL_SLOT_TABLE[level]
            assert len(slots) == 9  # 9 spell levels


# ── Hit Dice ──────────────────────────────────────────────────────────────


class TestHitDice:
    """Hit dice management."""

    def test_init_hit_dice(self):
        """Hit dice initialized at character level."""
        rm = ResourceManager()
        state = {}
        hd = rm.init_hit_dice(state, 5, hit_die_faces=8)
        assert hd["current"] == 5
        assert hd["max"] == 5
        assert hd["faces"] == 8

    def test_spend_hit_dice_heals(self):
        """Spending hit dice heals HP."""
        rm = ResourceManager()
        state = {"player": {"hp_current": 15, "hp_max": 40}}
        rm.init_hit_dice(state, 3, hit_die_faces=8)
        result = rm.spend_hit_dice(state, count=1)
        assert result["dice_spent"] == 1
        assert result["hp_healed"] >= 1  # d8 roll
        assert result["dice_remaining"] == 2

    def test_no_hit_dice_remaining(self):
        """Cannot spend hit dice when none remain."""
        rm = ResourceManager()
        state = {"player": {"hp_current": 15, "hp_max": 40}}
        rm.init_hit_dice(state, 1)
        rm.spend_hit_dice(state, count=1)  # Use the only die
        result = rm.spend_hit_dice(state)
        assert "error" in result


# ── 4.6-4.8 Rests ────────────────────────────────────────────────────────


class TestRests:
    """Task 4.6-4.8: short rest and long rest."""

    def test_short_rest_heals(self):
        """Short rest heals using hit dice."""
        rm = ResourceManager()
        state = {"player": {"hp_current": 15, "hp_max": 40}}
        rm.init_hit_dice(state, 3, hit_die_faces=8)
        result = rm.short_rest(state)
        assert result["rest_type"] == "short"
        assert result["hp_healed"] >= 1
        assert result["dice_remaining"] == 2

    def test_long_rest_full_recovery(self):
        """Long rest restores HP to max."""
        rm = ResourceManager()
        state = {
            "player": {
                "hp_current": 5,
                "hp_max": 40,
                "death_saves": {"successes": 1, "failures": 2},
                "is_unconscious": True,
            },
        }
        rm.init_hit_dice(state, 5)
        rm.init_spell_slots(state, 5)
        # Use some slots
        rm.use_spell_slot(state, 1)
        rm.use_spell_slot(state, 1)

        result = rm.long_rest(state)

        assert result["rest_type"] == "long"
        assert result["hp_restored"] == 35  # 5 → 40
        assert state["player"]["hp_current"] == 40
        assert result["spell_slots_restored"] is True
        # Check slots restored
        assert rm.available_spell_slots(state, 1) == 4  # All 4 back
        # Check death saves reset
        assert state["player"]["death_saves"]["successes"] == 0
        assert "is_unconscious" not in state["player"]
        # Hit dice partially restored
        assert result["hit_dice_restored"] >= 1


# ── 4.9 HP Critical ───────────────────────────────────────────────────────


class TestHPCritical:
    """Task 4.9: hp_is_critical at 25% threshold."""

    def test_hp_is_critical_true(self):
        """HP <= 25% returns True."""
        rm = ResourceManager()
        state = {"player": {"hp_current": 10, "hp_max": 40}}
        assert rm.hp_is_critical(state) is True

    def test_hp_is_critical_false(self):
        """HP > 25% returns False."""
        rm = ResourceManager()
        state = {"player": {"hp_current": 11, "hp_max": 40}}
        assert rm.hp_is_critical(state) is False

    def test_hp_is_critical_at_boundary(self):
        """HP exactly at 25%."""
        rm = ResourceManager()
        state = {"player": {"hp_current": 10, "hp_max": 40}}  # 25%
        assert rm.hp_is_critical(state) is True
        state["player"]["hp_current"] = 11  # 27.5%
        assert rm.hp_is_critical(state) is False


# ── Per-round flags ───────────────────────────────────────────────────────


class TestRoundFlags:
    """Action economy per-round flags."""

    def test_reset_round_flags(self):
        """Round flags reset for new round."""
        rm = ResourceManager()
        state = {}
        rm.reset_round_flags(state)
        flags = state["player"]["per_round_flags"]
        assert flags["action"] is False
        assert flags["bonus"] is False
        assert flags["reaction"] is False

    def test_mark_action_used(self):
        """Marking action prevents reuse."""
        rm = ResourceManager()
        state = {}
        rm.reset_round_flags(state)
        assert rm.mark_action_used(state, "action") is True
        assert rm.mark_action_used(state, "action") is False  # Already used

    def test_is_action_available(self):
        """Check action availability."""
        rm = ResourceManager()
        state = {}
        rm.reset_round_flags(state)
        assert rm.is_action_available(state, "bonus") is True
        rm.mark_action_used(state, "bonus")
        assert rm.is_action_available(state, "bonus") is False
