"""
Tests for dice_engine.py — edge cases and full coverage.
"""
from bot.dice_engine import resolve_check, roll


class TestRollEdgeCases:
    def test_roll_multiple_dice(self):
        r = roll("3d6")
        assert len(r["rolls"]) == 3
        assert all(1 <= x <= 6 for x in r["rolls"])

    def test_roll_with_modifier(self):
        r = roll("2d6+5")
        assert r["modifier"] == 5
        assert r["total"] == sum(r["rolls"]) + 5

    def test_roll_with_negative_modifier(self):
        r = roll("1d20-3")
        assert r["modifier"] == -3
        assert r["total"] == r["rolls"][0] - 3

    def test_roll_d4(self):
        r = roll("1d4")
        assert r["rolls"][0] in range(1, 5)

    def test_roll_d6(self):
        r = roll("1d6")
        assert r["rolls"][0] in range(1, 7)

    def test_roll_d8(self):
        r = roll("1d8")
        assert r["rolls"][0] in range(1, 9)

    def test_roll_d10(self):
        r = roll("1d10")
        assert r["rolls"][0] in range(1, 11)

    def test_roll_d12(self):
        r = roll("1d12")
        assert r["rolls"][0] in range(1, 13)

    def test_roll_d100(self):
        r = roll("1d100")
        assert r["rolls"][0] in range(1, 101)

    def test_roll_no_modifier(self):
        r = roll("2d6")
        assert r["modifier"] == 0
        assert r["total"] == sum(r["rolls"])

    def test_roll_nat_20_detected(self):
        r = roll("d20")
        assert r["is_crit"] == (r["rolls"][0] == 20)
        assert r["is_fumble"] == (r["rolls"][0] == 1)

    def test_roll_string_format_preserved(self):
        r = roll("2d6+3")
        assert r["str"] == "2d6+3"


class TestResolveCheckEdgeCases:
    """resolve_check takes a roll_result dict (from roll()), not raw numbers."""

    def test_resolve_check_exact_dc(self):
        r = roll("d20")
        r["total"] = 10  # Force exact value
        result = resolve_check(r, 10, False, False)
        assert result["success"] is True

    def test_resolve_check_above_dc(self):
        r = roll("d20")
        r["total"] = 15  # Force above
        result = resolve_check(r, 10, False, False)
        assert result["success"] is True
        assert result["margin"] == 5

    def test_resolve_check_below_dc(self):
        r = roll("d20")
        r["total"] = 7  # Force below
        result = resolve_check(r, 10, False, False)
        assert result["success"] is False
        assert result["margin"] == -3

    def test_resolve_check_advantage(self):
        r = roll("d20")
        result = resolve_check(r, 15, True, False)
        assert len(result["rolls"]) == 2  # Two dice rolled

    def test_resolve_check_disadvantage(self):
        r = roll("d20")
        result = resolve_check(r, 15, False, True)
        assert len(result["rolls"]) == 2  # Two dice rolled

    def test_resolve_check_advantage_cancels_disadvantage(self):
        r = roll("d20")
        result = resolve_check(r, 15, True, True)
        assert len(result["rolls"]) == 1  # Cancels out

    def test_resolve_check_note_contains_outcome(self):
        r = roll("d20")
        result = resolve_check(r, 10, False, False)
        assert "note" in result
        assert len(result["note"]) > 0
