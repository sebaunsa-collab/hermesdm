"""
pacing_engine.py — Decide scene types, detect loops, and manage milestone progression.

The PacingEngine is the "narrative director" of HermesDM. It looks at the story arc,
recent history, and player actions to decide:
1. What SceneType should come next (anti-loop, anti-stagnation)
2. Whether the current milestone is complete
3. How much "pressure" to apply to the narrative to advance the plot
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from dataclasses import dataclass

from dm.narrative_generator import SceneType
from dm.story_arc import StoryArc

if TYPE_CHECKING:
    from state.state_manager import GameState


# Thresholds for loop detection
_LOOP_CONFIG = {
    "same_type_threshold": 6,       # N scenes of same type → force change
    "exploration_without_beat": 10, # N explorations without story beat → force beat
    "combat_chain_threshold": 4,    # N combats in a row → force rest/dialogue
    "dialogue_chain_threshold": 8,  # N dialogues in a row → force action
}

# SceneType preferences by milestone type


_MILESTONE_SCENE_PREFERENCES = {
    "hook": [SceneType.EXPLORATION, SceneType.DIALOGUE, SceneType.STORY_BEAT],
    "rising_action": [SceneType.EXPLORATION, SceneType.COMBAT, SceneType.DIALOGUE, SceneType.STORY_BEAT],
    "midpoint": [SceneType.STORY_BEAT, SceneType.COMBAT, SceneType.DIALOGUE],
    "climax": [SceneType.COMBAT, SceneType.STORY_BEAT],
    "resolution": [SceneType.REST, SceneType.DIALOGUE, SceneType.STORY_BEAT],
}




# ── Scene Director helpers ────────────────────────────────────────────────

def get_milestone_tier(state: dict) -> int:
    """Get milestone tier (1-3) from state for encounter difficulty scaling."""
    story = state.get("story_arc", {})
    milestones = story.get("milestones", [])
    if not milestones:
        return 1
    current = story.get("current_milestone", 0)
    total = len(milestones)
    if total <= 0:
        return 1
    progress = current / max(total, 1)
    if progress > 0.66:
        return 3
    if progress > 0.33:
        return 2
    return 1


def get_scene_count(state: dict) -> int:
    """Get current scene count from state."""
    return state.get("scene_count", 0)


def get_turns_since_encounter(state: dict) -> int:
    """Get turns since last encounter from state."""
    return state.get("turns_since_encounter", 0)

class PacingEngine:
    """
    Narrative director that prevents loops and ensures story progression.
    """

    def __init__(self, story_arc: StoryArc, history: Optional[list[dict]] = None) -> None:
        self.arc = story_arc
        self.history = history or []
        self.scenes_since_main_threat = 0  # Track scenes since last main threat callback

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def reset_scenes_since_main_threat(self) -> None:
        """Reset the main threat scene counter. Call when narrative references the main threat."""
        self.scenes_since_main_threat = 0

    def should_inject_event(self) -> bool:
        """
        Determine if a GM event should be injected to move the plot forward.
        
        Returns True when:
        - milestone_pressure >= 0.7 (high pressure toward milestone)
        - scene_count >= max_scenes - 1 (approaching scene limit)
        """
        cm = self.arc.current_milestone
        if not cm:
            return False
        
        # Calculate current milestone pressure
        pressure = self._get_milestone_pressure(cm)
        
        if pressure >= 0.7:
            return True
        if cm.scene_count >= cm.max_scenes - 1:
            return True
        return False
    
    def _get_milestone_pressure(self, cm) -> float:
        """Calculate current milestone pressure (0.0-1.0)."""
        if cm.max_scenes <= cm.min_scenes:
            return 0.5
        pressure = (cm.scene_count - cm.min_scenes) / (cm.max_scenes - cm.min_scenes)
        return max(0.0, min(1.0, pressure))
    
    def update_pressure(self, action_type: str, success: bool, was_roll: bool) -> None:
        """
        Update milestone pressure based on player actions.
        
        - Progress toward milestone: milestone_pressure -= 0.2
        - Failed roll: milestone_pressure += 0.1
        - Time passing: milestone_pressure += 0.05
        - scene_count >= max_scenes: milestone_pressure = min(1.0, milestone_pressure + 0.15)
        """
        cm = self.arc.current_milestone
        if not cm:
            return
        
        # Get current pressure
        pressure = self._get_milestone_pressure(cm)
        
        # Adjust based on action
        if success and was_roll:
            # Successful roll that advances the plot
            pressure -= 0.2
        elif was_roll and not success:
            # Failed roll creates tension
            pressure += 0.1
        else:
            # Time passing / neutral action
            pressure += 0.05
        
        # Scene limit pressure
        if cm.scene_count >= cm.max_scenes:
            pressure = min(1.0, pressure + 0.15)
        
        # Update milestone's scene_count as proxy for pressure
        # (We don't have a separate milestone_pressure field on Milestone,
        # so we rely on scene_count calculations)
        # Just record the scene
        self.arc.record_scene(action_type if action_type else "unknown")
        
        # Track scenes since main threat
        self.scenes_since_main_threat += 1
    
    def get_event_context(self) -> dict:
        """
        Get event injection context for the narrative generator.
        
        Returns dict with:
        - inject_event: bool
        - event_types: list of event type suggestions
        - milestone_objective: str
        - main_threat: str
        - milestone_pressure: float
        """
        if not self.should_inject_event():
            return {"inject_event": False}
        
        cm = self.arc.current_milestone
        if not cm:
            return {"inject_event": False}
        
        return {
            "inject_event": True,
            "event_types": [
                "gm_event",      # Generic GM-driven event
                "arrival",       # NPC or creature arrives
                "environmental", # Weather, environment changes
                "revelation",    # Truth is revealed
                "complication",  # Existing situation worsens
                "callback",      # Callback to earlier events
                "time_pressure", # Time deadline approaches
            ],
            "milestone_objective": cm.description,
            "main_threat": self._get_main_threat(),
            "milestone_pressure": self._get_milestone_pressure(cm),
            "force_callback": self.scenes_since_main_threat >= 3,
            "callback_reason": "Main threat reminder" if self.scenes_since_main_threat >= 3 else None,
        }
    
    def _get_main_threat(self) -> str:
        """Get the main threat description from the campaign."""
        if self.arc.current_milestone:
            desc = self.arc.current_milestone.description
            # Extract first sentence as main threat
            if desc:
                return desc.split(".")[0] if "." in desc else desc[:80]
        return ""

    def get_next_scene_type(
        self,
        player_action: str,
        last_result: Optional[dict] = None,
    ) -> SceneType:
        """
        Decide the SceneType for the next narrative beat.

        Priority:
        1. Anti-loop detection (highest priority)
        2. Milestone type preferences
        3. Max-scenes pressure (force story beat if over limit)
        4. Player action inference
        """
        # 1. Anti-loop check
        loop_forced = self._check_loop_pressure()
        if loop_forced:
            return loop_forced

        cm = self.arc.current_milestone
        if not cm:
            # Campaign complete — epilogue
            return SceneType.STORY_BEAT

        # 2. Max-scenes pressure: force STORY_BEAT to advance milestone
        if cm.scene_count >= cm.max_scenes:
            return SceneType.STORY_BEAT

        # 3. Strong pressure: nudge toward STORY_BEAT when near max
        if cm.scene_count >= cm.max_scenes - 1 and cm.type not in ("climax", "resolution"):
            # 50% chance to force story beat when near limit
            import random
            if random.random() < 0.5:
                return SceneType.STORY_BEAT

        # 4. Min-scenes check: don't advance too fast
        if cm.scene_count < cm.min_scenes:
            # Stay in milestone-appropriate scenes, avoid premature resolution
            if cm.type == "hook":
                return self._infer_from_action(player_action, default=SceneType.EXPLORATION)
            elif cm.type == "rising_action":
                return self._infer_from_action(player_action, default=SceneType.EXPLORATION)
            elif cm.type == "climax":
                return self._infer_from_action(player_action, default=SceneType.COMBAT)

        # 5. Milestone type preferences + action inference
        inferred = self._infer_from_action(player_action)
        preferences = _MILESTONE_SCENE_PREFERENCES.get(cm.type, [SceneType.EXPLORATION])

        # If inferred matches preferences, use it
        if inferred in preferences:
            return inferred

        # Otherwise pick from preferences based on variety
        return self._pick_varied_from_preferences(preferences)

    def check_milestone_advance(self, narrative_text: str) -> bool:
        """
        Check if the current milestone should be marked complete.

        Heuristics:
        - scene_count >= max_scenes → FORCED
        - scene_count >= min_scenes AND narrative signals progress → advance
        - scene_count >= min_scenes AND no progress for 2 scenes → nudge
        """
        cm = self.arc.current_milestone
        if not cm:
            return False

        # Hard cap: max scenes reached
        if cm.scene_count >= cm.max_scenes:
            # Milestone about to advance - update pressure for milestone completion
            self.update_pressure("milestone_complete", success=True, was_roll=False)
            self.scenes_since_main_threat = 0  # Reset: new milestone = new threat context
            # ── P3: Set world_flag for milestone completion ──────────────
            self._set_milestone_flag(cm)
            return True

        # Soft cap: min scenes reached, check if narrative signals progress
        if cm.scene_count >= cm.min_scenes:
            if self._narrative_signals_progress(narrative_text):
                # Milestone advancing due to progress - positive pressure adjustment
                self.update_pressure("progress", success=True, was_roll=False)
                self.scenes_since_main_threat = 0  # Reset: new milestone = new threat context
                # ── P3: Set world_flag for milestone completion ──────────
                self._set_milestone_flag(cm)
                return True

        return False

    def _set_milestone_flag(self, cm) -> None:
        """Set world_flag for milestone completion (Phase 3 gate)."""
        try:
            from state.state_manager import load_state, save_state
            state_data = getattr(self.arc, '_state', None)
            if state_data is None:
                return
            campaign_id = state_data.get("campaign", {}).get("id")
            if not campaign_id:
                return
            flag_name = f"milestone_{cm.id}_complete" if hasattr(cm, 'id') else f"milestone_complete"
            state = load_state(campaign_id)
            if state is None:
                return
            state.setdefault("world_flags", {})[flag_name] = True
            save_state(campaign_id, state)
        except Exception:
            pass  # Non-critical — world_flags is additive

    def get_milestone_context(self) -> dict:
        """Return context for the narrative generator."""
        return self.arc.get_milestone_context()

        cm = self.arc.current_milestone
        if not cm:
            return ""

        lines = [
            f"",
            f"═══ CONTEXTO DE PROGRESO ═══",
            f"Milestone actual: {cm.id} ({cm.type})",
            f"Objetivo: {cm.description}",
            f"Escenas aquí: {cm.scene_count}/{cm.max_scenes}",
        ]

        # Pressure messaging
        if cm.scene_count >= cm.max_scenes - 1:
            lines.append("⚠️ PRESIÓN MÁXIMA: Este milestone debe resolverse AHORA.")
        elif cm.scene_count >= cm.min_scenes + 1:
            lines.append(f"⏳ Presión de avance: la trama debe avanzar hacia el siguiente hito.")

        if cm.type == "climax":
            lines.append("🎭 CLIMAX: La confrontación final. Todo está en juego.")
        elif cm.type == "resolution":
            lines.append("🌅 RESOLUCIÓN: Las consecuencias se revelan. Cierra con fuerza.")

        lines.append("═══")
        return "\n".join(lines)

    def record_scene(self, scene_type: SceneType) -> None:
        """Record that a scene happened."""
        self.arc.record_scene(scene_type.value)

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _check_loop_pressure(self) -> Optional[SceneType]:
        """Detect loops and force a different scene type."""
        recent = self.arc.recent_scene_types
        if not recent:
            return None

        # 1. Too many combats in a row → force dialogue/rest
        combat_threshold = _LOOP_CONFIG["combat_chain_threshold"]
        if len(recent) >= combat_threshold:
            last_n = recent[-combat_threshold:]
            if all(t == "COMBAT" for t in last_n):
                return SceneType.DIALOGUE

        # 2. Too many explorations/dialogues without story beat → force story beat
        expl_threshold = _LOOP_CONFIG["exploration_without_beat"]
        if len(recent) >= expl_threshold:
            last_n = recent[-expl_threshold:]
            if all(t in ("EXPLORATION", "DIALOGUE") for t in last_n):
                if "STORY_BEAT" not in last_n:
                    return SceneType.STORY_BEAT

        # 3. Generic same type repeated → force different
        threshold = _LOOP_CONFIG["same_type_threshold"]
        if len(recent) >= threshold:
            last_type = recent[-1]
            if all(t == last_type for t in recent[-threshold:]):
                return self._force_different_type(last_type)

        # Too many dialogues in a row
        dialogue_threshold = _LOOP_CONFIG["dialogue_chain_threshold"]
        if len(recent) >= dialogue_threshold:
            last_n = recent[-dialogue_threshold:]
            if all(t == "DIALOGUE" for t in last_n):
                return SceneType.EXPLORATION

        return None

    def _force_different_type(self, current_type: str) -> SceneType:
        """Pick a scene type different from the current one."""
        cm = self.arc.current_milestone
        preferences = _MILESTONE_SCENE_PREFERENCES.get(
            cm.type if cm else "rising_action",
            [SceneType.EXPLORATION, SceneType.DIALOGUE, SceneType.COMBAT],
        )

        # Filter out current type
        options = [p for p in preferences if p.value != current_type]
        if not options:
            options = [SceneType.EXPLORATION, SceneType.DIALOGUE]

        import random
        return random.choice(options)

    def _infer_from_action(self, player_action: str, default: SceneType = SceneType.EXPLORATION) -> SceneType:
        """Infer scene type from player action text."""
        action_lower = player_action.lower()

        combat_keywords = [
            "ataco", "atacar", "golpeo", "disparo", "lanzo", "tiro", "combate",
            "fight", "attack", "hit", "shoot", "stab", "slash", "punch",
        ]
        dialogue_keywords = [
            "hablo", "digo", "pregunto", "persuado", "intimido", "nego",
            "talk", "say", "ask", "persuade", "intimidate", "negotiate",
        ]
        rest_keywords = [
            "descanso", "dormir", "curo", "recupero", "descansamos",
            "rest", "sleep", "heal", "recover",
        ]
        stealth_keywords = [
            "sigilo", "escabullir", "escondo", "observo", "investigo",
            "stealth", "sneak", "hide", "observe", "investigate",
        ]

        if any(kw in action_lower for kw in combat_keywords):
            return SceneType.COMBAT
        if any(kw in action_lower for kw in dialogue_keywords):
            return SceneType.DIALOGUE
        if any(kw in action_lower for kw in rest_keywords):
            return SceneType.REST
        if any(kw in action_lower for kw in stealth_keywords):
            return SceneType.EXPLORATION

        return default

    def _pick_varied_from_preferences(self, preferences: list[SceneType]) -> SceneType:
        """Pick from preferences, avoiding the most recent type."""
        import random

        recent = self.arc.recent_scene_types
        if not recent or not preferences:
            return random.choice(preferences) if preferences else SceneType.EXPLORATION

        last_type = recent[-1]
        # Try to avoid the last type if possible
        alternatives = [p for p in preferences if p.value != last_type]
        if alternatives:
            return random.choice(alternatives)
        return random.choice(preferences)

    def _narrative_signals_progress(self, narrative_text: str) -> bool:
        """
        Heuristic: does the narrative text suggest ACTUAL milestone progress?

        Only triggers on STRONG signals that indicate quest/story resolution,
        NOT on generic exploration keywords.
        """
        text_lower = narrative_text.lower()

        # STRONG signals: these indicate real story progression
        strong_signals = [
            "la verdad es que", "el secreto es", "la puerta se abre",
            "has resuelto", "has completado", "has derrotado al",
            "el jefe ha caido", "la mision se completa",
            "has encontrado la", "has descubierto la verdad",
            "el ancient", "the ancient", "the truth is",
            "you have defeated", "quest complete", "mission complete",
        ]

        # Only count if at least 2 strong signals appear
        matches = sum(1 for sig in strong_signals if sig in text_lower)
        return matches >= 2


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def create_pacing_engine(state: dict) -> PacingEngine:
    """Create a PacingEngine from campaign state."""
    arc_data = state.get("story_arc")
    if arc_data:
        story_arc = StoryArc.from_dict(arc_data)
    else:
        # No arc defined — create a default medium one
        from dm.story_arc import create_default_story_arc
        story_arc = create_default_story_arc("medium")

    history = state.get("history", [])
    return PacingEngine(story_arc=story_arc, history=history)
