"""
location_graph.py — Location graph with BFS pathfinding and progression gating.

Phase 2 of Narrative Progression Gates: defines a directed graph of locations
with prerequisites and lock flags that gate player travel.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Location:
    """A named location in the game world with travel constraints."""

    name: str
    description: str = ""
    connections: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    locked_until_flag: Optional[str] = None
    distance_from_previous: int = 1
    obstacles: list[str] = field(default_factory=list)

    def is_accessible(self, world_flags: dict) -> bool:
        """Check if this location is accessible given current world_flags.

        Returns True only when ALL prerequisites are met AND the lock flag
        (if set) is True.
        """
        for prereq in self.prerequisites:
            if not world_flags.get(prereq, False):
                return False
        if self.locked_until_flag and not world_flags.get(
            self.locked_until_flag, False
        ):
            return False
        return True


class LocationGraph:
    """A directed graph of Location nodes with BFS pathfinding and gating.

    Travel is allowed only along explicitly defined connection edges.
    The destination location's is_accessible() determines if travel
    is permitted (checks both prerequisites and lock flags).
    """

    def __init__(self, locations: dict[str, Location] | None = None) -> None:
        self._locations: dict[str, Location] = locations or {}

    @property
    def locations(self) -> dict[str, Location]:
        return self._locations

    def can_travel_to(
        self, current: str, destination: str, world_flags: dict
    ) -> tuple[bool, str]:
        """Check if travel from current to destination is possible.

        Returns (True, "") if travel is allowed.
        Returns (False, reason) if blocked by missing edge, prerequisite, or lock.
        """
        # Same location is always allowed
        if current == destination:
            return True, ""

        # Both nodes must exist
        if current not in self._locations:
            return False, f"Location '{current}' does not exist"
        if destination not in self._locations:
            return False, f"Location '{destination}' does not exist"

        source = self._locations[current]

        # Edge must exist
        if destination not in source.connections:
            return False, f"No path from '{current}' to '{destination}'"

        # Check destination accessibility (prerequisites + lock flag)
        dest = self._locations[destination]
        if not dest.is_accessible(world_flags):
            if dest.locked_until_flag and not world_flags.get(
                dest.locked_until_flag, False
            ):
                return False, (
                    f"'{destination}' is locked "
                    f"(requires '{dest.locked_until_flag}')"
                )
            missing = [
                p for p in dest.prerequisites
                if not world_flags.get(p, False)
            ]
            if missing:
                return False, (
                    f"'{destination}' requires prerequisites: "
                    f"{', '.join(missing)}"
                )
            return False, f"'{destination}' is not accessible"

        return True, ""

    def get_path(
        self, start: str, goal: str, world_flags: dict
    ) -> list[str]:
        """Find the shortest path from start to goal using BFS.

        Returns the path as a list of location names [start, ..., goal],
        or an empty list if no valid path exists (considering gates).
        """
        if start == goal:
            if start in self._locations:
                return [start]
            return []

        if start not in self._locations or goal not in self._locations:
            return []

        # BFS with visited set
        queue = deque([[start]])
        visited = {start}

        while queue:
            path = queue.popleft()
            current = path[-1]

            loc = self._locations[current]

            for neighbor in loc.connections:
                if neighbor in visited:
                    continue

                # Check if we can travel from current to neighbor
                ok, _ = self.can_travel_to(current, neighbor, world_flags)
                if not ok:
                    continue

                new_path = path + [neighbor]

                if neighbor == goal:
                    return new_path

                visited.add(neighbor)
                queue.append(new_path)

        return []
