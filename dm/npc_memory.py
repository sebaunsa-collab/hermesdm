"""
npc_memory.py — NPC Memory System for HermesDM.

NPCs remember past interactions with players. This creates continuity:
- NPCs reference past conversations
- Disposition shifts based on history
- NPCs can hold grudges or become loyal allies
- Story threads connect across sessions

Design: MemoryEngine tracks interactions as events with timestamps
and provides queries for "what does NPC X remember about player Y?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# -- Memory Types ------------------------------------------------------------

MEMORY_INTERACTION = "interaction"      # Player talked to NPC
MEMORY_COMBAT = "combat"                # Player fought near/with NPC
MEMORY_GIFT = "gift"                    # Player gave something
MEMORY_DEMAND = "demand"                # Player threatened/demanded
MEMORY_OBSERVATION = "observation"      # NPC witnessed player do something
MEMORY_QUEST = "quest"                  # Quest-related memory
MEMORY_TRADE = "trade"                  # Business transaction
MEMORY_PROMISE = "promise"              # Player made a promise
MEMORY_BETRAYAL = "betrayal"            # Player broke trust

# Positive memories increase disposition, negative decrease it
POSITIVE_MEMORIES = {MEMORY_GIFT, MEMORY_QUEST}
NEGATIVE_MEMORIES = {MEMORY_DEMAND, MEMORY_BETRAYAL}


# -- Data Classes ------------------------------------------------------------

@dataclass
class NPCMemory:
    """A single memory entry for an NPC."""
    memory_type: str
    description: str
    player_name: str
    timestamp: str = ""
    disposition_delta: int = 0  # how this memory affected disposition
    importance: int = 1         # 1-5, 5 = life-changing
    flags_set: list = field(default_factory=list)  # world flags this memory set
    resolved: bool = False      # has this memory been acted upon?

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "memory_type": self.memory_type,
            "description": self.description,
            "player_name": self.player_name,
            "timestamp": self.timestamp,
            "disposition_delta": self.disposition_delta,
            "importance": self.importance,
            "flags_set": self.flags_set,
            "resolved": self.resolved,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NPCMemory":
        return cls(
            memory_type=data.get("memory_type", "interaction"),
            description=data.get("description", ""),
            player_name=data.get("player_name", ""),
            timestamp=data.get("timestamp", ""),
            disposition_delta=data.get("disposition_delta", 0),
            importance=data.get("importance", 1),
            flags_set=data.get("flags_set", []),
            resolved=data.get("resolved", False),
        )


@dataclass
class NPCMemoryProfile:
    """
    Full memory profile for one NPC.
    Tracks ALL memories, relationship level, and behavioral flags.
    """
    npc_id: str
    npc_name: str
    memories: list[NPCMemory] = field(default_factory=list)
    disposition_value: int = 0  # -100 to +100
    trust_level: int = 0        # -10 to +10
    last_interaction: str = ""
    total_interactions: int = 0

    @property
    def disposition(self) -> str:
        if self.disposition_value <= -40:
            return "hostile"
        elif self.disposition_value <= -10:
            return "wary"
        elif self.disposition_value <= 10:
            return "neutral"
        elif self.disposition_value <= 40:
            return "friendly"
        else:
            return "allied"

    def add_memory(self, memory: NPCMemory) -> None:
        """Add a memory and adjust disposition."""
        self.memories.append(memory)
        self.disposition_value = max(-100, min(100,
            self.disposition_value + memory.disposition_delta))
        self.total_interactions += 1
        self.last_interaction = memory.timestamp

    def get_recent_memories(self, count: int = 5) -> list[NPCMemory]:
        """Get most recent memories."""
        return self.memories[-count:]

    def get_important_memories(self, min_importance: int = 3) -> list[NPCMemory]:
        """Get memories above importance threshold."""
        return [m for m in self.memories if m.importance >= min_importance]

    def get_memories_about(self, player_name: str) -> list[NPCMemory]:
        """Get all memories about a specific player."""
        return [m for m in self.memories if m.player_name == player_name]

    def get_unresolved_memories(self) -> list[NPCMemory]:
        """Get memories that haven't been acted upon."""
        return [m for m in self.memories if not m.resolved]

    def remember_for_dialogue(self, player_name: str, max_memories: int = 3) -> str:
        """
        Generate a dialogue-relevant memory summary.
        Used by LLM prompt to make NPCs reference past interactions.
        """
        relevant = self.get_memories_about(player_name)
        if not relevant:
            return ""

        recent = relevant[-max_memories:]
        lines = [f"Memories about {player_name}:"]
        for m in recent:
            lines.append(f"- [{m.memory_type}] {m.description}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "npc_id": self.npc_id,
            "npc_name": self.npc_name,
            "memories": [m.to_dict() for m in self.memories],
            "disposition_value": self.disposition_value,
            "trust_level": self.trust_level,
            "last_interaction": self.last_interaction,
            "total_interactions": self.total_interactions,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NPCMemoryProfile":
        return cls(
            npc_id=data.get("npc_id", ""),
            npc_name=data.get("npc_name", ""),
            memories=[NPCMemory.from_dict(m) for m in data.get("memories", [])],
            disposition_value=data.get("disposition_value", 0),
            trust_level=data.get("trust_level", 0),
            last_interaction=data.get("last_interaction", ""),
            total_interactions=data.get("total_interactions", 0),
        )


# -- Memory Engine -----------------------------------------------------------

class MemoryEngine:
    """
    Manages NPC memories across the game.

    Reads/writes state["npc_memories"] for persistence.
    """

    def __init__(self, state: dict) -> None:
        self.state = state
        self._profiles: dict[str, NPCMemoryProfile] = {}
        self._load()

    def _load(self) -> None:
        """Load all NPC memory profiles from state."""
        raw = self.state.get("npc_memories", {})
        for npc_id, data in raw.items():
            self._profiles[npc_id] = NPCMemoryProfile.from_dict(data)

    def save(self) -> None:
        """Persist all profiles to state."""
        self.state["npc_memories"] = {
            npc_id: profile.to_dict()
            for npc_id, profile in self._profiles.items()
        }

    def _get_or_create(self, npc_id: str, npc_name: str = "") -> NPCMemoryProfile:
        """Get or create a memory profile for an NPC."""
        if npc_id not in self._profiles:
            self._profiles[npc_id] = NPCMemoryProfile(
                npc_id=npc_id,
                npc_name=npc_name or npc_id,
            )
        return self._profiles[npc_id]

    # -- Record Memories -----------------------------------------------------

    def record_interaction(
        self, npc_id: str, npc_name: str, player_name: str,
        description: str, disposition_delta: int = 0,
        importance: int = 1, flags: Optional[list] = None,
    ) -> None:
        """Record a conversation or interaction."""
        profile = self._get_or_create(npc_id, npc_name)
        profile.add_memory(NPCMemory(
            memory_type=MEMORY_INTERACTION,
            description=description,
            player_name=player_name,
            disposition_delta=disposition_delta,
            importance=importance,
            flags_set=flags or [],
        ))
        self.save()

    def record_combat(
        self, npc_id: str, npc_name: str, player_name: str,
        description: str, disposition_delta: int = 0,
        importance: int = 2,
    ) -> None:
        """Record a combat-related event."""
        profile = self._get_or_create(npc_id, npc_name)
        profile.add_memory(NPCMemory(
            memory_type=MEMORY_COMBAT,
            description=description,
            player_name=player_name,
            disposition_delta=disposition_delta,
            importance=importance,
        ))
        self.save()

    def record_gift(
        self, npc_id: str, npc_name: str, player_name: str,
        description: str, disposition_delta: int = 10,
    ) -> None:
        """Record a gift or positive contribution."""
        profile = self._get_or_create(npc_id, npc_name)
        profile.add_memory(NPCMemory(
            memory_type=MEMORY_GIFT,
            description=description,
            player_name=player_name,
            disposition_delta=disposition_delta,
            importance=2,
        ))
        self.save()

    def record_demand(
        self, npc_id: str, npc_name: str, player_name: str,
        description: str, disposition_delta: int = -15,
    ) -> None:
        """Record a threat or demand."""
        profile = self._get_or_create(npc_id, npc_name)
        profile.add_memory(NPCMemory(
            memory_type=MEMORY_DEMAND,
            description=description,
            player_name=player_name,
            disposition_delta=disposition_delta,
            importance=3,
        ))
        self.save()

    def record_betrayal(
        self, npc_id: str, npc_name: str, player_name: str,
        description: str, disposition_delta: int = -30,
    ) -> None:
        """Record a betrayal of trust."""
        profile = self._get_or_create(npc_id, npc_name)
        profile.add_memory(NPCMemory(
            memory_type=MEMORY_BETRAYAL,
            description=description,
            player_name=player_name,
            disposition_delta=disposition_delta,
            importance=5,
        ))
        self.save()

    def record_promise(
        self, npc_id: str, npc_name: str, player_name: str,
        description: str, disposition_delta: int = 5,
    ) -> None:
        """Record a promise made by the player."""
        profile = self._get_or_create(npc_id, npc_name)
        profile.add_memory(NPCMemory(
            memory_type=MEMORY_PROMISE,
            description=description,
            player_name=player_name,
            disposition_delta=disposition_delta,
            importance=3,
        ))
        self.save()

    def record_observation(
        self, npc_id: str, npc_name: str, player_name: str,
        description: str, disposition_delta: int = 0,
        importance: int = 1,
    ) -> None:
        """Record an observation (NPC saw the player do something)."""
        profile = self._get_or_create(npc_id, npc_name)
        profile.add_memory(NPCMemory(
            memory_type=MEMORY_OBSERVATION,
            description=description,
            player_name=player_name,
            disposition_delta=disposition_delta,
            importance=importance,
        ))
        self.save()

    # -- Query Memories ------------------------------------------------------

    def get_profile(self, npc_id: str) -> Optional[NPCMemoryProfile]:
        """Get full memory profile for an NPC."""
        return self._profiles.get(npc_id)

    def get_disposition(self, npc_id: str) -> str:
        """Get NPC disposition based on memory."""
        profile = self._profiles.get(npc_id)
        if not profile:
            return "neutral"
        return profile.disposition

    def get_dialogue_context(self, npc_id: str, npc_name: str,
                              player_name: str) -> str:
        """
        Generate context for LLM dialogue prompt.
        Includes: disposition, trust, relevant memories.
        """
        profile = self._get_or_create(npc_id, npc_name)

        lines = [
            f"NPC: {profile.npc_name}",
            f"Disposition: {profile.disposition} ({profile.disposition_value:+d})",
            f"Trust: {profile.trust_level:+d}",
            f"Total interactions: {profile.total_interactions}",
        ]

        if profile.last_interaction:
            lines.append(f"Last interaction: {profile.last_interaction}")

        # Recent memories
        memory_text = profile.remember_for_dialogue(player_name)
        if memory_text:
            lines.append(f"\n{memory_text}")

        # Unresolved memories
        unresolved = profile.get_unresolved_memories()
        if unresolved:
            lines.append("\nUnresolved matters:")
            for m in unresolved[-3:]:
                lines.append(f"  - [{m.memory_type}] {m.description}")

        return "\n".join(lines)

    def get_npc_memory_display(self, npc_id: str) -> str:
        """Format NPC memories for player-facing display."""
        profile = self._profiles.get(npc_id)
        if not profile:
            return "No memories recorded for this NPC."

        lines = [f"🧠 **{profile.npc_name}'s Memory**"]
        lines.append(f"Disposition: {profile.disposition} ({profile.disposition_value:+d})")
        lines.append(f"Interactions: {profile.total_interactions}\n")

        if not profile.memories:
            lines.append("No specific memories recorded.")
            return "\n".join(lines)

        # Group by type
        by_type: dict[str, list] = {}
        for m in profile.memories:
            by_type.setdefault(m.memory_type, []).append(m)

        type_icons = {
            MEMORY_INTERACTION: "\U0001f4ac",
            MEMORY_COMBAT: "\u2694\ufe0f",
            MEMORY_GIFT: "\U0001f381",
            MEMORY_DEMAND: "\U0001f4a3",
            MEMORY_OBSERVATION: "\U0001f441\ufe0f",
            MEMORY_QUEST: "\U0001f4dc",
            MEMORY_TRADE: "\U0001f4b0",
            MEMORY_PROMISE: "\U0001f91d",
            MEMORY_BETRAYAL: "\U0001f525",
        }

        for mem_type, memories in by_type.items():
            icon = type_icons.get(mem_type, "\U0001f4dd")
            lines.append(f"**{icon} {mem_type.title()}:**")
            for m in memories[-3:]:  # Show last 3 of each type
                delta = f" ({m.disposition_delta:+d})" if m.disposition_delta != 0 else ""
                lines.append(f"  \u2022 {m.description}{delta}")

        return "\n".join(lines)

    # -- Batch Operations ----------------------------------------------------

    def adjust_all_dispositions(self, npc_id: str, delta: int) -> None:
        """Adjust disposition for an NPC (e.g., faction-wide change)."""
        profile = self._profiles.get(npc_id)
        if profile:
            profile.disposition_value = max(-100, min(100,
                profile.disposition_value + delta))
            self.save()

    def clear_old_memories(self, max_per_type: int = 10) -> int:
        """Prune old memories, keeping only the most recent N per type.
        Returns number of memories pruned.
        """
        pruned = 0
        for profile in self._profiles.values():
            by_type: dict[str, list] = {}
            for m in profile.memories:
                by_type.setdefault(m.memory_type, []).append(m)

            new_memories = []
            for mem_type, memories in by_type.items():
                # Keep most recent N, plus all important ones
                important = [m for m in memories if m.importance >= 4]
                recent = memories[-max_per_type:]
                kept = list({id(m): m for m in important + recent}.values())
                pruned += len(memories) - len(kept)
                new_memories.extend(kept)

            profile.memories = sorted(new_memories,
                key=lambda m: m.timestamp, reverse=True)

        if pruned > 0:
            self.save()
        return pruned

    def export_all(self) -> dict:
        """Export all profiles as serializable dict."""
        return {
            npc_id: profile.to_dict()
            for npc_id, profile in self._profiles.items()
        }

    def import_all(self, data: dict) -> None:
        """Import profiles from serialized dict."""
        for npc_id, profile_data in data.items():
            self._profiles[npc_id] = NPCMemoryProfile.from_dict(profile_data)
        self.save()
