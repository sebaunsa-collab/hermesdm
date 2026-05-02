"""
Tests for state/state_validator.py — validation logic for HermesDM.
"""

import pytest
from state.state_validator import (
    ValidationResponse,
    ValidationResult,
    add_npc_memory,
    enforce_world_consistency,
    validate_action,
    validate_npc_memory,
)


# ── Tests: validate_action ──────────────────────────────────────────────────

class TestValidateActionKill:
    """validate_action with kill/attack actions."""

    def test_kill_dead_npc_blocked(self):
        """Killing an already-dead NPC returns BLOCKED."""
        state = {
            "npcs": {
                "goblin_01": {"name": "Goblin Scout", "status": "DEAD"},
            }
        }
        result = validate_action("kill", "player1", "goblin_01", state)
        assert result.result == ValidationResult.BLOCKED
        assert "already dead" in result.message

    def test_kill_unconscious_npc_blocked(self):
        """Killing an unconscious NPC returns BLOCKED."""
        state = {
            "npcs": {
                "bandit_01": {"name": "Bandit", "status": "UNCONSCIOUS"},
            }
        }
        result = validate_action("damage", "player1", "bandit_01", state)
        assert result.result == ValidationResult.BLOCKED
        assert "unconscious" in result.message

    def test_kill_alive_npc_allowed(self):
        """Killing a living NPC returns ALLOWED."""
        state = {
            "npcs": {
                "orc_01": {"name": "Orc Warrior", "status": "ALIVE"},
            }
        }
        result = validate_action("attack", "player1", "orc_01", state)
        assert result.result == ValidationResult.ALLOWED


class TestValidateActionHeal:
    """validate_action with heal actions."""

    def test_heal_exceeds_max_corrected(self):
        """Healing when current > max returns CORRECTED with corrected HP."""
        state = {
            "characters": {
                "player1": {
                    "name": "Valdric",
                    "hp": {"current": 50, "max": 40},
                }
            }
        }
        result = validate_action("heal", "cleric1", "player1", state)
        assert result.result == ValidationResult.CORRECTED
        assert result.corrected_value is not None
        assert result.corrected_value["current"] == 40

    def test_heal_below_max_allowed(self):
        """Healing when current < max returns ALLOWED."""
        state = {
            "characters": {
                "player1": {
                    "name": "Valdric",
                    "hp": {"current": 10, "max": 40},
                }
            }
        }
        result = validate_action("heal", "cleric1", "player1", state)
        assert result.result == ValidationResult.ALLOWED


class TestValidateActionTalk:
    """validate_action with talk/interact actions."""

    def test_talk_hostile_npc_corrected(self):
        """Talking to a hostile NPC that won't speak returns CORRECTED."""
        state = {
            "npcs": {
                "dragon_01": {
                    "name": "Ancient Dragon",
                    "disposition": "HOSTILE",
                    "speaks_to_players": False,
                }
            }
        }
        result = validate_action("talk", "player1", "dragon_01", state)
        assert result.result == ValidationResult.CORRECTED
        assert "hostile" in result.message.lower()


class TestValidateActionSpell:
    """validate_action with cast_spell actions."""

    def test_spell_non_caster_blocked(self):
        """A fighter cannot cast spells — returns BLOCKED."""
        state = {
            "characters": {
                "fighter1": {
                    "name": "Boromir",
                    "class": "fighter",
                }
            }
        }
        result = validate_action("cast_spell", "fighter1", "goblin_01", state)
        assert result.result == ValidationResult.BLOCKED
        assert "cannot cast" in result.message.lower()

    def test_spell_caster_allowed(self):
        """A wizard can cast spells — returns ALLOWED."""
        state = {
            "characters": {
                "wizard1": {
                    "name": "Gandalf",
                    "class": "wizard",
                }
            }
        }
        result = validate_action("cast_spell", "wizard1", "goblin_01", state)
        assert result.result == ValidationResult.ALLOWED


class TestValidateActionUnknown:
    """validate_action with unknown action types."""

    def test_unknown_action_allowed(self):
        """Unknown action types return ALLOWED by default."""
        result = validate_action("dance", "player1", None, {})
        assert result.result == ValidationResult.ALLOWED
        assert result.message is None


# ── Tests: validate_npc_memory ──────────────────────────────────────────────

class TestValidateNPCMemory:
    """validate_npc_memory checks for memory contradictions."""

    def test_memory_contradiction_blocked(self):
        """Adding a memory that contradicts established facts returns BLOCKED.

        Note: validate_npc_memory uses LIST membership (not substring)
        for contradiction detection — so exact keyword matches in memory
        entries are required.
        """
        state = {
            "npcs": {
                "vendor_01": {
                    "name": "Shopkeep",
                    "memory": ["saved", "ally"],
                }
            }
        }
        result = validate_npc_memory(
            "vendor_01",
            "The hero attacked my shop and became an enemy",
            state,
        )
        assert result.result == ValidationResult.BLOCKED
        assert "contradicts" in result.message.lower()

    def test_memory_valid_allowed(self):
        """Adding a consistent memory returns ALLOWED."""
        state = {
            "npcs": {
                "vendor_01": {
                    "name": "Shopkeep",
                    "memory": ["The hero saved my shop from bandits"],
                }
            }
        }
        result = validate_npc_memory(
            "vendor_01",
            "The hero returned to buy supplies",
            state,
        )
        assert result.result == ValidationResult.ALLOWED

    def test_memory_npc_not_found_blocked(self):
        """Non-existent NPC returns BLOCKED."""
        state = {"npcs": {}}
        result = validate_npc_memory("nonexistent_01", "Something happened", state)
        assert result.result == ValidationResult.BLOCKED
        assert "not found" in result.message.lower()




