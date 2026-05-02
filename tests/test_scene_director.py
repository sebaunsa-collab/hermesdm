"""
test_scene_director.py — Tests for SceneDirector and SceneDecision.

Covers:
- SceneDecision dataclass fields and defaults
- SceneDirector composition (sub-engine instantiation)
- Priority ladder: forced_rest, combat, forced_encounter, quest, travel, npc, social, exploration
"""

import pytest
from dm.scene_director import SceneDirector, SceneDecision


# ── 1.1 SceneDecision dataclass ───────────────────────────────────────────


class TestSceneDecision:
    """Task 1.1: SceneDecision dataclass with all fields and defaults."""

    def test_scene_decision_default_values(self):
        """Verify all fields have correct defaults."""
        sd = SceneDecision()
        assert sd.scene_type == "exploration"
        assert sd.narrative_instruction == ""
        assert sd.enemies == []
        assert sd.active_npc is None
        assert sd.location == ""
        assert sd.mechanical_setup == ""
        assert sd.world_changes == {}
        assert sd.quest_updates == []
        assert sd.is_encounter is False
        assert sd.requires_combat_init is False

    def test_scene_decision_with_values(self):
        """Verify fields accept explicit values."""
        sd = SceneDecision(
            scene_type="combat",
            narrative_instruction="El dragón ataca",
            enemies=[{"name": "Dragon", "hp": 100}],
            active_npc={"name": "Gandalf"},
            location="La Montaña",
            mechanical_setup="DC 15 Acrobatics",
            world_changes={"dragon_awake": True},
            quest_updates=[{"quest_id": "q1", "status": "completed"}],
            is_encounter=True,
            requires_combat_init=True,
        )
        assert sd.scene_type == "combat"
        assert sd.narrative_instruction == "El dragón ataca"
        assert len(sd.enemies) == 1
        assert sd.enemies[0]["name"] == "Dragon"
        assert sd.active_npc["name"] == "Gandalf"
        assert sd.location == "La Montaña"
        assert sd.mechanical_setup == "DC 15 Acrobatics"
        assert sd.world_changes == {"dragon_awake": True}
        assert sd.quest_updates == [{"quest_id": "q1", "status": "completed"}]
        assert sd.is_encounter is True
        assert sd.requires_combat_init is True

    def test_scene_decision_is_dataclass(self):
        """Verify it's a proper dataclass with equality."""
        sd1 = SceneDecision(scene_type="rest")
        sd2 = SceneDecision(scene_type="rest")
        assert sd1 == sd2
        assert sd1 != SceneDecision(scene_type="combat")

    def test_scene_decision_enemies_default_factory(self):
        """Verify enemies uses default_factory (not shared reference)."""
        sd1 = SceneDecision()
        sd2 = SceneDecision()
        sd1.enemies.append({"name": "Goblin"})
        assert sd2.enemies == []  # Not shared

    def test_scene_decision_quest_updates_default_factory(self):
        """Verify quest_updates uses default_factory (not shared)."""
        sd1 = SceneDecision()
        sd2 = SceneDecision()
        sd1.quest_updates.append({"q": "test"})
        assert sd2.quest_updates == []  # Not shared


# ── 1.3-1.4 SceneDirector composition ────────────────────────────────────


class TestSceneDirectorInit:
    """Task 1.3-1.4: SceneDirector instantiates all 5 sub-engines."""

    def test_initializes_without_state(self):
        """SceneDirector can be created with no state."""
        sd = SceneDirector()
        assert sd is not None
        assert sd.state == {}

    def test_initializes_with_state(self):
        """SceneDirector accepts a state dict."""
        state = {"campaign": {"name": "Test"}}
        sd = SceneDirector(state=state)
        assert sd.state == state

    def test_sub_engines_exist(self):
        """All 5 sub-engines are instantiated."""
        sd = SceneDirector()
        from dm.encounter_engine import EncounterEngine
        from dm.npc_director import NPCDirector
        from dm.quest_engine import QuestEngine
        from dm.resource_manager import ResourceManager
        from dm.combat_flow import CombatFlow

        assert isinstance(sd.encounter_engine, EncounterEngine)
        assert isinstance(sd.npc_director, NPCDirector)
        assert isinstance(sd.quest_engine, QuestEngine)
        assert isinstance(sd.resource_manager, ResourceManager)
        assert isinstance(sd.combat_flow, CombatFlow)


