"""
conditions.py — D&D 5e Conditions System for HermesDM.

Defines all 15 official conditions and their mechanical effects.
Each condition has:
- stat_save: which stat to save against (or None for passive conditions)
- dc_type: how the DC is determined (e.g., "caster_dc", "fixed", "end_of_turn")
- effects: list of mechanical effects on gameplay
- duration: how long it lasts (rounds, saves, etc.)
- removal: how to remove it (save, rest, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConditionEffect:
    """A single mechanical effect of a condition."""
    description: str
    attack_modifier: int = 0  # modifier to attack rolls (-2 = disadvantage equivalent)
    ac_modifier: int = 0  # modifier to AC
    speed_multiplier: float = 1.0  # multiplier to movement speed
    damage_per_turn: int = 0  # automatic damage per turn
    advantage_on_saves: list = field(default_factory=list)  # stat names
    disadvantage_on_saves: list = field(default_factory=list)  # stat names
    disadvantage_on_attacks: bool = False  # disadvantage on all attack rolls
    auto_fail_strength_save: bool = False
    auto_fail_dex_save: bool = False
    incapacitated: bool = False  # can't take actions
    invisible: bool = False  # can't be seen
    advantage_on_attacks_against: bool = False  # attacks against this creature have advantage


@dataclass
class ConditionDef:
    """Definition of a D&D 5e condition."""
    name: str
    description: str
    stat_save: Optional[str] = None  # "str", "dex", "con", "int", "wis", "cha" or None
    save_dc_type: str = "end_of_turn"  # "end_of_turn", "action", " caster_dc", "fixed"
    effects: ConditionEffect = field(default_factory=ConditionEffect)
    duration_type: str = "save_ends"  # "save_ends", "rounds", "permanent", "rest"
    duration_rounds: int = 0  # 0 = save ends
    removal_save: Optional[str] = None  # which save removes it
    removal_save_dc: int = 10  # DC for removal save


# ── All 15 D&D 5e Conditions ──────────────────────────────────────────────

CONDITIONS: dict[str, ConditionDef] = {
    "blinded": ConditionDef(
        name="Blinded",
        description="Can't see. Auto-fail DEX/STR saves vs visual. Attacks against have advantage. Attacks have disadvantage.",
        effects=ConditionEffect(
            disadvantage_on_attacks=True,
            advantage_on_attacks_against=True,
            auto_fail_dex_save=True,
            auto_fail_strength_save=True,
            description="Can't see anything"
        ),
    ),
    "charmed": ConditionDef(
        name="Charmed",
        description="Can't attack the charmer. Charmer has advantage on social checks.",
        effects=ConditionEffect(
            incapacitated=True,
            description="Can't harm the charmer"
        ),
    ),
    "deafened": ConditionDef(
        name="Deafened",
        description="Can't hear. Auto-fail WIS/CHA saves that rely on hearing.",
        effects=ConditionEffect(
            description="Can't hear anything"
        ),
    ),
    "frightened": ConditionDef(
        name="Frightened",
        description="Disadvantage on attacks and saves while source is visible.",
        effects=ConditionEffect(
            disadvantage_on_attacks=True,
            description="Terrified — disadvantage while source visible"
        ),
    ),
    "grappled": ConditionDef(
        name="Grappled",
        description="Speed becomes 0. Can't benefit from bonus speed.",
        effects=ConditionEffect(
            speed_multiplier=0.0,
            description="Grappled — can't move"
        ),
    ),
    "incapacitated": ConditionDef(
        name="Incapacitated",
        description="Can't take actions or reactions.",
        effects=ConditionEffect(
            incapacitated=True,
            description="Can't take actions or reactions"
        ),
    ),
    "invisible": ConditionDef(
        name="Invisible",
        description="Can't be seen. Attacks against have disadvantage. Your attacks have advantage.",
        effects=ConditionEffect(
            invisible=True,
            advantage_on_attacks_against=True,
            description="Invisible — can't be seen"
        ),
    ),
    "paralyzed": ConditionDef(
        name="Paralyzed",
        description="Incapacitated + auto-fail STR/DEX. Attacks against within 5ft are crits.",
        effects=ConditionEffect(
            incapacitated=True,
            auto_fail_strength_save=True,
            auto_fail_dex_save=True,
            advantage_on_attacks_against=True,
            description="Paralyzed — can't move or act"
        ),
    ),
    "petrified": ConditionDef(
        name="Petrified",
        description="Weight x10. Incapacitated. Resistance to all damage. Immune to poison/disease.",
        effects=ConditionEffect(
            incapacitated=True,
            description="Turned to stone"
        ),
    ),
    "poisoned": ConditionDef(
        name="Poisoned",
        description="Disadvantage on attacks and ability checks.",
        effects=ConditionEffect(
            disadvantage_on_attacks=True,
            description="Poisoned — disadvantage on attacks and checks"
        ),
    ),
    "prone": ConditionDef(
        name="Prone",
        description="Disadvantage on attacks. Melee attacks against have advantage. Ranged attacks against have disadvantage.",
        effects=ConditionEffect(
            disadvantage_on_attacks=True,
            advantage_on_attacks_against=True,
            description="Lying on the ground"
        ),
    ),
    "restrained": ConditionDef(
        name="Restrained",
        description="Speed 0. Attacks against have advantage. Your attacks have disadvantage. DEX saves at disadvantage.",
        effects=ConditionEffect(
            speed_multiplier=0.0,
            disadvantage_on_attacks=True,
            advantage_on_attacks_against=True,
            auto_fail_dex_save=True,
            description="Restrained — can't move"
        ),
    ),
    "stunned": ConditionDef(
        name="Stunned",
        description="Incapacitated + auto-fail STR/DEX. Attacks against have advantage.",
        effects=ConditionEffect(
            incapacitated=True,
            auto_fail_strength_save=True,
            auto_fail_dex_save=True,
            advantage_on_attacks_against=True,
            description="Stunned — can't do anything"
        ),
    ),
    "unconscious": ConditionDef(
        name="Unconscious",
        description="Incapacitated + drops prone + auto-fail STR/DEX. Attacks within 5ft auto-hit (crits).",
        effects=ConditionEffect(
            incapacitated=True,
            auto_fail_strength_save=True,
            auto_fail_dex_save=True,
            advantage_on_attacks_against=True,
            description="Unconscious — drops prone, auto-crit within 5ft"
        ),
    ),
    "exhaustion": ConditionDef(
        name="Exhaustion",
        description="6 levels. Each level: disadvantage on checks, halved speed, disadvantage on attacks/saves, max HP halved, speed 0, death.",
        effects=ConditionEffect(
            disadvantage_on_attacks=True,
            description="Exhausted — multiple penalties per level"
        ),
    ),
}


def get_condition(name: str) -> Optional[ConditionDef]:
    """Get a condition definition by name."""
    return CONDITIONS.get(name.lower())


def get_condition_effects(name: str) -> Optional[ConditionEffect]:
    """Get the mechanical effects of a condition."""
    cond = get_condition(name)
    return cond.effects if cond else None


def has_disadvantage_on_attacks(char) -> bool:
    """Check if a character has disadvantage on attacks due to conditions."""
    for cond_name in getattr(char, 'conditions', []):
        cond = get_condition(cond_name)
        if cond and cond.effects.disadvantage_on_attacks:
            return True
    return False


def has_advantage_on_attacks_against(char) -> bool:
    """Check if attacks against a character have advantage due to conditions."""
    for cond_name in getattr(char, 'conditions', []):
        cond = get_condition(cond_name)
        if cond and cond.effects.advantage_on_attacks_against:
            return True
    return False


def is_incapacitated(char) -> bool:
    """Check if a character is incapacitated."""
    for cond_name in getattr(char, 'conditions', []):
        cond = get_condition(cond_name)
        if cond and cond.effects.incapacitated:
            return True
    return False


def get_condition_summary(char) -> str:
    """Get a human-readable summary of a character's conditions."""
    conditions = getattr(char, 'conditions', [])
    if not conditions:
        return "No conditions"
    parts = []
    for cond_name in conditions:
        cond = get_condition(cond_name)
        if cond:
            parts.append(f"• {cond.name}: {cond.effects.description}")
        else:
            parts.append(f"• {cond_name}")
    return "\n".join(parts)


