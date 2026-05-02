"""
spellbook.py — D&D 5e Spellbook Management for HermesDM.

Two types of spellcasters in D&D 5e:

1. KNOWN SPELLS (Bard, Sorcerer, Warlock, Paladin, Ranger, EK, AT):
   - Know a FIXED number of spells at each level
   - Always have those spells available (no preparation needed)
   - Learn new spells when leveling up

2. PREPARED SPELLS (Wizard, Cleric, Druid, Artificer):
   - Have a spellbook with ALL spells learned
   - Must PREPARE a subset each day (after long rest)
   - Prepared count = spellcasting ability mod + level (min 1)

This module manages the spellbook, known/prepared tracking, and
provides the data layer for /spells and /prepare commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from bot.spell_manager import SPELLS, Spell, get_spell


# -- Class Spell Lists (D&D 5e SRD) ------------------------------------------

# Spells available per class at each level
# Format: {class_name: {spell_level: [spell_names]}}

CLASS_SPELL_LISTS: dict[str, dict[int, list[str]]] = {
    "wizard": {
        0: ["fire bolt", "shocking grasp", "mind sliver", "thaumaturgy",
            "light", "minor illusion", "prestidigitation", "ray of frost",
            "acid splash", "mage hand"],
        1: ["magic missile", "shield", "sleep", "detect magic", "find familiar",
            "mage armor", "burning hands", "chromatic orb", "feather fall",
            "fog cloud", "ice knife", "identify", "longstrider", "catapult"],
        2: ["scorching ray", "hold person", "misty step", "invisibility",
            "mirror image", "web", "detect thoughts", "darkness",
            "shatter", "blur", "magic weapon", "invisibility"],
        3: ["fireball", "counterspell", "fly", "lightning bolt", "dispel magic",
            "haste", "slow", "stinking cloud", "tongues", "remove curse",
            "clairvoyance", "sleet storm", "fireball"],
        4: ["polymorph", "wall of fire", "dimension door", "greater invisibility",
            "banishment", "arcane eye", "black tentacles", "stone shape"],
        5: ["cone of cold", "wall of force", "telekinesis", "scrying",
            "animate objects", "hold monster", "passwall", "teleportation circle"],
    },
    "cleric": {
        0: ["sacred flame", "thaumaturgy", "spare the dying", "guidance",
            "toll the dead", "mending", "resistance", "light"],
        1: ["healing word", "guiding bolt", "bless", "shield of faith",
            "cure wounds", "sanctuary", "command", "inflict wounds"],
        2: ["spiritual weapon", "hold person", "lesser restoration",
            "silence", "prayer of healing", "augury"],
        3: ["fireball", "revivify", "spirit guardians", "mass healing word",
            "dispel magic", "beacon of hope"],
        4: ["banishment", "death ward", "guardian of faith", "freedom of movement"],
        5: ["flame strike", "mass cure wounds", "banishing smite", "dispel evil"],
    },
    "sorcerer": {
        0: ["fire bolt", "shocking grasp", "mind sliver", "thaumaturgy",
            "light", "minor illusion", "prestidigitation"],
        1: ["magic missile", "shield", "thunderwave", "chromatic orb",
            "burning hands", "detect magic", "fog cloud"],
        2: ["scorching ray", "hold person", "misty step", "invisibility",
            "mirror image", "darkness", "shatter", "web"],
        3: ["fireball", "counterspell", "lightning bolt", "haste",
            "slow", "dispel magic", "stinking cloud"],
        4: ["polymorph", "wall of fire", "dimension door", "greater invisibility",
            "banishment", "blight"],
        5: ["cone of cold", "animate objects", "hold monster", "telekinesis"],
    },
    "bard": {
        0: ["prestidigitation", "vicious mockery", "mage hand", "light",
            "minor illusion", "mending"],
        1: ["charm person", "cure wounds", "disguise self", "healing word",
            "heroism", "silvery barbs", "faerie fire", "Thunderwave"],
        2: ["invisibility", "hold person", "suggestion", "mirror image",
            "detect thoughts", "enhance ability", "calm emotions"],
        3: ["counterspell", "fly", "hypnotic pattern", "dispel magic",
            "leomund's tiny hut", "sending", "tongues"],
        4: ["dimension door", "polymorph", "greater invisibility", "banishment"],
        5: ["hold monster", "modify memory", "teleportation circle", "animate objects"],
    },
    "warlock": {
        0: ["eldritch blast", "minor illusion", "thaumaturgy", "prestidigitation",
            "mind sliver", "booming blade", "green-flame blade"],
        1: ["hex", "armor of agathys", "charm person", "hellish rebuke",
            "witch bolt", "dissonant whispers", "wrathful smite"],
        2: ["hold person", "invisibility", "misty step", "darkness",
            "mirror image", "shatter", "crown of madness"],
        3: ["fireball", "counterspell", "hypnotic pattern", "vampiric touch",
            "remove curse", "spirit shroud"],
        4: ["banishment", "dimension door", "greater invisibility", "blight"],
        5: ["hold monster", "circle of death", "enervation", "teleportation circle"],
    },
    "druid": {
        0: ["druidcraft", "thorn whip", "produce flame", "guidance",
            "shillelagh", "poison spray", "mending"],
        1: ["entangle", "faerie fire", "thunderwave", "healing word",
            "cure wounds", "speak with animals", "goodberry"],
        2: ["hold person", "flaming sphere", "moonbeam", "spike growth",
            "lesser restoration", "animal messenger"],
        3: ["fireball", "call lightning", "conjure animals", "plant growth",
            "dispel magic", "revivify", "wind wall"],
        4: ["polymorph", "wall of fire", "freedom of movement", "ice storm"],
        5: ["cone of cold", "animate objects", "mass cure wounds", "insect plague"],
    },
    "paladin": {
        0: [],  # Paladins don't get cantrips
        1: ["bless", "command", "cure wounds", "divine favor", "heroism",
            "protection from evil", "shield of faith", "smiting"],
        2: ["lesser restoration", "hold person", "zone of truth", "magic weapon"],
        3: ["revivify", "dispel magic", "remove curse", "spirit guardians"],
        4: ["death ward", "banishment", "freedom of movement"],
        5: ["flame strike", "banishing smite", "mass cure wounds"],
    },
    "ranger": {
        0: [],
        1: ["entangle", "goodberry", "hunters mark", "cure wounds",
            "speak with animals", "alarm"],
        2: ["lesser restoration", "pass without trace", "spike growth",
            "animal messenger", "hold person"],
        3: ["conjure animals", "plant growth", "revivify", "non-detection"],
        4: ["freedom of movement", "grasping vine", "stoneskin"],
        5: ["commune with nature", "tree stride"],
    },
}


# -- Spellcaster Classification ----------------------------------------------

SPELLCASTING_ABILITY = {
    "wizard": "int",
    "cleric": "wis",
    "druid": "wis",
    "sorcerer": "cha",
    "bard": "cha",
    "warlock": "cha",
    "paladin": "wis",
    "ranger": "wis",
    "artificer": "int",
    "fighter": None,
    "rogue": None,
    "barbarian": None,
    "monk": None,
}

# Classes that use PREPARED spellcasting (must prepare after long rest)
PREPARED_CASTERS = {"wizard", "cleric", "druid", "artificer"}

# Classes that use KNOWN spellcasting (always available)
KNOWN_CASTERS = {"bard", "sorcerer", "warlock", "paladin", "ranger"}


# -- Data Classes ------------------------------------------------------------

@dataclass
class Spellbook:
    """
    Manages a character's spellbook: all learned spells, known/prepared.

    For KNOWN casters: spells_known IS the spellbook (no preparation needed)
    For PREPARED casters: spellbook is all learned, prepared is the daily subset
    """
    # All spells the character has learned (level -> [spell_names])
    spellbook: dict[int, list[str]] = field(default_factory=dict)
    # Spells known (for known casters) -- same as spellbook
    spells_known: dict[int, list[str]] = field(default_factory=dict)
    # Spells prepared today (for prepared casters) -- level -> [spell_names]
    prepared: dict[int, list[str]] = field(default_factory=dict)
    # Spellcasting class
    caster_class: str = "wizard"
    # Number of cantrips known
    cantrips_known: int = 0

    def is_prepared_caster(self) -> bool:
        return self.caster_class in PREPARED_CASTERS

    def is_known_caster(self) -> bool:
        return self.caster_class in KNOWN_CASTERS

    def get_prepared_count_for_level(self, spell_level: int, char_level: int,
                                      ability_mod: int) -> int:
        """
        How many spells can be prepared at this spell level.
        Total prepared = ability_mod + char_level (min 1)
        Distributed across levels by spell slot availability.
        """
        max_prepared = max(1, ability_mod + char_level)
        return max_prepared

    def get_all_available_spells(self) -> dict[int, list[str]]:
        """Get all spells available to cast (known or prepared, depending on class)."""
        if self.is_known_caster():
            return dict(self.spells_known)
        else:
            return dict(self.prepared)

    def get_available_at_level(self, spell_level: int) -> list[str]:
        """Get available spells at a specific spell level."""
        available = self.get_all_available_spells()
        return available.get(spell_level, [])

    def get_cantrips(self) -> list[str]:
        """Get all known cantrips."""
        return self.spellbook.get(0, [])

    def learn_spell(self, spell_name: str, spell_level: int) -> bool:
        """Add a spell to the spellbook. Returns True if successful."""
        if spell_level not in self.spellbook:
            self.spellbook[spell_level] = []

        if spell_name.lower() not in [s.lower() for s in self.spellbook[spell_level]]:
            self.spellbook[spell_level].append(spell_name)
        else:
            return False  # Already known

        # For known casters, also add to spells_known
        if self.is_known_caster():
            if spell_level not in self.spells_known:
                self.spells_known[spell_level] = []
            if spell_name.lower() not in [s.lower() for s in self.spells_known[spell_level]]:
                self.spells_known[spell_level].append(spell_name)

        return True

    def prepare_spell(self, spell_name: str, spell_level: int) -> bool:
        """Prepare a spell (for prepared casters only)."""
        if not self.is_prepared_caster():
            return False

        # Must be in spellbook first
        book_spells = [s.lower() for s in self.spellbook.get(spell_level, [])]
        if spell_name.lower() not in book_spells:
            return False

        if spell_level not in self.prepared:
            self.prepared[spell_level] = []

        if spell_name.lower() not in [s.lower() for s in self.prepared[spell_level]]:
            self.prepared[spell_level].append(spell_name)
            return True
        return False  # Already prepared

    def unprepare_spell(self, spell_name: str, spell_level: int) -> bool:
        """Remove a spell from prepared list."""
        if not self.is_prepared_caster():
            return False
        if spell_level in self.prepared:
            self.prepared[spell_level] = [
                s for s in self.prepared[spell_level]
                if s.lower() != spell_name.lower()
            ]
            return True
        return False

    def unprepare_all(self) -> None:
        """Clear all prepared spells (for long rest preparation)."""
        self.prepared.clear()

    def format_spellbook(self) -> str:
        """Human-readable spellbook display."""
        lines = [f"📖 **Spellbook** ({self.caster_class.title()})"]

        # Cantrips
        cantrips = self.spellbook.get(0, [])
        if cantrips:
            lines.append(f"\n**Cantrips ({len(cantrips)}):**")
            for s in cantrips:
                lines.append(f"  \u2022 {s}")

        # Spells by level
        for lvl in range(1, 10):
            book_spells = self.spellbook.get(lvl, [])
            if not book_spells:
                continue

            if self.is_prepared_caster():
                prepared = self.prepared.get(lvl, [])
                prepared_names = [s.lower() for s in prepared]
                lines.append(f"\n**Level {lvl} Spells ({len(book_spells)} known, {len(prepared)} prepared):**")
                for s in book_spells:
                    marker = "\u2705" if s.lower() in prepared_names else "\u2b1c"
                    lines.append(f"  {marker} {s}")
            else:
                lines.append(f"\n**Level {lvl} Spells ({len(book_spells)}):**")
                for s in book_spells:
                    lines.append(f"  \u2022 {s}")

        return "\n".join(lines)

    def format_preparation(self) -> str:
        """Show preparation status (for prepared casters)."""
        if not self.is_prepared_caster():
            return "Your class does not require spell preparation."

        lines = ["\u267f **Spell Preparation**"]
        lines.append("_Use /prepare <spell name> to prepare a spell._")
        lines.append("_Spells reset on long rest._\n")

        for lvl in range(1, 10):
            book_spells = self.spellbook.get(lvl, [])
            prepared = self.prepared.get(lvl, [])
            if not book_spells:
                continue

            prepared_names = [s.lower() for s in prepared]
            lines.append(f"**Level {lvl}:** ({len(prepared)} prepared)")
            for s in book_spells:
                marker = "\u2705" if s.lower() in prepared_names else "\u2b1c"
                lines.append(f"  {marker} {s}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "spellbook": {str(k): v for k, v in self.spellbook.items()},
            "spells_known": {str(k): v for k, v in self.spells_known.items()},
            "prepared": {str(k): v for k, v in self.prepared.items()},
            "caster_class": self.caster_class,
            "cantrips_known": self.cantrips_known,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Spellbook":
        def _parse_dict(d):
            if not d:
                return {}
            return {int(k): v for k, v in d.items()}

        return cls(
            spellbook=_parse_dict(data.get("spellbook", {})),
            spells_known=_parse_dict(data.get("spells_known", {})),
            prepared=_parse_dict(data.get("prepared", {})),
            caster_class=data.get("caster_class", "wizard"),
            cantrips_known=data.get("cantrips_known", 0),
        )


# -- Spell List Queries ------------------------------------------------------

def get_class_spell_list(class_name: str, spell_level: int) -> list[str]:
    """Get available spells for a class at a given spell level."""
    class_spells = CLASS_SPELL_LISTS.get(class_name, {})
    return class_spells.get(spell_level, [])


def get_cantrip_count_for_level(class_name: str, level: int) -> int:
    """Number of cantrips known at character level."""
    counts = {
        "wizard": {1: 3, 4: 4, 10: 5},
        "sorcerer": {1: 4, 10: 5},
        "bard": {1: 2, 10: 3},
        "cleric": {1: 3, 10: 4},
        "druid": {1: 2, 10: 3},
        "warlock": {1: 2, 4: 3},
        "artificer": {1: 2, 10: 3},
    }
    class_counts = counts.get(class_name, {})
    result = 0
    for threshold in sorted(class_counts.keys()):
        if level >= threshold:
            result = class_counts[threshold]
    return max(2, result)


def get_spells_known_count(class_name: str, level: int) -> dict[int, int]:
    """
    Number of spells known per spell level at character level.
    Only for known casters.
    """
    # Bard spells known (PHB pg 53)
    bard = {
        1: {1: 4}, 2: {1: 4}, 3: {1: 4, 2: 2}, 4: {1: 5, 2: 3},
        5: {1: 4, 2: 3, 3: 2}, 6: {1: 4, 2: 3, 3: 3},
        7: {1: 4, 2: 3, 3: 3, 4: 1}, 8: {1: 4, 2: 3, 3: 3, 4: 2},
        9: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}, 10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    }

    # Sorcerer spells known (PHB pg 101)
    sorcerer = {
        1: {1: 2}, 2: {1: 2}, 3: {1: 3, 2: 1}, 4: {1: 4, 2: 2},
        5: {1: 4, 2: 3, 3: 1}, 6: {1: 4, 2: 3, 3: 2},
        7: {1: 4, 2: 3, 3: 2, 4: 1}, 8: {1: 4, 2: 3, 3: 3, 4: 2},
        9: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}, 10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    }

    # Warlock spells known (PHB pg 106)
    warlock = {
        1: {1: 2}, 2: {1: 3}, 3: {1: 4}, 4: {1: 5}, 5: {1: 5, 2: 1},
        6: {1: 5, 2: 2}, 7: {1: 5, 2: 2, 3: 1}, 8: {1: 5, 2: 2, 3: 2},
        9: {1: 5, 2: 2, 3: 2, 4: 1}, 10: {1: 5, 2: 2, 3: 2, 4: 2},
    }

    tables = {"bard": bard, "sorcerer": sorcerer, "warlock": warlock}
    table = tables.get(class_name, {})
    clamped = max(1, min(level, 20))
    return table.get(clamped, {})


def create_spellbook_for_class(class_name: str, level: int) -> Spellbook:
    """
    Create a Spellbook for a character class at a given level.
    Auto-populates spells known/prepared for the level.
    """
    class_name = class_name.lower()
    sb = Spellbook(caster_class=class_name)

    # Cantrips
    cantrip_count = get_cantrip_count_for_level(class_name, level)
    sb.cantrips_known = cantrip_count
    cantrips = get_class_spell_list(class_name, 0)[:cantrip_count]
    sb.spellbook[0] = cantrips

    if class_name in KNOWN_CASTERS:
        # Known casters: populate spells_known from class list
        known_counts = get_spells_known_count(class_name, level)
        for spell_lvl, count in known_counts.items():
            available = get_class_spell_list(class_name, spell_lvl)
            chosen = available[:count]
            sb.spellbook[spell_lvl] = chosen
            sb.spells_known[spell_lvl] = chosen
    elif class_name in PREPARED_CASTERS:
        # Prepared casters: all spells from class list up to max slot level
        from dm.spell_engine import get_spell_slots, CASTER_TYPE_MAP
        caster_type = CASTER_TYPE_MAP.get(class_name, "full")
        slots = get_spell_slots(level, caster_type)
        max_spell_level = max((lvl for lvl, cnt in slots.items() if cnt > 0), default=0)

        for spell_lvl in range(0, max_spell_level + 1):
            available = get_class_spell_list(class_name, spell_lvl)
            sb.spellbook[spell_lvl] = available

    return sb


# -- Convenience Functions ---------------------------------------------------

def cast_from_spellbook(char, spell_name: str, target: str = "") -> str:
    """
    Cast a spell from the character's spellbook.
    Checks known/prepared status, consumes slot, returns narrative.
    """
    from bot.spell_manager import cast_spell, get_spell

    spell = get_spell(spell_name)
    if not spell:
        return f"Unknown spell: {spell_name}"

    # Check availability based on class type
    spellbook_data = getattr(char, 'spellbook', None)
    if spellbook_data and isinstance(spellbook_data, Spellbook):
        available = spellbook_data.get_available_at_level(spell.level)
        if spell.level > 0 and spell_name.lower() not in [s.lower() for s in available]:
            return f"{char.name} does not know or have prepared {spell.name}."

    # Delegate to existing cast_spell
    return cast_spell(char, spell_name, target)
