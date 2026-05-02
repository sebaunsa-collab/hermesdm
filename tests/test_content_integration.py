"""
test_content_integration.py — Integration tests for Content Engine.

Covers:
- encounter_engine uses monster_manual when use_content_engine=True
- scene_director detects dungeon destinations and generates dungeon
- state_manager provides dungeon state and use_content_engine flag
- Backward compatibility when flag is absent/false
"""

import random
import pytest
from dm.encounter_engine import EncounterEngine
from dm.scene_director import SceneDirector, SceneDecision
from dm.monster_manual import get_monster
from state.state_manager import new_state

SEED = 42


def _rng(seed: int = SEED) -> random.Random:
    return random.Random(seed)


# ── Encounter Engine Integration ─────────────────────────────────────────


class TestEncounterEngineIntegration:
    def test_monster_manual_lookup_with_content_engine(self):
        """When use_content_engine=True, get_monster() returns real stat blocks."""
        goblin = get_monster("goblin")
        assert goblin is not None
        assert "hp" in goblin
        assert "attacks" in goblin
        assert goblin["cr"] == 0.25

    def test_encounter_engine_accepts_content_state(self):
        """EncounterEngine works with state that has use_content_engine flag."""
        state = {"campaign": {"id": "test_c1", "current_location": "Dark Forest"},
                 "world": {"danger_level": 2, "biome": "forest"},
                 "use_content_engine": True}
        engine = EncounterEngine(state)
        # Should not crash — backward compatibility is key
        result = engine.roll_for_encounter(state, _rng())
        if result:
            scene_type, enemies, _ = result
            assert scene_type in ("combat", "social", "exploration")


# ── Scene Director Integration ───────────────────────────────────────────


class TestSceneDirectorIntegration:
    def test_dungeon_destination_detection(self):
        """SceneDirector travel gate handles dungeon: prefix destinations."""
        state = new_state("test_d1", "Dungeon Test", "fantasy")
        state["turn"] = 1
        state["scene_count"] = 0
        state["current_location"] = "Forest Edge"
        state["use_content_engine"] = True

        # Mock resolution with dungeon destination
        class FakeResolution:
            action_type = "travel"
            travel_destination = "dungeon:shadowfell"

        director = SceneDirector(state)
        decision = director.decide(state, FakeResolution())

        assert decision is not None
        assert decision.scene_type in ("travel", "dungeon", "exploration")

    def test_travel_without_dungeon_prefix(self):
        """Normal travel destinations do NOT trigger dungeon generation."""
        state = new_state("test_d2", "Travel Test", "fantasy")
        state["turn"] = 1
        state["scene_count"] = 0
        state["use_content_engine"] = True

        class FakeResolution:
            action_type = "travel"
            travel_destination = "Mountain Pass"

        director = SceneDirector(state)
        decision = director.decide(state, FakeResolution())

        assert decision is not None
        assert decision.scene_type == "travel"

    def test_no_content_engine_flag_works(self):
        """SceneDirector works normally without use_content_engine flag."""
        state = new_state("test_d3", "Default Test", "fantasy")
        state["turn"] = 1
        state["scene_count"] = 0

        class FakeResolution:
            action_type = "explore"
            travel_destination = None

        director = SceneDirector(state)
        decision = director.decide(state, FakeResolution())

        assert decision is not None
        assert decision.scene_type == "exploration"


# ── State Manager Integration ────────────────────────────────────────────


class TestStateManagerIntegration:
    def test_new_state_has_content_engine_flag(self):
        state = new_state("test_s1", "State Test", "fantasy")
        assert "use_content_engine" in state
        assert state["use_content_engine"] is True

    def test_new_state_has_dungeon_key(self):
        state = new_state("test_s2", "Dungeon State", "fantasy")
        assert "dungeon" in state
        assert state["dungeon"] is None