class TestValidateActionKillCharacter:
    """validate_action kill/attack on characters."""

    def test_kill_character_at_zero_hp_blocked(self):
        """Attacking a character at 0 HP returns BLOCKED."""
        state = {
            "characters": {
                "player1": {
                    "name": "Downed Hero",
                    "hp": {"current": 0, "max": 40},
                }
            }
        }
        result = validate_action("kill", "npc1", "player1", state)
        assert result.result == ValidationResult.BLOCKED
        assert "already at 0" in result.message


class TestValidateActionUseItem:
    """validate_action use_item edge cases."""

    def test_use_item_not_in_inventory_blocked(self):
        """Using an item not in inventory returns BLOCKED."""
        state = {
            "characters": {
                "player1": {
                    "name": "Valdric",
                    "inventory": [
                        {"name": "Healing Potion", "qty": 1},
                    ],
                }
            }
        }
        result = validate_action("use_item", "player1", "Fireball Scroll", state)
        assert result.result == ValidationResult.BLOCKED

    def test_use_item_character_not_in_state_allowed(self):
        """Actor not in state returns ALLOWED (graceful fallback)."""
        result = validate_action("use_item", "ghost1", "Potion", {})
        assert result.result == ValidationResult.ALLOWED


class TestAddNPCMemoryEdgeCases:
    """add_npc_memory additional paths."""

    def test_add_memory_npc_not_found(self):
        """Adding memory to non-existent NPC returns False."""
        state = {"npcs": {}}
        success, msg = add_npc_memory("c1", "npc_x", "something", state=state)
        assert success is False
        assert "not found" in msg.lower()

    def test_add_memory_contradiction_blocked(self):
        """Memory that contradicts established facts is blocked."""
        state = {
            "npcs": {
                "npc_a": {"name": "Guard", "memory": ["ally"]},
            }
        }
        success, msg = add_npc_memory("c1", "npc_a", "became an enemy", state=state)
        assert success is False
        assert "contradicts" in msg.lower()

    def test_add_memory_creates_memory_list(self):
        """NPC without memory field gets one created."""
        state = {
            "npcs": {
                "npc_z": {"name": "Mysterious Stranger"},
            }
        }
        success, msg = add_npc_memory("c1", "npc_z", "Seen near the tavern", state=state)
        assert success is True
        assert "memory" in state["npcs"]["npc_z"]
        assert len(state["npcs"]["npc_z"]["memory"]) == 1


class TestValidateActionLocationChange:
    """validate_action change_location."""

    def test_change_to_same_location_blocked(self):
        """Changing to current location returns BLOCKED."""
        state = {
            "campaign": {"current_location": "Tavern"},
        }
        result = validate_action("change_location", "player1", "Tavern", state)
        assert result.result == ValidationResult.BLOCKED

    def test_change_to_new_location_allowed(self):
        """Changing to different location returns ALLOWED."""
        state = {
            "campaign": {"current_location": "Tavern"},
        }
        result = validate_action("change_location", "player1", "Dungeon", state)
        assert result.result == ValidationResult.ALLOWED

# ── Tests: enforce_world_consistency ────────────────────────────────────────

class TestEnforceWorldConsistency:
    """enforce_world_consistency checks narrative vs world state."""

    def test_no_contradictions_returns_unchanged(self):
        """Narrative without contradictions is returned unchanged."""
        narrative = "The goblin scout lurks in the shadows."
        state = {
            "npcs": {
                "goblin_01": {"name": "Goblin Scout", "status": "ALIVE"},
            }
        }
        result = enforce_world_consistency(narrative, state)
        assert result == narrative

    def test_dead_npc_contradiction_still_returns_narrative(self):
        """Even with dead NPC contradiction, returns original narrative."""
        narrative = "The Goblin Scout smiles and draws his sword."
        state = {
            "npcs": {
                "goblin_01": {"name": "Goblin Scout", "status": "DEAD"},
            }
        }
        result = enforce_world_consistency(narrative, state)
        assert isinstance(result, str)
        # Currently returns unchanged (corrections only logged)


# ── Tests: add_npc_memory ───────────────────────────────────────────────────

class TestAddNPCMemory:
    """add_npc_memory adds validated memories to NPCs."""

    def test_add_memory_with_state_validation(self):
        """Valid memory with explicit state is added successfully."""
        state = {
            "npcs": {
                "npc_01": {"name": "Guard", "memory": ["Met the party"]},
            }
        }
        success, msg = add_npc_memory(
            "campaign_1", "npc_01", "The party paid the toll", state=state
        )
        assert success is True
        assert "Guard" in msg
        assert len(state["npcs"]["npc_01"]["memory"]) == 2
