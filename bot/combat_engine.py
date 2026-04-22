"""
combat_engine.py — Combat resolution.
resolve_attack, apply_damage, resolve_spell, conditions.
No narrative — pure mechanics.
"""
import random

# Standard D&D 5e damage die by weapon type
WEAPON_DAMAGE = {
    "unarmed": "1",
    "dagger": "1d4",
    "sword": "1d8",
    "longsword": "1d8",
    "greatsword": "2d6",
    "shortsword": "1d6",
    "rapier": "1d8",
    "scimitar": "1d6",
    "handaxe": "1d6",
    "battleaxe": "1d8",
    "greataxe": "1d12",
    "warhammer": "1d8",
    "greatclub": "1d8",
    "mace": "1d6",
    "spear": "1d6",
    "javelin": "1d6",
    "longbow": "1d8",
    "shortbow": "1d6",
    "light_xbow": "1d8",
    "heavy_xbow": "1d10",
    "sling": "1d4",
    # Defaults
    "default": "1d6"
}


def parse_dice(dice_str: str) -> tuple[int, int]:
    """Parse 'NdN' string. Returns (count, sides)."""
    parts = dice_str.lower().split("d")
    count = int(parts[0]) if parts[0] else 1
    sides = int(parts[1]) if len(parts) > 1 else 6
    return count, sides


def roll_dice(dice_str: str) -> list[int]:
    """Roll a dice string like '2d6'. Returns list of individual rolls."""
    count, sides = parse_dice(dice_str)
    return [random.randint(1, sides) for _ in range(count)]


def get_weapon_damage(weapon: str) -> str:
    return WEAPON_DAMAGE.get(weapon.lower(), WEAPON_DAMAGE["default"])


def resolve_attack(
    attacker_name: str,
    defender_name: str,
    attack_roll: int,
    weapon: str = "sword",
    advantage: bool = False,
    disadvantage: bool = False,
    defender_ac: int = 10,
    rage_bonus: int = 0,
    attack_bonus: int = 0,
) -> dict:
    """
    Resolve a melee/ranged attack.
    Returns {hit, crit, damage, rolls, note}
    """
    if advantage and disadvantage:
        advantage = False
        disadvantage = False

    # Determine effective roll
    if advantage and not disadvantage:
        roll2 = random.randint(1, 20)
        effective_roll = max(attack_roll, roll2)
    elif disadvantage and not advantage:
        roll2 = random.randint(1, 20)
        effective_roll = min(attack_roll, roll2)
    else:
        effective_roll = attack_roll

    nat = effective_roll
    is_crit = (nat == 20)
    is_fumble = (nat == 1)

    if is_fumble:
        return {
            "hit": False,
            "crit": False,
            "fumble": True,
            "damage": 0,
            "rolls": [effective_roll],
            "note": f"NATURAL 1! {attacker_name} fumbles!",
            "attacker": attacker_name,
            "defender": defender_name
        }

    if is_crit:
        # Roll double dice for crit. Attack bonus NOT doubled (only weapon dice).
        dmg_str = get_weapon_damage(weapon)
        count, sides = parse_dice(dmg_str)
        base_rolls = [random.randint(1, sides) for _ in range(count * 2)]
        damage = sum(base_rolls) + attack_bonus + rage_bonus
        return {
            "hit": True,
            "crit": True,
            "fumble": False,
            "damage": damage,
            "rolls": base_rolls,
            "note": f"NATURAL 20! CRITICAL HIT! {damage} damage!",
            "attacker": attacker_name,
            "defender": defender_name
        }

    hit = effective_roll >= defender_ac
    if not hit:
        return {
            "hit": False,
            "crit": False,
            "fumble": False,
            "damage": 0,
            "rolls": [effective_roll],
            "note": f"Miss! {attacker_name} attacks for {effective_roll} vs AC {defender_ac}.",
            "attacker": attacker_name,
            "defender": defender_name
        }

    # Normal hit
    dmg_str = get_weapon_damage(weapon)
    dmg_rolls = roll_dice(dmg_str)
    damage = sum(dmg_rolls) + rage_bonus

    return {
        "hit": True,
        "crit": False,
        "fumble": False,
        "damage": damage,
        "rolls": dmg_rolls,
        "note": f"Hit! {attacker_name} deals {damage} damage to {defender_name}! ({dmg_rolls})",
        "attacker": attacker_name,
        "defender": defender_name
    }


