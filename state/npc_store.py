"""
state/npc_store.py — NPC Persistence Layer.

NPCs survive bot restarts and are stored in the campaign state file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NPCMemory:
    """A single memory/knowledge entry about an NPC."""
    key: str       # e.g. "secret_weakness", "relationship_player_Valdric"
    value: str
    added_by: str  # player name or "DM"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "added_by": self.added_by,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> NPCMemory:
        return cls(
            key=d["key"],
            value=d["value"],
            added_by=d.get("added_by", "DM"),
            timestamp=d.get("timestamp", datetime.now().isoformat()),
        )


@dataclass
class NPCRecord:
    """
    A persistent NPC that survives restarts.
    """
    npc_id: str           # unique ID (stable across restarts)
    name: str             # display name
    title: str            # "Innkeeper", "Guild Master", etc.
    description: str     # physical appearance
    personality: str      # personality traits
    motivation: str       # what they want
    secret: str | None    # hidden agenda/secret
    location: str         # current location in the world
    memory: list[NPCMemory] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)  # "merchant", "quest_giver", "criminal"
    mood: str = "neutral"  # current disposition
    disposition: str = "indifferent"  # vs players: friendly/hostile/indifferent
    notes: str = ""       # free-form DM notes

    def add_memory(self, key: str, value: str, added_by: str = "DM") -> None:
        # Update existing or add new
        for m in self.memory:
            if m.key == key:
                m.value = value
                m.timestamp = datetime.now().isoformat()
                return
        self.memory.append(NPCMemory(key=key, value=value, added_by=added_by))

    def get_memory(self, key: str) -> str | None:
        for m in self.memory:
            if m.key == key:
                return m.value
        return None

    def format_memory(self) -> str:
        if not self.memory:
            return "_No memories recorded._"
        lines = []
        for m in self.memory:
            lines.append(f"  • **{m.key}**: {m.value} _(by {m.added_by})_")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "npc_id": self.npc_id,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "personality": self.personality,
            "motivation": self.motivation,
            "secret": self.secret,
            "location": self.location,
            "memory": [m.to_dict() for m in self.memory],
            "tags": self.tags,
            "mood": self.mood,
            "disposition": self.disposition,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> NPCRecord:
        return cls(
            npc_id=d["npc_id"],
            name=d["name"],
            title=d.get("title", ""),
            description=d.get("description", ""),
            personality=d.get("personality", ""),
            motivation=d.get("motivation", ""),
            secret=d.get("secret"),
            location=d.get("location", "Unknown"),
            memory=[NPCMemory.from_dict(m) for m in d.get("memory", [])],
            tags=d.get("tags", []),
            mood=d.get("mood", "neutral"),
            disposition=d.get("disposition", "indifferent"),
            notes=d.get("notes", ""),
        )


class NPCStore:
    """
    Manages all persistent NPCs for a campaign.
    Lives in campaign state; survives bot restarts.
    """

    def __init__(self):
        self.npcs: dict[str, NPCRecord] = {}

    def add(self, npc: NPCRecord) -> str:
        """Add or replace an NPC. Returns the npc_id."""
        self.npcs[npc.npc_id] = npc
        return npc.npc_id

    def get(self, npc_id: str) -> NPCRecord | None:
        return self.npcs.get(npc_id)

    def find_by_name(self, name: str) -> NPCRecord | None:
        name_lower = name.lower()
        for npc in self.npcs.values():
            if npc.name.lower() == name_lower:
                return npc
        return None

    def find_by_location(self, location: str) -> list[NPCRecord]:
        loc_lower = location.lower()
        return [n for n in self.npcs.values() if n.location.lower() == loc_lower]

    def find_by_tag(self, tag: str) -> list[NPCRecord]:
        tag_lower = tag.lower()
        return [n for n in self.npcs.values() if tag_lower in [t.lower() for t in n.tags]]

    def search(self, query: str) -> list[NPCRecord]:
        """Full-text search across name, title, description, personality, notes."""
        q = query.lower()
        results = []
        for npc in self.npcs.values():
            score = 0
            if q in npc.name.lower():
                score += 10
            if q in npc.title.lower():
                score += 5
            if q in npc.description.lower():
                score += 3
            if q in npc.personality.lower():
                score += 2
            if q in npc.notes.lower():
                score += 1
            if npc.secret and q in npc.secret.lower():
                score += 4
            if score > 0:
                results.append((score, npc))
        results.sort(key=lambda x: -x[0])
        return [n for _, n in results]

    def remove(self, npc_id: str) -> bool:
        return bool(self.npcs.pop(npc_id, None))

    def to_dict(self) -> dict:
        return {npc_id: npc.to_dict() for npc_id, npc in self.npcs.items()}

    @classmethod
    def from_dict(cls, d: dict) -> NPCStore:
        store = cls()
        for npc_id, npc_data in d.items():
            store.npcs[npc_id] = NPCRecord.from_dict(npc_data)
        return store

    def format_all(self) -> str:
        if not self.npcs:
            return "_No NPCs in this world yet._"
        lines = []
        for npc in sorted(self.npcs.values(), key=lambda n: n.location):
            tag_str = ", ".join(f"#{t}" for t in npc.tags) if npc.tags else ""
            lines.append(f"**{npc.name}** — {npc.title} @ {npc.location} {tag_str}")
            lines.append(f"  _{npc.personality[:80]}_")
        return "\n".join(lines)

    def format_npc(self, npc_id: str) -> str:
        npc = self.get(npc_id)
        if not npc:
            return "_NPC not found._"
        tag_str = " ".join(f"#{t}" for t in npc.tags) if npc.tags else ""
        lines = [
            f"**{npc.name}** — {npc.title} {tag_str}",
            f"📍 {npc.location} | 😐 {npc.mood} | ⚖️ {npc.disposition}",
            f"\n_{npc.description}_",
        ]
        if npc.personality:
            lines.append(f"\n**Personalidad**: {npc.personality}")
        if npc.motivation:
            lines.append(f"**Motivación**: {npc.motivation}")
        if npc.secret:
            lines.append(f"**Secreto**: {npc.secret}")
        if npc.notes:
            lines.append(f"**Notas DM**: {npc.notes}")
        mem = self.format_npc_memory(npc_id)
        if mem != "_No memories recorded._":
            lines.append("\n**Memoria**:")
            lines.append(mem)
        return "\n".join(lines)

    def format_npc_memory(self, npc_id: str) -> str:
        npc = self.get(npc_id)
        if not npc:
            return "_NPC not found._"
        return npc.format_memory()
