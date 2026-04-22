"""
test_character_sheet.py
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.character_sheet import (
    CLASS_DEFINITIONS,
    HP,
    Character,
    DeathSaves,
    Item,
    create_character,
)


class TestCharacter:
    def test_modifier(self):
        c = create_character("Valdric", "fighter")
        c.stats["str"] = 16
        assert c.mod("str") == 3
        assert c.mod_str("str") == "+3"

    def test_hp(self):
        hp = HP(max=10, current=10)
        lost = hp.apply_damage(4)
        assert lost == 4
        assert hp.current == 6

    def test_temp_hp(self):
        hp = HP(max=10, current=10, temp=5)
        lost = hp.apply_damage(3)
        assert lost == 3  # Absorbed by temp HP
        assert hp.temp == 2
        assert hp.current == 10

    def test_heal(self):
        hp = HP(max=10, current=3)
        healed = hp.heal(4)
        assert healed == 4
        assert hp.current == 7
        assert hp.heal(10) == 3  # Caps at max (7→10), returns actual healed

    def test_death_saves(self):
        ds = DeathSaves()
        assert ds.successes == 0
        ds.successes = 2
        ds.failures = 1
        assert ds.successes == 2
        assert ds.failures == 1

    def test_conditions(self):
        c = create_character("Valdric", "fighter")
        c.add_condition("prone")
        assert "prone" in c.conditions
        c.remove_condition("prone")
        assert "prone" not in c.conditions

    def test_inventory(self):
        c = create_character("Valdric", "fighter")
        c.add_item(Item("Longsword", 1, "A fine blade"))
        assert len(c.inventory) == 1
        c.add_item(Item("Longsword", 1))  # Should stack
        assert c.inventory[0].quantity == 2

    def test_proficiency(self):
        c = create_character("Valdric", "fighter")
        c.proficiencies = ["athletics", "intimidation"]
        assert c.is_proficient("athletics")
        assert not c.is_proficient("arcana")

    def test_to_dict_from_dict(self):
        c = create_character("Valdric", "fighter", level=3)
        d = c.to_dict()
        restored = Character.from_dict(d)
        assert restored.name == c.name
        assert restored.player_class == c.player_class
        assert restored.level == c.level


class TestClassDefinitions:
    def test_all_classes_defined(self):
        for cls_name in ["fighter", "wizard", "rogue", "cleric", "ranger", "barbarian"]:
            assert cls_name in CLASS_DEFINITIONS
            c = create_character("Test", cls_name)
            assert c.player_class == cls_name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
