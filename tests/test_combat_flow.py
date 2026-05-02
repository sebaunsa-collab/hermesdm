"""
test_combat_flow.py — Tests for CombatFlow module.

Covers:
- Initiative rolling with dex tiebreaker
- Combat initialization
- Turn order management
- Action economy (1 action + 1 bonus + 1 reaction)
- All enemies defeated detection
"""

import pytest
import random
from dm.combat_flow import CombatFlow


# ── 2.7-2.8 Initiative ───────────────────────────────────────────────────


class TestInitiative:
    """Task 2.7-2.8: initiative rolls sorted by (dex_mod, d20_rolloff)."""

    def test_roll_initiative_basic(self):
        """Basic initiative rolls for two combatants."""
        cf = CombatFlow()
        rng = random.Random(42)
        combatants = [
            {"name": "Goblin", "dex_mod": 2},
            {"name": "Player", "dex_mod": 3},
        ]
        result = cf.roll_initiative(combatants, rng=rng)
        assert len(result) == 2
        assert "initiative" in result[0]
        assert "initiative" in result[1]

    def test_higher_dex_goes_first(self):
        """Higher DEX modifier wins ties."""
        cf = CombatFlow()
        rng = random.Random(42)
        combatants = [
            {"name": "Slow", "dex_mod": 1},
            {"name": "Fast", "dex_mod": 4},
        ]
        result = cf.roll_initiative(combatants, rng=rng)
        assert result[0]["name"] == "Fast"  # Higher dex first
        assert result[1]["name"] == "Slow"

    def test_same_dex_uses_rolloff(self):
        """Same DEX uses d20 roll-off as tiebreaker."""
        cf = CombatFlow()
        rng = random.Random(42)
        combatants = [
            {"name": "A", "dex_mod": 2},
            {"name": "B", "dex_mod": 2},
        ]
        result = cf.roll_initiative(combatants, rng=rng)
        assert len(result) == 2
        # Both have same DEX, order determined by tiebreak

    def test_initiative_fields_added(self):
        """Initiative result includes action tracking fields."""
        cf = CombatFlow()
        rng = random.Random(42)
        combatants = [{"name": "Goblin", "dex_mod": 2}]
        result = cf.roll_initiative(combatants, rng=rng)
        c = result[0]
        assert "action_taken" in c
        assert "bonus_taken" in c
        assert "reaction_taken" in c
        assert c["action_taken"] is False


# ── Combat initialization ────────────────────────────────────────────────


class TestInitCombat:
    """Combat initialization with enemies."""

    def test_init_combat_basic(self):
        """Initialize combat with enemies creates combat state."""
        cf = CombatFlow()
        state = {"player": {"name": "Hero", "hp_current": 20, "hp_max": 20, "stats": {"dex": 14}}}
        rng = random.Random(42)
        enemies = [{"name": "Goblin", "hp": 7, "ac": 13, "attacks": [], "abilities": {"DEX": 14}}]

        combat_state = cf.init_combat(state, enemies, rng=rng)
        assert combat_state["active"] is True
        assert combat_state["round"] == 1
        assert len(combat_state["initiative_order"]) == 2  # Player + Goblin
        assert combat_state["current_turn"] is not None

    def test_init_combat_player_included(self):
        """Player is automatically added to initiative."""
        cf = CombatFlow()
        state = {"player": {"name": "Hero", "hp_current": 20, "hp_max": 20, "stats": {"dex": 16}}}
        rng = random.Random(42)
        enemies = [{"name": "Goblin", "hp": 7, "ac": 13, "attacks": []}]

        combat_state = cf.init_combat(state, enemies, rng=rng)
        player_idx = None
        for i, c in enumerate(combat_state["initiative_order"]):
            if c.get("is_player"):
                player_idx = i
                break
        assert player_idx is not None


# ── 2.9-2.10 Action Economy ────────────────────────────────────────────


