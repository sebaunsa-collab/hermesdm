# SPEC — Spell Slots (D&D 5e)

## Context

Currently spellcasting in HermesDM has no slots — a spell always works regardless of class level. This is the bare minimum needed to feel like D&D magic.

## Objetivo

Implement spell slots por nivel de personaje. Spellcasters知道她有多少 slots disponibles.

## Modelo de Datos

### SpellSlotTrack (character_sheet.py)

```python
@dataclass
class SpellSlotTrack:
    """Tracks used spell slots per spell level (1-9)."""
    total: list[int] = field(default_factory=lambda: [0]*9)
    used: list[int] = field(default_factory=lambda: [0]*9)

    def available(self, level: int) -> int:
        return self.total[level-1] - self.used[level-1]
    
    def use(self, level: int) -> bool:
        if self.available(level) <= 0:
            return False
        self.used[level-1] += 1
        return True

    def restore_all(self) -> None:
        self.used = [0]*9
```

### SPELL_SLOTS_BY_CLASS (character_sheet.py)

```python
# Spell slots per long rest (D&D 5e PHB)
SPELL_SLOTS_BY_CLASS: dict[str, dict[int, int]] = {
    # wizard: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1}
    # warlock: pact slots (handled separately)
    # full caster (wizard, cleric): 4/3/3/3/3/2/2/2/1
    # half caster (paladin, ranger): 4/3/3/3/2 (derived: levels 1-9 map to 4/3/3/3/2/2/2/1/1)
}
```

## SPELL_SLOTS_BY_CLASS

```python
# D&D 5e PHB spell slots per spell level by class type
# {spell_level: slots_at_max_level}
# Full caster: wizard, cleric, druid, sorcerer, bard, paladin (aura), ranger
# Half caster: paladin, ranger → fewer high-level slots
# Warlock: handled separately (pact magic, always max slots)

SPELL_SLOTS_FULL: dict[int, int] = {
    1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1
}
SPELL_SLOTS_HALF: dict[int, int] = {
    1: 4, 2: 3, 3: 3, 4: 2, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1
}

SPELL_SLOTS_BY_CLASS: dict[str, dict[int, int]] = {
    # Full casters
    "wizard": SPELL_SLOTS_FULL,
    "cleric": SPELL_SLOTS_FULL,
    "druid": SPELL_SLOTS_FULL,
    "sorcerer": SPELL_SLOTS_FULL,
    "bard": SPELL_SLOTS_FULL,
    "paladin": SPELL_SLOTS_HALF,   # half caster
    "ranger": SPELL_SLOTS_HALF,     # half caster
    # Warlock (pact magic — separate system)
    "warlock": {1: 1, 2: 1, 3: 1, 4: 1},  # all slots = max level, regenerates on short rest
}
```

## Level-Up Recalculation

When a character levels up:
1. Look up the class's spell slot table for the new character level
2. For spellcasters, update `spell_slots.total` for all levels

```python
def _recalculate_spell_slots(char: Character) -> dict:
    """Return dict of {level: new_total} for spell slot changes."""
    cls = char.player_class
    if cls not in SPELL_SLOTS_BY_CLASS:
        return {}
    table = SPELL_SLOTS_BY_CLASS[cls]
    changes = {}
    for spell_lvl, slots in table.items():
        char.spell_slots.total[spell_lvl-1] = slots
        changes[spell_lvl] = slots
    return changes
```

## Changes to Character Dataclass

Add to `Character`:
```python
spell_slots: SpellSlotTrack = field(default_factory=SpellSlotTrack)
```

## Changes to Spell Casting

In `spell_manager.py` and `/cast` command:
1. Check if spell level > 0
2. If spellcaster: require slot, use it
3. If non-spellcaster or no slots left: error message

```python
def cast_spell(char: Character, spell_name: str, target: str = "") -> str:
    spell = SPELLS.get(spell_name)
    if not spell:
        return f"Unknown spell: {spell_name}"
    
    level = spell["level"]
    if level > 0:  # cantrips have level 0
        if not char.spell_slots.use(level):
            return f"{char.name} has no level {level} spell slots remaining."
```

## Command Changes

`/cast <spell> [target]` now shows remaining slots:
```
🔥 Casts *Fireball* (Lv3) at the goblin — [2/3 Lv3 slots remaining]
```

New command `/slots` or `/spellslots`:
```
⚡ Spell Slots — Miral (Wizard Lv5)
Lv1: 4/4  Lv2: 3/3  Lv3: 3/3  Lv4: 0/3  Lv5: 0/3
```

## State Persistence

Spell slots save/load with character state.

## Tests

- Level 1 wizard starts with 4/4/3/3/3 Lv1-5 slots
- Casting a Lv3 spell uses 1 Lv3 slot
- `/rest long` restores all slots
- Non-spellcasters (fighter, rogue, barbarian) have no slots
- Warlock regenerates slots on short rest

## Implementation Order

1. `SpellSlotTrack` dataclass in `character_sheet.py`
2. `SPELL_SLOTS_BY_CLASS` dict
3. Add `spell_slots` to `Character` dataclass
4. `_recalculate_spell_slots()` in `level_up()`
5. Update `spell_manager.py` to check/use slots
6. Update `/cast` command output to show slots
7. Add `/slots` command
8. State persistence (SpellSlotTrack must be serializable)
9. Tests
