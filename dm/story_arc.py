"""
story_arc.py — Story arc dataclasses and serialization for HermesDM pacing system.

A StoryArc defines the narrative skeleton of a campaign: milestones that
progress from hook → rising action → climax → resolution. The PacingEngine
uses this to direct scene generation and detect stagnation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Milestone:
    """A single narrative milestone within a story arc."""

    id: str
    type: str  # "hook" | "rising_action" | "midpoint" | "climax" | "resolution"
    description: str
    completed: bool = False
    completed_at: Optional[str] = None
    scene_count: int = 0
    min_scenes: int = 2
    max_scenes: int = 5

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "completed": self.completed,
            "completed_at": self.completed_at,
            "scene_count": self.scene_count,
            "min_scenes": self.min_scenes,
            "max_scenes": self.max_scenes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Milestone:
        return cls(
            id=data["id"],
            type=data["type"],
            description=data["description"],
            completed=data.get("completed", False),
            completed_at=data.get("completed_at"),
            scene_count=data.get("scene_count", 0),
            min_scenes=data.get("min_scenes", 2),
            max_scenes=data.get("max_scenes", 5),
        )


@dataclass
class StoryArc:
    """Full narrative arc for a campaign."""

    pacing_level: str  # "short" | "medium" | "long"
    total_sessions: int
    milestones: list[Milestone] = field(default_factory=list)
    current_index: int = 0
    total_scenes: int = 0

    # Loop detection tracking
    recent_scene_types: list[str] = field(default_factory=list)
    max_recent_track: int = 10

    def to_dict(self) -> dict:
        return {
            "pacing_level": self.pacing_level,
            "total_sessions": self.total_sessions,
            "milestones": [m.to_dict() for m in self.milestones],
            "current_index": self.current_index,
            "total_scenes": self.total_scenes,
            "recent_scene_types": self.recent_scene_types,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StoryArc:
        return cls(
            pacing_level=data["pacing_level"],
            total_sessions=data["total_sessions"],
            milestones=[Milestone.from_dict(m) for m in data.get("milestones", [])],
            current_index=data.get("current_index", 0),
            total_scenes=data.get("total_scenes", 0),
            recent_scene_types=data.get("recent_scene_types", []),
        )

    @property
    def current_milestone(self) -> Optional[Milestone]:
        if 0 <= self.current_index < len(self.milestones):
            return self.milestones[self.current_index]
        return None

    @property
    def is_complete(self) -> bool:
        return self.current_index >= len(self.milestones)

    def record_scene(self, scene_type: str) -> None:
        """Record that a scene of type *scene_type* just happened."""
        self.total_scenes += 1
        self.recent_scene_types.append(scene_type)
        if len(self.recent_scene_types) > self.max_recent_track:
            self.recent_scene_types = self.recent_scene_types[-self.max_recent_track:]

        if self.current_milestone:
            self.current_milestone.scene_count += 1

    def advance_milestone(self, timestamp: Optional[str] = None) -> bool:
        """Advance to the next milestone. Returns True if advanced."""
        if self.current_milestone:
            self.current_milestone.completed = True
            self.current_milestone.completed_at = timestamp
        self.current_index += 1
        return True

    def get_milestone_context(self) -> dict:
        """Return context dict for narrative generator."""
        cm = self.current_milestone
        if not cm:
            return {"campaign_complete": True}

        progress_pressure = 0.0
        if cm.max_scenes > cm.min_scenes:
            progress_pressure = (cm.scene_count - cm.min_scenes) / (cm.max_scenes - cm.min_scenes)
            progress_pressure = max(0.0, min(1.0, progress_pressure))

        return {
            "current_milestone_id": cm.id,
            "current_milestone_type": cm.type,
            "current_milestone_description": cm.description,
            "scenes_in_milestone": cm.scene_count,
            "min_scenes": cm.min_scenes,
            "max_scenes": cm.max_scenes,
            "progress_pressure": round(progress_pressure, 2),
            "milestone_index": self.current_index,
            "total_milestones": len(self.milestones),
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

PACING_CONFIG = {
    "short": {
        "total_sessions": 5,
        "milestone_specs": [
            ("hook", "hook", 1, 2),
            ("rising_action", "rising_action", 2, 4),
            ("climax", "climax", 1, 2),
            ("resolution", "resolution", 1, 1),
        ],
    },
    "medium": {
        "total_sessions": 10,
        "milestone_specs": [
            ("hook", "hook", 1, 3),
            ("rising_action_1", "rising_action", 2, 4),
            ("rising_action_2", "rising_action", 2, 4),
            ("climax", "climax", 1, 3),
            ("resolution", "resolution", 1, 2),
        ],
    },
    "long": {
        "total_sessions": 20,
        "milestone_specs": [
            ("hook", "hook", 1, 3),
            ("rising_action_1", "rising_action", 2, 5),
            ("midpoint", "midpoint", 1, 2),
            ("rising_action_2", "rising_action", 2, 5),
            ("rising_action_3", "rising_action", 2, 4),
            ("climax", "climax", 1, 3),
            ("resolution", "resolution", 1, 2),
        ],
    },
}


def create_story_arc_from_ai_response(
    pacing_level: str,
    ai_milestones: list[dict],
) -> StoryArc:
    """
    Build a StoryArc from AI-generated milestone descriptions.

    ai_milestones: list of {"id": ..., "type": ..., "description": ...}
    """
    config = PACING_CONFIG.get(pacing_level, PACING_CONFIG["medium"])
    specs = {s[0]: s for s in config["milestone_specs"]}

    milestones = []
    for am in ai_milestones:
        spec = specs.get(am["id"], (am["id"], am["type"], 2, 5))
        milestones.append(
            Milestone(
                id=am["id"],
                type=am["type"],
                description=am["description"],
                min_scenes=spec[2],
                max_scenes=spec[3],
            )
        )

    return StoryArc(
        pacing_level=pacing_level,
        total_sessions=config["total_sessions"],
        milestones=milestones,
    )


def create_default_story_arc(pacing_level: str = "medium") -> StoryArc:
    """Fallback arc when AI generation fails."""
    config = PACING_CONFIG.get(pacing_level, PACING_CONFIG["medium"])
    milestones = []
    for spec in config["milestone_specs"]:
        milestones.append(
            Milestone(
                id=spec[0],
                type=spec[1],
                description=f"Milestone {spec[0]} — avanza la trama principal.",
                min_scenes=spec[2],
                max_scenes=spec[3],
            )
        )
    return StoryArc(
        pacing_level=pacing_level,
        total_sessions=config["total_sessions"],
        milestones=milestones,
    )
