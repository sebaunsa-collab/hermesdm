"""
dm/__init__.py — HermesDM narrative system module.

Exports:
    - NarrativeGenerator: Template-based scene narration
    - SceneType: Scene classification enum
"""
from .narrative_generator import NarrativeGenerator, SceneType

__all__ = [
    "NarrativeGenerator",
    "SceneType",
]
