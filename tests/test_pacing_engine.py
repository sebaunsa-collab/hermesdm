import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dm.pacing_engine import PacingEngine, SceneType


class MockStoryArc:
    def __init__(self):
        self._milestones = []
        self._current_idx = 0
        self.recent_scene_types = []
        self._scene_log = []

    @property
    def current_milestone(self):
        if self._milestones and self._current_idx < len(self._milestones):
            return self._milestones[self._current_idx]
        return None

    def get_milestone_context(self):
        return {"campaign_complete": False}

    def record_scene(self, scene_type: str) -> None:
        """Record a scene happened, tracking scene types."""
        self._scene_log.append(scene_type)
        self.recent_scene_types.append(scene_type)
        # Keep recent scene types bounded (matching StoryArc max_recent_track=20)
        if len(self.recent_scene_types) > 20:
            self.recent_scene_types = self.recent_scene_types[-20:]


@pytest.fixture
def pacing_engine():
    arc = MockStoryArc()
    arc._milestones = [
        MagicMock(id="intro", type="hook", description="Introduction",
                  scene_count=0, max_scenes=3, min_scenes=1),
    ]
    return PacingEngine(arc, history=[])


class TestPacingEngine:
    def test_pacing_engine_initialization(self, pacing_engine):
        assert pacing_engine is not None
        assert hasattr(pacing_engine, "arc")
        assert hasattr(pacing_engine, "scenes_since_main_threat")

    def test_should_inject_event_returns_bool(self, pacing_engine):
        pacing_engine.scene_count = 0
        pacing_engine.max_scenes = 5
        result = pacing_engine.should_inject_event()
        assert isinstance(result, bool)

    def test_get_event_context_returns_dict(self, pacing_engine):
        ctx = pacing_engine.get_event_context()
        assert isinstance(ctx, dict)

    def test_update_pressure_accepts_args(self, pacing_engine):
        pacing_engine.milestone_pressure = 0.5
        pacing_engine.update_pressure("attack", success=True, was_roll=True)
        assert isinstance(pacing_engine.milestone_pressure, float)

    def test_record_scene_increments_count(self, pacing_engine):
        pacing_engine.record_scene(SceneType.EXPLORATION)
        assert len(pacing_engine.arc.recent_scene_types) > 0
        assert "EXPLORATION" in pacing_engine.arc.recent_scene_types

    def test_get_next_scene_type_returns_scenetype(self, pacing_engine):
        result = pacing_engine.get_next_scene_type("ataco", SceneType.COMBAT)
        assert isinstance(result, SceneType)

    def test_check_milestone_advance_returns_bool(self, pacing_engine):
        result = pacing_engine.check_milestone_advance("heroe avanza")
        assert isinstance(result, bool)

    def test_get_milestone_context_returns_dict(self, pacing_engine):
        ctx = pacing_engine.get_milestone_context()
        assert isinstance(ctx, dict)
