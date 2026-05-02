"""
loot_tables.py — D&D 5e loot and treasure tables.

Provides coin tables by CR bracket, gem and art object tables,
magic item tables A-I, and roll functions for individual/hoard treasure.
Part of Scene Director's content engine suite.

Design: Pure data + random rolls. Seeded RNG for determinism.
"""

from __future__ import annotations

import random
from typing import List, Optional

# ── CR bracket helper ─────────────────────────────────────────────────────

def _cr_bracket(cr: float) -> tuple:
    """Map CR to a bracket tuple for table lookups."""
    if cr <= 0.25:
        return (0, 0.25)
    elif cr <= 0.5:
        return (0.26, 0.5)
    elif cr <= 1:
        return (0.51, 1)
    elif cr <= 4:
        return (1.01, 4)
    elif cr <= 7:
        return (4.01, 7)
    elif cr <= 10:
        return (7.01, 10)
    elif cr <= 14:
        return (10.01, 14)
    else:
        return (14.01, 30)


# ── COIN_TABLE: (min_cr, max_cr) → {denom: dice_formula} ──────────────
# Each formula gives the dice to roll for an INDIVIDUAL creature's treasure.
COIN_TABLE: dict = {
    (0, 0.25):    {"cp": "3d6", "sp": "0", "ep": "0", "gp": "0", "pp": "0"},
    (0.26, 0.5):  {"cp": "3d6", "sp": "1d6", "ep": "0", "gp": "0", "pp": "0"},
    (0.51, 1):    {"cp": "6d6", "sp": "2d6", "ep": "1d4", "gp": "0", "pp": "0"},
    (1.01, 4):    {"cp": "8d6", "sp": "4d6", "ep": "2d6", "gp": "1d4", "pp": "0"},
    (4.01, 7):    {"cp": "0", "sp": "6d6", "ep": "4d6", "gp": "2d6", "pp": "1d4"},
    (7.01, 10):   {"cp": "0", "sp": "8d6", "ep": "6d6", "gp": "4d6", "pp": "2d6"},
    (10.01, 14):  {"cp": "0", "sp": "0", "ep": "8d6", "gp": "6d6", "pp": "4d6"},
    (14.01, 30):  {"cp": "0", "sp": "0", "ep": "0", "gp": "8d6", "pp": "6d6"},
}

# ── GEM_TABLE: CR bracket → list of {name, value} ───────────────────────

GEM_TABLE: dict = {
    (0, 0.25): [
        {"name": "Battered quartz fragment", "value": 5},
        {"name": "Chipped agate", "value": 7},
        {"name": "Dull turquoise", "value": 8},
        {"name": "Rough azurite", "value": 5},
        {"name": "Mossy malachite", "value": 10},
    ],
    (0.26, 0.5): [
        {"name": "Small jade", "value": 15},
        {"name": "Bloodstone", "value": 20},
        {"name": "Citrine", "value": 15},
        {"name": "Freshwater pearl", "value": 12},
        {"name": "Onyx", "value": 18},
    ],
    (0.51, 1): [
        {"name": "Amber", "value": 25},
        {"name": "Moonstone", "value": 30},
        {"name": "Carnelian", "value": 25},
        {"name": "Quartz crystal", "value": 20},
        {"name": "Zircon", "value": 35},
    ],
    (1.01, 4): [
        {"name": "Garnet", "value": 50},
        {"name": "Amethyst", "value": 45},
        {"name": "Pearl", "value": 60},
        {"name": "Jade eye", "value": 55},
        {"name": "Spinel", "value": 40},
    ],
    (4.01, 7): [
        {"name": "Topaz", "value": 100},
        {"name": "Opal", "value": 120},
        {"name": "Jet", "value": 80},
        {"name": "Star rose quartz", "value": 110},
        {"name": "Peridot", "value": 90},
    ],
    (7.01, 10): [
        {"name": "Sapphire", "value": 250},
        {"name": "Emerald", "value": 300},
        {"name": "Jacinth", "value": 200},
        {"name": "Black pearl", "value": 280},
        {"name": "Star ruby", "value": 350},
    ],
    (10.01, 14): [
        {"name": "Diamond", "value": 500},
        {"name": "Fire opal", "value": 600},
        {"name": "Blue sapphire", "value": 550},
        {"name": "Jacinth (large)", "value": 480},
        {"name": "Ruby", "value": 650},
    ],
    (14.01, 30): [
        {"name": "Flawless diamond", "value": 1000},
        {"name": "King's ruby", "value": 1200},
        {"name": "Star sapphire", "value": 1500},
        {"name": "Black diamond", "value": 2000},
        {"name": "Heart of the mountain", "value": 2500},
    ],
}

