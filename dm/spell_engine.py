"""
spell_engine.py — Spell slot tables, DC/attack calculations, concentration.
Deterministic engine following D&D 5e SRD rules.
Part of Scene Director's sub-engine suite.

Design: SpellEngine does LOOKUP (what slots at L5?), ResourceManager does
TRACKING (how many left?). Concentration checks are owned here.
"""

import random
from typing import Optional, Tuple

# ── Caster type classification ────────────────────────────────────────────
CASTER_TYPE_MAP: dict[str, str] = {
    # Full casters
    "wizard": "full",
    "cleric": "full",
    "druid": "full",
    "sorcerer": "full",
    "bard": "full",
    "warlock": "full",
    # Half casters (spellcasting starts at level 2)
    "paladin": "half",
    "ranger": "half",
    # Third casters (Eldritch Knight, Arcane Trickster — start at level 3)
    "eldritch_knight": "third",
    "arcane_trickster": "third",
    # Non-casters
    "fighter": "none",
    "rogue": "none",
    "barbarian": "none",
    "monk": "none",
    "artificer": "full",  # Artificer is a half-caster in 5e but gets slots at L1
}

# ── Full caster spell slot tables (Wizard, Cleric, Druid, Sorc, Bard) ─────
# Index = character level → [L1, L2, L3, L4, L5, L6, L7, L8, L9] slots
FULL_CASTER_SLOTS: dict[int, list[int]] = {
    1:  [2, 0, 0, 0, 0, 0, 0, 0, 0],
    2:  [3, 0, 0, 0, 0, 0, 0, 0, 0],
    3:  [4, 2, 0, 0, 0, 0, 0, 0, 0],
    4:  [4, 3, 0, 0, 0, 0, 0, 0, 0],
    5:  [4, 3, 2, 0, 0, 0, 0, 0, 0],
    6:  [4, 3, 3, 0, 0, 0, 0, 0, 0],
    7:  [4, 3, 3, 1, 0, 0, 0, 0, 0],
    8:  [4, 3, 3, 2, 0, 0, 0, 0, 0],
    9:  [4, 3, 3, 3, 1, 0, 0, 0, 0],
    10: [4, 3, 3, 3, 2, 0, 0, 0, 0],
    11: [4, 3, 3, 3, 2, 1, 0, 0, 0],
    12: [4, 3, 3, 3, 2, 1, 0, 0, 0],
    13: [4, 3, 3, 3, 2, 1, 1, 0, 0],
    14: [4, 3, 3, 3, 2, 1, 1, 0, 0],
    15: [4, 3, 3, 3, 2, 1, 1, 1, 0],
    16: [4, 3, 3, 3, 2, 1, 1, 1, 0],
    17: [4, 3, 3, 3, 2, 1, 1, 1, 1],
    18: [4, 3, 3, 3, 3, 1, 1, 1, 1],
    19: [4, 3, 3, 3, 3, 2, 1, 1, 1],
    20: [4, 3, 3, 3, 3, 2, 2, 1, 1],
}

# ── Half caster spell slot tables (Paladin, Ranger) ───────────────────────
# Spellcasting level = max(1, level - 1) → effectively floor(level/2) scaling
HALF_CASTER_SLOTS: dict[int, list[int]] = {
    1:  [0, 0, 0, 0, 0, 0, 0, 0, 0],
    2:  [2, 0, 0, 0, 0, 0, 0, 0, 0],
    3:  [3, 0, 0, 0, 0, 0, 0, 0, 0],
    4:  [3, 0, 0, 0, 0, 0, 0, 0, 0],
    5:  [4, 2, 0, 0, 0, 0, 0, 0, 0],
    6:  [4, 2, 0, 0, 0, 0, 0, 0, 0],
    7:  [4, 3, 0, 0, 0, 0, 0, 0, 0],
    8:  [4, 3, 0, 0, 0, 0, 0, 0, 0],
    9:  [4, 3, 2, 0, 0, 0, 0, 0, 0],
    10: [4, 3, 2, 0, 0, 0, 0, 0, 0],
    11: [4, 3, 3, 0, 0, 0, 0, 0, 0],
    12: [4, 3, 3, 0, 0, 0, 0, 0, 0],
    13: [4, 3, 3, 1, 0, 0, 0, 0, 0],
    14: [4, 3, 3, 1, 0, 0, 0, 0, 0],
    15: [4, 3, 3, 2, 0, 0, 0, 0, 0],
    16: [4, 3, 3, 2, 0, 0, 0, 0, 0],
    17: [4, 3, 3, 3, 1, 0, 0, 0, 0],
    18: [4, 3, 3, 3, 1, 0, 0, 0, 0],
    19: [4, 3, 3, 3, 2, 0, 0, 0, 0],
    20: [4, 3, 3, 3, 2, 0, 0, 0, 0],
}

