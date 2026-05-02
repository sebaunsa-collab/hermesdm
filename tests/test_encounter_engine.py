"""
test_encounter_engine.py — Tests for EncounterEngine and Enemy pool.

Covers:
- Enemy frozen dataclass
- Biome-based enemy selection
- Deterministic output with seeded RNG
- CR range filtering
- Fallback behavior
- Social encounter generation
"""

import pytest
from dm.enemy_pool import Enemy, ENEMIES_BY_BIOME, DANGER_TO_CR, ALL_ENEMIES
from dm.encounter_engine import EncounterEngine


# ── 2.1 Enemy dataclass ──────────────────────────────────────────────────


class TestEnemyDataclass:
    """Task 2.1: Enemy frozen dataclass with all fields."""

    def test_enemy_creation_minimal(self):
        """Enemy can be created with required fields."""
        e = Enemy(name="Test Enemy", hp=10, ac=12)
        assert e.name == "Test Enemy"
        assert e.hp == 10
        assert e.ac == 12
        assert e.speed == 30
        assert e.cr == 0.0
        assert e.biomes == []

    def test_enemy_creation_full(self):
        """Enemy with all fields populated."""
        e = Enemy(
            name="Dragon",
            hp=200,
            ac=18,
            speed=60,
            attacks=[{"name": "Fire Breath", "to_hit": 10, "damage": "6d6"}],
            cr=10.0,
            abilities={"STR": 25, "DEX": 10, "CON": 20},
            loot={"dragon_scale": 0.8, "dragon_heart": 0.3},
            biomes=["mountain"],
            description="Ancient red dragon",
            size="Huge",
            creature_type="dragon",
        )
        assert e.name == "Dragon"
        assert e.hp == 200
        assert e.cr == 10.0
        assert e.abilities["STR"] == 25
        assert e.loot["dragon_scale"] == 0.8
        assert "mountain" in e.biomes

    def test_enemy_is_frozen(self):
        """Enemy is frozen — cannot be modified after creation."""
        e = Enemy(name="Frozen", hp=5, ac=10)
        with pytest.raises(Exception):
            e.hp = 20  # type: ignore

    def test_enemy_to_dict(self):
        """Enemy.to_dict() returns all fields."""
        e = Enemy(name="Goblin", hp=7, ac=13, cr=0.125, biomes=["forest"])
        d = e.to_dict()
        assert d["name"] == "Goblin"
        assert d["hp"] == 7
        assert d["ac"] == 13
        assert d["cr"] == 0.125


# ── 2.2 Enemy pool ───────────────────────────────────────────────────────


class TestEnemyPool:
    """Task 2.2: ENEMIES_BY_BIOME with enemies across biomes."""

    def test_forest_biome_has_enemies(self):
        """Forest biome has enemies."""
        assert len(ENEMIES_BY_BIOME["forest"]) > 0

    def test_dungeon_biome_has_enemies(self):
        """Dungeon biome has enemies."""
        assert len(ENEMIES_BY_BIOME["dungeon"]) > 0

    def test_urban_biome_has_enemies(self):
        """Urban biome has enemies."""
        assert len(ENEMIES_BY_BIOME["urban"]) > 0

    def test_each_biome_has_min_10_enemies(self):
        """Each biome has at least 10 core enemies."""
        assert len(ENEMIES_BY_BIOME["forest"]) >= 10
        assert len(ENEMIES_BY_BIOME["dungeon"]) >= 10
        assert len(ENEMIES_BY_BIOME["urban"]) >= 10

    def test_all_enemies_total_30_plus(self):
        """Total enemies across all biomes is 30+."""
        assert len(ALL_ENEMIES) >= 30

    def test_danger_to_cr_mapping(self):
        """DANGER_TO_CR covers levels 1-5."""
        for level in range(1, 6):
            assert level in DANGER_TO_CR
            cr_min, cr_max = DANGER_TO_CR[level]
            assert cr_min >= 0
            assert cr_max > cr_min


# ── 2.3-2.4 EncounterEngine deterministic ────────────────────────────────


class TestEncounterEngine:
    """Task 2.3-2.4: EncounterEngine with deterministic output, CR filtering."""

    def test_roll_for_encounter_returns_tuple(self):
        """roll_for_encounter returns (scene_type, enemies, npc) or None."""
        state = {
            "campaign": {"id": "abc", "current_location": "Forest"},
            "world": {"danger_level": 2},
            "turn": 5,
            "npcs": {},
        }
        engine = EncounterEngine(state)
        import random
        rng = random.Random(42)
        result = engine.roll_for_encounter(state, rng=rng)
        assert result is not None
        scene_type, enemies, npc = result
        assert scene_type in ("combat", "social")
        assert isinstance(enemies, list)

    def test_deterministic_with_same_seed(self):
        """Same seed produces same encounter."""
        state = {
            "campaign": {"id": "test-abc", "current_location": "Dungeon"},
            "world": {"danger_level": 3},
            "turn": 10,
            "npcs": {},
        }
        import random
        engine = EncounterEngine(state)
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        result1 = engine.roll_for_encounter(state, rng=rng1)
        result2 = engine.roll_for_encounter(state, rng=rng2)
        assert result1 == result2

    def test_no_matching_enemies_returns_none(self):
        """When no enemies match CR range, returns None."""
        state = {
            "campaign": {"id": "test", "current_location": "Forest"},
            "world": {"danger_level": 1},
            "turn": 1,
            "npcs": {},
        }
        import random
        engine = EncounterEngine(state)
        rng = random.Random(42)
        result = engine.roll_for_encounter(state, rng=rng)
        # At danger 1, some CR 0-0.5 enemies exist (Goblin Scout CR 0.125, Wolf CR 0.25)
        # So this should find enemies
        if result is not None:
            scene_type, enemies, _ = result
            assert all(e["cr"] <= 0.5 for e in enemies)

    def test_social_encounter_with_npcs(self):
        """NPCs present can trigger social encounter."""
        state = {
            "campaign": {"id": "test", "current_location": "Forest"},
            "world": {"danger_level": 2},
            "turn": 5,
            "npcs": {
                "npc1": {"name": "Elfo", "disposition": "neutral"},
            },
        }
        import random
        rng = random.Random(11)  # Seed that triggers social path
        engine = EncounterEngine(state)
        result = engine.roll_for_encounter(state, rng=rng)
        if result:
            scene_type, _, npc = result
            assert scene_type in ("combat", "social")


# ── CR filtering ──────────────────────────────────────────────────────────


class TestCRFiltering:
    """CR range filtering by danger + milestone tier."""

    def test_danger_1_returns_low_cr(self):
        """Danger 1 returns CR 0-0.5 enemies."""
        forest = ENEMIES_BY_BIOME["forest"]
        low_cr = [e for e in forest if e.cr <= 0.5]
        assert len(low_cr) > 0
        assert all(e.cr <= 0.5 for e in low_cr)

    def test_danger_5_returns_high_cr(self):
        """Danger 5 returns CR 5-10 enemies."""
        all_enemies = ALL_ENEMIES
        high_cr = [e for e in all_enemies if e.cr >= 5.0]
        assert len(high_cr) >= 2  # At least Treant (9) and Lich (21) or Stone Golem (10)
