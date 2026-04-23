# SPEC: HermesDM Profile Distribution

## Status: DRAFT

---

## Overview

Package HermesDM as a Hermes Agent profile for **3-command installation** by end users. The profile bundles everything needed to run a fully functional D&D 5e bot: personality, config, skills, and entry point.

---

## Background

HermesDM is currently a standalone Python project (`git clone → pip install → configure → run`). This requires ~10 manual steps and deep knowledge of the codebase structure.

Hermes Agent profiles provide isolated environments with their own `config.yaml`, `.env`, `SOUL.md`, skills, and gateway. The `hermes profile export/import` commands can bundle an entire profile into a `.tar.gz` for redistribution.

**Goal:** Reduce installation to 3 commands:
```bash
curl -L https://.../hermesdm.tar.gz -o hermesdm.tar.gz
hermes profile import hermesdm.tar.gz
dm gateway start
```

---

## Technical Foundation

### Hermes Profile Structure

Each Hermes profile lives at `~/.hermes/profiles/<name>/` with:

```
~/.hermes/profiles/dm/
├── config.yaml          # Model, provider, tools, MCP servers
├── .env                 # API keys (TELEGRAM_BOT_TOKEN, MINIMAX_API_KEY, etc.)
├── SOUL.md              # Personality prompt (the "DM voice")
├── skills/              # Profile-local skills (overrides system skills)
│   ├── hermesdm/
│   ├── dnd-spell-slots-impl/
│   ├── hermesdm-dev-patterns/
│   └── hermesdm-testing-protocol/
├── memories/            # Persistent memory (empty on first install)
├── sessions/            # Chat session history
├── cron/                # Scheduled jobs
└── gateway_state.json   # Gateway runtime state
```

### Hermes Profile Commands

```bash
hermes profile create dm              # Create blank profile (needs manual config)
hermes profile export dm -o dm.tar.gz  # Package profile → .tar.gz
hermes profile import dm.tar.gz       # Restore from .tar.gz
dm gateway start                      # Start the DM's Telegram bot
dm setup                             # Interactive config wizard
dm chat                              # Chat with the DM
```

### Token Lock System

Two profiles **cannot** use the same Telegram bot token. If a second profile tries to use an already-in-use token, Hermes Agent blocks it with an error. This prevents accidental token conflicts.

---

## Profile Contents

### SOUL.md — DM Personality

The `SOUL.md` defines the DM's voice and behavior. Must include:

- **Core identity:** "You are HermesDM, an AI Dungeon Master for D&D 5e..."
- **Tone:** Serious narrative, evocative descriptions, dramatic tension
- **Command awareness:** List all commands the bot responds to
- **Image generation:** When/how to trigger automatic images
- **Genre handling:** How to adapt narrative for fantasy/dungeon/horror/tavern/scifi
- **Anti-bleed:** Clear boundary — this is HermesDM, not the user's personal assistant
- **Language:** Spanish (primary), with English options for spell names and LLM prompts

### config.yaml — Runtime Configuration

```yaml
model:
  provider: minimax
  name: minimax/minimax-m2.7

gateway:
  platform: telegram
  # TELEGRAM_BOT_TOKEN injected from .env

tools:
  enabled:
    - terminal
    - execute_code
    - skills
    - browser
    - vision
    - file
    - cronjob
    - todo
    - tts

skills:
  # Profile-local skills override system skills
  # Only D&D-related skills are bundled
  search_paths:
    - ~/.hermes/profiles/dm/skills

image_generation:
  provider: pollinations  # Default, user can change via /settings
  auto_triggers:
    nat_20: true
    nat_1: true
    death: true
    boss_combat: true
    discovery: true
    session_end: true
    hp_below_25: true
  cooldown_minutes: 5
```

### .env Template — User Configuration

```
# Required
TELEGRAM_BOT_TOKEN=your_botfather_token_here

# Optional (Pollinations works without this)
MINIMAX_API_KEY=

# Optional (OpenAI for better narration)
OPENAI_API_KEY=

# Optional (for image generation)
FLUX_ENDPOINT=http://localhost:7860
```

### Skills to Bundle

The following skills are D&D-specific and bundled with the profile:

| Skill | Purpose |
|-------|---------|
| `hermesdm` (meta) | Links to the repo, entry point, command reference |
| `hermesdm-development` | Development patterns, file editing gotchas |
| `hermesdm-testing-protocol` | REPL testing protocol |
| `dnd-spell-slots-impl` | Spell slots system specification |

**Skills NOT included:** Generic skills (notion, github, etc.) — they bloat the bundle and are irrelevant for D&D.

### Entry Point