# ── ART_TABLE: CR bracket → list of {name, value} ─────────────────────

ART_TABLE: dict = {
    (0, 0.25): [
        {"name": "Crude wooden carving", "value": 5},
        {"name": "Tattered tapestry scrap", "value": 8},
        {"name": "Clay pendant", "value": 6},
        {"name": "Rusted iron ring", "value": 4},
        {"name": "Woven bead necklace", "value": 7},
    ],
    (0.26, 0.5): [
        {"name": "Silver locket", "value": 20},
        {"name": "Embroidered silk handkerchief", "value": 15},
        {"name": "Carved bone figurine", "value": 18},
        {"name": "Painted ceramic urn", "value": 22},
        {"name": "Bronze statuette", "value": 25},
    ],
    (0.51, 1): [
        {"name": "Gold-plated chalice", "value": 40},
        {"name": "Leather-bound journal", "value": 30},
        {"name": "Silver music box", "value": 45},
        {"name": "Framed portrait", "value": 35},
        {"name": "Jeweled hairpin", "value": 50},
    ],
    (1.01, 4): [
        {"name": "Gold ring set with bloodstones", "value": 75},
        {"name": "Ivory statuette", "value": 90},
        {"name": "Silk robe with gold embroidery", "value": 100},
        {"name": "Silver ewer", "value": 80},
        {"name": "Carved harp of exotic wood", "value": 120},
    ],
    (4.01, 7): [
        {"name": "Gold cup with jade inlay", "value": 200},
        {"name": "Marble bust", "value": 250},
        {"name": "Elven tapestry", "value": 180},
        {"name": "Enameled gold bracelet", "value": 220},
        {"name": "Dwarven ceremonial axe (decorative)", "value": 300},
    ],
    (7.01, 10): [
        {"name": "Gold crown with gemstones", "value": 500},
        {"name": "Ornate platinum scepter", "value": 600},
        {"name": "Ancient dragon-scale shield (decorative)", "value": 450},
        {"name": "Obsidian chess set with silver pieces", "value": 400},
        {"name": "Gilded dragon skull", "value": 550},
    ],
    (10.01, 14): [
        {"name": "Jeweled platinum crown", "value": 1000},
        {"name": "Solid gold idol", "value": 1200},
        {"name": "Legendary painting by a master", "value": 800},
        {"name": "Mithral chain coif (decorative)", "value": 950},
        {"name": "Ancient tome with jeweled cover", "value": 1100},
    ],
    (14.01, 30): [
        {"name": "Emperor's crown with dragon gems", "value": 2500},
        {"name": "Adamantine throne fragment", "value": 3000},
        {"name": "Dragon Queen's scepter", "value": 5000},
        {"name": "Primordial artifact (decorative)", "value": 4000},
        {"name": "Sphere of annihilation replica", "value": 3500},
    ],
}

# ── MAGIC_ITEM_TABLES: TABLE_A through TABLE_I ──────────────────────────

