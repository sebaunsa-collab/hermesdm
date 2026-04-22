"""
bot/__init__.py — HermesDM bot package.

Exports key classes and the app builder for external use.
"""

from bot.character_sheet import (
    ALL_SKILLS,
    CLASS_DEFINITIONS,
    HP,
    RARITIES,
    SKILL_BY_STAT,
    STATS,
    VALID_CONDITIONS,
    XP_THRESHOLDS,
    Character,
    DeathSaves,
    Item,
    create_character,
    get_level_from_xp,
    get_proficiency_bonus,
    get_xp_to_next_level,
    level_up_character,
    normalize_class_name,
    resolve_class,
)
from bot.combat_engine import (
    SPELLS,
    WEAPON_DAMAGE,
    apply_damage,
    get_weapon_damage,
    parse_dice,
    resolve_attack,
    resolve_spell,
    roll_dice,
)
from bot.dice_engine import (
    DiceError,
    resolve_check,
    roll,
)
from bot.skill_checks import (
    ABILITIES,
    DC_TABLE,
    describe_check,
    get_dc,
    resolve_save,
    resolve_skill_check,
)
from bot.telegram_handler import (
    ChatState,
    Settings,
    build_app,
    settings,
)
from bot.turn_manager import (
    Combatant,
    CombatState,
    combat_summary,
    delay,
    end_combat,
    next_turn,
    remove_combatant,
    roll_initiative,
    start_combat,
)

__all__ = [
    # character_sheet
    "Character",
    "Item",
    "HP",
    "DeathSaves",
    "create_character",
    "CLASS_DEFINITIONS",
    "STATS",
    "SKILL_BY_STAT",
    "ALL_SKILLS",
    "normalize_class_name",
    "resolve_class",
    "VALID_CONDITIONS",
    "RARITIES",
    "XP_THRESHOLDS",
    "get_level_from_xp",
    "get_proficiency_bonus",
    "get_xp_to_next_level",
    "level_up_character",
    # combat_engine
    "resolve_attack",
    "apply_damage",
    "resolve_spell",
    "SPELLS",
    "roll_dice",
    "parse_dice",
    "get_weapon_damage",
    "WEAPON_DAMAGE",
    # dice_engine
    "roll",
    "resolve_check",
    "DiceError",
    # turn_manager
    "CombatState",
    "Combatant",
    "start_combat",
    "next_turn",
    "end_combat",
    "combat_summary",
    "roll_initiative",
    "delay",
    "remove_combatant",
    # skill_checks
    "resolve_skill_check",
    "resolve_save",
    "describe_check",
    "get_dc",
    "DC_TABLE",
    "ABILITIES",
    # telegram_handler
    "ChatState",
    "Settings",
    "settings",
    "build_app",
]
