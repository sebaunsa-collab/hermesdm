"""
xp_engine.py — XP calculation, leveling, and proficiency bonus.
Deterministic engine following D&D 5e SRD tables.
Part of Scene Director's sub-engine suite.

Design: Stand-alone module so XP can come from combat, quests, or milestones.
"""

from typing import List, Optional

# ── CR to XP reward table (D&D 5e SRD) ────────────────────────────────────
CR_XP: dict[float, int] = {
    0: 10,
    0.125: 25,
    0.25: 50,
    0.5: 100,
    1: 200,
    2: 450,
    3: 700,
    4: 1100,
    5: 1800,
    6: 2300,
    7: 2900,
    8: 3900,
    9: 5000,
    10: 5900,
    11: 7200,
    12: 8400,
    13: 10000,
    14: 11500,
    15: 13000,
    16: 15000,
    17: 18000,
    18: 20000,
    19: 22000,
    20: 25000,
    21: 33000,
    22: 41000,
    23: 50000,
    24: 62000,
    25: 75000,
    26: 90000,
    27: 105000,
    28: 120000,
    29: 135000,
    30: 155000,
}

# ── Level thresholds (XP required to REACH this level) ────────────────────
XP_THRESHOLDS: dict[int, int] = {
    1: 0,
    2: 300,
    3: 900,
    4: 2700,
    5: 6500,
    6: 14000,
    7: 23000,
    8: 34000,
    9: 48000,
    10: 64000,
    11: 85000,
    12: 100000,
    13: 120000,
    14: 140000,
    15: 165000,
    16: 195000,
    17: 225000,
    18: 265000,
    19: 305000,
    20: 355000,
}

# ── Proficiency bonus by level threshold ("at level X, bonus becomes Y") ──
# Keys are the level AT which the bonus changes
_PROF_BONUS_TABLE: dict[int, int] = {1: 2, 5: 3, 9: 4, 13: 5, 17: 6}


def _proficiency_for_level(level: int) -> int:
    """Calculate proficiency bonus for a given level using threshold rules."""
    prof = 2
    for threshold, bonus in sorted(_PROF_BONUS_TABLE.items()):
        if level >= threshold:
            prof = bonus
    return prof


# Pre-compute PROFICIENCY_BONUS table for direct lookup tests
PROFICIENCY_BONUS: dict[int, int] = {}
for _lv in range(1, 21):
    PROFICIENCY_BONUS[_lv] = _proficiency_for_level(_lv)


def calculate_xp(enemy_cr: float = 1.0, party_size: int = 1) -> int:
    """Calculate XP per character from a defeated enemy.

    Args:
        enemy_cr: Challenge Rating of the enemy (must be in CR_XP)
        party_size: Number of characters splitting the XP

    Returns:
        XP per character (floor division)

    Raises:
        ValueError: If enemy_cr is not in CR_XP table
    """
    if enemy_cr not in CR_XP:
        raise ValueError(f"Invalid CR: {enemy_cr}. Must be one of {sorted(CR_XP.keys())}")
    total = CR_XP[enemy_cr]
    return total // party_size


def award_xp(character: dict, xp_gained: int) -> dict:
    """Add XP to a character, detect level-ups, update proficiency bonus.

    The character dict is copied (not mutated in place). Level-ups are
    applied sequentially (XP can trigger multiple levels in one award).

    Args:
        character: dict with 'xp', 'level' keys (defaults: xp=0, level=1)
        xp_gained: amount of XP to add

    Returns:
        {
            "character": dict with updated xp, level, proficiency_bonus,
            "levels_gained": list[int] of levels reached,
            "messages": list[str] of level-up messages
        }
    """
    char = dict(character)
    # Normalize: accept both 'xp' and 'xp_current' as input
    if "xp" not in char and "xp_current" in char:
        char["xp"] = char["xp_current"]
    char.setdefault("xp", 0)
    char.setdefault("level", 1)
    char["xp"] += xp_gained

    levels_gained: list[int] = []
    messages: list[str] = []

    while True:
        next_level = char["level"] + 1
        # Level cap at 20 (no level 21+)
        if next_level not in XP_THRESHOLDS or char["xp"] < XP_THRESHOLDS[next_level]:
            break
        char["level"] = next_level
        levels_gained.append(next_level)
        messages.append(f"Subiste al nivel {next_level}!")

    # Update proficiency bonus based on current level
    char["proficiency_bonus"] = _proficiency_for_level(char["level"])

    return {
        "character": char,
        "levels_gained": levels_gained,
        "messages": messages,
    }


# ── Bulk XP award from defeated enemies ───────────────────────────────────

def award_combat_xp(
    characters: list[dict],
    defeated_enemies: list[dict],
    party_size: Optional[int] = None,
) -> dict:
    """Award XP to all characters from defeated enemies.

    Each enemy's CR is used to look up XP, total is divided by party size.
    If party_size is None, len(characters) is used.

    Args:
        characters: list of character dicts
        defeated_enemies: list of enemy dicts with 'cr' keys
        party_size: number of party members (defaults to len(characters))

    Returns:
        {
            "total_xp": int,
            "xp_per_player": int,
            "results": list[dict] — per-character award_xp results,
            "any_level_ups": bool
        }
    """
    if party_size is None:
        party_size = max(1, len(characters))

    total_xp = 0
    for enemy in defeated_enemies:
        cr = enemy.get("cr", 0)
        if cr in CR_XP:
            total_xp += CR_XP[cr]

    xp_per_player = total_xp // party_size

    results = []
    any_level_ups = False
    for char in characters:
        result = award_xp(char, xp_per_player)
        results.append(result)
        if len(result["levels_gained"]) > 0:
            any_level_ups = True

    return {
        "total_xp": total_xp,
        "xp_per_player": xp_per_player,
        "results": results,
        "any_level_ups": any_level_ups,
    }
