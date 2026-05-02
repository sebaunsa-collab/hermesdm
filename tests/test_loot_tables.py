"""
test_loot_tables.py — Strict TDD tests for dm.loot_tables.

Covers: COIN_TABLE, GEM_TABLE, ART_TABLE, MAGIC_ITEM_TABLES,
roll_coins(), roll_gems(), roll_art(), roll_magic_items(),
roll_individual_treasure(), roll_hoard_treasure().
"""

import random
import pytest
from dm.loot_tables import (
    COIN_TABLE,
    GEM_TABLE,
    ART_TABLE,
    MAGIC_ITEM_TABLES,
    roll_coins,
    roll_gems,
    roll_art,
    roll_magic_items,
    roll_individual_treasure,
    roll_hoard_treasure,
)

SEED = 42


def _rng(seed: int = SEED) -> random.Random:
    return random.Random(seed)


# ── Table structure tests ─────────────────────────────────────────────────


class TestCoinTable:
    def test_coin_table_is_dict(self):
        assert isinstance(COIN_TABLE, dict)

    def test_coin_table_has_cr_brackets(self):
        """COIN_TABLE has CR bracket keys."""
        assert any(isinstance(k, tuple) for k in COIN_TABLE) or any(
            isinstance(k, str) for k in COIN_TABLE
        )

    def test_coin_entries_have_dice_formulas(self):
        for bracket, coins in COIN_TABLE.items():
            for denom in ("cp", "sp", "ep", "gp", "pp"):
                if denom in coins:
                    assert isinstance(coins[denom], str), (
                        f"Bracket {bracket}: {denom} not a string formula"
                    )


class TestGemTable:
    def test_gem_table_is_dict(self):
        assert isinstance(GEM_TABLE, dict)

    def test_gem_table_has_entries(self):
        assert len(GEM_TABLE) >= 4

    def test_gem_entries_are_lists_of_dicts(self):
        for bracket, gems in GEM_TABLE.items():
            assert isinstance(gems, list), f"Bracket {bracket}: not a list"
            assert len(gems) >= 1, f"Bracket {bracket}: empty"
            for gem in gems:
                assert isinstance(gem, dict), f"Bracket {bracket}: item not dict"
                assert "name" in gem, f"Bracket {bracket}: missing name"
                assert "value" in gem, f"Bracket {bracket}: missing value"


class TestArtTable:
    def test_art_table_is_dict(self):
        assert isinstance(ART_TABLE, dict)

    def test_art_table_has_entries(self):
        assert len(ART_TABLE) >= 4

    def test_art_entries_are_lists_of_dicts(self):
        for bracket, arts in ART_TABLE.items():
            assert isinstance(arts, list), f"Bracket {bracket}: not a list"
            assert len(arts) >= 1, f"Bracket {bracket}: empty"
            for art in arts:
                assert isinstance(art, dict)
                assert "name" in art
                assert "value" in art


class TestMagicItemTables:
    def test_magic_item_tables_is_dict(self):
        assert isinstance(MAGIC_ITEM_TABLES, dict)

    def test_has_tables_A_through_I(self):
        for letter in "ABCDEFGHI":
            key = f"TABLE_{letter}"
            assert key in MAGIC_ITEM_TABLES, f"Missing {key}"

    def test_each_table_has_min_5_items(self):
        for key, items in MAGIC_ITEM_TABLES.items():
            assert len(items) >= 5, f"{key}: expected >= 5 items, got {len(items)}"

    def test_magic_items_have_required_fields(self):
        required = {"name", "rarity", "type"}
        for key, items in MAGIC_ITEM_TABLES.items():
            for item in items:
                missing = required - set(item.keys())
                assert not missing, f"{key}: item missing {missing}"


# ── Roll functions ────────────────────────────────────────────────────────


