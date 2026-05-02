"""
choice_tracker.py — Player Choice Tracking and Branching Narratives for HermesDM.

Tracks player decisions as they happen, creating a decision tree that the
narrative generator uses to branch storylines. Every significant choice
creates consequences that ripple forward.

Design: ChoiceTracker is a simple append-only log + consequence resolver.
It reads/writes state["choices"] for persistence.

The LLM narrative generator receives recent choices as context, enabling
branching dialogue and story adaptation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# -- Choice Categories -------------------------------------------------------

CATEGORY_MORAL = "moral"           # Good vs evil decision
CATEGORY_TACTICAL = "tactical"     # How to approach a problem
CATEGORY_SOCIAL = "social"         # Who to align with
CATEGORY_EXPLORATION = "exploration"  # Where to go / what to investigate
CATEGORY_QUEST = "quest"           # Quest-related decision
CATEGORY_COMBAT = "combat"         # Combat strategy choice
CATEGORY_CHARACTER = "character"   # Roleplay/personality choice


@dataclass
class Choice:
    """A single player choice decision."""
    choice_id: str                 # unique ID (auto-generated)
    category: str                  # one of CATEGORY_*
    description: str               # what was decided
    options: list[str]             # what options were available
    chosen: str                    # which option was selected
    player_name: str = ""
    timestamp: str = ""
    turn_number: int = 0
    # Consequences
    flags_set: list[str] = field(default_factory=list)   # world flags this set
    flags_cleared: list[str] = field(default_factory=list)  # flags removed
    disposition_changes: dict = field(default_factory=dict)  # {npc_id: delta}
    narrative_threads: list[str] = field(default_factory=list)  # story threads activated
    # Metadata
    reversible: bool = False       # can the player undo this?
    importance: int = 1            # 1-5, 5 = campaign-defining
    branch_id: str = ""            # which narrative branch this creates

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if not self.choice_id:
            self.choice_id = f"choice_{int(datetime.now().timestamp())}"

    def to_dict(self) -> dict:
        return {
            "choice_id": self.choice_id,
            "category": self.category,
            "description": self.description,
            "options": self.options,
            "chosen": self.chosen,
            "player_name": self.player_name,
            "timestamp": self.timestamp,
            "turn_number": self.turn_number,
            "flags_set": self.flags_set,
            "flags_cleared": self.flags_cleared,
            "disposition_changes": self.disposition_changes,
            "narrative_threads": self.narrative_threads,
            "reversible": self.reversible,
            "importance": self.importance,
            "branch_id": self.branch_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Choice":
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class Consequence:
    """A delayed consequence that triggers when conditions are met."""
    consequence_id: str
    trigger_flag: str              # world flag that triggers this
    description: str               # what happens
    effect_type: str               # "flag_set", "npc_disposition", "narrative", "combat"
    effect_data: dict = field(default_factory=dict)
    fired: bool = False
    fired_at: str = ""

    def to_dict(self) -> dict:
        return {
            "consequence_id": self.consequence_id,
            "trigger_flag": self.trigger_flag,
            "description": self.description,
            "effect_type": self.effect_type,
            "effect_data": self.effect_data,
            "fired": self.fired,
            "fired_at": self.fired_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Consequence":
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


# -- Choice Tracker ----------------------------------------------------------

class ChoiceTracker:
    """
    Tracks player choices and resolves branching consequences.

    Usage:
        tracker = ChoiceTracker(state)

        # Record a choice
        tracker.record_choice(
            category="moral",
            description="The blacksmith asks you to steal from the merchant",
            options=["Steal the goods", "Refuse and report to guard", "Blackmail the blacksmith"],
            chosen="Refuse and report to guard",
            player_name="Valdric",
            importance=3,
            flags_set=["reported_blacksmith", "guard_trust"],
            disposition_changes={"blacksmith": -20, "guard_captain": +15},
            narrative_threads=["guard_questline"],
        )

        # Check what happened because of past choices
        active_threads = tracker.get_active_threads()
        context = tracker.get_narrative_context()
    """

    def __init__(self, state: dict) -> None:
        self.state = state
        self._choices: list[Choice] = []
        self._consequences: list[Consequence] = []
        self._load()

    def _load(self) -> None:
        data = self.state.get("choices", {})
        self._choices = [Choice.from_dict(c) for c in data.get("log", [])]
        self._consequences = [Consequence.from_dict(c) for c in data.get("consequences", [])]

    def save(self) -> None:
        self.state["choices"] = {
            "log": [c.to_dict() for c in self._choices],
            "consequences": [c.to_dict() for c in self._consequences],
        }

    # -- Record Choices ------------------------------------------------------

    def record_choice(
        self,
        category: str,
        description: str,
        options: list[str],
        chosen: str,
        player_name: str = "",
        turn_number: int = 0,
        flags_set: Optional[list[str]] = None,
        flags_cleared: Optional[list[str]] = None,
        disposition_changes: Optional[dict] = None,
        narrative_threads: Optional[list[str]] = None,
        reversible: bool = False,
        importance: int = 1,
        branch_id: str = "",
    ) -> Choice:
        """
        Record a player choice with its consequences.

        Returns the created Choice object.
        """
        choice = Choice(
            choice_id=f"choice_{len(self._choices) + 1}_{int(datetime.now().timestamp())}",
            category=category,
            description=description,
            options=options,
            chosen=chosen,
            player_name=player_name,
            turn_number=turn_number,
            flags_set=flags_set or [],
            flags_cleared=flags_cleared or [],
            disposition_changes=disposition_changes or {},
            narrative_threads=narrative_threads or [],
            reversible=reversible,
            importance=importance,
            branch_id=branch_id,
        )

        self._choices.append(choice)

        # Apply immediate effects
        world_flags = self.state.setdefault("world_flags", {})
        for flag in choice.flags_set:
            world_flags[flag] = True
        for flag in choice.flags_cleared:
            world_flags.pop(flag, None)

        # Apply disposition changes
        npcs = self.state.get("npcs", {})
        for npc_id, delta in choice.disposition_changes.items():
            if npc_id in npcs:
                npc = npcs[npc_id]
                current = npc.get("disposition_value", 0)
                new_val = max(-100, min(100, current + delta))
                npc["disposition_value"] = new_val
                # Update disposition label
                if new_val <= -40:
                    npc["disposition"] = "hostile"
                elif new_val <= -10:
                    npc["disposition"] = "wary"
                elif new_val <= 10:
                    npc["disposition"] = "neutral"
                elif new_val <= 40:
                    npc["disposition"] = "friendly"
                else:
                    npc["disposition"] = "allied"

        self.save()
        return choice

    def add_consequence(
        self,
        trigger_flag: str,
        description: str,
        effect_type: str = "narrative",
        effect_data: Optional[dict] = None,
    ) -> Consequence:
        """
        Register a delayed consequence that fires when a flag is set.
        """
        cons = Consequence(
            consequence_id=f"cons_{len(self._consequences) + 1}",
            trigger_flag=trigger_flag,
            description=description,
            effect_type=effect_type,
            effect_data=effect_data or {},
        )
        self._consequences.append(cons)
        self.save()
        return cons

    # -- Resolve Consequences ------------------------------------------------

    def check_consequences(self) -> list[Consequence]:
        """
        Check all pending consequences and fire any whose trigger flag is set.
        Returns list of fired consequences.
        """
        world_flags = self.state.get("world_flags", {})
        fired = []

        for cons in self._consequences:
            if cons.fired:
                continue
            if world_flags.get(cons.trigger_flag, False):
                cons.fired = True
                cons.fired_at = datetime.now().isoformat()
                fired.append(cons)

                # Apply effect
                self._apply_consequence_effect(cons)

        if fired:
            self.save()
        return fired

    def _apply_consequence_effect(self, cons: Consequence) -> None:
        """Apply the effect of a fired consequence."""
        if cons.effect_type == "flag_set":
            flag = cons.effect_data.get("flag", "")
            if flag:
                self.state.setdefault("world_flags", {})[flag] = True

        elif cons.effect_type == "npc_disposition":
            npc_id = cons.effect_data.get("npc_id", "")
            delta = cons.effect_data.get("delta", 0)
            if npc_id:
                npcs = self.state.get("npcs", {})
                if npc_id in npcs:
                    npc = npcs[npc_id]
                    current = npc.get("disposition_value", 0)
                    npc["disposition_value"] = max(-100, min(100, current + delta))

        elif cons.effect_type == "narrative":
            # Just flag it for the narrative generator
            self.state.setdefault("world_flags", {})[
                f"consequence_{cons.consequence_id}"] = True

    # -- Query Choices -------------------------------------------------------

    def get_recent_choices(self, count: int = 5) -> list[Choice]:
        """Get most recent choices."""
        return self._choices[-count:]

    def get_choices_by_category(self, category: str) -> list[Choice]:
        """Get all choices in a category."""
        return [c for c in self._choices if c.category == category]

    def get_important_choices(self, min_importance: int = 3) -> list[Choice]:
        """Get all important choices."""
        return [c for c in self._choices if c.importance >= min_importance]

    def get_active_threads(self) -> list[str]:
        """Get all narrative threads that are currently active."""
        threads = set()
        for choice in self._choices:
            threads.update(choice.narrative_threads)
        return sorted(threads)

    def has_choice_been_made(self, description_keyword: str) -> bool:
        """Check if a specific choice was already made (by keyword match)."""
        keyword = description_keyword.lower()
        return any(keyword in c.description.lower() or keyword in c.chosen.lower()
                   for c in self._choices)

    def get_choice_by_id(self, choice_id: str) -> Optional[Choice]:
        """Get a specific choice by its ID."""
        for c in self._choices:
            if c.choice_id == choice_id:
                return c
        return None

    # -- Narrative Context ---------------------------------------------------

    def get_narrative_context(self, max_choices: int = 10) -> str:
        """
        Generate narrative context for the LLM.
        Includes recent choices, active threads, and pending consequences.
        """
        lines = ["## Player Choices Context"]

        # Recent choices
        recent = self.get_recent_choices(max_choices)
        if recent:
            lines.append("\nRecent decisions:")
            for c in recent:
                icon = {
                    CATEGORY_MORAL: "\U0001f3af",
                    CATEGORY_TACTICAL: "\u2699\ufe0f",
                    CATEGORY_SOCIAL: "\U0001f91d",
                    CATEGORY_EXPLORATION: "\U0001f5fa\ufe0f",
                    CATEGORY_QUEST: "\U0001f4dc",
                    CATEGORY_COMBAT: "\u2694\ufe0f",
                    CATEGORY_CHARACTER: "\U0001f3ad",
                }.get(c.category, "\U0001f4dd")
                lines.append(f"  {icon} [{c.category}] {c.description}")
                lines.append(f"     Chose: **{c.chosen}**")

        # Active threads
        threads = self.get_active_threads()
        if threads:
            lines.append(f"\nActive story threads: {', '.join(threads)}")

        # Pending consequences
        pending = [c for c in self._consequences if not c.fired]
        if pending:
            lines.append(f"\nPending consequences: {len(pending)}")
            for c in pending[:3]:
                lines.append(f"  - {c.description} (triggered by: {c.trigger_flag})")

        # Important choices summary
        important = self.get_important_choices()
        if important:
            lines.append(f"\nKey decisions ({len(important)}):")
            for c in important[-3:]:
                lines.append(f"  **{c.description}** -> {c.chosen}")

        return "\n".join(lines)

    def get_choice_display(self) -> str:
        """Format choices for player-facing display."""
        if not self._choices:
            return "No significant choices have been made yet."

        lines = ["\U0001f333 **Decision Tree**"]
        lines.append("_Your choices shape the world around you._\n")

        by_category: dict[str, list] = {}
        for c in self._choices:
            by_category.setdefault(c.category, []).append(c)

        icons = {
            CATEGORY_MORAL: "\U0001f3af",
            CATEGORY_TACTICAL: "\u2699\ufe0f",
            CATEGORY_SOCIAL: "\U0001f91d",
            CATEGORY_EXPLORATION: "\U0001f5fa\ufe0f",
            CATEGORY_QUEST: "\U0001f4dc",
            CATEGORY_COMBAT: "\u2694\ufe0f",
            CATEGORY_CHARACTER: "\U0001f3ad",
        }

        for cat, choices in by_category.items():
            icon = icons.get(cat, "\U0001f4dd")
            lines.append(f"**{icon} {cat.title()}**")
            for c in choices[-3:]:
                lines.append(f"  \u2022 {c.description}")
                lines.append(f"    \u2192 **{c.chosen}**")

        return "\n".join(lines)

    # -- Serialization -------------------------------------------------------

    def export_all(self) -> dict:
        return {
            "log": [c.to_dict() for c in self._choices],
            "consequences": [c.to_dict() for c in self._consequences],
        }

    def import_all(self, data: dict) -> None:
        self._choices = [Choice.from_dict(c) for c in data.get("log", [])]
        self._consequences = [Consequence.from_dict(c) for c in data.get("consequences", [])]
        self.save()