def apply_damage(target_hp, damage: int) -> dict:
    """
    Apply damage to a target HP object.
    Returns breakdown of damage taken.
    """
    temp = target_hp.temp
    absorbed_by_temp = min(temp, damage)
    remaining_damage = damage - absorbed_by_temp

    old_hp = target_hp.current
    target_hp.temp = max(0, temp - damage)
    target_hp.current = max(0, target_hp.current - remaining_damage)

    actual = old_hp - target_hp.current

    return {
        "damage_dealt": actual,
        "hp_lost": actual,
        "temp_absorbed": absorbed_by_temp,
        "current_hp": target_hp.current,
        "temp_hp": target_hp.temp,
        "dead": target_hp.current == 0,
        "unconscious": target_hp.current == 0
    }


def resolve_spell(
    caster_level: int,
    spell_name: str,
    spell_save_dc: int,
    target_count: int,
    spell_data: dict,
    targets_save: list[bool] = None
) -> dict:
    """
    Resolve a spell with possible saving throw.
    spell_data: {damage: "XdY", healing: X, range: "self" or N,
                  aoe: bool, description: str}
    Returns {damage_per_target, total_damage, spell_name, note}
    """
    if targets_save is None:
        targets_save = [False] * target_count

    dmg_str = spell_data.get("damage", "0")
    count, sides = parse_dice(dmg_str) if dmg_str != "0" else (0, 0)

    results = []
    for i, saved in enumerate(targets_save):
        if saved:
            # Half damage on successful save
            if count > 0:
                full = sum(random.randint(1, sides) for _ in range(count))
                dmg = full // 2
            else:
                dmg = 0
            results.append({"target": i + 1, "saved": True, "damage": dmg, "rolls": []})
        else:
            if count > 0:
                rolls = [random.randint(1, sides) for _ in range(count)]
                dmg = sum(rolls)
            else:
                dmg = 0
                rolls = []
            results.append({"target": i + 1, "saved": False, "damage": dmg, "rolls": rolls})

    total = sum(r["damage"] for r in results)
    return {
        "spell_name": spell_name,
        "results": results,
        "total_damage": total,
        "note": f"{spell_name} deals {total} total damage across {target_count} targets."
    }


# ---- Spell definitions (simplified D&D 5e) ----

SPELLS = {
    "magic_missile": {
        "damage": "1d4+1",
        "type": "evocation",
        "range": 120,
        "components": "V, S",
        "description": "Two missiles, each hitting a creature. No attack roll.",
        "save": None,
        "casting_time": "1 action",
        "concentration": False
    },
    "fireball": {
        "damage": "8d6",
        "type": "evocation",
        "range": 150,
        "components": "V, S, M (a tiny ball of bat guano and sulfur)",
        "description": "20ft radius sphere. DEX save for half.",
        "save": "dex",
        "dc_base": 15,
        "casting_time": "1 action",
        "concentration": False
    },
    "shield": {
        "damage": "0",
        "type": "abjuration",
        "range": "self",
        "components": "V, S",
        "description": "+5 AC until next turn.",
        "save": None,
        "casting_time": "1 reaction",
        "concentration": False,
        "effect": "ac_bonus",
        "ac_bonus": 5
    },
    "cure_wounds": {
        "damage": "0",
        "type": "evocation",
        "range": "touch",
        "components": "V, S",
        "description": "Heal 1d8 + spellcasting mod.",
        "save": None,
        "casting_time": "1 action",
        "concentration": False,
        "healing": "1d8"
    },
    "hold_person": {
        "damage": "0",
        "type": "enchantment",
        "range": 60,
        "components": "V, S, M (a small, straight piece of iron)",
        "description": "Target paralyzed. WIS save. Concentration.",
        "save": "wis",
        "dc_base": 15,
        "casting_time": "1 action",
        "concentration": True,
        "effect": "paralyze"
    },
    "healing_word": {
        "damage": "0",
        "type": "evocation",
        "range": 60,
        "components": "V",
        "description": "Heal 1d4 + spellcasting mod as bonus action.",
        "save": None,
        "casting_time": "1 bonus action",
        "concentration": False,
        "healing": "1d4"
    }
}


if __name__ == "__main__":
    print("=== combat_engine sanity test ===")
    result = resolve_attack("Valdric", "Goblin", 16, weapon="longsword", defender_ac=14)
    print(result)
    result = resolve_attack("Valdric", "Goblin", 20, weapon="longsword", defender_ac=14)
    print(result)
