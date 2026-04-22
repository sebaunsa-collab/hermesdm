"""
bot/spell_manager.py — D&D 5e Spell System.
SpellSlotTrack and SPELLS registry with slot consumption.
"""
from __future__ import annotations

import random

# ── Spell dataclass ─────────────────────────────────────────────────────────

class Spell:
    __slots__ = ('name', 'level', 'school', 'casting_time', 'range', 'duration',
                 'description', 'damage', 'damage_type', 'heal', 'save', 'aoe', 'notes')

    def __init__(self, name: str, level: int, school: str, casting_time: str,
                 range: str, duration: str, description: str,
                 damage: str | None = None, damage_type: str | None = None,
                 heal: int | None = None, save: str | None = None,
                 aoe: str | None = None, notes: str | None = None):
        self.name = name
        self.level = level
        self.school = school
        self.casting_time = casting_time
        self.range = range
        self.duration = duration
        self.description = description
        self.damage = damage
        self.damage_type = damage_type
        self.heal = heal
        self.save = save
        self.aoe = aoe
        self.notes = notes


# ── Spell registry ─────────────────────────────────────────────────────────

SPELLS: dict[str, Spell] = {}

def _s(name, level, school, casting_time, rng, duration, desc,
       damage=None, dtype=None, heal=None, save=None, aoe=None, notes=None):
    SPELLS[name.lower()] = Spell(name, level, school, casting_time, rng,
                                  duration, desc, damage, dtype, heal, save, aoe, notes)

# Cantrips
_s("Fire Bolt", 0, "Evocation", "1 action", "120 ft", "Instantaneous",
   "You hurl a mote of fire.", damage="1d10", dtype="fire")
_s("Sacred Flame", 0, "Evocation", "1 action", "60 ft", "Instantaneous",
   "Flame-like radiance descends.", damage="1d8", dtype="radiant", save="DEX")
_s("Shocking Grasp", 0, "Evocation", "1 action", "Touch", "Instantaneous",
   "Lightning springs from your hand.", damage="1d8", dtype="lightning", notes="Adv vs metal armor")
_s("Mind Sliver", 0, "Enchantment", "1 action", "60 ft", "1 round",
   "Psychic energy strikes the mind.", damage="1d6", dtype="psychic", save="INT")
_s("Thaumaturgy", 0, "Transmutation", "1 action", "30 ft", "Up to 1 minute",
   "Minor wonder of power.")

# Level 1
_s("Magic Missile", 1, "Evocation", "1 action", "120 ft", "Instantaneous",
   "Three force darts.", damage="3x(1d4+1)", dtype="force")
_s("Guiding Bolt", 1, "Evocation", "1 action", "120 ft", "1 round",
   "Light streaks forward.", damage="4d6", dtype="radiant", notes="Adv on next attack")
_s("Healing Word", 1, "Evocation", "Bonus action", "60 ft", "Instantaneous",
   "Creature regains HP.", heal=8)
_s("Thunderwave", 1, "Evocation", "1 action", "Self (15-ft)", "Instantaneous",
   "Thundering wave.", damage="2d8", dtype="thunder", save="CON", aoe="15-ft cube")
_s("Shield", 1, "Abjuration", "Reaction", "Self", "1 round",
   "Invisible barrier.", notes="+5 AC until next turn")
_s("Sleep", 1, "Enchantment", "1 action", "90 ft", "1 minute",
   "Creatures fall unconscious.", notes="Lowest HP affected first")

# Level 2
_s("Scorching Ray", 2, "Evocation", "1 action", "120 ft", "Instantaneous",
   "Three fire rays.", damage="2d6", dtype="fire", notes="3 ranged attacks")
_s("Spiritual Weapon", 2, "Evocation", "Bonus action", "60 ft", "1 minute",
   "Spectral weapon.", damage="1d8", dtype="force", notes="No concentration")
_s("Hold Person", 2, "Enchantment", "1 action", "60 ft", "Up to 1 minute",
   "Target paralyzed.", save="WIS", notes="Concentration")
_s("Misty Step", 2, "Conjuration", "Bonus action", "Self", "Instantaneous",
   "Teleport 30 ft.", notes="No op attacks")

# Level 3
_s("Fireball", 3, "Evocation", "1 action", "150 ft", "Instantaneous",
   "Explosion of fire.", damage="8d6", dtype="fire", save="DEX", aoe="20-ft radius")
_s("Counterspell", 3, "Abjuration", "Reaction", "60 ft", "Instantaneous",
   "Interrupt spellcasting.", notes="Auto-fail vs 4th+")
