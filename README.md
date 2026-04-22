<img width="240" height="240" alt="5134172295139101640" src="https://github.com/user-attachments/assets/1e18c38e-d4ed-4a4d-a51b-c0c3b2ab892b" />

# HermesDM — AI Dungeon Master via Telegram

> Your AI-powered Dungeon Master runs straight in Telegram. Real dice, character sheets, turn-based combat, world continuity, LLM narration, and contextual image generation.

![D&D 5e](https://img.shields.io/badge/D%26D-5e-960020?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
[![Tests](https://img.shields.io/badge/Tests-274%20%E2%9C%85-brightgreen?style=flat-square)](tests/)

---

## What is this? 🎲

HermesDM is a fully autonomous D&D 5e game engine that lives inside Telegram. No need for Roll20, D&D Beyond, or any other tool — just open a chat with your bot and play.

The DM is powered by an LLM that narrates the world, generates NPC dialogue, resolves actions, and builds the story dynamically. Dice rolls are real, character sheets persist across sessions, and the AI automatically generates images for dramatic moments.

**Quick example of what a session looks like:**

```
⚔️ COMBATE: Valdric vs Ancient Dragon
Valdric tira ataque con ventaja... [2d20+7 → 18, 19+7=26] ¡NAT 20!
NarrativeGenerator: "Valdric delivers a devastating blow to the wounded dragon,
the beast crashing down from the sky in flames, dramatic cinematic battle scene"
[MiniMax image sent to group]
```

---

## Features Overview

| Feature | Status |
|---------|--------|
| Real dice rolls (1d4 → 1d20+, advantage, saves) | ✅ |
| Character sheets with HP, XP, inventory, conditions | ✅ |
| Spell slot system (Wizards, Clerics, Warlocks...) | ✅ |
| Death saves that survive bot restarts | ✅ |
| Persistent NPCs with memory | ✅ |
| Turn-based combat engine | ✅ |
| LLM narration & NPC dialogue | ✅ |
| Auto-image generation (Pollinations, MiniMax, Flux) | ✅ |
| Campaign state persistence (JSON) | ✅ |
| 5 campaign genres (fantasy, dungeon, horror, tavern, scifi) | ✅ |
| Telegram-native — no external apps needed | ✅ |

---

## Quick Start

```bash
# 1. Clone e instala
git clone https://github.com/sherman/hermesdm.git
cd hermesdm
pip install -e .

# 2. Configura tokens
cp config.yaml.example config.yaml
# Edita TELEGRAM_BOT_TOKEN y LLM_API_KEY en config.yaml

# 3. Ejecuta
python -m bot.telegram_bot
```

That's it. Open Telegram, find your bot, and type `/start`.

---

## All Commands

### 🎮 Game Management
| Command | Description |
|---------|-------------|
| `/start` | Launch the new campaign wizard |
| `/campaign` | Show active campaign info |
| `/newgame` | Reset and start a fresh campaign |
| `/end` | End session — generates epilogue + scene image |
| `/settings` | View/edit difficulty, tone, image provider |

### 👤 Characters
| Command | Description |
|---------|-------------|
| `/create <name> <class>` | Create character (Lvl 1, standard array) |
| `/delete <name>` | Delete character |
| `/chars` | List all campaign characters |
| `/char <name>` | Full character sheet |
| `/hp <name> [value]` | View or modify HP |
| `/xp <name> [value]` | View or modify XP |
| `/levelup <name>` | Level up (auto-recalculates HP) |
| `/conditions <name> [add/remove]` | Manage conditions (poisoned, stunned...) |
| `/deathsave <name> [success/fail]` | Death saving throw |
| `/rest` | Long rest (recover all) |
| `/shortrest` | Short rest (1 hit die + CON mod HP) |

### 🎒 Inventory
| Command | Description |
|---------|-------------|
| `/inventory <name>` | Show inventory |
| `/item <name> <item>` | Add item |
| `/give <name> <item>` | Alias for `/item` |
| `/drop <name> <item>` | Remove item |
| `/equip <name> <item>` | Equip item |
| `/unequip <name> [item]` | Unequip item(s) |

### 🎲 Dice & Checks
| Command | Description |
|---------|-------------|
| `/roll <dice>` | Roll dice (e.g. `2d6+3`, `1d20+5`) |
| `/r <dice>` | Short alias |
| `/flip` | Coin flip (1d2) |
| `/check <stat> [adv/dis]` | Skill check (str, dex, con, etc.) |
| `/save <stat> [dc]` | Saving throw (default DC 10) |

### ✨ Magic & Spellcasting
| Command | Description |
|---------|-------------|
| `/cast <name> <spell> [target]` | Cast a spell (consumes slot if applicable) |
| `/spells` | List available spells by level |

**Available Spells:**
- **Cantrips:** Fire Bolt, Sacred Flame, Shocking Grasp, Mind Sliver, Thaumaturgy
- **Lv1:** Magic Missile, Guiding Bolt, Healing Word, Thunderwave, Shield, Sleep
- **Lv2:** Scorching Ray, Spiritual Weapon, Hold Person, Misty Step
- **Lv3:** Fireball, Counterspell, Mass Healing Word
- **Lv4:** Polymorph, Wall of Fire
- **Lv5:** Cone of Cold, Flame Strike

**Spell Slot System:**
| Class | Lv1 | Lv2 | Lv3 | Lv4 | Lv5 |
|-------|-----|-----|-----|-----|-----|
| Wizard | 4 | 3 | 3 | 3 | 3 |
| Cleric/Druid/Bard | 4 | 3 | 3 | 3 | 3 |
| Paladin/Ranger | 4 | 3 | 3 | 2 | 2 |
| Warlock | Pact slot (short rest) | | | | |

### ⚔️ Combat
| Command | Description |
|---------|-------------|
| `/combat` | Current combat status |
| `/join` | Join active combat |
| `/attack <target>` | Attack (alias: `/j`) |
| `/endturn` | End your turn |
| `/flee` | Flee combat |
| `/status` | Party HP, AC, conditions |
| `/summon <name> [type]` | Summon generic monster |
| `/monster <name> [HP] [AC]` | Summon custom monster |
| `/remove <name>` | Remove creature from combat |
| `/monsters` | List monsters in combat |

### 🧙 NPCs
| Command | Description |
|---------|-------------|
| `/npc <name>` | Query or create NPC |
| `/npcs` | List active NPCs |
| `/npcnote <name> <note>` | Add DM note about NPC |
| `/talk <npc> <message>` | Talk to an NPC (LLM dialogue) |
| `/npcsearch <query>` | Search NPCs by name/title |
| `/npcmemory <name> <key> <value>` | Register memory about NPC |

### 🖼️ Narration & Images
| Command | Description |
|---------|-------------|
| `/act <action>` | Narrate an action in the world |
| `/scene <description>` | Describe the current scene |
| `/image <prompt>` | Manually generate an image |
| `/sceneimage` | Auto-generate image of current scene |

---

## Campaign Genres

When you run `/newgame`, you pick a genre. Each genre ships with unique system prompts for the LLM:

| Genre | Vibe | Description |
|-------|------|-------------|
| `fantasy` | 🏰 | High fantasy medieval adventures |
| `dungeon` | 🗝️ | Dungeon crawling, puzzles, traps |
| `tavern` | 🍺 | Political intrigue, missions from the tavern |
| `horror` | 👻 | Psychological horror, survival |
| `scifi` | 🚀 | Sci-fi, space opera, cyberpunk |

---

## How Auto-Images Work 📸

The DM generates images **automatically** during narratively important moments — no manual triggers needed.

### Trigger Events
| Event | Image? |
|-------|--------|
| Natural 20 (critical hit) | ✅ |
| Natural 1 (fumble) | ✅ |
| Character death (HP = 0) | ✅ |
| Boss combat starts | ✅ |
| New location/NPC discovered | ✅ |
| Session ends | ✅ |
| HP drops below 25% | ✅ |
| Normal turn | ❌ |

### Supported Providers
| Provider | Quality | Speed | Cost |
|----------|---------|-------|------|
| Pollinations | Good | ~1s | Free |
| MiniMax | Excellent | ~10s | API key |
| Flux | High | Variable | Local |

### Configuration
```yaml
# config.yaml
image_provider: "pollinations"   # default
minimax_api_key: "your-key"      # optional
```

Or at runtime via `/settings`:
```
image_provider: minimax
```

---

## Architecture

```
hermesdm/
├── bot/
│   ├── telegram_handler.py      # Entry point, command routing
│   ├── character_sheet.py        # HP, XP, inventory, conditions, death saves
│   ├── combat_engine.py          # Initiative, attack resolution, crits
│   ├── diceRoller.py             # Dice parsing, rolling, formatted output
│   ├── skill_checks.py           # Skill checks, saving throws
│   ├── spell_manager.py          # Spellcasting, damage, saves
│   └── monsters.py              # Monster definitions, summon
├── dm/
│   ├── narrative_generator.py    # LLM narration, NPC dialogue
│   ├── world_builder.py          # World/NPC generation per genre
│   ├── image_provider.py         # ABC + Pollinations/MiniMax/Flux
│   └── image_event_handler.py    # Auto-trigger logic + cooldown
├── adapters/mode_b/
│   └── action_router.py          # /j action routing, ActionResult
├── state/
│   └── state_manager.py          # Campaign state, JSON persistence
└── tests/                        # 274 tests
    ├── test_combat_engine.py
    ├── test_character_sheet.py
    ├── test_diceRoller.py
    ├── test_skill_checks.py
    └── ...
```

### Action Flow (Combat Example)

```
/j attack dragon
  → action_router.route()         # Parse action, determine type
  → combat_engine.resolve()        # Roll dice, calculate damage
  → narrative_generator.generate_scene()  # LLM narration
  → image_event_handler.maybe_generate()  # Should we generate image?
  → telegram_handler._maybe_send_scene_image()  # Send if yes
```

### Image Generation Flow

```
NarrativeGenerator.generate_scene()
  → Result { narrative, triggered_image, scene_type }
      ↓ triggered_image = True
ImageEventHandler.maybe_generate()
  → Check cooldown (5 min default)
  → Check trigger rules (nat_20, death, boss, etc.)
      ↓ allowed
ImageProvider.generate()
  → build_scene_prompt()        # Context + genre → prompt
  → Pollinations / MiniMax / Flux  # API call
  → /tmp/hermesdm_*.png        # Local file
      ↓
TelegramBot.send_photo()
  → Image to group
```

---

## Campaign State

All state lives in `~/.hermes/hermesdm_state.json`:

```json
{
  "campaign_id": "uuid",
  "name": "The Dragon's Lair",
  "genre": "fantasy",
  "status": "active",
  "difficulty": "normal",
  "tone": "serious",
  "current_location": "Dark Forest",
  "image_provider": "pollinations",
  "auto_image_triggers": {
    "nat_20": true,
    "death": true,
    "boss_combat": true,
    "discovery": true,
    "session_end": true
  },
  "characters": { ... },
  "npcs": { ... },
  "timeline": [ ... ],
  "combat": { ... }
}
```

---

## Development

```bash
# Run all tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=bot --cov=dm --cov=adapters

# Validate campaign state
python -c "from state.state_manager import validate_state; validate_state()"

# Lint
ruff check bot dm adapters

# Type check
mypy bot dm --ignore-missing-imports
```

---

## Detailed Specifications

- [SPEC_SPELL_SLOTS.md](SPEC_SPELL_SLOTS.md) — D&D 5e spell slot system
- [SPEC_NPC_PERSISTENCE.md](SPEC_NPC_PERSISTENCE.md) — Persistent NPCs with memory
- [SPEC_IMAGE_GENERATION.md](SPEC_IMAGE_GENERATION.md) — Auto-image system
- [SPEC_DEATH_SAVES_PERSISTENCE.md](SPEC_DEATH_SAVES_PERSISTENCE.md) — Death saves across restarts
- [SPEC_DICE_ANIMATION.md](SPEC_DICE_ANIMATION.md) — Animated dice rendering
- [SPEC_PLAN_B.md](SPEC_PLAN_B.md) — Plan B: Hermes Agent as DM
- [PROJECT_PLAN.md](PROJECT_PLAN.md) — Full project roadmap

---

## Author

**Sherman** — [@TheShugarBoy](https://twitter.com/TheShugarBoy)

Built with Python, Telegram Bots API, and MiniMax LLM.
