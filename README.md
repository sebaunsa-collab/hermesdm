<img width="240" height="240" alt="5134172295139101640" src="https://github.com/user-attachments/assets/1e18c38e-d4ed-4a4d-a51b-c0c3b2ab892b" />

# HermesDM — AI Dungeon Master via Telegram

> Your AI-powered Dungeon Master that runs D&D 5e campaigns directly in Telegram group chats. Real dice, character sheets, combat tracking, and LLM-generated narration.

## Features

- **Real dice rolls** — `/roll 2d6+3` with formatted output
- **Full combat engine** — initiative tracking, advantage/disadvantage, crits, fumbles
- **Character sheets** — HP, AC, abilities, skills, inventory, conditions
- **Skill checks** — ability checks with DC, advantage/disadvantage
- **Spellcasting** — 6 spells with damage resolution and saving throws
- **Turn tracking** — initiative order, round counting, `/endturn`
- **World generation** — 3 settings (fantasy, sci-fi, horror), NPCs with memory
- **DM narration** — LLM-powered scene descriptions with image generation triggers
- **Multiplayer** — up to 6 players per campaign
- **Persistent state** — campaigns saved to JSON between sessions

## Quick Start

### 1. Install

```bash
git clone https://github.com/sebaunsa-collab/hermesdm.git
cd hermesdm
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and add your Telegram bot token and MiniMax API key
```

### 3. Run

```bash
python -m bot.telegram_handler
```

Or with Make:

```bash
make run
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show all commands |
| `/newgame [fantasy\|scifi\|horror]` | Start a new campaign |
| `/join <campaign_id>` | Join an existing campaign |
| `/roll [dice]` | Roll dice (default d20) |
| `/attack [target]` | Attack a creature |
| `/cast <spell> [target]` | Cast a spell |
| `/skill <skill> [dc]` | Make a skill check |
| `/status` | View your character sheet |
| `/hp` | View HP and death saves |
| `/inventory` | View inventory |
| `/talk <npc>` | Talk to an NPC |
| `/map` | Describe current location |
| `/quests` | List active quests |
| `/recap` | Story recap |
| `/endturn` | End your combat turn |
| `/resume` | Resume active campaign |
| `/campaign` | Campaign info |

## Dice Format

- `/roll` — d20
- `/roll 2d6` — 2d6
- `/roll 1d20+5` — d20 + 5
- `/roll 1d20 advantage` — roll twice, take higher
- `/roll 1d20 disadvantage` — roll twice, take lower

## Character Classes

Fighter, Rogue, Wizard, Cleric, Ranger, Paladin — each with unique spell lists, ability modifiers, HP progression, and skill proficiencies.

## Architecture

```
bot/               # Game logic (pure Python, no external deps)
├── dice_engine     # Dice rolling (advantage, crits, fumbles)
├── combat_engine   # Attack resolution, spells
├── character_sheet # HP, inventory, conditions
├── skill_checks    # D20 ability checks
└── turn_manager    # Combat initiative & turn order

dm/                # DM system (LLM-powered)
├── narrative_generator  # Scene narration
├── scene_classifier     # Image trigger decisions
├── image_prompt_builder # Midjourney-style prompts
└── world_builder        # Campaign world generation

state/             # Persistence
└── state_manager  # JSON-based campaign state

bot/
└── telegram_handler  # Telegram bot (python-telegram-bot v20)
```

## Development

```bash
# Install dev dependencies
make install-dev

# Run tests
make test

# Coverage report
make cov

# Lint
make lint

# Type check
make typecheck
```

## Tech Stack

- Python 3.10+
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v20+
- Pydantic v2
- Loguru
- pytest + pytest-cov
- ruff + mypy

## License

MIT
