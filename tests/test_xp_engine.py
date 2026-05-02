# tests/test_xp_engine.py — Strict TDD: Phase 1 tests for dm.xp_engine
"""15 tests covering CR→XP lookup, party split, level-up detection,
   multi-level skip, proficiency scaling, level 20 cap, invalid CR."""
import pytest
from dm.xp_engine import calculate_xp, award_xp, CR_XP, XP_THRESHOLDS, PROFICIENCY_BONUS


# ── CR to XP table tests ──────────────────────────────────────────────────

class TestCRToXP:
    def test_cr_0_returns_10(self):
        assert CR_XP[0] == 10

    def test_cr_0_125_returns_25(self):
        assert CR_XP[0.125] == 25

    def test_cr_0_5_returns_100(self):
        assert CR_XP[0.5] == 100

    def test_cr_1_returns_200(self):
        assert CR_XP[1] == 200

    def test_cr_5_returns_1800(self):
        assert CR_XP[5] == 1800

    def test_cr_20_returns_25000(self):
        assert CR_XP[20] == 25000

    def test_cr_30_returns_155000(self):
        assert CR_XP[30] == 155000


# ── calculate_xp tests ────────────────────────────────────────────────────

class TestCalculateXP:
    def test_solo_player_full_xp(self):
        result = calculate_xp(enemy_cr=1.0, party_size=1)
        assert result == 200

    def test_party_of_4_split_xp(self):
        result = calculate_xp(enemy_cr=1.0, party_size=4)
        assert result == 50  # 200 // 4

    def test_uneven_division_floors(self):
        result = calculate_xp(enemy_cr=0.25, party_size=4)
        assert result == 12  # 50 // 4 = 12

    def test_invalid_cr_raises(self):
        with pytest.raises(ValueError):
            calculate_xp(enemy_cr=1.5, party_size=1)

    def test_cr_2_plus_cr_1_combined(self):
        xp2 = calculate_xp(2, party_size=4)  # 450 // 4 = 112
        xp1 = calculate_xp(1, party_size=4)  # 200 // 4 = 50
        assert xp2 == 112
        assert xp1 == 50
        assert xp2 + xp1 == 162


# ── XP thresholds table tests ─────────────────────────────────────────────

class TestXPThresholds:
    def test_level_1_threshold_is_0(self):
        assert XP_THRESHOLDS[1] == 0

    def test_level_2_threshold_is_300(self):
        assert XP_THRESHOLDS[2] == 300

    def test_level_5_threshold_is_6500(self):
        assert XP_THRESHOLDS[5] == 6500

    def test_level_20_threshold_is_355000(self):
        assert XP_THRESHOLDS[20] == 355000


# ── award_xp tests ────────────────────────────────────────────────────────

class TestAwardXP:
    def test_award_xp_increments(self):
        char = {"name": "Test", "xp": 0, "level": 1}
        result = award_xp(char, 100)
        assert result["character"]["xp"] == 100
        assert result["character"]["level"] == 1
        assert len(result["levels_gained"]) == 0
        assert len(result["messages"]) == 0

    def test_level_up_from_xp_award(self):
        char = {"name": "Test", "xp": 280, "level": 1}
        result = award_xp(char, 50)  # 280 + 50 = 330 >= 300
        assert result["character"]["xp"] == 330
        assert result["character"]["level"] == 2
        assert result["levels_gained"] == [2]
        assert "Subiste al nivel 2" in result["messages"][0]

    def test_multi_level_up_in_one_award(self):
        char = {"name": "Test", "xp": 0, "level": 1}
        result = award_xp(char, 1000)  # crosses L2 (300) and L3 (900)
        assert result["character"]["xp"] == 1000
        assert result["character"]["level"] == 3
        assert result["levels_gained"] == [2, 3]
        assert len(result["messages"]) == 2

    def test_level_20_cap_no_further_leveling(self):
        char = {"name": "Test", "xp": 300000, "level": 19}
        result = award_xp(char, 100000)
        assert result["character"]["level"] == 20
        assert result["character"]["xp"] == 400000
        # Should not go to level 21
        assert 21 not in result["levels_gained"]

    def test_proficiency_bonus_updates_on_level_up(self):
        char = {"name": "Test", "xp": 6000, "level": 4}
        result = award_xp(char, 1000)  # L4->L5: 6500->7000
        assert result["character"]["level"] == 5
        assert result["character"]["proficiency_bonus"] == 3

    def test_default_level_is_1_when_missing(self):
        char = {"name": "Test", "xp": 0}
        result = award_xp(char, 500)
        assert result["character"]["level"] == 2
        assert result["character"]["xp"] == 500

    def test_default_xp_is_0_when_missing(self):
        char = {"name": "Test", "level": 1}
        result = award_xp(char, 200)
        assert result["character"]["xp"] == 200

    def test_proficiency_bonus_scales_L1_to_L17(self):
        expected = {1: 2, 4: 2, 5: 3, 8: 3, 9: 4, 12: 4, 13: 5, 16: 5, 17: 6, 20: 6}
        for level, bonus in expected.items():
            assert PROFICIENCY_BONUS[min(level, 20)] == bonus


# ── Proficiency bonus scaling integration test ─────────────────────────────

class TestProficiencyIntegration:
    def test_level_1_has_prof_2(self):
        char = {"name": "Test", "xp": 0, "level": 1}
        result = award_xp(char, 10)
        assert result["character"]["proficiency_bonus"] == 2

    def test_level_5_has_prof_3(self):
        char = {"name": "Test", "xp": 6400, "level": 4}
        result = award_xp(char, 200)  # L4->L5, prof +2->+3
        assert result["character"]["level"] == 5
        assert result["character"]["proficiency_bonus"] == 3