# ── Third caster spell slot tables (Eldritch Knight, Arcane Trickster) ────
# Spellcasting level = max(1, floor(level/3))
THIRD_CASTER_SLOTS: dict[int, list[int]] = {
    1:  [0, 0, 0, 0, 0, 0, 0, 0, 0],
    2:  [0, 0, 0, 0, 0, 0, 0, 0, 0],
    3:  [2, 0, 0, 0, 0, 0, 0, 0, 0],
    4:  [3, 0, 0, 0, 0, 0, 0, 0, 0],
    5:  [3, 0, 0, 0, 0, 0, 0, 0, 0],
    6:  [3, 0, 0, 0, 0, 0, 0, 0, 0],
    7:  [4, 2, 0, 0, 0, 0, 0, 0, 0],
    8:  [4, 2, 0, 0, 0, 0, 0, 0, 0],
    9:  [4, 2, 0, 0, 0, 0, 0, 0, 0],
    10: [4, 3, 0, 0, 0, 0, 0, 0, 0],
    11: [4, 3, 0, 0, 0, 0, 0, 0, 0],
    12: [4, 3, 0, 0, 0, 0, 0, 0, 0],
    13: [4, 3, 2, 0, 0, 0, 0, 0, 0],
    14: [4, 3, 2, 0, 0, 0, 0, 0, 0],
    15: [4, 3, 2, 0, 0, 0, 0, 0, 0],
    16: [4, 3, 3, 0, 0, 0, 0, 0, 0],
    17: [4, 3, 3, 0, 0, 0, 0, 0, 0],
    18: [4, 3, 3, 0, 0, 0, 0, 0, 0],
    19: [4, 3, 3, 1, 0, 0, 0, 0, 0],
    20: [4, 3, 3, 1, 0, 0, 0, 0, 0],
}


def _ability_mod(ability_score: int) -> int:
    """Calculate D&D ability modifier: (score - 10) // 2."""
    return (ability_score - 10) // 2


def _prof_bonus(level: int) -> int:
    """Proficiency bonus: +2 (1-4), +3 (5-8), +4 (9-12), +5 (13-16), +6 (17-20)."""
    return 2 + ((level - 1) // 4)


def get_spell_slots(level: int, caster_type: str) -> dict[int, int]:
    """Get MAX spell slots for a character at given level.

    Args:
        level: Character level (1-20)
        caster_type: "full", "half", "third", "none", or a class name like "wizard"

    Returns:
        dict of {spell_level (1-9): slot_count}
    """
    # Normalize class name to caster type
    actual_type = CASTER_TYPE_MAP.get(caster_type, caster_type) if caster_type in CASTER_TYPE_MAP else caster_type

    # Guard: clamp level
    clamped = max(1, min(level, 20))

    table: dict[int, list[int]]
    if actual_type == "full":
        table = FULL_CASTER_SLOTS
    elif actual_type == "half":
        table = HALF_CASTER_SLOTS
    elif actual_type == "third":
        table = THIRD_CASTER_SLOTS
    else:
        # Non-caster: no slots
        return {i: 0 for i in range(1, 10)}

    slots_list = table.get(clamped, table[1])
    return {i + 1: slots_list[i] for i in range(9)}


def calculate_spell_dc(level: int, spellcasting_ability: int) -> int:
    """Calculate spell save DC per D&D 5e rules: 8 + prof + ability_mod.

    Args:
        level: Character level (determines proficiency bonus)
        spellcasting_ability: The spellcasting ability score (e.g., INT=16)

    Returns:
        Spell save DC (integer)
    """
    prof = _prof_bonus(level)
    mod = _ability_mod(spellcasting_ability)
    return 8 + prof + mod


def calculate_spell_attack(level: int, spellcasting_ability: int) -> int:
    """Calculate spell attack modifier: prof + ability_mod.

    Args:
        level: Character level (determines proficiency bonus)
        spellcasting_ability: The spellcasting ability score

    Returns:
        Spell attack modifier (integer)
    """
    prof = _prof_bonus(level)
    mod = _ability_mod(spellcasting_ability)
    return prof + mod


def concentration_save(
    damage_taken: int,
    con_mod: int,
    rng: Optional[random.Random] = None,
) -> Tuple[bool, int]:
    """Roll a concentration saving throw when a concentrating caster takes damage.

    Concentration DC = max(10, damage_taken // 2)
    If the d20 roll + con_mod >= DC, concentration is maintained.
    A natural 1 on the d20 ALWAYS fails (auto-fail rule).

    Args:
        damage_taken: amount of damage the caster took
        con_mod: Constitution modifier of the caster
        rng: Optional seeded random.Random for deterministic testing

    Returns:
        (saved: bool, dc: int) — True if concentration maintained, False if broken
    """
    dc = max(10, damage_taken // 2)
    rng = rng or random.Random()
    d20 = rng.randint(1, 20)

    # Natural 1 always fails
    if d20 == 1:
        return False, dc

    return (d20 + con_mod) >= dc, dc