MAGIC_ITEM_TABLES: dict = {
    "TABLE_A": [
        {"name": "Potion of Healing", "rarity": "common", "type": "potion",
         "description": "Regains 2d4+2 hit points when drunk.", "attunement": False},
        {"name": "Spell Scroll (Cantrip)", "rarity": "common", "type": "scroll",
         "description": "Contains a single cantrip spell.", "attunement": False},
        {"name": "Potion of Climbing", "rarity": "common", "type": "potion",
         "description": "Grants climbing speed equal to walking speed for 1 hour.", "attunement": False},
        {"name": "Potion of Animal Friendship", "rarity": "common", "type": "potion",
         "description": "Cast Animal Friendship when drunk.", "attunement": False},
        {"name": "Scroll of Protection (Fey)", "rarity": "common", "type": "scroll",
         "description": "Creates a barrier against fey.", "attunement": False},
        {"name": "Spellwrought Tattoo (1st level)", "rarity": "common", "type": "wondrous",
         "description": "Tattoo containing a single 1st-level spell.", "attunement": False},
        {"name": "Feather Token (Anchor)", "rarity": "common", "type": "wondrous",
         "description": "Transforms into a ship anchor on command.", "attunement": False},
    ],
    "TABLE_B": [
        {"name": "Potion of Greater Healing", "rarity": "uncommon", "type": "potion",
         "description": "Regains 4d4+4 hit points when drunk.", "attunement": False},
        {"name": "Potion of Fire Breath", "rarity": "uncommon", "type": "potion",
         "description": "Exhale fire for 1 hour (3 uses).", "attunement": False},
        {"name": "Potion of Resistance (Fire)", "rarity": "uncommon", "type": "potion",
         "description": "Resistance to fire damage for 1 hour.", "attunement": False},
        {"name": "Spell Scroll (2nd level)", "rarity": "uncommon", "type": "scroll",
         "description": "Contains a 2nd-level spell.", "attunement": False},
        {"name": "Ammunition +1", "rarity": "uncommon", "type": "ammunition",
         "description": "10 pieces of +1 ammunition.", "attunement": False},
        {"name": "Dust of Disappearance", "rarity": "uncommon", "type": "wondrous",
         "description": "Turns invisible when scattered.", "attunement": False},
        {"name": "Elemental Gem (Fire)", "rarity": "uncommon", "type": "wondrous",
         "description": "Summons a fire elemental when broken.", "attunement": False},
        {"name": "Wand of Magic Detection", "rarity": "uncommon", "type": "wand",
         "description": "3 charges. Cast Detect Magic.", "attunement": False},
    ],
    "TABLE_C": [
        {"name": "Potion of Superior Healing", "rarity": "rare", "type": "potion",
         "description": "Regains 8d4+8 hit points.", "attunement": False},
        {"name": "Spell Scroll (4th level)", "rarity": "rare", "type": "scroll",
         "description": "Contains a 4th-level spell.", "attunement": False},
        {"name": "Ammunition +2", "rarity": "rare", "type": "ammunition",
         "description": "10 pieces of +2 ammunition.", "attunement": False},
        {"name": "Potion of Invulnerability", "rarity": "rare", "type": "potion",
         "description": "Resistance to ALL damage for 1 minute.", "attunement": False},
        {"name": "Oil of Etherealness", "rarity": "rare", "type": "potion",
         "description": "Enter Ethereal Plane for 1 hour.", "attunement": False},
        {"name": "Elixir of Health", "rarity": "rare", "type": "potion",
         "description": "Cures all diseases, blindness, deafness.", "attunement": False},
        {"name": "Robe of Useful Items", "rarity": "rare", "type": "wondrous",
         "description": "Patches become mundane items when removed.", "attunement": False},
    ],
    "TABLE_D": [
        {"name": "Potion of Supreme Healing", "rarity": "very rare", "type": "potion",
         "description": "Regains 10d4+20 hit points.", "attunement": False},
        {"name": "Spell Scroll (6th level)", "rarity": "very rare", "type": "scroll",
         "description": "Contains a 6th-level spell.", "attunement": False},
        {"name": "Ammunition +3", "rarity": "very rare", "type": "ammunition",
         "description": "10 pieces of +3 ammunition.", "attunement": False},
        {"name": "Oil of Sharpness", "rarity": "very rare", "type": "potion",
         "description": "Coated weapon gains +3 to attacks and damage for 1 hour.", "attunement": False},
        {"name": "Sovereign Glue", "rarity": "very rare", "type": "wondrous",
         "description": "Permanently bonds two objects together.", "attunement": False},
        {"name": "Universal Solvent", "rarity": "very rare", "type": "wondrous",
         "description": "Dissolves any adhesive, including sovereign glue.", "attunement": False},
        {"name": "Arrow of Slaying (Dragon)", "rarity": "very rare", "type": "ammunition",
         "description": "Forces a DC 17 CON save or takes 6d10 extra damage.", "attunement": False},
    ],
    "TABLE_E": [
        {"name": "Weapon +1", "rarity": "uncommon", "type": "weapon",
         "description": "A magic weapon with +1 to attack and damage.", "attunement": False},
        {"name": "Shield +1", "rarity": "uncommon", "type": "shield",
         "description": "A +1 magic shield.", "attunement": False},
        {"name": "Wand of Magic Missiles", "rarity": "uncommon", "type": "wand",
         "description": "7 charges. Cast Magic Missile (1 charge per level).", "attunement": False},
        {"name": "Bag of Holding", "rarity": "uncommon", "type": "wondrous",
         "description": "Interior space larger than exterior. 500 lb/64 cu ft.", "attunement": False},
        {"name": "Boots of Elvenkind", "rarity": "uncommon", "type": "wondrous",
         "description": "Advantage on Stealth checks, silent steps.", "attunement": False},
        {"name": "Cloak of Elvenkind", "rarity": "uncommon", "type": "wondrous",
         "description": "Disadvantage on Perception checks to see you. Advantage on Stealth.", "attunement": True},
        {"name": "Gauntlets of Ogre Power", "rarity": "uncommon", "type": "wondrous",
         "description": "STR becomes 19 while worn.", "attunement": True},
        {"name": "Headband of Intellect", "rarity": "uncommon", "type": "wondrous",
         "description": "INT becomes 19 while worn.", "attunement": True},
    ],
    "TABLE_F": [
        {"name": "Weapon +2", "rarity": "rare", "type": "weapon",
         "description": "+2 to attack and damage.", "attunement": False},
        {"name": "Shield +2", "rarity": "rare", "type": "shield",
         "description": "+2 magic shield.", "attunement": False},
        {"name": "Bracers of Defense", "rarity": "rare", "type": "wondrous",
         "description": "+2 AC while wearing no armor.", "attunement": True},
        {"name": "Cloak of Displacement", "rarity": "rare", "type": "wondrous",
         "description": "Attacks have disadvantage until you take damage each round.", "attunement": True},
        {"name": "Ring of Protection", "rarity": "rare", "type": "ring",
         "description": "+1 to AC and saving throws.", "attunement": True},
        {"name": "Ring of Spell Storing", "rarity": "rare", "type": "ring",
         "description": "Stores up to 5 spell levels of spells.", "attunement": True},
        {"name": "Wand of Fireballs", "rarity": "rare", "type": "wand",
         "description": "7 charges. Cast Fireball (3 charges, DC 15).", "attunement": True},
    ],
    "TABLE_G": [
        {"name": "Weapon +3", "rarity": "very rare", "type": "weapon",
         "description": "+3 to attack and damage.", "attunement": False},
        {"name": "Shield +3", "rarity": "very rare", "type": "shield",
         "description": "+3 magic shield.", "attunement": False},
        {"name": "Belt of Fire Giant Strength", "rarity": "very rare", "type": "wondrous",
         "description": "STR becomes 25 while worn.", "attunement": True},
        {"name": "Carpet of Flying (5ft x 7ft)", "rarity": "very rare", "type": "wondrous",
         "description": "Fly speed 60 ft, carries 800 lbs.", "attunement": False},
        {"name": "Crystal Ball", "rarity": "very rare", "type": "wondrous",
         "description": "Cast Scrying (DC 17) once per day.", "attunement": True},
        {"name": "Robe of Scintillating Colors", "rarity": "very rare", "type": "wondrous",
         "description": "Dazzling colors cause disadvantage on attacks and DC 15 WIS save or stunned.", "attunement": True},
        {"name": "Staff of Fire", "rarity": "very rare", "type": "staff",
         "description": "10 charges. Cast Burning Hands, Fireball, Wall of Fire.", "attunement": True},
    ],
    "TABLE_H": [
        {"name": "Armor of Invulnerability (Plate)", "rarity": "legendary", "type": "armor",
         "description": "Resistance to nonmagical damage. Immune for 10 min once per day.", "attunement": True},
        {"name": "Cloak of Invisibility", "rarity": "legendary", "type": "wondrous",
         "description": "Become invisible for up to 2 hours (in 1-min increments).", "attunement": True},
        {"name": "Cubic Gate", "rarity": "legendary", "type": "wondrous",
         "description": "Opens a portal to another plane 3 times per day.", "attunement": False},
        {"name": "Deck of Many Things", "rarity": "legendary", "type": "wondrous",
         "description": "Draw cards for unpredictable, reality-altering effects.", "attunement": False},
        {"name": "Luck Blade", "rarity": "legendary", "type": "weapon",
         "description": "+1 longsword with 1d4-1 wishes.", "attunement": True},
        {"name": "Ring of Three Wishes", "rarity": "legendary", "type": "ring",
         "description": "Contains 3 castings of Wish spell.", "attunement": False},
        {"name": "Talisman of Pure Good", "rarity": "legendary", "type": "wondrous",
         "description": "Good cleric/paladin: instant destruction of evil creature at touch.", "attunement": True},
    ],
    "TABLE_I": [
        {"name": "Ring of Invisibility", "rarity": "legendary", "type": "ring",
         "description": "Become invisible as an action, remain invisible until attacking or casting.", "attunement": True},
        {"name": "Rod of Lordly Might", "rarity": "legendary", "type": "rod",
         "description": "Transforms into multiple weapons. 6 modes of attack.", "attunement": True},
        {"name": "Staff of the Magi", "rarity": "legendary", "type": "staff",
         "description": "50 charges. Absorb spells. Cast dozens of spells.", "attunement": True},
        {"name": "Vorpal Sword", "rarity": "legendary", "type": "weapon",
         "description": "+3 sword. On natural 20, decapitate target.", "attunement": True},
        {"name": "Holy Avenger", "rarity": "legendary", "type": "weapon",
         "description": "+3 longsword. 10 ft. aura: advantage on all saves vs spells.", "attunement": True},
        {"name": "Sphere of Annihilation", "rarity": "legendary", "type": "wondrous",
         "description": "2-ft void obliterating all matter. DC 25 Arcana check to control.", "attunement": False},
        {"name": "Talisman of Ultimate Evil", "rarity": "legendary", "type": "wondrous",
         "description": "Evil cleric/paladin: instant destruction of good creature at touch.", "attunement": True},
    ],
}