_s("Mass Healing Word", 3, "Evocation", "Bonus action", "60 ft", "Instantaneous",
   "6 creatures heal.", heal=8)

# Level 4
_s("Polymorph", 4, "Transmutation", "1 action", "60 ft", "Up to 1 hour",
   "Transform into a beast.", save="WIS", notes="Concentration")
_s("Wall of Fire", 4, "Evocation", "1 action", "120 ft", "Up to 1 minute",
   "Wall of flame.", damage="5d8", dtype="fire", save="DEX", notes="Concentration")

# Level 5
_s("Cone of Cold", 5, "Evocation", "1 action", "Self (60-ft)", "Instantaneous",
   "Cold breath.", damage="8d8", dtype="cold", save="CON", aoe="60-ft cone")
_s("Flame Strike", 5, "Evocation", "1 action", "60 ft", "Instantaneous",
   "Column of fire.", damage="4d6", dtype="fire+rad", save="DEX", aoe="10-ft cylinder")


# ── Public API ──────────────────────────────────────────────────────────────

def get_spell(name: str) -> Spell | None:
    return SPELLS.get(name.lower())

def list_spells_by_level(level: int) -> list[Spell]:
    return [s for s in SPELLS.values() if s.level == level]

def _roll_damage(damage: str, dtype: str | None) -> tuple[int, str]:
    """Roll damage string like '8d6' or '3x(1d4+1)'. Returns (total, line)."""
    try:
        expr = damage.lower().strip()
        if 'x(' in expr:
            count_str, rest = expr.split('x(')
            rest = rest.rstrip(')')
            bonus = 0
            if '+' in rest:
                sides_part, bonus_str = rest.split('+')
                bonus = int(bonus_str)
                sides = int(sides_part)
            else:
                sides = int(rest)
            count = int(count_str)
            rolls = [random.randint(1, sides) for _ in range(count)]
            total = sum(rolls) + bonus
            line = f"{damage} = **{total}** {dtype or ''}"
        else:
            count_str, sides_str = expr.split('d')
            count = int(count_str) if count_str else 1
            sides = int(sides_str)
            rolls = [random.randint(1, sides) for _ in range(count)]
            total = sum(rolls)
            line = f"{damage} = **{total}** {dtype or ''}"
        return total, line
    except Exception:
        return 0, f"{damage} {dtype or ''}"

def cast_spell(char, spell_name: str, target: str = "") -> str:
    """Cast a spell — consumes slot if level >= 1. Returns narrative."""
    spell = get_spell(spell_name)
    if not spell:
        return f"Unknown spell: {spell_name}"

    # Slot check
    if spell.level > 0:
        if not char.spell_slots.use(spell.level):
            char.spell_slots.available(spell.level)
            return (f"✗ {char.name} cannot cast {spell.name} — "
                    f"no Lv{spell.level} slots. {char.spell_slots.format_all()}")
        slot_note = f" (Lv{spell.level} slot used — {char.spell_slots.format_all()})"
    else:
        slot_note = " (cantrip)"

    # Build response
    lines = [f"✨ **{char.name} casts {spell.name}**{slot_note}"]

    if spell.damage:
        _, dmg_line = _roll_damage(spell.damage, spell.damage_type)
        if spell.save:
            lines.append(f"{dmg_line} — {target} vs {spell.save} save")
        else:
            lines.append(f"{dmg_line} to {target or 'target'}")

    if spell.heal:
        healed = random.randint(1, 4) + 4
        old = char.current if hasattr(char, 'current') else char.hp.current
        char.current = min(char.max if hasattr(char, 'max') else char.hp.max, old + healed)
        lines.append(f"🩹 Restores **{healed}** HP to {target or char.name}")

    if spell.notes:
        lines.append(f"_({spell.notes})_")

    return "\n".join(lines)

def format_spell_list(char) -> str:
    """Spell list with available slots."""
    lines = ["*Spellbook*"]
    any_slots = False
    for lvl in range(1, 6):
        spells = list_spells_by_level(lvl)
        if not spells:
            continue
        avail = char.spell_slots.available(lvl)
        total = char.spell_slots.total[lvl - 1]
        any_slots = True
        lines.append(f"\nLv{lvl} **[{avail}/{total}]**")
        for s in spells:
            lines.append(f"  • {s.name}")
    if not any_slots:
        lines.append("\n_No slots available. Take a long rest._")
    return "\n".join(lines)
