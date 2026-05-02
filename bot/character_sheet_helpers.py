"""
character_sheet_helpers.py — Extension: static helpers for Scene Director engines.

Added helpers:
- get_max_hp(cid): Returns character max HP
- get_spell_slots(cid): Returns character spell slots state
- get_hit_dice_max(cid): Returns max hit dice for character level
- get_dex_mod(cid): Returns DEX modifier
"""

# These helpers work with Character instances or dicts
# Imported by ResourceManager and CombatFlow for state access

from typing import Optional, Dict, Any


def get_max_hp(char_or_data) -> int:
    """Get max HP from Character or player data dict."""
    if hasattr(char_or_data, 'hp'):
        return char_or_data.hp.max
    if isinstance(char_or_data, dict):
        return char_or_data.get("hp_max", char_or_data.get("hp", {}).get("max", 10))
    return 10


def get_hp_current(char_or_data) -> int:
    """Get current HP from Character or player data dict."""
    if hasattr(char_or_data, 'hp'):
        return char_or_data.hp.current
    if isinstance(char_or_data, dict):
        return char_or_data.get("hp_current", char_or_data.get("hp", {}).get("current", 10))
    return 10


def get_spell_slots(char_or_data, level: int) -> int:
    """Get available spell slots at given level."""
    if hasattr(char_or_data, 'spell_slots'):
        return char_or_data.spell_slots.available(level)
    if isinstance(char_or_data, dict):
        slots = char_or_data.get("spell_slots", {})
        total = slots.get("total", [0] * 9)
        used = slots.get("used", [0] * 9)
        idx = max(0, level - 1)
        return max(0, total[idx] - used[idx]) if idx < len(total) else 0
    return 0


def get_hit_dice_remaining(char_or_data) -> int:
    """Get remaining hit dice."""
    if hasattr(char_or_data, 'hp'):
        return char_or_data.hp.hit_dice_remaining
    if isinstance(char_or_data, dict):
        hd = char_or_data.get("hit_dice", {})
        return hd.get("current", 1)
    return 1


def get_hit_dice_max(char_or_data) -> int:
    """Get max hit dice (typically = character level)."""
    if hasattr(char_or_data, 'hp'):
        if hasattr(char_or_data, 'level'):
            return char_or_data.level
    if isinstance(char_or_data, dict):
        hd = char_or_data.get("hit_dice", {})
        return hd.get("max", 1)
    return 1


def get_dex_mod(char_or_data) -> int:
    """Get DEX modifier."""
    if hasattr(char_or_data, 'mod'):
        return char_or_data.mod("dex")
    if isinstance(char_or_data, dict):
        stats = char_or_data.get("stats", {})
        dex = stats.get("dex", 10)
        return (dex - 10) // 2
    return 0