# ── Dice parser ───────────────────────────────────────────────────────────

def _parse_dice(formula: str, rng: random.Random) -> int:
    """Parse a dice formula like '3d6' or '2d4+2' and return the rolled result.

    Returns 0 for '0' or empty formula.
    """
    if not formula or formula.strip() == "0":
        return 0
    formula = formula.strip()
    total = 0
    rest = formula
    if "+" in formula:
        parts = formula.split("+")
        rest = parts[0]
        for p in parts[1:]:
            total += int(p.strip())
    if "d" in rest:
        count_str, sides_str = rest.split("d")
        count = int(count_str)
        sides = int(sides_str)
        for _ in range(count):
            total += rng.randint(1, sides)
    elif rest.isdigit():
        total += int(rest)
    return total


# ── Roll Functions ────────────────────────────────────────────────────────

def roll_coins(cr: float, rng: Optional[random.Random] = None) -> dict:
    """Roll coin amounts for a creature of given CR.

    Returns dict: {cp, sp, ep, gp, pp} with integer counts.
    """
    rng = rng or random.Random()
    bracket = _cr_bracket(cr)
    # Find the best matching bracket
    coin_entry = None
    for key, entry in COIN_TABLE.items():
        if bracket[0] >= key[0] and bracket[0] <= key[1]:
            coin_entry = entry
            break
    if coin_entry is None:
        # fallback: use first bracket
        coin_entry = COIN_TABLE.get((0, 0.25), COIN_TABLE[list(COIN_TABLE.keys())[0]])

    return {
        denom: _parse_dice(coin_entry.get(denom, "0"), rng)
        for denom in ("cp", "sp", "ep", "gp", "pp")
    }


