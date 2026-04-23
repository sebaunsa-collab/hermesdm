---
name: dnd-spell-slots-impl
description: Correct implementation of D&D 5e spell slots — per-character-level lookup tables, warlock pact magic, con_mod bug, and HP dataclass from_dict pitfall. Reference for HermesDM.
tags:
  - d&d
  - d&d-5e
  - spell-slots
  - gaming
required_environment_variables: []
required_commands: []
setup_needed: false
---

# D&D 5e Spell Slots — Correct Implementation

## The Core Problem

Naive approach: `{spell_level: slots}` dict where keys are spell levels 1-9. **WRONG** — iterating and assigning `total[spell_lvl-1] = total` overwrites all previous slots.

## Correct Approach: Per-Level Lookup Table

Use a `dict[spell_level, list[int]]` where the list index = character_level - 1.

```python
# {spell_level: [slots_at_Lv1, Lv2, Lv3, ...Lv20]}
_SPELL_SLOTS_PROGRESSION: dict[int, list[int]] = {
    1: [2, 3, 4, 4, 4, 4, 4, 4, 4, 4, ...],  # Lv1 char=2, Lv2=3, Lv3=4...
    2: [0, 0, 2, 3, 3, 3, 3, 3, 3, 3, ...],  # No Lv2 slots until Lv3
    3: [0, 0, 0, 0, 2, 3, 3, 3, 3, 3, ...],  # No Lv3 until Lv5
    4: [0, 0, 0, 0, 0, 0, 1, 2, 2, 2, ...],  # No Lv4 until Lv7
    5: [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, ...],  # No Lv5 until Lv9
    6: [0] * 20,  # No Lv6-9 spells for full casters
    7: [0] * 20,
    8: [0] * 20,
    9: [0] * 20,
}
```

Half caster (paladin/ranger): spellcasting_level = char_level // 2.

Warlock: Pact Magic — character_level determines (slot_count, slot_level).

## Key Gotchas

### HP.short_rest() con_mod Bug

`HP` dataclass has no `con_mod` attribute. `Character.short_rest()` must compute con_mod and pass it:

```python
def short_rest(self) -> dict:
    con_mod = self.stats.get("con", 10) // 2 - 5
    recovered = self.hp.short_rest(con_mod)  # pass con_mod!
```

NOT `self.hp.short_rest()` — that references `self.con_mod` which doesn't exist on HP.

### HP Dataclass in from_dict

When reconstructing Character from dict, `hp_data` is already a dict with the HP fields. Using `HP(**hp_data)` bypasses `__post_init__`. Create HP via constructor:

```python
hp_data = data.get("hp", {})
hp = HP(
    max=hp_data.get("max", 10),
    current=hp_data.get("current", hp_data.get("max", 10)),
    temp=hp_data.get("temp", 0),
    hit_die_faces=hp_data.get("hit_die_faces", 8),
    hit_dice_remaining=hp_data.get("hit_dice_remaining", 0),
)
```

### Spell Slot Retrieval

```python
def _get_spell_slots_for_level(caster_type: str, char_level: int) -> list[int]:
    idx = max(1, min(char_level, 20)) - 1  # 0-indexed
    progression = _SPELL_SLOTS_HALF_PROGRESSION if caster_type in ("paladin", "ranger") else _SPELL_SLOTS_PROGRESSION
    result = [0] * 9
    for spell_lvl in range(1, 10):
        row = progression.get(spell_lvl, [0] * 20)
        if idx < len(row):
            result[spell_lvl - 1] = row[idx]
    return result
```

## Test Assertions (verified against PHB)

| Character | Expected Spell Slots |
|-----------|---------------------|
| Wizard Lv1 | Lv1: 2/2 |
| Wizard Lv3 | Lv1: 4/4 \| Lv2: 2/2 (NOT Lv3 yet — Lv3 spells at Lv5) |
| Wizard Lv5 | Lv1: 4/4 \| Lv2: 3/3 \| Lv3: 2/2 |
| Wizard Lv7 | Lv1: 4/4 \| Lv2: 3/3 \| Lv3: 3/3 \| Lv4: 1/1 |
| Wizard Lv10 | Lv1: 4/4 \| Lv2: 3/3 \| Lv3: 3/3 \| Lv4: 2/2 \| Lv5: 1/1 |
| Warlock Lv5 | Lv2: 3/3 (3 pact slots, spell level 2) |
| Warlock Lv11 | Lv4: 4/4 |
| Paladin Lv5 | Lv1: 2/2 \| Lv2: 2/2 (spellcasting level = 2) |
| Paladin Lv9 | Lv1: 4/4 \| Lv2: 3/3 \| Lv3: 2/2 (spellcasting level = 4) |

## Python 3.10 Compatibility

- **No `\n` inside f-string `{}`** — valid syntax in Python 3.12+, syntax error on 3.10
  - Use `chr(10)` instead: `f"{'hi'}{chr(10)}text"`
  - Ruff rule: `F-invalid-escape-sequence` (syntax error, not auto-fixable)
- **Forward references** — use `TYPE_CHECKING` guard for imports only needed for type hints:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from state.npc_store import NPCStore  # Only for type hints, not runtime
  ```

## Flaky Tests from Global RNG State

If a test passes in isolation but fails in the full suite, the Python `random` module may be in a depleted state from prior test calls. Fix by seeding:

```python
def test_modifier_applied_correctly(self):
    import random
    random.seed(0x5EED)  # Deterministic regardless of test execution order
    # ... rest of test
```

## Spell Slot Track Usage

```python
char.spell_slots.use(3)        # consume 1 slot Lv3 → bool
char.spell_slots.available(3)   # cuántos Lv3 quedan → int
char.spell_slots.format_all()  # string "[Lv1 4/4] [Lv2 3/3] [Lv3 2/3]"
char.spell_slots.long_rest()    # recupera todos los slots
char.spell_slots.short_rest()   # warlock: recupera pact slot
```

## Constants

```
SPELL_SLOTS_FULL  = {1:4, 2:3, 3:3, 4:3, 5:3, 6:2, 7:2, 8:1, 9:1}  # Wizard/Cleric/Druid/Sorcerer/Bard
SPELL_SLOTS_HALF  = {1:4, 2:3, 3:3, 4:2, 5:2, 6:1, 7:1, 8:1, 9:1}  # Paladin/Ranger
SPELL_SLOTS_WARLOCK = {1:1, 2:1, 3:1, 4:1, 5:1}  # Pact Magic — short rest regen
```