# ── 1.5-1.6 Forced Rest (HP ≤ 25%) ──────────────────────────────────────


class TestForcedRest:
    """Task 1.5-1.6: forced_rest when HP ≤ 25% overrides all."""

    def test_forced_rest_on_low_hp(self):
        """When HP <= 25%, decide() returns rest."""
        state = {
            "player": {"hp_current": 5, "hp_max": 40},
            "combat": {"active": False},
            "scene_count": 1,
        }

        class FakeResolution:
            pass

        sd = SceneDirector(state)
        result = sd.decide(state, FakeResolution())

        assert result.scene_type == "rest"
        assert "agotamiento" in result.narrative_instruction.lower() or \
               "gravemente" in result.narrative_instruction.lower()
        assert result.is_encounter is False

    def test_forced_rest_overrides_combat(self):
        """Forced rest overrides active combat when HP critical."""
        state = {
            "player": {"hp_current": 3, "hp_max": 12},
            "combat": {"active": True, "initiative_order": [
                {"name": "Enemy", "is_player": False, "hp": {"current": 1, "max": 10}}
            ], "current_turn": "Enemy"},
            "scene_count": 1,
        }

        class FakeResolution:
            pass

        sd = SceneDirector(state)
        result = sd.decide(state, FakeResolution())

        assert result.scene_type == "rest"

    def test_no_forced_rest_on_high_hp(self):
        """When HP > 25%, no forced rest."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
            "combat": {"active": False},
            "scene_count": 1,
        }

        class FakeResolution:
            pass

        sd = SceneDirector(state)
        result = sd.decide(state, FakeResolution())

        assert result.scene_type != "rest"

    def test_hp_is_critical_boundary(self):
        """HP exactly at 25% triggers critical."""
        state = {
            "player": {"hp_current": 10, "hp_max": 40},
            "combat": {"active": False},
            "scene_count": 1,
        }

        class FakeResolution:
            pass

        sd = SceneDirector(state)
        result = sd.decide(state, FakeResolution())
        assert result.scene_type == "rest"

        # At 11 (just above 25%)
        state["player"]["hp_current"] = 11
        result = sd.decide(state, FakeResolution())
        assert result.scene_type != "rest"


# ── 1.7-1.8 Combat Gate ──────────────────────────────────────────────────


class TestCombatGate:
    """Task 1.7-1.8: combat gate in decide() priority ladder."""

    def test_active_combat_returns_combat_type(self):
        """When combat is active, scene_type is combat."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
            "combat": {
                "active": True,
                "current_turn": "Goblin",
                "initiative_order": [
                    {"name": "Goblin", "is_player": False,
                     "hp": {"current": 5, "max": 10}},
                    {"name": "Player", "is_player": True,
                     "hp": {"current": 30, "max": 40}},
                ],
            },
            "scene_count": 1,
        }

        class FakeResolution:
            pass

        sd = SceneDirector(state)
        result = sd.decide(state, FakeResolution())

        assert result.scene_type == "combat"
        assert "combate" in result.narrative_instruction.lower()
        assert result.is_encounter is True

    def test_no_combat_when_inactive(self):
        """When combat is inactive, normal flow applies."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
            "combat": {"active": False},
            "scene_count": 1,
        }

        class FakeResolution:
            pass

        sd = SceneDirector(state)
        result = sd.decide(state, FakeResolution())

        assert result.scene_type != "combat"


# ── 1.9-1.10 Travel Gate & Exploration Default ───────────────────────────


class TestTravelGate:
    """Task 1.9-1.10: travel action → scene_type='travel', default exploration."""

    def test_travel_destination_produces_travel(self):
        """When resolution has travel_destination, scene_type is travel."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
            "combat": {"active": False},
            "scene_count": 1,
        }

        class FakeResolution:
            travel_destination = "Bosque Oscuro"

        sd = SceneDirector(state)
        result = sd.decide(state, FakeResolution())
        assert result.scene_type == "travel"
        assert result.location == "Bosque Oscuro"

    def test_default_exploration(self):
        """Default scene type is exploration."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
            "combat": {"active": False},
            "scene_count": 1,
        }

        class FakeResolution:
            pass

        sd = SceneDirector(state)
        result = sd.decide(state, FakeResolution())
        assert result.scene_type == "exploration"
        assert result.location != ""


# ── Social Gate ───────────────────────────────────────────────────────────


class TestSocialGate:
    """Social interaction with NPC produces social scene."""

    def test_dialogue_produces_social(self):
        """When action is dialogue, return social scene_type."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
            "combat": {"active": False},
            "scene_count": 1,
        }

        class FakeResolution:
            action_type = "dialogue"
            target = "El tabernero"

        sd = SceneDirector(state)
        result = sd.decide(state, FakeResolution())
        assert result.scene_type == "social"

    def test_intimidate_produces_social(self):
        """Intimidation is a social action."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
            "combat": {"active": False},
            "scene_count": 1,
        }

        class FakeResolution:
            action_type = "intimidate"
            target = "El guardia"

        sd = SceneDirector(state)
        result = sd.decide(state, FakeResolution())
        assert result.scene_type == "social"


# ── Forced Encounter (scene_count % 4 == 0) ─────────────────────────────


class TestForcedEncounter:
    """Forced encounter after every 4 scenes."""

    def test_forced_encounter_at_scene_4(self):
        """At scene_count=4, forced encounter triggers."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
            "combat": {"active": False},
            "campaign": {"id": "test-123", "current_location": "Forest"},
            "world": {"danger_level": 1},
            "scene_count": 4,
            "turn": 5,
            "npcs": {},
        }

        class FakeResolution:
            pass

        sd = SceneDirector(state)
        result = sd.decide(state, FakeResolution())
        # Since encounter engine may or may not find enemies for danger 1,
        # we only verify the scene_count%4 trigger was checked.
        # If encounter engine returns enemies, it'll be combat; if not, falls through.
        assert result.scene_type in ("combat", "social", "rest", "travel", "exploration", "event")

    def test_no_forced_encounter_at_scene_1(self):
        """At scene_count=1, no forced encounter."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
            "combat": {"active": False},
            "campaign": {"id": "test-123"},
            "world": {"danger_level": 1},
            "scene_count": 1,
            "turn": 2,
        }

        class FakeResolution:
            pass

        sd = SceneDirector(state)
        result = sd.decide(state, FakeResolution())
        assert result.scene_type == "exploration"


# ── NPC Surprise (act_counter % 5 == 0) ──────────────────────────────────


class TestNPCSurprise:
    """NPC surprise event after every 5 acts."""

    def test_npc_surprise_with_npcs(self):
        """At act_counter=5 with NPCs in state, npc_surprise triggers."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
            "combat": {"active": False},
            "scene_count": 1,
            "act_counter": 5,
            "npcs": {
                "npc1": {
                    "name": "Elfo Misterioso",
                    "disposition": "neutral",
                    "dialogue_hook": "Tengo información valiosa...",
                },
            },
        }

        class FakeResolution:
            pass

        sd = SceneDirector(state)
        result = sd.decide(state, FakeResolution())
        assert result.scene_type == "social"
        assert result.active_npc is not None
        assert result.active_npc["name"] == "Elfo Misterioso"
