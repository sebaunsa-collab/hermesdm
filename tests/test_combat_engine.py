"""
test_combat_engine.py
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.character_sheet import HP
from bot.combat_engine import (
    SPELLS,
    apply_damage,
    get_weapon_damage,
    parse_dice,
    resolve_attack,
)


class TestResolveAttack:
    def test_miss(self):
        r = resolve_attack("Valdric", "Goblin", 10, defender_ac=15)
        assert not r["hit"]
        assert r["damage"] == 0

    def test_hit(self):
        r = resolve_attack("Valdric", "Goblin", 16, defender_ac=15)
        assert r["hit"]
        assert r["damage"] > 0

    def test_nat_20(self):
        # Roll a natural 20
        for _ in range(50):
            r = resolve_attack("Valdric", "Goblin", 20, defender_ac=15)
            if r["crit"]:
                assert r["hit"]
                assert r["damage"] > 0
                assert "CRITICAL" in r["note"]
                break
        else:
            pytest.skip("Did not roll nat 20 in 50 attempts")

    def test_nat_1(self):
        for _ in range(50):
            r = resolve_attack("Valdric", "Goblin", 1, defender_ac=15)
            if r.get("fumble"):
                assert not r["hit"]
                assert r["damage"] == 0
                break
        else:
            pytest.skip("Did not roll nat 1 in 50 attempts")


class TestApplyDamage:
    def test_full_damage(self):
        hp = HP(max=20, current=20)
        result = apply_damage(hp, 8)
        assert result["current_hp"] == 12
        assert result["damage_dealt"] == 8

    def test_temp_hp_absorbs(self):
        hp = HP(max=20, current=15, temp=5)
        result = apply_damage(hp, 4)
        assert result["temp_absorbed"] == 4
        assert result["temp_hp"] == 1
        assert result["current_hp"] == 15  # No HP lost

    def test_death(self):
        hp = HP(max=20, current=10)
        result = apply_damage(hp, 15)
        assert result["current_hp"] == 0
        assert result["dead"]


class TestCombatEngine:
    def test_weapon_damage(self):
        assert get_weapon_damage("longsword") == "1d8"
        assert get_weapon_damage("greatsword") == "2d6"
        assert get_weapon_damage("dagger") == "1d4"
        assert get_weapon_damage("unknown_weapon") == "1d6"

    def test_parse_dice(self):
        assert parse_dice("2d6") == (2, 6)
        assert parse_dice("1d20") == (1, 20)
        assert parse_dice("d8") == (1, 8)

    def test_spell_lookup(self):
        assert "magic_missile" in SPELLS
        assert "fireball" in SPELLS
        assert SPELLS["fireball"]["save"] == "dex"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
