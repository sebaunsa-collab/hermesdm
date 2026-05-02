"""
test_monster_manual.py â€” Strict TDD tests for dm.monster_manual.

Covers: MONSTER_MANUAL structure, CR_XP table, get_monster(), get_monsters_by_cr().
"""

import pytest
from dm.monster_manual import (
    MONSTER_MANUAL,
    CR_XP as MM_CR_XP,
    get_monster,
    get_monsters_by_cr,
)

MANDATORY = [
    "goblin", "kobold", "skeleton", "zombie", "orc",
    "hobgoblin", "gnoll", "bugbear", "ogre", "werewolf",
    "owlbear", "displacer_beast", "troll", "wyvern",
    "stone_golem", "young_red_dragon", "lich",
]

REQUIRED_FIELDS = {
    "name", "size", "type", "alignment", "ac",
    "hp", "speed", "STR", "DEX", "CON", "INT", "WIS", "CHA",
    "saving_throws", "skills",
    "damage_resistances", "damage_immunities", "condition_immunities",
    "senses", "senses_passive", "languages", "cr", "xp",
    "attacks",
}

VALID_SIZES = {"Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"}


class TestMonsterManualStructure:
    def test_monster_manual_is_dict(self):
        assert isinstance(MONSTER_MANUAL, dict)

    def test_has_30_plus_creatures(self):
        assert len(MONSTER_MANUAL) >= 30

    def test_all_mandatory_creatures_present(self):
        for name in MANDATORY:
            assert name in MONSTER_MANUAL, f"Mandatory creature {name} missing"

    def test_each_creature_has_required_fields(self):
        for name, monster in MONSTER_MANUAL.items():
            missing = REQUIRED_FIELDS - set(monster.keys())
            assert not missing, f"{name} missing fields: {missing}"

    def test_hp_has_max_and_formula(self):
        for name, monster in MONSTER_MANUAL.items():
            hp = monster["hp"]
            assert isinstance(hp, dict), f"{name}: hp not dict"
            assert "max" in hp, f"{name}: hp missing max"
            assert "formula" in hp, f"{name}: hp missing formula"
            assert isinstance(hp["max"], int), f"{name}: hp max not int"
            assert isinstance(hp["formula"], str), f"{name}: hp formula not str"

    def test_cr_is_numeric(self):
        for name, monster in MONSTER_MANUAL.items():
            assert isinstance(monster["cr"], (int, float)), f"{name}: cr not numeric"

    def test_attacks_is_list_of_dicts(self):
        ATTACK_KEYS = {"name", "attack_bonus", "damage", "damage_type"}
        for name, monster in MONSTER_MANUAL.items():
            attacks = monster["attacks"]
            assert isinstance(attacks, list), f"{name}: attacks not list"
            assert len(attacks) >= 1, f"{name}: no attacks"
            for atk in attacks:
                missing = ATTACK_KEYS - set(atk.keys())
                assert not missing, f"{name} attack missing: {missing}"

    def test_valid_sizes(self):
        for name, monster in MONSTER_MANUAL.items():
            size = monster["size"]
            assert size in VALID_SIZES, f"{name}: invalid size {size}"


class TestCRXPTable:
    def test_cr_xp_is_dict(self):
        assert isinstance(MM_CR_XP, dict)

    def test_cr_0_xp(self):
        assert MM_CR_XP[0] == 10

    def test_cr_0_25_xp(self):
        assert MM_CR_XP[0.25] == 50

    def test_cr_0_5_xp(self):
        assert MM_CR_XP[0.5] == 100

    def test_cr_1_xp(self):
        assert MM_CR_XP[1] == 200

    def test_cr_5_xp(self):
        assert MM_CR_XP[5] == 1800

    def test_cr_10_xp(self):
        assert MM_CR_XP[10] == 5900

    def test_cr_21_xp(self):
        assert MM_CR_XP[21] == 33000

    def test_every_monster_cr_has_xp_entry(self):
        for name, monster in MONSTER_MANUAL.items():
            cr = monster["cr"]
            assert cr in MM_CR_XP, f"{name}: CR {cr} not in CR_XP"


class TestGetMonster:
    def test_get_monster_returns_dict(self):
        result = get_monster("goblin")
        assert isinstance(result, dict)

    def test_get_monster_returns_none_for_unknown(self):
        result = get_monster("cthulhu")
        assert result is None

    def test_get_monster_goblin_stats(self):
        goblin = get_monster("goblin")
        assert goblin is not None
        assert goblin["name"] == "goblin"
        assert goblin["cr"] == 0.25
        assert goblin["size"] == "Small"

    def test_get_monster_dragon_stats(self):
        dragon = get_monster("young_red_dragon")
        assert dragon is not None
        assert dragon["cr"] >= 8

    def test_get_monster_lich_has_high_cr(self):
        lich = get_monster("lich")
        assert lich is not None
        assert lich["cr"] >= 15

    def test_get_monster_exact_match_only(self):
        result = get_monster("Goblin")
        assert result is None


class TestGetMonstersByCR:
    def test_returns_list_of_strings(self):
        result = get_monsters_by_cr(0.0, 1.0)
        assert isinstance(result, list)
        assert all(isinstance(n, str) for n in result)

    def test_cr_0_to_0_5_includes_low_cr(self):
        result = get_monsters_by_cr(0.0, 0.5)
        found = set(result) & {"goblin", "kobold", "skeleton", "zombie"}
        assert len(found) >= 2, f"Expected 2+ low CR, got {found}"

    def test_cr_5_to_10_includes_mid_cr(self):
        result = get_monsters_by_cr(5.0, 10.0)
        found = set(result) & {"troll", "wyvern", "stone_golem", "young_red_dragon"}
        assert len(found) >= 2, f"Expected 2+ mid CR, got {found}"

    def test_cr_15_to_30_includes_lich(self):
        result = get_monsters_by_cr(15.0, 30.0)
        assert "lich" in result

    def test_empty_range_returns_empty(self):
        result = get_monsters_by_cr(100.0, 200.0)
        assert result == []

    def test_inclusive_bounds(self):
        result = get_monsters_by_cr(0.25, 0.25)
        for name in result:
            assert MONSTER_MANUAL[name]["cr"] == 0.25

    def test_boundary_cr_0_5_matches_orc(self):
        result = get_monsters_by_cr(0.5, 0.5)
        assert "orc" in result