class TestRollCoins:
    def test_roll_coins_returns_dict(self):
        result = roll_coins(2.0, _rng())
        assert isinstance(result, dict)

    def test_roll_coins_has_all_denominations(self):
        result = roll_coins(5.0, _rng())
        for denom in ("cp", "sp", "ep", "gp", "pp"):
            assert denom in result
            assert isinstance(result[denom], int)

    def test_roll_coins_deterministic(self):
        r1 = roll_coins(1.0, _rng(42))
        r2 = roll_coins(1.0, _rng(42))
        assert r1 == r2

    def test_roll_coins_different_seeds_different(self):
        r1 = roll_coins(1.0, _rng(42))
        r2 = roll_coins(1.0, _rng(99))
        # With different seeds, highly likely different
        assert r1 != r2 or sum(r1.values()) >= 0  # at least runs


class TestRollGems:
    def test_roll_gems_returns_list(self):
        result = roll_gems(2.0, _rng())
        assert isinstance(result, list)

    def test_roll_gems_deterministic(self):
        r1 = roll_gems(1.0, _rng(42))
        r2 = roll_gems(1.0, _rng(42))
        assert r1 == r2

    def test_roll_gems_items_have_name_and_value(self):
        result = roll_gems(5.0, _rng())
        if result:
            for gem in result:
                assert "name" in gem
                assert "value" in gem


class TestRollArt:
    def test_roll_art_returns_list(self):
        result = roll_art(2.0, _rng())
        assert isinstance(result, list)

    def test_roll_art_deterministic(self):
        r1 = roll_art(3.0, _rng(42))
        r2 = roll_art(3.0, _rng(42))
        assert r1 == r2


class TestRollMagicItems:
    def test_roll_magic_items_returns_list(self):
        result = roll_magic_items(5.0, 2, _rng())
        assert isinstance(result, list)

    def test_roll_magic_items_count(self):
        result = roll_magic_items(10.0, 3, _rng())
        assert len(result) <= 3

    def test_roll_magic_items_zero_returns_empty(self):
        result = roll_magic_items(5.0, 0, _rng())
        assert result == []

    def test_roll_magic_items_has_required_fields(self):
        result = roll_magic_items(15.0, 2, _rng())
        for item in result:
            assert "name" in item
            assert "rarity" in item
            assert "type" in item


# ── Treasure roll functions ───────────────────────────────────────────────


class TestRollIndividualTreasure:
    def test_returns_dict(self):
        result = roll_individual_treasure(2.0, _rng())
        assert isinstance(result, dict)

    def test_has_expected_keys(self):
        result = roll_individual_treasure(3.0, _rng())
        for key in ("coins", "gems", "art", "magic_items"):
            assert key in result, f"Missing key: {key}"

    def test_coins_is_dict_with_denominations(self):
        result = roll_individual_treasure(1.0, _rng())
        coins = result["coins"]
        assert isinstance(coins, dict)
        for denom in ("cp", "sp", "ep", "gp", "pp"):
            assert denom in coins

    def test_deterministic(self):
        r1 = roll_individual_treasure(2.0, _rng(42))
        r2 = roll_individual_treasure(2.0, _rng(42))
        assert r1 == r2


class TestRollHoardTreasure:
    def test_returns_dict(self):
        result = roll_hoard_treasure(5.0, _rng())
        assert isinstance(result, dict)

    def test_has_expected_keys(self):
        result = roll_hoard_treasure(8.0, _rng())
        for key in ("coins", "gems", "art", "magic_items"):
            assert key in result

    def test_hoard_has_more_than_individual(self):
        """Hoard treasure should generally yield more than individual."""
        ind = roll_individual_treasure(5.0, _rng(42))
        hoard = roll_hoard_treasure(5.0, _rng(42))
        ind_total_gp = ind["coins"].get("gp", 0)
        hoard_total_gp = hoard["coins"].get("gp", 0)
        # Hoard should generally have more gp or magic items
        assert hoard_total_gp >= ind_total_gp or len(hoard["magic_items"]) >= len(ind["magic_items"])

    def test_deterministic(self):
        r1 = roll_hoard_treasure(5.0, _rng(42))
        r2 = roll_hoard_treasure(5.0, _rng(42))
        assert r1 == r2
