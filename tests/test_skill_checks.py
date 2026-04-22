"""
test_skill_checks.py
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.character_sheet import create_character
from bot.skill_checks import describe_check, get_dc, resolve_save, resolve_skill_check


class TestSkillChecks:
    def setup_method(self):
        self.c = create_character("Valdric", "fighter")
        self.c.proficiencies = ["athletics", "intimidation", "perception"]
        self.c.stats["str"] = 16  # +3

    def test_skill_check_hit(self):
        # DC 5 is easy even with low roll
        result = resolve_skill_check(self.c, "athletics", dc=5)
        assert "success" in result
        assert "total" in result

    def test_skill_unknown(self):
        result = resolve_skill_check(self.c, "fake_skill_xyz", dc=10)
        assert "error" in result

    def test_proficiency_applied(self):
        # Athletics is in proficiencies
        result = resolve_skill_check(self.c, "athletics", dc=0)
        assert result.get("proficient")

    def test_non_proficiency(self):
        # Arcana is not in proficiencies
        result = resolve_skill_check(self.c, "arcana", dc=0)
        assert not result.get("proficient")

    def test_save(self):
        self.c.stats["con"] = 14  # +2
        result = resolve_save(self.c, "con", dc=10)
        assert "success" in result
        assert "total" in result

    def test_dc_table(self):
        assert get_dc("easy") == 10
        assert get_dc("medium") == 15
        assert get_dc(20) == 20

    def test_describe_check(self):
        desc = describe_check("athletics")
        assert "jump" in desc.lower() or "climb" in desc.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