def roll_saving_throw(char, stat: str, dc: int, advantage: bool = False, disadvantage: bool = False) -> dict:
    """Roll a saving throw for a character.

    Args:
        char: Character object
        stat: "str", "dex", "con", "int", "wis", "cha"
        dc: Difficulty class to beat
        advantage: roll 2d20, take higher
        disadvantage: roll 2d20, take lower

    Returns:
        dict with roll, total, success, stat_mod, proficiency, breakdown
    """
    import random

    stat_mod = char.mod(stat) if hasattr(char, 'mod') else 0
    proficiency = char.proficiency_bonus if hasattr(char, 'proficiency_bonus') else 0
    # Check if proficient in this save
    save_name = f"{stat}_save"
    if hasattr(char, 'is_proficient') and char.is_proficient(save_name):
        prof = proficiency
    else:
        prof = 0

    # Roll d20
    if advantage and not disadvantage:
        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)
        roll = max(roll1, roll2)
        breakdown = f"max({roll1},{roll2})"
    elif disadvantage and not advantage:
        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)
        roll = min(roll1, roll2)
        breakdown = f"min({roll1},{roll2})"
    else:
        roll = random.randint(1, 20)
        breakdown = str(roll)

    total = roll + stat_mod + prof
    success = total >= dc

    return {
        "roll": roll,
        "stat_mod": stat_mod,
        "proficiency": prof,
        "total": total,
        "dc": dc,
        "success": success,
        "breakdown": f"{breakdown} + {stat_mod} + {prof} = {total} vs DC {dc}",
    }


def check_condition_removal(char, condition_name: str) -> dict:
    """Check if a character can remove a condition via saving throw.

    Returns:
        dict with removed (bool), roll result, etc.
    """
    cond = get_condition(condition_name)
    if not cond:
        return {"removed": False, "reason": "Unknown condition"}

    if cond.removal_save:
        result = roll_saving_throw(char, cond.removal_save, cond.removal_save_dc)
        if result["success"]:
            char.remove_condition(condition_name)
            return {"removed": True, "roll": result}
        return {"removed": False, "roll": result}

    return {"removed": False, "reason": "Condition can't be removed by save"}
