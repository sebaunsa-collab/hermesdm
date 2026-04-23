"""
character_sheet.py — Player character definition.
Stats, HP, AC, inventory, conditions, death saves.
"""
from dataclasses import dataclass, field

# D&D 5e stat array (1-20, 10=human baseline)
STATS = ["str", "dex", "con", "int", "wis", "cha"]

SKILL_BY_STAT = {
    "str": ["athletics"],
    "dex": ["acrobatics", "sleight_of_hand", "stealth"],
    "con": [],
    "int": ["arcana", "history", "investigation", "nature", "religion"],
    "wis": ["animal_handling", "insight", "medicine", "perception", "survival"],
    "cha": ["deception", "intimidation", "performance", "persuasion"]
}

ALL_SKILLS = []
for skills in SKILL_BY_STAT.values():
    ALL_SKILLS.extend(skills)


# ── XP & Leveling constants (D&D 5e oficial) ────────────────────────────────

XP_THRESHOLDS = [
    0, 300, 900, 2700, 6500, 14000, 23000, 34000,
    48000, 64000, 85000, 100000, 120000, 140000,
    165000, 195000, 225000, 265000, 305000, 355000,
]

# Index = nivel. prof_bonus[nivel] → bonus. nivel 0 = 0 (no usado).
_PROFICIENCY_BONUS = [
    0,  # 0 (unused)
    2, 2, 2, 2,  # niveles 1-4
    3, 3, 3, 3,  # niveles 5-8
    4, 4, 4, 4,  # niveles 9-12
    5, 5, 5, 5,  # niveles 13-16
    6, 6, 6,     # niveles 17-20
]


def get_proficiency_bonus(level: int) -> int:
    """Retorna proficiency bonus para un nivel dado (D&D 5e)."""
    if level < 1:
        return 0
    if level > 20:
        level = 20
    return _PROFICIENCY_BONUS[level]


def get_xp_to_next_level(level: int) -> int | None:
    """XP necesaria para pasar del nivel actual al siguiente. None si es nivel 20."""
    if level < 1:
        return XP_THRESHOLDS[1]
    if level >= 20:
        return None
    return XP_THRESHOLDS[level]  # nivel 1 → 300, nivel 5 → 14000


def get_level_from_xp(xp: int) -> int:
    """Retorna el nivel correspondiente a una cantidad de XP."""
    level = 1
    for threshold in XP_THRESHOLDS[1:]:
        if xp >= threshold:
            level += 1
        else:
            break
    return min(level, 20)


# ── HP ─────────────────────────────────────────────────────────────────────

