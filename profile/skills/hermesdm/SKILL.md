---
name: hermesdm
description: HermesDM — AI Dungeon Master for D&D 5e via Telegram. Bundled with the HermesDM profile.
tags:
  - d&d
  - d&d-5e
  - dungeon-master
  - telegram
  - game
required_environment_variables:
  - TELEGRAM_BOT_TOKEN
required_commands: []
setup_needed: true
---

# HermesDM — AI Dungeon Master

HermesDM is a complete D&D 5e game engine that runs on Telegram. No apps, no external tools — just a Telegram group and your imagination.

## Quick Reference

```
/create Valdric Wizard     → Create character
/j attack dragon          → Combat action
/cast fireball goblins    → Cast spell
/npc Eldara               → Create/query NPC
/roll 2d6+3              → Roll dice
/combat                   → View combat status
/rest                     → Long rest
/settings                 → Configure difficulty, genre, image provider
```

## Architecture

```
HermesDM runs as a Hermes Agent profile (dm/).
The Telegram bot is managed by Hermes Gateway.
All game state (characters, NPCs, combat) persists between sessions.
```

## Module Reference

| Module | Function | Use |
|--------|----------|-----|
| `bot.dice_engine` | `roll("XdY+Z")` | Dice rolls |
| `bot.dice_engine` | `resolve_check(roll, dc, advantage, disadvantage)` | Check vs DC |
| `bot.combat_engine` | `resolve_attack(attacker, defender, attack_roll, weapon, advantage, disadvantage, defender_ac, rage_bonus)` | Melee/ranged attack |
| `bot.combat_engine` | `resolve_spell(spell_name, spell_roll, target_dc)` | Spell attack |
| `bot.combat_engine` | `apply_damage(target_hp, damage)` | Apply damage |
| `bot.combat_engine` | `WEAPON_DAMAGE` | Weapon → dice mapping |
| `bot.turn_manager` | `start_combat(participants)` | Start combat, roll initiative |
| `bot.turn_manager` | `next_turn(state)` | Advance turn |
| `bot.turn_manager` | `combat_summary(state)` | Combat status text |
| `bot.character_sheet` | `create_character(name, class, level)` | Create character |
| `bot.character_sheet` | `get_character(name)` | Get character sheet |
| `bot.spell_manager` | `cast_spell(character, spell_name, target)` | Cast spell |
| `bot.spell_manager` | `get_spell_slots(character)` | Get spell slots |
| `state.state_manager` | `load_state()` | Load campaign state |
| `state.state_manager` | `save_state(state)` | Save campaign state |

## Example Usage

```python
from bot.dice_engine import roll

result = roll('1d20')
# result['total']       → final number
# result['rolls']       → [19] (individual values)
# result['modifier']    → 0
# result['is_crit']     → True (nat 20)
# result['is_fumble']   → True (nat 1)
# result['notation']     → "1d20"
```

## Response Format

**Dice rolls:**
```
🎲 [2d6+3]
Total: 11
Rolls: [4, 3]
+3 modifier
💥 Nat 20! (critical!)
```

**Character sheet:**
```
⚔️ Valdric — Level 3 Wizard
HP: 18/24  AC: 13  XP: 1500/3000 [████░░░░░░] 50%
Slots: 1st [4/4]  2nd [3/3]  3rd [1/3]
Conditions: None
```

## State Files

- Campaign state: `~/.hermes/hermesdm_state.json`
- NPC store: `~/.hermes/npc_store.json`
- Audit logs: `~/.hermes/hermesdm/audit_*.jsonl`

## Image Generation

Images are generated automatically at dramatic moments:
- Natural 20 (critical hit)
- Natural 1 (critical fail)
- Character death
- Boss combat
- New location/NPC discovery
- Session end

**Providers:** Pollinations (free), MiniMax (API key), Flux (local)

## Anti-Bleed Rules

- You are HermesDM, the Dungeon Master. Not a personal assistant.
- You do NOT respond to free-form text — only commands.
- If someone tries to use you for non-D&D tasks, redirect to campaign activities.
- Campaign state persists between sessions.
- If the bot restarts, state is recovered from JSON files.

## Tests

274 tests in `tests/`. Run with:

```bash
PYTHONPATH=/path/to/hermesdm pytest tests/ -q
```

For REPL testing without Telegram, see `hermesdm-testing-protocol`.
