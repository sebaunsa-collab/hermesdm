---
name: hermesdm-testing-protocol
description: Protocol for testing HermesDM REPL without getting trapped — safe module import, Telegram handler testing via unittest mocks, and avoidant patterns.
tags:
  - hermesdm
  - testing
  - telegram
required_environment_variables: []
required_commands: []
setup_needed: false
---

# HermesDM Testing Protocol

## REPL Testing Without Telegram

### Safe Module Import

```python
import sys
sys.path.insert(0, '/path/to/hermesdm')

# Import the module you want to test
from bot.dice_engine import roll

# Test dice rolling
result = roll('2d6+3')
print(f"Total: {result['total']}, Rolls: {result['rolls']}")
```

### Testing Telegram Handlers (Safe — No Network)

```python
from bot.telegram_handler import cmd_me, ChatState
from unittest.mock import AsyncMock, MagicMock
import asyncio

msg = MagicMock()
msg.text = '/me se esconde'
msg.reply_text = AsyncMock()
update = MagicMock()
update.message = msg
update.effective_user.first_name = 'Valdric'
ctx = MagicMock()
ctx.args = ['se', 'esconde']
ctx.chat_data = {'_hermes_state': ChatState()}
ctx.chat_data['_hermes_state'].active_campaign = 'test'

# Create a test character
from bot.character_sheet import create_character
char = create_character('Valdric', 'rogue', 3)
ctx.chat_data['_hermes_state'].characters['valdric'] = char

asyncio.run(cmd_me(update, ctx))
print(msg.reply_text.call_args[0][0])
```

### Testing Combat Engine

```python
from bot.combat_engine import resolve_attack, WEAPON_DAMAGE

result = resolve_attack(
    attacker="Valdric",
    defender="Orc",
    attack_roll=15,
    weapon="longsword",
    advantage=False,
    disadvantage=False,
    defender_ac=14,
    rage_bonus=0
)
print(result)
```

## Avoidant Patterns

### DON'T: Run the Full Telegram App

Never call `main()` or `build_app()` in REPL testing — it will start polling and block.

### DON'T: Use Real API Calls

Image generation, LLM narration, and Telegram API calls all require network. Mock them:

```python
# Instead of real image generation
with patch('dm.image_provider.PollinationsProvider.generate') as mock:
    mock.return_value = '/tmp/test_image.png'
    # test your code
```

### DON'T: Touch Global State

State is persisted in JSON files. Isolate tests:

```python
# Create a temp state file for testing
import tempfile
import os

tmp_state = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
tmp_state.write(b'{}')
tmp_state.close()

# Patch the state path
with patch('state.state_manager._STATE_PATH', tmp_state.name):
    # run tests

os.unlink(tmp_state.name)
```

## Run Full Test Suite

```bash
cd /path/to/hermesdm
PYTHONPATH="" python3 -m pytest tests/ -v
```

### Run Specific Test File

```bash
PYTHONPATH="" python3 -m pytest tests/test_dice_engine.py -v
```

### Run with Coverage

```bash
PYTHONPATH="" python3 -m pytest tests/ --cov=bot --cov=dm -q
```

## Common Test Fixtures

```python
def make_fake_update(text: str, first_name: str = "TestPlayer") -> MagicMock:
    """Create a fake Telegram update for handler testing."""
    msg = MagicMock()
    msg.text = text
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.message = msg
    update.effective_user.first_name = first_name
    return update

def make_fake_context(chat_data: dict = None) -> MagicMock:
    """Create a fake Telegram context."""
    ctx = MagicMock()
    ctx.args = []
    ctx.chat_data = chat_data or {'_hermes_state': ChatState()}
    return ctx
```

## Flaky Tests — Global RNG

If a test passes in isolation but fails in the full suite:

```python
def test_modifier_applied_correctly(self):
    import random
    random.seed(0x5EED)  # Deterministic regardless of test order
    # ... rest of test
```
