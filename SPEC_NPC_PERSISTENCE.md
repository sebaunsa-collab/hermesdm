# SPEC — NPC Persistence

## Context

Currently NPCs exist only in the `world_builder.py` module's state — they are generated per-session but not saved to the campaign state file. If the bot restarts, all NPC memory is lost.

## Objetivo

NPCs persisten en campaign state entre sesiones. El DM puede crear, consultar y actualizar NPCs que sobreviven a reinicios.

## Modelo de Datos

### NPCRecord (new file: `state/npc_store.py`)

```python
@dataclass
class NPCRecord:
    """Persistent NPC record."""
    id: str
    name: str
    description: str
    location: str
    role: str                    # "shopkeeper", "quest_giver", "villain", "ally"
    mood: str                    # "friendly", "hostile", "neutral", "scared"
    disposition: str             # "friendly", "indifferent", "hostile"
    notes: list[str]             # DM notes about the NPC
    memory: list[str]            # Things the NPC "remembers" (important events)
    secrets: list[str]           # Hidden information (DM only)
    tags: list[str]              # For searching: ["merchant", "elf", "corrupt"]
    created_at: int              # Unix timestamp
    updated_at: int              # Unix timestamp
    genre: str                   # Campaign genre (for prompt building)
    
    def add_memory(self, event: str) -> None:
        """Record an event the NPC witnessed or was involved in."""
        self.memory.append(event)
        self.updated_at = int(time.time())
    
    def add_note(self, note: str) -> None:
        self.notes.append(note)
        self.updated_at = int(time.time())
```

## NPC Store (npc_store.py)

```python
class NPCStore:
    """Manages persistent NPCs for a campaign."""
    
    def __init__(self, state: dict):
        self.state = state
        if "npcs" not in state:
            state["npcs"] = {}
    
    def create(self, name: str, genre: str, role: str = "neutral",
               description: str = "", location: str = "") -> NPCRecord:
        npc = NPCRecord(
            id=str(uuid.uuid4())[:8],
            name=name,
            description=description or f"{name} is a mysterious figure.",
            location=location,
            role=role,
            mood="neutral",
            disposition="indifferent",
            notes=[],
            memory=[],
            secrets=[],
            tags=[],
            created_at=int(time.time()),
            updated_at=int(time.time()),
            genre=genre,
        )
        self.state["npcs"][npc.id] = asdict(npc)
        return npc
    
    def get(self, identifier: str) -> NPCRecord | None:
        """Find NPC by name (partial match) or ID."""
        # Try exact ID first
        if identifier in self.state["npcs"]:
            return NPCRecord(**self.state["npcs"][identifier])
        # Try name match (case-insensitive, partial)
        for npc_dict in self.state["npcs"].values():
            if identifier.lower() in npc_dict["name"].lower():
                return NPCRecord(**npc_dict)
        return None
    
    def list_all(self) -> list[NPCRecord]:
        return [NPCRecord(**n) for n in self.state["npcs"].values()]
    
    def update(self, npc_id: str, **kwargs) -> NPCRecord | None:
        """Update NPC fields. Returns updated record or None."""
        if npc_id not in self.state["npcs"]:
            return None
        for key, val in kwargs.items():
            if key in ("id", "created_at"):
                continue  # immutable
            self.state["npcs"][npc_id][key] = val
        self.state["npcs"][npc_id]["updated_at"] = int(time.time())
        return NPCRecord(**self.state["npcs"][npc_id])
    
    def delete(self, npc_id: str) -> bool:
        return bool(self.state["npcs"].pop(npc_id, None))
    
    def search(self, query: str) -> list[NPCRecord]:
        """Search by name, role, tags, or location."""
        q = query.lower()
        return [
            NPCRecord(**n) for n in self.state["npcs"].values()
            if q in n["name"].lower()
            or q in n["role"].lower()
            or q in n["location"].lower()
            or any(q in tag.lower() for tag in n["tags"])
        ]
```

## State Structure

```json
{
  "campaign_id": "...",
  "npcs": {
    "npc_abc123": {
      "id": "abc123",
      "name": "Grimbok the Forge",
      "description": "A scarred dwarven blacksmith...",
      "location": "Ironforge Tavern",
      "role": "quest_giver",
      "mood": "friendly",
      "disposition": "friendly",
      "notes": ["Knows about the old mine", "Owes money to the syndicate"],
      "memory": [
        "The party negotiated a discount on sword repairs",
        "Witnessed the dragon attack from the tavern window"
      ],
      "secrets": ["Has a map to the abandoned mine", "Is secretly a retired adventurer"],
      "tags": ["dwarf", "blacksmith", "ironforge", "quest"],
      "created_at": 1713000000,
      "updated_at": 1713050000,
      "genre": "fantasy"
    }
  }
}
```

## Integration with world_builder

The `WorldBuilder.generate_npc()` should check the NPCStore first:

```python
def get_or_create_npc(self, name: str) -> NPCRecord:
    """Get existing NPC or generate a new one."""
    existing = self.npc_store.get(name)
    if existing:
        return existing
    return self.world_builder.generate_npc(name)
```

## Command Changes

### `/npc <nombre>`
If NPC exists → show full record with memory timeline.
If NPC doesn't exist → trigger generation wizard (as before).

### `/npcs`
Shows all persisted NPCs with location and role.

### `/npcnote <nombre> <nota>`
DM adds a note to NPC's notes list.

### `/npcmemory <nombre> <evento>`
DM records an event in NPC's memory.

### `/npcdelete <nombre>`
DM removes NPC from campaign.

### `/npcsearch <query>`
Search NPCs by name/role/tags.

## Prompt Building from NPC Memory

When generating NPC dialogue or behavior, include relevant memories:

```
NPC: Grimbok the Forge (friendly dwarf blacksmith)
Memory:
- "The party negotiated a discount on sword repairs (Session 3)"
- "Witnessed the dragon attack from the tavern window (Session 5)"
```

## Tests

- NPC create → saved to state → survives round-trip (save + load)
- NPC update fields → persisted
- NPC delete → removed from state
- NPC search finds by name, role, tags
- Duplicate NPC name doesn't overwrite existing (creates new with same name)
- `get_or_create_npc` returns existing without regenerating

## Implementation Order

1. `NPCRecord` dataclass + `NPCStore` class in `state/npc_store.py`
2. Integrate `NPCStore` into `WorldBuilder.__init__`
3. `get_or_create_npc` method
4. Update `cmd_npc` in `telegram_handler.py` to use store
5. Add `/npcnote`, `/npcmemory`, `/npcdelete`, `/npcs`, `/npcsearch`
6. State round-trip test
7. Update `SPEC_NPC.md` (delete if exists, document in README)