def roll_gems(cr: float, rng: Optional[random.Random] = None) -> list:
    """Roll gems for a creature of given CR.

    Returns list of {name, value} dicts.
    """
    rng = rng or random.Random()
    bracket = _cr_bracket(cr)
    gems_pool = []
    for key, gems in GEM_TABLE.items():
        if bracket[0] >= key[0] and bracket[0] <= key[1]:
            gems_pool = gems
            break

    if not gems_pool:
        return []

    # Individual: 0-2 gems (weighted toward 0)
    count = 0
    roll = rng.randint(1, 100)
    if roll <= 40:
        count = 0
    elif roll <= 80:
        count = 1
    else:
        count = 2

    return [rng.choice(gems_pool) for _ in range(count)]


def roll_art(cr: float, rng: Optional[random.Random] = None) -> list:
    """Roll art objects for a creature of given CR.

    Returns list of {name, value} dicts.
    """
    rng = rng or random.Random()
    bracket = _cr_bracket(cr)
    art_pool = []
    for key, arts in ART_TABLE.items():
        if bracket[0] >= key[0] and bracket[0] <= key[1]:
            art_pool = arts
            break

    if not art_pool:
        return []

    # Individual: 0-1 art object
    roll = rng.randint(1, 100)
    count = 0
    if roll <= 30:  # 30% chance
        count = 1

    return [rng.choice(art_pool) for _ in range(count)]


