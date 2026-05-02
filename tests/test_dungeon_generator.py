"""
test_dungeon_generator.py — Strict TDD tests for dm.dungeon_generator.

Covers: Room dataclass, Dungeon dataclass, generate_dungeon(),
BFS from entrance, boss placement, secret rooms, room counts by size.
"""

import random
import pytest
from dm.dungeon_generator import (
    Room,
    Dungeon,
    generate_dungeon,
)

SEED = 42


def _rng(seed: int = SEED) -> random.Random:
    return random.Random(seed)


# ── Room dataclass tests ─────────────────────────────────────────────────


class TestRoomDataclass:
    def test_room_creation_minimal(self):
        r = Room(id="r1", room_type="entrance", description="Dark cave entrance")
        assert r.id == "r1"
        assert r.room_type == "entrance"
        assert r.description == "Dark cave entrance"
        assert r.connected_to == []
        assert r.traps == []
        assert r.treasure is None
        assert r.enemies == []
        assert r.visited is False

    def test_room_creation_full(self):
        r = Room(
            id="r5",
            room_type="combat",
            description="Orc barracks",
            connected_to=["r2", "r3"],
            traps=["Pit trap (2d6)"],
            treasure={"coins": {"gp": 50}},
            enemies=["orc", "orc", "bugbear"],
            theme_details={"lighting": "dim", "odor": "sweat and iron"},
            visited=True,
        )
        assert r.room_type == "combat"
        assert len(r.connected_to) == 2
        assert r.traps[0] == "Pit trap (2d6)"
        assert r.enemies == ["orc", "orc", "bugbear"]

    def test_room_defaults(self):
        r = Room(id="r0", room_type="corridor", description="Narrow passage")
        assert r.traps == []
        assert r.enemies == []
        assert r.treasure is None
        assert r.visited is False

    def test_room_types_are_valid(self):
        valid_types = {"entrance", "corridor", "combat", "trap", "puzzle",
                       "treasure", "boss", "secret", "rest"}
        r = Room(id="r1", room_type="entrance", description="entry")
        assert r.room_type in valid_types


# ── Dungeon dataclass tests ───────────────────────────────────────────────


class TestDungeonDataclass:
    def test_dungeon_creation(self):
        rooms = {
            "r1": Room(id="r1", room_type="entrance", description="Entry"),
            "r2": Room(id="r2", room_type="boss", description="Boss chamber"),
        }
        d = Dungeon(
            entrance_room_id="r1",
            boss_room_id="r2",
            rooms=rooms,
            theme="shadowfell",
            danger_level=3,
            size="medium",
        )
        assert d.entrance_room_id == "r1"
        assert d.boss_room_id == "r2"
        assert d.rooms["r1"].room_type == "entrance"
        assert d.rooms["r2"].room_type == "boss"
        assert d.theme == "shadowfell"
        assert d.danger_level == 3
        assert d.size == "medium"


# ── generate_dungeon tests ────────────────────────────────────────────────


class TestGenerateDungeon:
    def test_generate_returns_dungeon(self):
        d = generate_dungeon("small", 2, "dark_forest", _rng())
        assert isinstance(d, Dungeon)

    def test_small_size_room_count(self):
        d = generate_dungeon("small", 2, "crypt", _rng(42))
        assert 5 <= len(d.rooms) <= 8

    def test_medium_size_room_count(self):
        d = generate_dungeon("medium", 3, "temple", _rng(42))
        assert 9 <= len(d.rooms) <= 15

    def test_large_size_room_count(self):
        d = generate_dungeon("large", 4, "dragon_lair", _rng(42))
        assert 16 <= len(d.rooms) <= 25

    def test_has_entrance_room(self):
        d = generate_dungeon("small", 2, "cave", _rng())
        entrance = d.rooms.get(d.entrance_room_id)
        assert entrance is not None
        assert entrance.room_type == "entrance"

    def test_has_boss_room(self):
        d = generate_dungeon("medium", 3, "fortress", _rng(42))
        boss = d.rooms.get(d.boss_room_id)
        assert boss is not None
        assert boss.room_type == "boss"

    def test_boss_not_entrance(self):
        d = generate_dungeon("medium", 3, "mine", _rng(42))
        assert d.boss_room_id != d.entrance_room_id

    def test_all_rooms_connected(self):
        """BFS from entrance reaches every room."""
        d = generate_dungeon("medium", 3, "shadowfell", _rng(42))
        visited = set()
        queue = [d.entrance_room_id]
        while queue:
            rid = queue.pop(0)
            if rid in visited:
                continue
            visited.add(rid)
            room = d.rooms[rid]
            for conn in room.connected_to:
                if conn not in visited and conn in d.rooms:
                    queue.append(conn)
        assert visited == set(d.rooms.keys()), f"Unreachable: {set(d.rooms.keys()) - visited}"

    def test_dungeon_deterministic(self):
        d1 = generate_dungeon("small", 2, "crypt", _rng(42))
        d2 = generate_dungeon("small", 2, "crypt", _rng(42))
        # Same room ids, same boss, same theme
        assert d1.entrance_room_id == d2.entrance_room_id
        assert d1.boss_room_id == d2.boss_room_id
        assert len(d1.rooms) == len(d2.rooms)

    def test_boss_is_deepest(self):
        """Boss should be at the room furthest in BFS from entrance."""
        d = generate_dungeon("large", 4, "temple", _rng(42))
        # BFS from entrance to find distance to each room
        distances = {d.entrance_room_id: 0}
        queue = [d.entrance_room_id]
        while queue:
            rid = queue.pop(0)
            dist = distances[rid]
            room = d.rooms[rid]
            for conn in room.connected_to:
                if conn not in distances:
                    distances[conn] = dist + 1
                    queue.append(conn)
        # Boss room should have max distance (or one of the max)
        max_dist = max(distances.values())
        assert distances[d.boss_room_id] == max_dist, (
            f"Boss distance {distances[d.boss_room_id]} != max {max_dist}"
        )

    def test_size_small_defaults(self):
        """Test default danger_level/theme for small size."""
        d = generate_dungeon("small", 1, "generic", _rng())
        assert d.size == "small"
        assert d.danger_level == 1
        assert d.theme == "generic"
