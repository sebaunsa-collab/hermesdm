"""
tests/test_location_graph.py — Tests for Location Graph (Phase 2: Narrative Progression Gates).

Tests the location graph module:
  - Location dataclass with connections, prerequisites, lock_flag
  - LocationGraph can_travel_to() with edge checking
  - LocationGraph get_path() with BFS
  - Edge prerequisites and location locking via world_flags
"""

import pytest

from dm.location_graph import Location, LocationGraph


# ------------------------------------------------------------------
# Location Dataclass Tests
# ------------------------------------------------------------------

class TestLocationDataclass:
    """Tests for the Location dataclass."""

    def test_location_basic_fields(self):
        """Location should have name, description, and default empty connections."""
        loc = Location(name="Tavern")
        assert loc.name == "Tavern"
        assert loc.description == ""
        assert loc.connections == []
        assert loc.prerequisites == []
        assert loc.locked_until_flag is None
        assert loc.distance_from_previous == 1
        assert loc.obstacles == []

    def test_location_with_connections(self):
        """Location connections should be a list of neighbor names."""
        loc = Location(name="Forest", connections=["Tavern", "Cave"])
        assert "Tavern" in loc.connections
        assert "Cave" in loc.connections

    def test_location_with_prerequisites(self):
        """Location prerequisites should list required world_flags."""
        loc = Location(
            name="Dungeon",
            prerequisites=["bridge_repaired", "key_found"],
        )
        assert "bridge_repaired" in loc.prerequisites
        assert "key_found" in loc.prerequisites

    def test_location_with_lock_flag(self):
        """Location locked_until_flag should be a world_flag."""
        loc = Location(name="Boss Room", locked_until_flag="boss_key")
        assert loc.locked_until_flag == "boss_key"

    def test_is_accessible_no_requirements(self):
        """Location with no prerequisites or lock should always be accessible."""
        loc = Location(name="Tavern")
        assert loc.is_accessible({}) is True

    def test_is_accessible_prereq_met(self):
        """When all prerequisites are True, accessible."""
        loc = Location(name="Cave", prerequisites=["dark_vision"])
        flags = {"dark_vision": True}
        assert loc.is_accessible(flags) is True

    def test_is_accessible_prereq_not_met(self):
        """When a prerequisite is False, NOT accessible."""
        loc = Location(name="Cave", prerequisites=["dark_vision"])
        flags = {"dark_vision": False}
        assert loc.is_accessible(flags) is False

    def test_is_accessible_prereq_missing_from_flags(self):
        """When a prerequisite is not in flags dict, it defaults to False."""
        loc = Location(name="Cave", prerequisites=["dark_vision"])
        flags = {}  # dark_vision not set
        assert loc.is_accessible(flags) is False

    def test_is_accessible_lock_flag_blocks(self):
        """When locked_until_flag is False, NOT accessible regardless of prereqs."""
        loc = Location(name="Boss Room", locked_until_flag="boss_key")
        flags = {"boss_key": False}
        assert loc.is_accessible(flags) is False

    def test_is_accessible_lock_flag_allows(self):
        """When locked_until_flag is True, accessible."""
        loc = Location(name="Boss Room", locked_until_flag="boss_key")
        flags = {"boss_key": True}
        assert loc.is_accessible(flags) is True

    def test_is_accessible_both_prereq_and_lock(self):
        """Both prereqs AND lock must be met."""
        loc = Location(
            name="Final Chamber",
            prerequisites=["ritual_complete"],
            locked_until_flag="temple_key",
        )
        # both true → accessible
        assert loc.is_accessible({"ritual_complete": True, "temple_key": True}) is True
        # prereq true, lock false → NOT accessible
        assert loc.is_accessible({"ritual_complete": True, "temple_key": False}) is False
        # prereq false, lock true → NOT accessible
        assert loc.is_accessible({"ritual_complete": False, "temple_key": True}) is False


# ------------------------------------------------------------------
# LocationGraph Tests
# ------------------------------------------------------------------

