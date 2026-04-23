"""Tests for Pacing System (Fix 1)."""

import pytest

from dm.story_arc import Milestone, StoryArc, create_default_story_arc, PACING_CONFIG
from dm.pacing_engine import PacingEngine
from dm.narrative_generator import SceneType


# ─────────────────────────────────────────────────────────────
# StoryArc tests
# ─────────────────────────────────────────────────────────────

def test_create_default_story_arc_short():
    arc = create_default_story_arc("short")
    assert arc.pacing_level == "short"
    assert arc.total_sessions == 5
    assert len(arc.milestones) == 4
    assert arc.milestones[0].type == "hook"
    assert arc.milestones[-1].type == "resolution"


def test_create_default_story_arc_medium():
    arc = create_default_story_arc("medium")
    assert arc.pacing_level == "medium"
    assert arc.total_sessions == 10
    assert len(arc.milestones) == 5


def test_create_default_story_arc_long():
    arc = create_default_story_arc("long")
    assert arc.pacing_level == "long"
    assert arc.total_sessions == 20
    assert len(arc.milestones) == 7


def test_story_arc_record_scene():
    arc = create_default_story_arc("short")
    arc.record_scene("EXPLORATION")
    assert arc.total_scenes == 1
    assert arc.milestones[0].scene_count == 1
    assert arc.recent_scene_types == ["EXPLORATION"]


def test_story_arc_advance_milestone():
    arc = create_default_story_arc("short")
    arc.record_scene("EXPLORATION")
    arc.advance_milestone()
    assert arc.current_index == 1
    assert arc.milestones[0].completed is True
    assert arc.current_milestone.type == "rising_action"


def test_story_arc_is_complete():
    arc = create_default_story_arc("short")
    for _ in range(4):
        arc.advance_milestone()
    assert arc.is_complete is True
    assert arc.current_milestone is None


def test_get_milestone_context():
    arc = create_default_story_arc("short")
    ctx = arc.get_milestone_context()
    assert ctx["current_milestone_id"] == "hook"
    assert ctx["current_milestone_type"] == "hook"
    assert ctx["progress_pressure"] == 0.0

    # Add scenes to increase pressure
    for _ in range(3):
        arc.record_scene("EXPLORATION")
    ctx = arc.get_milestone_context()
    assert ctx["scenes_in_milestone"] == 3
    assert ctx["progress_pressure"] > 0.0


# ─────────────────────────────────────────────────────────────
# PacingEngine tests
# ─────────────────────────────────────────────────────────────

def test_detect_loop_same_type():
    arc = create_default_story_arc("medium")
    for _ in range(3):
        arc.record_scene("EXPLORATION")
    engine = PacingEngine(arc)
    result = engine._check_loop_pressure()
    assert result is not None
    assert result != SceneType.EXPLORATION


def test_detect_loop_exploration_chain():
    arc = create_default_story_arc("medium")
    for _ in range(5):
        arc.record_scene("EXPLORATION")
    engine = PacingEngine(arc)
    result = engine._check_loop_pressure()
    assert result == SceneType.STORY_BEAT


def test_detect_loop_combat_chain():
    arc = create_default_story_arc("medium")
    for _ in range(3):
        arc.record_scene("COMBAT")
    engine = PacingEngine(arc)
    result = engine._check_loop_pressure()
    assert result == SceneType.DIALOGUE


def test_get_next_scene_type_respects_milestone():
    arc = create_default_story_arc("short")
    engine = PacingEngine(arc)
    # Hook milestone should prefer exploration/dialogue/story_beat
    st = engine.get_next_scene_type("muevo hacia la puerta")
    assert st in (SceneType.EXPLORATION, SceneType.DIALOGUE, SceneType.STORY_BEAT)


def test_get_next_scene_type_climax_forces_combat():
    arc = create_default_story_arc("short")
    # Advance to climax
    arc.advance_milestone()  # hook -> rising
    arc.advance_milestone()  # rising -> climax
    engine = PacingEngine(arc)
    st = engine.get_next_scene_type("ataco al jefe")
    assert st == SceneType.COMBAT


def test_max_scenes_pressure():
    arc = create_default_story_arc("short")
    # Fill hook to max
    for _ in range(arc.milestones[0].max_scenes):
        arc.record_scene("EXPLORATION")
    engine = PacingEngine(arc)
    st = engine.get_next_scene_type("sigo explorando")
    assert st == SceneType.STORY_BEAT


def test_check_milestone_advance_forced_by_max():
    arc = create_default_story_arc("short")
    for _ in range(arc.milestones[0].max_scenes):
        arc.record_scene("EXPLORATION")
    engine = PacingEngine(arc)
    assert engine.check_milestone_advance("descubriste la verdad") is True


def test_check_milestone_advance_not_yet():
    arc = create_default_story_arc("short")
    arc.record_scene("EXPLORATION")
    engine = PacingEngine(arc)
    assert engine.check_milestone_advance("nada nuevo") is False


def test_narrative_signals_progress():
    arc = create_default_story_arc("short")
    engine = PacingEngine(arc)
    assert engine._narrative_signals_progress("descubriste la verdad oculta") is True
    assert engine._narrative_signals_progress("caminas por el pasillo") is False


def test_infer_from_action():
    arc = create_default_story_arc("short")
    engine = PacingEngine(arc)
    assert engine._infer_from_action("ataco al orco") == SceneType.COMBAT
    assert engine._infer_from_action("hablo con el mercader") == SceneType.DIALOGUE
    assert engine._infer_from_action("descanso en la posada") == SceneType.REST
    assert engine._infer_from_action("me escabullo entre las sombras") == SceneType.EXPLORATION


# ─────────────────────────────────────────────────────────────
# Serialization tests
# ─────────────────────────────────────────────────────────────

def test_story_arc_roundtrip():
    arc = create_default_story_arc("medium")
    arc.record_scene("COMBAT")
    arc.advance_milestone()
    data = arc.to_dict()
    restored = StoryArc.from_dict(data)
    assert restored.pacing_level == arc.pacing_level
    assert restored.current_index == arc.current_index
    assert restored.total_scenes == arc.total_scenes
    assert len(restored.milestones) == len(arc.milestones)
    assert restored.milestones[0].completed is True