def roll_magic_items(cr: float, count: int = 1,
                     rng: Optional[random.Random] = None) -> list:
    """Roll magic items from tables A-I based on CR.

    Args:
        cr: Challenge Rating to determine table access
        count: Number of magic items to roll
        rng: Optional seeded Random

    Returns list of item dicts.
    """
    rng = rng or random.Random()
    if count <= 0 or cr < 0:
        return []

    # Determine which tables are accessible by CR
    accessible_tables = []
    if cr >= 0:
        accessible_tables.append("TABLE_A")
    if cr >= 1:
        accessible_tables.append("TABLE_B")
    if cr >= 2:
        accessible_tables.append("TABLE_E")
    if cr >= 5:
        accessible_tables.append("TABLE_C")
    if cr >= 6:
        accessible_tables.append("TABLE_F")
    if cr >= 11:
        accessible_tables.append("TABLE_D")
    if cr >= 12:
        accessible_tables.append("TABLE_G")
    if cr >= 17:
        accessible_tables.append("TABLE_H")
    if cr >= 18:
        accessible_tables.append("TABLE_I")

    results = []
    for _ in range(count):
        table_key = rng.choice(accessible_tables)
        items = MAGIC_ITEM_TABLES.get(table_key, [])
        if items:
            results.append(dict(rng.choice(items)))

    return results


# ── Treasure Roll Functions ───────────────────────────────────────────────

def roll_individual_treasure(cr: float,
                              rng: Optional[random.Random] = None) -> dict:
    """Roll treasure for a single defeated creature.

    Returns dict: {coins: {cp,sp,ep,gp,pp}, gems: [], art: [], magic_items: []}
    """
    rng = rng or random.Random()
    return {
        "coins": roll_coins(cr, rng),
        "gems": roll_gems(cr, rng),
        "art": roll_art(cr, rng),
        "magic_items": roll_magic_items(cr, 1 if cr >= 5 else 0, rng),
    }


def roll_hoard_treasure(cr: float,
                         rng: Optional[random.Random] = None) -> dict:
    """Roll a treasure hoard (boss loot, dragon hoard, etc.).

    Richer than individual treasure — more coins, gems, art, and magic items.

    Returns dict: {coins: {cp,sp,ep,gp,pp}, gems: [], art: [], magic_items: []}
    """
    rng = rng or random.Random()

    # Hoard coins are 3x individual coins
    coins = {}
    for denom in ("cp", "sp", "ep", "gp", "pp"):
        coins[denom] = roll_coins(cr, rng)[denom] * 3

    # Hoard gems: roll individual gems 3 times
    gems = []
    for _ in range(3):
        gems.extend(roll_gems(cr, rng))

    # Hoard art: roll individual art 3 times
    art = []
    for _ in range(3):
        art.extend(roll_art(cr, rng))

    # Magic items: more generous for hoards
    magic_count = 0
    if cr >= 1:
        magic_count = 1
    if cr >= 5:
        magic_count = rng.randint(1, 2)
    if cr >= 10:
        magic_count = rng.randint(2, 4)
    if cr >= 17:
        magic_count = rng.randint(3, 6)

    magic_items = roll_magic_items(cr, magic_count, rng)

    return {
        "coins": coins,
        "gems": gems,
        "art": art,
        "magic_items": magic_items,
    }