class TestLocationGraphBasic:
    """Tests for LocationGraph construction and basic operations."""

    @pytest.fixture
    def simple_graph(self):
        """A simple 3-node graph: Tavern → Forest → Cave."""
        locations = {
            "Tavern": Location(name="Tavern", connections=["Forest"]),
            "Forest": Location(name="Forest", connections=["Tavern", "Cave"]),
            "Cave": Location(name="Cave", connections=["Forest"]),
        }
        return LocationGraph(locations=locations)

    def test_can_travel_direct_edge(self, simple_graph):
        """can_travel_to should return True when a direct edge exists."""
        assert simple_graph.can_travel_to("Tavern", "Forest", {})[0]

    def test_can_travel_no_edge(self, simple_graph):
        """can_travel_to should return False when no edge exists."""
        assert simple_graph.can_travel_to("Tavern", "Cave", {})[0] is False

    def test_can_travel_same_location(self, simple_graph):
        """can_travel_to same location should return True (staying put)."""
        assert simple_graph.can_travel_to("Tavern", "Tavern", {})[0]

    def test_can_travel_destination_not_in_graph(self, simple_graph):
        """can_travel_to non-existent destination should return False."""
        assert simple_graph.can_travel_to("Tavern", "Atlantis", {})[0] is False

    def test_can_travel_source_not_in_graph(self, simple_graph):
        """can_travel_to from non-existent source should return False."""
        assert simple_graph.can_travel_to("Atlantis", "Tavern", {})[0] is False

    def test_get_path_direct(self, simple_graph):
        """get_path for direct edge should return [source, dest]."""
        path = simple_graph.get_path("Tavern", "Forest", {})
        assert path == ["Tavern", "Forest"]

    def test_get_path_two_steps(self, simple_graph):
        """get_path for two-step path should return the full path."""
        path = simple_graph.get_path("Tavern", "Cave", {})
        assert path == ["Tavern", "Forest", "Cave"]

    def test_get_path_no_path(self, simple_graph):
        """get_path with no valid path should return empty list."""
        # Modify graph: remove Forest→Cave edge to make Cave unreachable from Tavern
        graph = LocationGraph(locations={
            "Tavern": Location(name="Tavern", connections=["Forest"]),
            "Forest": Location(name="Forest", connections=["Tavern"]),
            "Cave": Location(name="Cave", connections=[]),
        })
        path = graph.get_path("Tavern", "Cave", {})
        assert path == [] or path is None

    def test_get_path_same_node(self, simple_graph):
        """get_path from node to itself should return [node]."""
        path = simple_graph.get_path("Tavern", "Tavern", {})
        assert path == ["Tavern"]


# ------------------------------------------------------------------
# LocationGraph with Prerequisites and Locks
# ------------------------------------------------------------------

class TestLocationGraphWithGates:
    """Tests for travel gating via world_flags."""

    @pytest.fixture
    def gated_graph(self):
        """Graph with gated edges and locked locations."""
        locations = {
            "Village": Location(name="Village", connections=["Forest"]),
            "Forest": Location(
                name="Forest",
                connections=["Village", "Bridge", "Cave"],
            ),
            "Bridge": Location(
                name="Bridge",
                connections=["Forest", "Castle"],
                prerequisites=["bridge_repaired"],
            ),
            "Castle": Location(
                name="Castle",
                connections=["Bridge"],
                locked_until_flag="castle_key",
            ),
            "Cave": Location(
                name="Cave",
                connections=["Forest", "Dungeon"],
            ),
            "Dungeon": Location(
                name="Dungeon",
                connections=["Cave"],
                locked_until_flag="dungeon_open",
                prerequisites=["torch_lit"],
            ),
        }
        return LocationGraph(locations=locations)

    def test_travel_blocked_by_edge_prereq(self, gated_graph):
        """Village → Forest → Bridge should be blocked when bridge_repaired=False."""
        # Vill->For is free, For->Bridge requires bridge_repaired=True
        assert gated_graph.can_travel_to("Forest", "Bridge", {"bridge_repaired": False})[0] is False

    def test_travel_allowed_when_prereq_met(self, gated_graph):
        """When bridge_repaired=True, Forest → Bridge allowed."""
        assert gated_graph.can_travel_to("Forest", "Bridge", {"bridge_repaired": True})[0]

    def test_travel_blocked_by_location_lock(self, gated_graph):
        """Forest → Bridge → Castle blocked when castle_key=False."""
        assert gated_graph.can_travel_to("Bridge", "Castle", {"castle_key": False})[0] is False

    def test_travel_allowed_when_lock_met(self, gated_graph):
        """When castle_key=True, Bridge → Castle allowed."""
        assert gated_graph.can_travel_to("Bridge", "Castle", {"castle_key": True})[0]

    def test_travel_blocked_by_both_gates(self, gated_graph):
        """Cave → Dungeon needs torch_lit=True AND dungeon_open=True."""
        assert gated_graph.can_travel_to(
            "Cave", "Dungeon", {"torch_lit": True, "dungeon_open": False}
        )[0] is False
        assert gated_graph.can_travel_to(
            "Cave", "Dungeon", {"torch_lit": False, "dungeon_open": True}
        )[0] is False
        assert gated_graph.can_travel_to(
            "Cave", "Dungeon", {"torch_lit": True, "dungeon_open": True}
        )[0]

    def test_get_path_blocked_by_prereq(self, gated_graph):
        """get_path should return empty list when path blocked by prereq."""
        # Village → Forest → Bridge (blocked by bridge_repaired=False) → Castle
        path = gated_graph.get_path(
            "Village", "Castle", {"bridge_repaired": False, "castle_key": True}
        )
        assert path == [] or path is None

    def test_get_path_allowed_when_all_gates_open(self, gated_graph):
        """get_path should return full path when all gates are open."""
        path = gated_graph.get_path(
            "Village", "Castle", {"bridge_repaired": True, "castle_key": True}
        )
        assert path == ["Village", "Forest", "Bridge", "Castle"]

    def test_ungated_path_not_affected(self, gated_graph):
        """Ungated path (Village→Forest→Cave) should work regardless of flags."""
        path = gated_graph.get_path("Village", "Cave", {})
        assert path == ["Village", "Forest", "Cave"]


