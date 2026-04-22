# SPEC — Death Saves Persistencia

## Context

Currently when a character drops to 0 HP, death saves are tracked in memory. If the campaign state is saved/restored (or the bot restarts mid-combat), death saves are lost.

## Objetivo

Death saves survive bot restarts y se guardan en campaign state.

## Changes to DeathSaves (character_sheet.py)

```python
@dataclass
class DeathSaves:
    successes: int = 0
    failures: int = 0

    def roll(self) -> tuple[bool, bool]:
        """Roll death save, update counters, return (is_success, is_dead)."""
        roll = random.randint(1, 20)
        if roll == 1:
            self.failures += 2
        elif roll == 20:
            self.successes += 3  # Instant stabilize + 1 HP
        elif roll >= 10:
            self.successes += 1
        else:
            self.failures += 1
        
        if self.failures >= 3:
            return False, True  # dead
        if self.successes >= 3:
            return True, False  # stabilized
        return False, False
    
    def reset(self) -> None:
        self.successes = 0
        self.failures = 0
```

The key addition: **no changes needed to DeathSaves dataclass itself** — it's already a dataclass that serializes fine. The fix is ensuring it persists in the campaign state JSON.

## State Persistence — characters dict

In `state/campaign_state.json`, characters already save. We just need to ensure `death_saves` field is included:

```json
{
  "characters": {
    "valdric": {
      "name": "Valdric",
      "hp": {"current": 0, "max": 11, "temp": 0},
      "death_saves": {"successes": 1, "failures": 1},
      ...
    }
  }
}
```

## Changes to Character HP modification

When HP goes to 0:
- Set `death_saves` (already exists as dataclass field)
- Character stays "alive" but unconscious

When HP goes above 0:
- Reset death saves

```python
def modify_hp(self, amount: int) -> None:
    self.hp.current = max(-self.max_hp_cap, min(self.hp.max, self.hp.current + amount))
    if self.hp.current > 0:
        self.death_saves.reset()  # Reset on stabilization
```

## Changes to cmd_deathsave

Output should clarify current death save state:

```
☠️ Valdric — UNCONSCIOUS
HP: 0/11 | Death Saves: ⬛⬛⬛ ✓✓✗✗ ✗✗✗✗
Rolled 13 → SUCCESS (+1) — now: ✓✓✗✗
```

Format: 3 boxes for successes (✓ filled), 3 boxes for failures (✗ filled), remaining empty.

## Command: `/deathsave <nombre> [exito/fallo/reset]`

```
/deathsave Valdric         → rolls death save
/deathsave Valdric exito   → adds 1 success  
/deathsave Valdric fallo   → adds 1 failure
/deathsave Valdric reset   → resets death saves to 0/0
```

## Tests

- Death saves serialize/deserialize correctly through state
- HP > 0 resets death saves
- Character at 0 HP with 3 failures → dead
- Character at 0 HP with nat 20 on death save → restored to 1 HP
- Character at 0 HP with nat 1 on death save → +2 failures

## Implementation Order

1. Add `death_saves.reset()` when HP goes above 0
2. Add `_hp` setter in `Character` that handles death save reset
3. Update `cmd_deathsave` output format
4. Test state save/load round-trip
5. Update `/char` display to show death save status