@dataclass
class HP:
    max: int = 10
    current: int = 10
    temp: int = 0
    hit_die_faces: int = 8     # d4/d6/d8/d10/d12 según clase
    hit_dice_remaining: int = 0  # cuántos hit dice Disponibles para descanso

    def apply_damage(self, dmg: int) -> int:
        """Apply damage. Returns actual HP lost (accounts for temp)."""
        total = self.current + self.temp
        remaining = total - dmg
        if remaining < 0:
            remaining = 0
        actual_loss = total - remaining
        original_temp = self.temp
        self.temp = max(0, self.temp - dmg)
        excess = max(0, dmg - original_temp)
        self.current = max(0, self.current - excess)
        return actual_loss

    def heal(self, amount: int) -> int:
        if self.current >= self.max:
            return 0
        old = self.current
        self.current = min(self.max, self.current + amount)
        return self.current - old

    def apply_temp_hp(self, amount: int) -> None:
        self.temp = max(self.temp, amount)

    def level_up(self, con_mod: int) -> int:
        """
        Sube de nivel. Retorna HP ganado.
        HP gained = hit_die_roll + con_mod (mínimo 1).
        """
        import random
        roll = random.randint(1, self.hit_die_faces)
        gained = roll + con_mod
        self.max += max(1, gained)
        self.current = self.max  # cur-full al subir
        self.hit_dice_remaining += 1  # gana 1 hit die por nivel
        return max(1, gained)

    def full_heal(self) -> None:
        """Curación completa."""
        self.current = self.max
        self.temp = 0

    def short_rest(self, con_mod: int = 0) -> int:
        """
        Short rest: recupera 1 hit die + con_mod HP (hasta hit_dice_remaining).
        Retorna HP recuperado.
        """
        import random
        if self.hit_dice_remaining <= 0:
            return 0
        recovered = random.randint(1, self.hit_die_faces) + con_mod
        self.hit_dice_remaining -= 1
        self.current = min(self.max, self.current + recovered)
        return recovered

    def to_dict(self) -> dict:
        return {
            "max": self.max,
            "current": self.current,
            "temp": self.temp,
            "hit_die_faces": self.hit_die_faces,
            "hit_dice_remaining": self.hit_dice_remaining,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HP":
        return cls(
            max=data["max"],
            current=data["current"],
            temp=data.get("temp", 0),
            hit_die_faces=data.get("hit_die_faces", 8),
            hit_dice_remaining=data.get("hit_dice_remaining", 0),
        )


# ── Item ────────────────────────────────────────────────────────────────────

RARITIES = {"common", "uncommon", "rare", "very rare", "legendary", "artifact"}


@dataclass
class Item:
    name: str
    quantity: int = 1
    weight: float = 0.0          # pounds
    rarity: str = "common"       # common/uncommon/rare/very rare/legendary/artifact
    is_equipped: bool = False
    armor_class: int | None = None  # si es armadura
    attack_bonus: int | None = None  # si es arma
    damage_dice: str | None = None   # "1d8" si es arma
    description: str = ""
    is_magic: bool = False
    is_consumable: bool = False  # poción, comida, etc.

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "quantity": self.quantity,
            "weight": self.weight,
            "rarity": self.rarity,
            "is_equipped": self.is_equipped,
            "armor_class": self.armor_class,
            "attack_bonus": self.attack_bonus,
            "damage_dice": self.damage_dice,
            "description": self.description,
            "is_magic": self.is_magic,
            "is_consumable": self.is_consumable,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        return cls(
            name=data["name"],
            quantity=data.get("quantity", 1),
            weight=data.get("weight", 0.0),
            rarity=data.get("rarity", "common"),
            is_equipped=data.get("is_equipped", False),
            armor_class=data.get("armor_class"),
            attack_bonus=data.get("attack_bonus"),
            damage_dice=data.get("damage_dice"),
            description=data.get("description", ""),
            is_magic=data.get("is_magic", False),
            is_consumable=data.get("is_consumable", False),
        )


# ── Level-up helper ────────────────────────────────────────────────────────

def level_up_character(char: "Character", hit_die_faces: int) -> dict:
    """
    Sube de nivel a un personaje.
    Retorna dict con {old_level, new_level, hp_gained, prof_bonus, slots}.
    """
    old_level = char.level
    con_mod = char.mod("con")
    gained = char.hp.level_up(con_mod)
    char.level += 1
    char.proficiency_bonus = get_proficiency_bonus(char.level)

    # Recalculate spell slots
    slot_changes = {}
    if char.player_class in SPELL_SLOTS_BY_CLASS:
        table = SPELL_SLOTS_BY_CLASS[char.player_class]
        for spell_lvl, total in table.items():
            char.spell_slots.total[spell_lvl - 1] = total
            slot_changes[spell_lvl] = total

    return {
        "old_level": old_level,
        "new_level": char.level,
        "hp_gained": gained,
        "prof_bonus": char.proficiency_bonus,
        "slots": slot_changes,
    }


@dataclass
class DeathSaves:
    successes: int = 0
    failures: int = 0

    def reset(self) -> None:
        self.successes = 0
        self.failures = 0

    def roll(self) -> tuple[bool, bool]:
        """
        Roll a death saving throw.
        Returns (stabilized_or_hp_restored, dead).
        """
        import random
        roll = random.randint(1, 20)
        if roll == 1:
            self.failures += 2
        elif roll == 20:
            self.successes += 3  # Instant stabilize + 1 HP
        elif roll >= 10:
            self.successes += 1
        else:
            self.failures += 1

        if self.failures >= 3:
            return False, True  # dead
        if self.successes >= 3:
            return True, False  # stabilized
        return False, False

    def format(self) -> str:
        """Death save status as emoji string."""
        successes = "✓" * self.successes + "⬛" * (3 - self.successes)
        failures = "✗" * self.failures + "⬛" * (3 - self.failures)
        return f"{successes} | {failures}"


# ── Spell Slots (D&D 5e) ───────────────────────────────────────────────────

@dataclass
class SpellSlotTrack:
    """Tracks used spell slots per spell level (1-9)."""
    total: list[int] = field(default_factory=lambda: [0]*9)
    used: list[int] = field(default_factory=lambda: [0]*9)

    def available(self, level: int) -> int:
        """Slots available at given level (1-9)."""
        if not (1 <= level <= 9):
            return 0
        return max(0, self.total[level-1] - self.used[level-1])

    def use(self, level: int) -> bool:
        """Use one slot at level. Returns True if successful."""
        if self.available(level) <= 0:
            return False
        self.used[level-1] += 1
        return True

    def restore_all(self) -> None:
        """Restore all slots (long rest)."""
        self.used = [0] * 9

    def restore_level(self, level: int, count: int = 1) -> None:
        """Restore 'count' slots at level (short rest for warlock)."""
        if not (1 <= level <= 9):
            return
        self.used[level-1] = max(0, self.used[level-1] - count)

    def format_all(self) -> str:
        """Human-readable slot status."""
        parts = []
        for lvl in range(1, 10):
            t = self.total[lvl-1]
            if t > 0:
                a = self.available(lvl)
                parts.append(f"Lv{lvl}: {a}/{t}")
        return " | ".join(parts) if parts else "No spell slots"


# Spell slot progression by character level (D&D 5e PHB, pg 165)
# Full caster: spell level = character level
# dict = {spell_level: [slots_at_char_Lv1, Lv2, Lv3, ...Lv20]}
# 0 = no slots at that spell level for that character level
_SPELL_SLOTS_PROGRESSION: dict[int, list[int]] = {
    #    Lv1 Lv2 Lv3 Lv4 Lv5 Lv6 Lv7 Lv8 Lv9 Lv10...Lv20
    1: [2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
    2: [0, 0, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3],
    3: [0, 0, 0, 0, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3],
    4: [0, 0, 0, 0, 0, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    5: [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    6: [0] * 20,
    7: [0] * 20,
    8: [0] * 20,
    9: [0] * 20,
}

_SPELL_SLOTS_HALF_PROGRESSION: dict[int, list[int]] = {
    # Paladin/Ranger: spellcasting level = char_level // 2
    1: [0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    2: [0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    3: [0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    4: [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    5: [0] * 20,
}


def _get_spell_slots_for_level(
    caster_type: str, char_level: int
) -> list[int]:
    """
    Return total slots list [Lv1..Lv9] for a caster at char_level (1-indexed).
    Full caster: spellcasting_level = char_level
    Half caster: spellcasting_level = char_level // 2
    Warlock: handled separately via _get_warlock_slots
    """
    if caster_type == "warlock":
        return _get_warlock_slots(char_level)

    # char_level is 1-indexed (1-20)
    idx = max(1, min(char_level, 20)) - 1  # 0-indexed

    if caster_type in ("paladin", "ranger"):
        progression = _SPELL_SLOTS_HALF_PROGRESSION
        char_level // 2
    else:
        progression = _SPELL_SLOTS_PROGRESSION

    result = [0] * 9
    for spell_lvl in range(1, 10):
        row = progression.get(spell_lvl, [0] * 20)
        if idx < len(row):
            result[spell_lvl - 1] = row[idx]

    return result


def _get_warlock_slots(char_level: int) -> list[int]:
    """Return total slots list for warlock at char_level. Only highest level has slots."""
    result = [0] * 9
    if char_level < 1 or char_level > 20:
        return result
    count, lvl = _WARLOCK_PACT[char_level]
    result[lvl - 1] = count
    return result
# Warlock: Pact Magic (D&D 5e PHB)
# dict = {character_level: (slot_count, spell_level_of_slot)}
# All pact slots are the SAME spell level (max level based on character level)
_WARLOCK_PACT: dict[int, tuple[int, int]] = {
    1: (1, 1),  2: (2, 1),  3: (2, 2),  4: (2, 2),
    5: (3, 2),  6: (3, 2),  7: (4, 3),  8: (4, 3),
    9: (3, 3), 10: (3, 3), 11: (4, 4), 12: (4, 4),
   13: (3, 4), 14: (3, 4), 15: (4, 5), 16: (4, 5),
   17: (5, 5), 18: (5, 5), 19: (4, 5), 20: (5, 5),
}

# NOTE: Warlock handled via _get_warlock_slots, not in this dict.
# For reference: full caster max slots = {1:4, 2:3, 3:3, 4:3, 5:3, 6:2, 7:2, 8:1, 9:1}
SPELL_SLOTS_BY_CLASS: dict[str, dict[int, int]] = {
    # Full casters — actual slots derived from _get_spell_slots_for_level
    "wizard": {},
    "cleric": {},
    "druid": {},
    "sorcerer": {},
    "bard": {},
    # Half casters — actual slots derived from _get_spell_slots_for_level
    "paladin": {},
    "ranger": {},
}


# Valid conditions
VALID_CONDITIONS = {
    "blinded", "charmed", "deafened", "frightened", "grappled",
    "incapacitated", "invisible", "paralyzed", "petrified", "poisoned",
    "prone", "restrained", "stunned", "unconscious", "exhaustion"
}

@dataclass
class Character:
    name: str
    player_class: str  # fighter, wizard, rogue, etc.
    level: int = 1
    stats: dict = field(default_factory=lambda: {
        "str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10
    })
    hp: HP = field(default_factory=HP)
    ac: int = 10
    proficiencies: list = field(default_factory=list)  # skills[] + saving_throws[]
    inventory: list = field(default_factory=list)  # Item[]
    conditions: list = field(default_factory=list)  # condition names
    death_saves: DeathSaves = field(default_factory=DeathSaves)
    spell_slots: SpellSlotTrack = field(default_factory=SpellSlotTrack)
    proficiency_bonus: int = 2

    # XP / Leveling
    xp: int = 0

    # Inventory
    carried_gold: int = 0
    weight_carried: float = 0.0
    inventory_slots: int = 10
    equipped_weapon: str | None = None
    equipped_armor: str | None = None

    # --- Acciones que duran hasta el siguiente turno ---
    has_disengaged: bool = False
    has_dashed: bool = False
    is_helping: bool = False
    helping_target: str | None = None
    is_dodging: bool = False
    is_hiding: bool = False

    # Ready action
    pending_ready: dict | None = None  # {"action": "...", "trigger": "..."}

    # Inventory tracking
    object_uses: dict = field(default_factory=lambda: {"potion": 2, "torch": 3})

    def mod(self, stat: str) -> int:
        """Modifier for a stat (floor((stat-10)/2))."""
        if self.stats is None:
            return 0
        return (self.stats.get(stat, 10) - 10) // 2

    def mod_str(self, stat: str) -> str:
        m = self.mod(stat)
        return f"{m:+d}"

    def ac_with_dex(self) -> int:
        """AC = 10 + dex mod (basic, no armor)."""
        return 10 + self.mod("dex")

    def is_proficient(self, skill_or_save: str) -> bool:
        return skill_or_save in self.proficiencies

    def attack_bonus(self) -> int:
        """Base attack bonus = strength/dex mod + proficiency."""
        return self.mod("str")

    def save_dc(self) -> int:
        """Spell save DC = 8 + prof + mod."""
        return 8 + self.proficiency_bonus + self.mod("int")

    def add_condition(self, cond: str) -> None:
        if cond.lower() in VALID_CONDITIONS:
            self.conditions.append(cond.lower())

    def remove_condition(self, cond: str) -> None:
        if cond.lower() in self.conditions:
            self.conditions.remove(cond.lower())

    def add_item(self, item: Item) -> None:
        for existing in self.inventory:
            if existing.name == item.name:
                existing.quantity += item.quantity
                return
        if len(self.inventory) < self.inventory_slots:
            self.inventory.append(item)

    def remove_item(self, name: str, qty: int = 1) -> bool:
        for item in self.inventory:
            if item.name == name:
                item.quantity -= qty
                if item.quantity <= 0:
                    self.inventory.remove(item)
                return True
        return False

    def long_rest(self) -> dict:
        """
        Long rest (8h): restore all HP, all hit dice, all spell slots.
        D&D 5e: All HP restored, all hit dice restored, death saves reset.
        """
        self.hp.current = self.hp.max
        self.hp.temp = 0
        self.hp.hit_dice_remaining = self.level  # Full hit dice restored
        self.death_saves.reset()
        self.spell_slots.restore_all()
        self.conditions.clear()
        return {
            "hp_restored": self.hp.max,
            "hit_dice_restored": self.level,
            "spell_slots": self.spell_slots.format_all(),
        }

    def short_rest(self) -> dict:
        """
        Short rest (1h): recover 1 hit die + CON mod HP.
        Warlock Pact Magic: restore ALL pact magic slots (short rest regen).
        """
        con_mod = self.stats.get("con", 10) // 2 - 5
        recovered = self.hp.short_rest(con_mod)
        # Warlock: all pact slots come back on short rest
        if self.player_class == "warlock":
            self.spell_slots.restore_all()
        return {"hp_recovered": recovered}

    def get_weight_carried(self) -> float:
        """Calculate total weight of inventory."""
        return sum(item.weight * item.quantity for item in self.inventory)

    def get_carrying_capacity(self) -> float:
        """STR × 15 lbs (D&D 5e standard)."""
        return self.stats.get("str", 10) * 15

    def is_encumbered(self) -> bool:
        """Over carrying capacity."""
        return self.get_weight_carried() > self.get_carrying_capacity()

    def take_damage(self, amount: int) -> tuple[bool, str]:
        """
        Apply damage. If HP drops to 0, character falls unconscious and
        death saves are reset (ready for new death saves).
        If HP > 0 afterward, death saves reset automatically.
        Returns (unconscious, narrative_message).
        """
        if amount <= 0:
            return False, f"{self.name} takes no damage."

        temp_absorbed = min(self.hp.temp, amount)
        remaining = amount - temp_absorbed
        self.hp.temp = max(0, self.hp.temp - temp_absorbed)

        if remaining > 0:
            self.hp.current -= remaining

        if self.hp.current <= 0:
            self.hp.current = 0
            self.death_saves.reset()  # Fresh death saves when falling
            self.conditions.append("unconscious")
            unconscious_msg = (
                f"{self.name} drops to 0 HP and falls **unconscious**! "
                f"Death saves: {self.death_saves.format()}"
            )
            return True, unconscious_msg

        # HP > 0 — clear death saves automatically
        if self.death_saves.successes > 0 or self.death_saves.failures > 0:
            self.death_saves.reset()

        if "unconscious" in self.conditions:
            self.conditions.remove("unconscious")

        return False, (
            f"{self.name} takes {remaining} damage "
            f"({self.hp.current}/{self.hp.max} HP)"
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "class": self.player_class,
            "level": self.level,
            "xp": self.xp,
            "stats": self.stats,
            "hp": self.hp.to_dict(),
            "ac": self.ac,
            "proficiencies": self.proficiencies,
            "inventory": [i.to_dict() for i in self.inventory],
            "conditions": self.conditions,
            "death_saves": {
                "successes": self.death_saves.successes,
                "failures": self.death_saves.failures
            },
            "carried_gold": self.carried_gold,
            "equipped_weapon": self.equipped_weapon,
            "equipped_armor": self.equipped_armor,
            "has_disengaged": self.has_disengaged,
            "has_dashed": self.has_dashed,
            "is_helping": self.is_helping,
            "helping_target": self.helping_target,
            "is_dodging": self.is_dodging,
            "is_hiding": self.is_hiding,
            "pending_ready": self.pending_ready,
            "object_uses": self.object_uses,
            "spell_slots": {
                "total": self.spell_slots.total,
                "used": self.spell_slots.used,
            },
        }

    @classmethod
    def from_dict(cls, data: dict, campaign_classes: dict | None = None) -> "Character":
        """Recreate Character from serialized dict (e.g. from campaign state JSON)."""
        hp = HP.from_dict(data.get("hp", {}))
        ds = DeathSaves(
            successes=data.get("death_saves", {}).get("successes", 0),
            failures=data.get("death_saves", {}).get("failures", 0)
        )
        # Load spell slots if present
        slot_data = data.get("spell_slots", {})
        slots = SpellSlotTrack(
            total=slot_data.get("total", [0]*9),
            used=slot_data.get("used", [0]*9),
        )
        inv = [Item.from_dict(i) for i in data.get("inventory", [])]
        c = cls(
            name=data["name"],
            player_class=data["class"],
            level=data.get("level", 1),
            xp=data.get("xp", 0),
            stats=data.get("stats") or {},
            hp=hp,
            ac=data.get("ac", 10),
            proficiencies=data.get("proficiencies", []),
            inventory=inv,
            conditions=data.get("conditions", []),
            death_saves=ds,
            spell_slots=slots,
            carried_gold=data.get("carried_gold", 0),
            equipped_weapon=data.get("equipped_weapon"),
            equipped_armor=data.get("equipped_armor"),
        )
        return c


# ── Dynamic class helpers ─────────────────────────────────

def _to_ascii(text: str) -> str:
    """Strip accents/diacritics: 'Médico' → 'Medico', 'ñ' → 'n'."""
    accents = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u",
        "à": "a", "è": "e", "ì": "i", "ò": "o", "ù": "u",
        "ä": "a", "ë": "e", "ï": "i", "ö": "o",
        "ñ": "n", "ç": "c",
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U",
        "À": "A", "È": "E", "Ì": "I", "Ò": "O", "Ù": "U",
        "Ä": "A", "Ë": "E", "Ï": "I", "Ö": "O",
        "Ñ": "N", "Ç": "C",
    }
    return "".join(accents.get(ch, ch) for ch in text)


def normalize_class_name(class_name: str) -> str:
    """'Médico' → 'medico', 'Fire Mage' → 'fire_mage'. Lowercase + sin acentos."""
    return _to_ascii(class_name).lower().replace(" ", "_").replace("-", "_")


def resolve_class(class_name: str, campaign_classes: dict | None) -> dict | None:
    """
    Busca una clase por nombre en:
    1. campaign_classes (específico de la campaña)
    2. CLASS_DEFINITIONS (defaults D&D 5e)
    Retorna None si no existe.
    """
    normalized = normalize_class_name(class_name)
    if campaign_classes and normalized in campaign_classes:
        return campaign_classes[normalized]
    if normalized in CLASS_DEFINITIONS:
        return CLASS_DEFINITIONS[normalized]
    return None


# ── Class definitions (D&D 5e defaults) ─────────────────────────────────────

CLASS_DEFINITIONS = {
    "barbarian": {
        "hit_die": 12,
        "primary_stat": "str",
        "secondary_stat": "con",
        "skills": ["animal_handling", "athletics", "insight", "intimidation", "nature", "perception", "survival"],
        "num_skills": 2,
        "proficiency_bonus": 2,
        "features": ["Rage (2/rest, +2 damage)", "Reckless Attack"],
        "spellcasting": False,
    },
    "bard": {
        "hit_die": 8,
        "primary_stat": "cha",
        "secondary_stat": "dex",
        "skills": list(ALL_SKILLS),
        "num_skills": 3,
        "proficiency_bonus": 2,
        "features": ["Bardic Inspiration", "Spellcasting (CHA)"],
        "spellcasting": True,
    },
    "cleric": {
        "hit_die": 8,
        "primary_stat": "wis",
        "skills": ["history", "insight", "medicine", "persuasion", "religion"],
        "num_skills": 2,
        "proficiency_bonus": 2,
        "features": ["Spellcasting (WIS)", "Divine Domain"],
        "spellcasting": True,
    },
    "druid": {
        "hit_die": 8,
        "primary_stat": "wis",
        "secondary_stat": "int",
        "skills": ["arcana", "animal_handling", "insight", "medicine", "nature", "perception", "religion", "survival"],
        "num_skills": 2,
        "proficiency_bonus": 2,
        "features": ["Wild Shape", "Spellcasting (WIS)"],
        "spellcasting": True,
    },
    "fighter": {
        "hit_die": 10,
        "primary_stat": "str",
        "secondary_stat": "con",
        "skills": ["athletics", "history", "insight", "perception", "survival"],
        "num_skills": 2,
        "proficiency_bonus": 2,
        "features": ["Fighting Style", "Second Wind"],
        "spellcasting": False,
    },
    "monk": {
        "hit_die": 8,
        "primary_stat": "dex",
        "secondary_stat": "wis",
        "skills": ["acrobatics", "athletics", "history", "insight", "religion", "stealth"],
        "num_skills": 2,
        "proficiency_bonus": 2,
        "features": ["Martial Arts (d4)", "Ki (2 points)"],
        "spellcasting": False,
    },
    "paladin": {
        "hit_die": 10,
        "primary_stat": "str",
        "secondary_stat": "cha",
        "skills": ["athletics", "insight", "intimidation", "medicine", "persuasion", "religion"],
        "num_skills": 2,
        "proficiency_bonus": 2,
        "features": ["Divine Smite", "Lay on Hands"],
        "spellcasting": True,
    },
    "ranger": {
        "hit_die": 10,
        "primary_stat": "dex",
        "secondary_stat": "wis",
        "skills": ["animal_handling", "athletics", "insight", "investigation", "nature", "perception", "stealth", "survival"],
        "num_skills": 3,
        "proficiency_bonus": 2,
        "features": ["Favored Enemy", "Natural Explorer"],
        "spellcasting": True,
    },
    "rogue": {
        "hit_die": 8,
        "primary_stat": "dex",
        "secondary_stat": "int",
        "skills": ["acrobatics", "athletics", "deception", "insight", "intimidation", "investigation", "perception", "performance", "persuasion", "sleight_of_hand", "stealth"],
        "num_skills": 4,
        "proficiency_bonus": 2,
        "features": ["Sneak Attack (1d6)", "Cunning Action"],
        "spellcasting": False,
    },
    "sorcerer": {
        "hit_die": 6,
        "primary_stat": "cha",
        "secondary_stat": "con",
        "skills": ["arcana", "deception", "insight", "intimidation", "persuasion", "religion"],
        "num_skills": 2,
        "proficiency_bonus": 2,
        "features": ["Sorcery Points", "Metamagic"],
        "spellcasting": True,
    },
    "warlock": {
        "hit_die": 8,
        "primary_stat": "cha",
        "secondary_stat": "dex",
        "skills": ["arcana", "deception", "history", "intimidation", "investigation", "nature", "religion"],
        "num_skills": 2,
        "proficiency_bonus": 2,
        "features": ["Eldritch Invocations", "Pact Magic"],
        "spellcasting": True,
    },
    "wizard": {
        "hit_die": 6,
        "primary_stat": "int",
        "secondary_stat": "wis",
        "skills": ["arcana", "history", "insight", "investigation", "medicine", "religion"],
        "num_skills": 2,
        "proficiency_bonus": 2,
        "features": ["Spellcasting (INT)", "Arcane Recovery"],
        "spellcasting": True,
    },
    "artificer": {
        "hit_die": 8,
        "primary_stat": "int",
        "secondary_stat": "con",
        "skills": ["arcana", "history", "insight", "investigation", "medicine", "sleight_of_hand", "thieves'_tool", "wis"],
        "num_skills": 2,
        "proficiency_bonus": 2,
        "features": ["Infusions", "Magical Tinkering"],
        "spellcasting": True,
    },
}


def create_character(name: str, player_class: str, level: int = 1,
                     stat_array: dict | None = None,
                     campaign_classes: dict | None = None) -> Character:
    """
    Factory: create a character with D&D 5e rules.

    Args:
        name: Character name.
        player_class: Class name (e.g. 'fighter', 'Médico', 'survivor').
        level: Character level (default 1).
        stat_array: Override stat values (standard array: STR 15, DEX 14, CON 13, INT 12, WIS 10, CHA 8).
        campaign_classes: Optional dict of campaign-specific classes.
    """
    cls_def = resolve_class(player_class, campaign_classes)
    if cls_def is None:
        raise ValueError(f"Clase desconocida: '{player_class}'")

    hit_die = cls_def["hit_die"]

    stats = stat_array or {
        "str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8
    }
    con_mod = ((stats.get("con", 10) - 10) // 2)
    max_hp = hit_die + con_mod

    hp = HP(
        max=max_hp,
        current=max_hp,
        temp=0,
        hit_die_faces=hit_die,
        hit_dice_remaining=1,  # 1 hit die al empezar
    )

    char = Character(
        name=name,
        player_class=normalize_class_name(player_class),
        level=level,
        stats=stats,
        hp=hp,
        ac=10,
        proficiencies=[],
        inventory_slots=10 + (level // 2),
    )

    # Initialize spell slots for spellcasters
    cls_key = normalize_class_name(player_class)
    if cls_key in SPELL_SLOTS_BY_CLASS:
        char.spell_slots.total = _get_spell_slots_for_level(cls_key, level)
    elif cls_key == "warlock":
        char.spell_slots.total = _get_warlock_slots(level)

    return char


if __name__ == "__main__":
    c = create_character("Valdric", "fighter", level=1)
    print(f"Character: {c.name} ({c.player_class})")
    print(f"HP: {c.hp.current}/{c.hp.max} ({c.hp.hit_die_faces} hit die)")
    print(f"AC: {c.ac_with_dex()}")
    print(f"Level: {c.level} | XP: {c.xp}/{get_xp_to_next_level(c.level)}")
    print(f"Proficiency: +{c.proficiency_bonus}")
    print("Stats: {s: c.mod_str(s) for s in STATS}")
    print(f"Attack bonus: {c.attack_bonus():+d}")