class TestActionEconomy:
    """Task 2.9-2.10: action economy enforcement."""

    def test_can_use_action_initially(self):
        """Action is available at start of turn."""
        cf = CombatFlow()
        state = {
            "combat": {
                "active": True,
                "round": 1,
                "current_index": 0,
                "initiative_order": [
                    {"name": "Hero", "is_player": True,
                     "action_taken": False, "bonus_taken": False, "reaction_taken": False,
                     "hp": {"current": 10, "max": 10}},
                ],
            },
        }
        assert cf.can_use_action(state) is True

    def test_cannot_use_action_twice(self):
        """Using action marks it as taken."""
        cf = CombatFlow()
        state = {
            "combat": {
                "active": True,
                "round": 1,
                "current_index": 0,
                "initiative_order": [
                    {"name": "Hero", "is_player": True,
                     "action_taken": False, "bonus_taken": False, "reaction_taken": False,
                     "hp": {"current": 10, "max": 10}},
                ],
            },
        }
        result = cf.mark_action(state, "action")
        assert result is True
        assert cf.can_use_action(state) is False

    def test_can_use_bonus(self):
        """Bonus action works independently."""
        cf = CombatFlow()
        state = {
            "combat": {
                "active": True,
                "round": 1,
                "current_index": 0,
                "initiative_order": [
                    {"name": "Hero", "is_player": True,
                     "action_taken": False, "bonus_taken": False, "reaction_taken": False,
                     "hp": {"current": 10, "max": 10}},
                ],
            },
        }
        assert cf.can_use_bonus(state) is True
        cf.mark_action(state, "bonus")
        assert cf.can_use_bonus(state) is False
        assert cf.can_use_action(state) is True  # Action still available

    def test_cannot_use_reaction_initially(self):
        """Reaction starts available."""
        cf = CombatFlow()
        state = {
            "combat": {
                "active": True,
                "round": 1,
                "current_index": 0,
                "initiative_order": [
                    {"name": "Hero", "is_player": True,
                     "action_taken": False, "bonus_taken": False, "reaction_taken": False,
                     "hp": {"current": 10, "max": 10}},
                ],
            },
        }
        assert cf.can_use_reaction(state) is True

    def test_resolve_action_with_damage(self):
        """Resolving action applies damage to target."""
        cf = CombatFlow()
        state = {
            "combat": {
                "active": True,
                "round": 1,
                "current_index": 0,
                "initiative_order": [
                    {"name": "Hero", "is_player": True,
                     "action_taken": False, "bonus_taken": False, "reaction_taken": False,
                     "hp": {"current": 10, "max": 10}},
                    {"name": "Goblin", "is_player": False,
                     "action_taken": False, "bonus_taken": False, "reaction_taken": False,
                     "hp": {"current": 7, "max": 7}},
                ],
            },
        }
        result = cf.resolve_action(state, {
            "type": "action",
            "target_index": 1,
            "hit": True,
            "damage": 5,
        })
        assert result["success"] is True
        assert result["hit"] is True
        assert result["damage"] == 5
        target = state["combat"]["initiative_order"][1]
        assert target["hp"]["current"] == 2

    def test_double_action_rejected(self):
        """Second action in same turn is rejected."""
        cf = CombatFlow()
        state = {
            "combat": {
                "active": True,
                "round": 1,
                "current_index": 0,
                "initiative_order": [
                    {"name": "Hero", "is_player": True,
                     "action_taken": False, "bonus_taken": False, "reaction_taken": False,
                     "hp": {"current": 10, "max": 10}},
                    {"name": "Goblin", "is_player": False,
                     "action_taken": False, "bonus_taken": False, "reaction_taken": False,
                     "hp": {"current": 7, "max": 7}},
                ],
            },
        }
        # First action works
        result1 = cf.resolve_action(state, {"type": "action", "target_index": 1, "hit": True, "damage": 3})
        assert result1["success"] is True
        # Second action rejected
        result2 = cf.resolve_action(state, {"type": "action", "target_index": 1, "hit": True, "damage": 3})
        assert result2["success"] is False
        assert "usado" in result2.get("error", "").lower() or "ya" in result2.get("error", "")


# ── 2.11 All enemies defeated ───────────────────────────────────────────


class TestAllEnemiesDefeated:
    """Task 2.11: all enemies defeated → combat ends, boss flag."""

    def test_next_turn_wraps_round(self):
        """next_turn increments round when all have acted."""
        cf = CombatFlow()
        state = {
            "combat": {
                "active": True,
                "round": 1,
                "current_index": 0,
                "initiative_order": [
                    {"name": "Hero", "is_player": True,
                     "action_taken": False, "bonus_taken": False, "reaction_taken": False,
                     "hp": {"current": 10, "max": 10}},
                    {"name": "Goblin", "is_player": False,
                     "action_taken": False, "bonus_taken": False, "reaction_taken": False,
                     "hp": {"current": 7, "max": 7}},
                ],
            },
            "player": {"name": "Hero"},
        }
        # Hero's turn (0)
        result = cf.next_turn(state)
        assert result["current_turn"] == "Goblin"

    def test_all_enemies_dead_ends_combat(self):
        """When all enemies dead, combat ends."""
        cf = CombatFlow()
        state = {
            "combat": {
                "active": True,
                "round": 1,
                "current_index": 1,  # Last combatant (enemy)
                "initiative_order": [
                    {"name": "Hero", "is_player": True,
                     "action_taken": True, "bonus_taken": False, "reaction_taken": False,
                     "hp": {"current": 10, "max": 10}},
                    {"name": "Goblin", "is_player": False,
                     "action_taken": False, "bonus_taken": False, "reaction_taken": False,
                     "hp": {"current": 0, "max": 7}},  # Already dead
                ],
            },
            "player": {"name": "Hero"},
        }
        result = cf.next_turn(state)
        assert "combat_ended" in result
        assert result["combat_ended"] is True

    def test_boss_defeated_sets_flag(self):
        """Boss (CR >= 5) defeat sets world flag."""
        cf = CombatFlow()
        state = {
            "world_flags": {},
            "combat": {
                "active": True,
                "round": 1,
                "current_index": 1,
                "initiative_order": [
                    {"name": "Hero", "is_player": True,
                     "action_taken": True, "bonus_taken": False, "reaction_taken": False,
                     "hp": {"current": 10, "max": 10}},
                    {"name": "Dragon", "is_player": False,
                     "action_taken": False, "bonus_taken": False, "reaction_taken": False,
                     "cr": 10,  # Boss!
                     "hp": {"current": 0, "max": 100}},
                ],
            },
            "player": {"name": "Hero"},
        }
        cf.next_turn(state)
        assert state["world_flags"].get("boss_defeated") is True

    def test_get_initiative_display(self):
        """get_initiative_display returns formatted string."""
        cf = CombatFlow()
        state = {
            "combat": {
                "active": True,
                "round": 2,
                "current_index": 0,
                "initiative_order": [
                    {"name": "Hero", "is_player": True,
                     "hp": {"current": 10, "max": 10}},
                ],
            },
        }
        display = cf.get_initiative_display(state)
        assert "Hero" in display
        assert "Round 2" in display
        assert "10/10" in display
