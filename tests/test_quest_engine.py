"""
test_quest_engine.py — Tests for QuestEngine module.

Covers:
- Quest CRUD operations
- Objective state machine (pending→active→completed/failed)
- 7 objective types
- Prerequisite flags
- Quest completion → world flag
- Advancement check
"""

import pytest
from dm.quest_engine import QuestEngine


# ── Quest CRUD ───────────────────────────────────────────────────────────


class TestQuestCRUD:
    """Creating, reading quests."""

    def test_create_quest(self):
        """Create a quest adds to active and by_id."""
        state = {}
        engine = QuestEngine(state)
        quest = engine.create_quest(
            state,
            "q1",
            "Slay the Dragon",
            [
                {"type": "kill", "target": "Dragon", "description": "Kill the dragon"},
                {"type": "reach_location", "target": "Dragon's Lair",
                 "description": "Find the lair"},
            ],
            description="The dragon terrorizes the village",
            reward="1000 gold",
        )
        assert quest["name"] == "Slay the Dragon"
        assert quest["status"] == "active"
        assert len(quest["objectives"]) == 2
        assert state["quests"]["active"] == ["q1"]
        assert "q1" in state["quests"]["by_id"]

    def test_get_quest(self):
        """Get quest by ID."""
        state = {}
        engine = QuestEngine(state)
        engine.create_quest(state, "q1", "Test", [{"type": "kill", "target": "X"}])
        quest = engine.get_quest(state, "q1")
        assert quest is not None
        assert quest["name"] == "Test"

    def test_get_active_quests(self):
        """Get all active quests."""
        state = {}
        engine = QuestEngine(state)
        engine.create_quest(state, "q1", "Q1", [{"type": "kill", "target": "A"}])
        engine.create_quest(state, "q2", "Q2", [{"type": "collect", "target": "B"}])
        active = engine.get_active_quests(state)
        assert len(active) == 2


# ── 3.5 Objective State Machine ──────────────────────────────────────────


class TestObjectiveStateMachine:
    """Task 3.5: objective state machine pending→active→completed/failed."""

    def test_pending_to_active(self):
        """Objective moves from pending to active."""
        state = {}
        engine = QuestEngine(state)
        engine.create_quest(state, "q1", "Test", [
            {"type": "kill", "target": "Goblin", "description": "Kill goblins"}
        ])
        result = engine.activate_objective(state, "q1", 0)
        assert result is not None
        assert result["status"] == "active"

    def test_active_to_completed(self):
        """Objective moves from active to completed."""
        state = {}
        engine = QuestEngine(state)
        engine.create_quest(state, "q1", "Test", [
            {"type": "kill", "target": "Goblin"}
        ])
        engine.activate_objective(state, "q1", 0)
        result = engine.complete_objective(state, "q1", 0)
        assert result["status"] == "completed"

    def test_active_to_failed(self):
        """Objective can be failed."""
        state = {}
        engine = QuestEngine(state)
        engine.create_quest(state, "q1", "Test", [
            {"type": "kill", "target": "Goblin"}
        ])
        engine.activate_objective(state, "q1", 0)
        result = engine.fail_objective(state, "q1", 0)
        assert result["status"] == "failed"

    def test_invalid_transition_rejected(self):
        """Jumping from pending to completed is rejected."""
        state = {}
        engine = QuestEngine(state)
        engine.create_quest(state, "q1", "Test", [
            {"type": "kill", "target": "Goblin"}
        ])
        # Try to complete a pending objective directly
        result = engine.complete_objective(state, "q1", 0)
        assert result is None  # Rejected

    def test_failed_cannot_recover(self):
        """Failed objective cannot go to completed."""
        state = {}
        engine = QuestEngine(state)
        engine.create_quest(state, "q1", "Test", [
            {"type": "kill", "target": "Goblin"}
        ])
        engine.activate_objective(state, "q1", 0)
        engine.fail_objective(state, "q1", 0)
        result = engine.complete_objective(state, "q1", 0)
        assert result is None


# ── 3.7 Quest Completion → World Flag ────────────────────────────────────


class TestQuestCompletion:
    """Task 3.7: all objectives completed → world flag set."""

    def test_all_objectives_done_completes_quest(self):
        """When all objectives are completed, quest completes."""
        state = {}
        engine = QuestEngine(state)
        engine.create_quest(state, "q1", "Clean Dungeon", [
            {"type": "kill", "target": "Rats"},
            {"type": "collect", "target": "Ancient Book"},
        ])
        engine.activate_objective(state, "q1", 0)
        engine.complete_objective(state, "q1", 0)
        engine.activate_objective(state, "q1", 1)
        engine.complete_objective(state, "q1", 1)

        assert "q1" in state["quests"]["completed"]
        assert "q1" not in state["quests"]["active"]
        assert state["quests"]["by_id"]["q1"]["status"] == "completed"
        assert state["world_flags"].get("quest_q1_completed") is True


# ── 3.8 Prerequisite Flags ───────────────────────────────────────────────


class TestPrerequisiteFlags:
    """Task 3.8: prerequisite flag not met blocks completion."""

    def test_prerequisite_blocks_completion(self):
        """Objective with unmet prerequisite cannot complete."""
        state = {"world_flags": {"gate_open": False}}
        engine = QuestEngine(state)
        engine.create_quest(state, "q1", "Test", [
            {"type": "kill", "target": "Guardian",
             "prerequisite_flag": "gate_open"}
        ])
        engine.activate_objective(state, "q1", 0)
        result = engine.complete_objective(state, "q1", 0)
        assert result is None  # Blocked

    def test_prerequisite_met_allows_completion(self):
        """Objective with met prerequisite can complete."""
        state = {"world_flags": {"gate_open": True}}
        engine = QuestEngine(state)
        engine.create_quest(state, "q1", "Test", [
            {"type": "kill", "target": "Guardian",
             "prerequisite_flag": "gate_open"}
        ])
        engine.activate_objective(state, "q1", 0)
        result = engine.complete_objective(state, "q1", 0)
        assert result["status"] == "completed"


# ── Quest Summary ─────────────────────────────────────────────────────────


class TestQuestSummary:
    """Quest summary formatting."""

    def test_get_quest_summary_active(self):
        """Quest summary shows active quests."""
        state = {}
        engine = QuestEngine(state)
        engine.create_quest(state, "q1", "Rescue Mission", [
            {"type": "kill", "target": "Kidnappers", "description": "Eliminate kidnappers"},
            {"type": "escort", "target": "Princess", "description": "Escort princess"},
        ])
        engine.activate_objective(state, "q1", 0)
        summary = engine.get_quest_summary(state)
        assert "Rescue Mission" in summary
        assert "Kidnappers" in summary or "Eliminate" in summary