# ------------------------------------------------------------------
# LocationGraph can_travel_to return tuple (result, reason) - spec compliant
# ------------------------------------------------------------------

class TestCanTravelToReason:
    """Tests for can_travel_to returning reason string."""

    @pytest.fixture
    def gated_graph(self):
        locations = {
            "Town": Location(name="Town", connections=["Road"]),
            "Road": Location(
                name="Road",
                connections=["Town", "Gate"],
                prerequisites=["road_clear"],
            ),
            "Gate": Location(
                name="Gate",
                connections=["Road"],
                locked_until_flag="gate_open",
            ),
        }
        return LocationGraph(locations=locations)

    def test_can_travel_returns_true_and_reason(self, gated_graph):
        """can_travel_to should return (True, '') on success."""
        ok, reason = gated_graph.can_travel_to("Town", "Road", {"road_clear": True})
        assert ok is True
        assert reason == ""

    def test_can_travel_blocked_prereq_returns_reason(self, gated_graph):
        """can_travel_to should return (False, reason) when blocked by prereq."""
        ok, reason = gated_graph.can_travel_to("Town", "Road", {"road_clear": False})
        assert ok is False
        assert "road_clear" in reason.lower()

    def test_can_travel_blocked_lock_returns_reason(self, gated_graph):
        """can_travel_to should return (False, reason) when blocked by lock."""
        ok, reason = gated_graph.can_travel_to("Road", "Gate", {
            "road_clear": True, "gate_open": False
        })
        assert ok is False
        assert "gate_open" in reason.lower() or "lock" in reason.lower()


# ------------------------------------------------------------------
# Edge Cases
# ------------------------------------------------------------------

class TestLocationGraphEdgeCases:
    """Edge case tests for LocationGraph."""

    def test_empty_graph(self):
        """Empty graph should handle lookups gracefully."""
        graph = LocationGraph(locations={})
        assert graph.can_travel_to("A", "B", {})[0] is False
        assert graph.get_path("A", "B", {}) == []

    def test_single_node_graph(self):
        """Single node graph."""
        graph = LocationGraph(locations={
            "Start": Location(name="Start")
        })
        assert graph.can_travel_to("Start", "Start", {})[0]
        assert graph.get_path("Start", "Start", {}) == ["Start"]

    def test_disconnected_graph(self):
        """Two separate clusters with no path between them."""
        graph = LocationGraph(locations={
            "A": Location(name="A", connections=["B"]),
            "B": Location(name="B", connections=["A"]),
            "C": Location(name="C", connections=["D"]),
            "D": Location(name="D", connections=["C"]),
        })
        assert graph.can_travel_to("A", "C", {})[0] is False
        assert graph.get_path("A", "C", {}) == []