The bot's Telegram handler entry point lives at:
```
bot/telegram_handler.py
```

This is called by Hermes Gateway via the profile's configured entry point. The profile must set:

```yaml
# In config.yaml or via dm setup
entry_point: bot.telegram_handler:main
```

---

## Installation Workflow

### Developer Side (Packaging)

```bash
# 1. Set up the profile locally
hermes profile create dm

# 2. Configure it (SOUL.md, config.yaml, .env template, skills)
# (manual setup, one-time)

# 3. Export
hermes profile export dm -o hermesdm.tar.gz

# 4. Upload to GitHub Releases as "hermesdm-v{version}.tar.gz"
```

### User Side (Installation)

```bash
# 1. Download the bundle
curl -L https://github.com/sebaunsa-collab/hermesdm/releases/latest/download/hermesdm.tar.gz -o hermesdm.tar.gz

# 2. Import into Hermes Agent
hermes profile import hermesdm.tar.gz

# 3. Configure API keys
dm setup
# (or: dm config set TELEGRAM_BOT_TOKEN=xxx)

# 4. Start the bot
dm gateway start
```

---

## Versioning Strategy

- **Format:** `hermesdm-v{YY.MM}.tar.gz` (e.g., `hermesdm-v25.04.tar.gz`)
- **Release location:** GitHub Releases of `sebaunsa-collab/hermesdm`
- **Latest tag:** `hermesdm-latest.tar.gz` symlink (or use GitHub's `latest` redirect)
- **In-archive version:** Stored in `VERSION` file inside the archive

### Version File

```
VERSION: 25.04
BUNDLED: 2025-04-22
SPEC: SPEC_HERMESDM_PROFILE.md
```

---

## Acceptance Criteria

### AC1: Profile Export Integrity
- [ ] `hermes profile export dm` produces a `.tar.gz` file
- [ ] The archive contains: `config.yaml`, `.env`, `SOUL.md`, `skills/`, `VERSION`
- [ ] The archive does NOT contain: audit logs, sessions, memories, state DB
- [ ] File size is reasonable (< 10MB without sessions)

### AC2: Profile Import Works
- [ ] `hermes profile import dm.tar.gz` creates `~/.hermes/profiles/dm/`
- [ ] All expected files are present after import
- [ ] No existing profile is overwritten without confirmation

### AC3: Gateway Starts
- [ ] `dm gateway start` starts without errors
- [ ] Bot responds to `/start` command
- [ ] Bot ignores non-command text (no free-form LLM responses)

### AC4: Commands Work
- [ ] `/roll 2d6+3` → dice roll output
- [ ] `/create Valdric Wizard` → character created
- [ ] `/chars` → list characters
- [ ] `/npc Eldara` → NPC description

### AC5: Skills Isolated
- [ ] `dm skills list` shows only bundled D&D skills
- [ ] System skills (notion, github, etc.) are NOT visible from dm profile
- [ ] `hermes skills list` (default profile) still shows all system skills

### AC6: Image Generation
- [ ] Image provider is configurable via `config.yaml`
- [ ] `/image test prompt` generates an image (or fails gracefully with clear message)

### AC7: Profile Upgrade Path
- [ ] User can `hermes profile import` a newer version
- [ ] Import is additive (doesn't wipe existing campaign state unless forced)
- [ ] Version conflict is reported clearly

---

## File Structure

```
hermesdm/
├── SPEC_HERMESDM_PROFILE.md      # This spec
├── profile/                       # Files for the Hermes profile
│   ├── config.yaml               # Runtime config template
│   ├── .env                      # API keys template
│   ├── SOUL.md                   # DM personality prompt
│   ├── VERSION                   # Version file
│   └── skills/                   # D&D-only skills
│       ├── hermesdm/
│       ├── dnd-spell-slots-impl/
│       ├── hermesdm-dev-patterns/
│       └── hermesdm-testing-protocol/
├── install.sh                    # Optional: curl-based installer
├── README_PROFILE.md             # Profile-specific README (for end users)
└── tests/
    └── test_profile_distribution.py  # Unit tests for the workflow
```

---

## Non-Goals (Out of Scope)

- Migrating existing HermesDM state (JSON → Hermes memory)
- Running HermesDM as a standalone process (without Hermes Agent)
- Supporting multiple DM profiles simultaneously on the same machine
- Auto-upgrade of installed profiles

---

## Dependencies

- Hermes Agent installed (`curl -fsSL https://hermes-agent.nousresearch.com/install.sh | sh`)
- Python 3.12+
- Telegram Bot Token (from @BotFather)
- Optional: MiniMax API key (for better narration), OpenAI API key

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2025-04-22 | Sherman | Initial draft |
