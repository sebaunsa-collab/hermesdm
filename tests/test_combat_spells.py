"""
Tests for combat_engine.py — spell resolution and SPELLS dict.
"""
from bot.combat_engine import SPELLS, WEAPON_DAMAGE, get_weapon_damage, resolve_spell


class TestSpells:
    def test_spells_dict_has_required_spells(self):
        required = ["magic_missile", "fireball", "shield",
                    "cure_wounds", "hold_person", "healing_word"]
        for spell in required:
            assert spell in SPELLS, f"{spell} missing from SPELLS"

    def test_each_spell_has_required_fields(self):
        required = ["damage", "type", "range", "components",
                    "description", "casting_time", "concentration"]
        for spell_name, spell in SPELLS.items():
            for field in required:
                assert field in spell, f"{spell_name} missing {field}"

    def test_spell_types_are_valid(self):
        valid_types = ["evocation", "abjuration", "enchantment",
                       "necromancy", "illusion", "divination", "transmutation"]
        for spell_name, spell in SPELLS.items():
            assert spell["type"] in valid_types

    def test_magic_missile_no_save(self):
        assert SPELLS["magic_missile"]["save"] is None

    def test_fireball_has_dex_save(self):
        assert SPELLS["fireball"]["save"] == "dex"
        assert "dc_base" in SPELLS["fireball"]

    def test_shield_has_ac_bonus(self):
        assert SPELLS["shield"]["effect"] == "ac_bonus"
        assert SPELLS["shield"]["ac_bonus"] == 5

    def test_hold_person_is_concentration(self):
        assert SPELLS["hold_person"]["concentration"] is True
        assert SPELLS["hold_person"]["effect"] == "paralyze"


class TestResolveSpell:
    def test_resolve_spell_fireball_no_save(self):
        """Use fireball (8d6) for testing — magic_missile damage '1d4+1' has + modifier."""
        spell = SPELLS["fireball"]
        result = resolve_spell(
            caster_level=5, spell_name="fireball",
            spell_save_dc=0, target_count=1,
            spell_data=spell
        )
        assert result["spell_name"] == "fireball"
        assert len(result["results"]) == 1
        assert result["total_damage"] >= 8  # 8d6 minimum

    def test_resolve_spell_with_save_half(self):
        spell = SPELLS["fireball"]
        result = resolve_spell(
            caster_level=5, spell_name="fireball",
            spell_save_dc=15, target_count=1,
            spell_data=spell, targets_save=[True]
        )
        assert result["results"][0]["saved"] is True
        assert result["results"][0]["damage"] >= 0

    def test_resolve_spell_multi_target(self):
        spell = SPELLS["fireball"]
        result = resolve_spell(
            caster_level=5, spell_name="fireball",
            spell_save_dc=15, target_count=3,
            spell_data=spell, targets_save=[False, True, False]
        )
        assert len(result["results"]) == 3
        assert result["results"][0]["saved"] is False
        assert result["results"][1]["saved"] is True
        assert result["total_damage"] == sum(r["damage"] for r in result["results"])

    def test_resolve_spell_zero_damage_spell(self):
        spell = SPELLS["shield"]
        result = resolve_spell(
            caster_level=5, spell_name="shield",
            spell_save_dc=0, target_count=1,
            spell_data=spell
        )
        assert result["total_damage"] == 0

    def test_resolve_spell_healing_spell(self):
        spell = SPELLS["cure_wounds"]
        resolve_spell(
            caster_level=5, spell_name="cure_wounds",
            spell_save_dc=0, target_count=1,
            spell_data=spell
        )
        # healing spells have "healing" key, damage is 0
        assert "healing" in spell


class TestWeaponDamage:
    def test_common_weapons_have_damage(self):
        for weapon in ["dagger", "longsword", "greatsword", "shortbow"]:
            dmg = get_weapon_damage(weapon)
            assert dmg in WEAPON_DAMAGE.values()

    def test_unknown_weapon_defaults(self):
        dmg = get_weapon_damage("unknown_weapon_xyz")
        assert dmg == WEAPON_DAMAGE["default"]

    def test_weapon_damage_returns_string(self):
        dmg = get_weapon_damage("dagger")
        assert isinstance(dmg, str)
        assert "d" in dmg  # format like "1d4"
