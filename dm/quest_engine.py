"""
quest_engine.py — Quest tracking with objective state machines.

Part of Scene Director's sub-engine suite. Tracks quests as state machines
with 7 objective types. Each objective has status: pending→active→completed/failed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Objective types
OBJECTIVE_TYPES = [
    "kill",           # Kill specific enemies
    "collect",        # Collect items
    "deliver",        # Deliver item to NPC/location
    "escort",         # Escort NPC safely
    "discover",       # Discover location/secret
    "talk_to",        # Talk to specific NPC
    "reach_location", # Reach a specific location
]

VALID_STATUSES = {"pending", "active", "completed", "failed"}


class QuestEngine:
    """Tracks quests as state machines with objective lists.

    Reads/writes state["quests"] for persistence.
    """

    def __init__(self, state: dict | None = None) -> None:
        self.state = state or {}

    # ── Quest CRUD ────────────────────────────────────────────────────────

    def create_quest(self, state: dict, quest_id: str, name: str,
                     objectives: List[dict],
                     description: str = "",
                     reward: str = "") -> dict:
        """Create a new quest and add to active quests.

        Args:
            state: Game state dict
            quest_id: Unique quest identifier
            name: Quest name
            objectives: List of {type, target, description, ...}
            description: Quest description
            reward: Quest reward text

        Returns:
            The created quest dict
        """
        quests = state.setdefault("quests", {"active": [], "completed": [],
                                             "failed": [], "by_id": {}})

        objectives_data = []
        for obj in objectives:
            objectives_data.append({
                "type": obj.get("type", "kill"),
                "target": obj.get("target", ""),
                "description": obj.get("description", ""),
                "status": "pending",
                "prerequisite_flag": obj.get("prerequisite_flag"),
            })

        quest = {
            "id": quest_id,
            "name": name,
            "description": description,
            "reward": reward,
            "status": "active",
            "objectives": objectives_data,
        }

        quests["active"].append(quest_id)
        quests["by_id"][quest_id] = quest
        return quest

    def get_quest(self, state: dict, quest_id: str) -> Optional[dict]:
        """Get a quest by ID."""
        return state.get("quests", {}).get("by_id", {}).get(quest_id)

    def get_active_quests(self, state: dict) -> List[dict]:
        """Get all active quests."""
        quests = state.get("quests", {}).get("by_id", {})
        active_ids = state.get("quests", {}).get("active", [])
        return [quests[qid] for qid in active_ids if qid in quests]

    # ── Objective Management ──────────────────────────────────────────────

    def update_objective(self, state: dict, quest_id: str,
                         objective_index: int,
                         new_status: str) -> Optional[dict]:
        """Update the status of a quest objective.

        Args:
            state: Game state
            quest_id: Quest identifier
            objective_index: Index of objective in quest's objectives list
            new_status: New status (active, completed, failed)

        Returns:
            Updated objective dict or None on error
        """
        quest = self.get_quest(state, quest_id)
        if not quest:
            return None

        objectives = quest.get("objectives", [])
        if objective_index < 0 or objective_index >= len(objectives):
            return None

        objective = objectives[objective_index]

        # Check prerequisite flag
        prereq = objective.get("prerequisite_flag")
        if prereq:
            world_flags = state.get("world_flags", {})
            if not world_flags.get(prereq, False):
                return None  # Blocked by prerequisite

        # Status transition validation
        current = objective.get("status", "pending")
        valid_transitions = {
            "pending": {"active"},
            "active": {"completed", "failed"},
        }
        if new_status not in valid_transitions.get(current, set()):
            return None  # Invalid transition

        objective["status"] = new_status
        return objective

    def activate_objective(self, state: dict, quest_id: str,
                           objective_index: int) -> Optional[dict]:
        """Activate a pending objective (pending → active)."""
        return self.update_objective(state, quest_id, objective_index, "active")

    def complete_objective(self, state: dict, quest_id: str,
                           objective_index: int) -> Optional[dict]:
        """Mark an objective as completed (active → completed)."""
        result = self.update_objective(state, quest_id, objective_index, "completed")
        if result:
            # Check if all objectives completed → quest completed
            quest = self.get_quest(state, quest_id)
            if quest:
                all_done = all(
                    obj.get("status") == "completed"
                    for obj in quest.get("objectives", [])
                )
                if all_done:
                    self._complete_quest(state, quest_id)
        return result

    def fail_objective(self, state: dict, quest_id: str,
                       objective_index: int) -> Optional[dict]:
        """Mark an objective as failed (active → failed)."""
        return self.update_objective(state, quest_id, objective_index, "failed")

    def _complete_quest(self, state: dict, quest_id: str) -> None:
        """Move quest from active to completed and set world flag."""
        quests = state.setdefault("quests", {"active": [], "completed": [],
                                             "failed": [], "by_id": {}})
        if quest_id in quests["active"]:
            quests["active"].remove(quest_id)
            quests["completed"].append(quest_id)

        quest = quests["by_id"].get(quest_id)
        if quest:
            quest["status"] = "completed"
            # Set world flag for quest completion
            flag_name = f"quest_{quest_id}_completed"
            state.setdefault("world_flags", {})[flag_name] = True

    # ── Advancement Check ─────────────────────────────────────────────────

    def check_advancement(self, state: dict,
                          resolution=None) -> List[dict]:
        """Check if any active quest objectives advanced.

        Called each turn by SceneDirector. Returns list of quest_updates.

        Args:
            state: Game state
            resolution: ActionResolution from _resolve()

        Returns:
            List of {quest_id, objective_index, status, ...} updates
        """
        updates = []
        active_quests = self.get_active_quests(state)

        for quest in active_quests:
            quest_id = quest["id"]
            for i, obj in enumerate(quest.get("objectives", [])):
                if obj["status"] != "active":
                    continue

                obj_type = obj.get("type", "")
                target = obj.get("target", "")

                # Check kill objective
                if obj_type == "kill" and resolution:
                    killed = getattr(resolution, "kill", False)
                    killed_target = getattr(resolution, "target", "")
                    if killed and target.lower() in killed_target.lower():
                        self.complete_objective(state, quest_id, i)
                        updates.append({
                            "quest_id": quest_id,
                            "objective_index": i,
                            "status": "completed",
                            "type": "kill",
                            "target": target,
                        })

                # Check reach_location objective
                if obj_type == "reach_location":
                    current_loc = state.get("campaign", {}).get("current_location", "")
                    if target.lower() in current_loc.lower():
                        self.complete_objective(state, quest_id, i)
                        updates.append({
                            "quest_id": quest_id,
                            "objective_index": i,
                            "status": "completed",
                            "type": "reach_location",
                            "location": target,
                        })

                # Check talk_to objective (removed from this — handled by NPC director)
                # For talk_to: NPC director handles dialogue completion

        return updates

    def get_quest_summary(self, state: dict) -> str:
        """Return a human-readable quest summary."""
        active = self.get_active_quests(state)
        if not active:
            return "No active quests."

        lines = ["📜 **Quest Log**"]
        for q in active:
            obj_count = len(q.get("objectives", []))
            completed = sum(1 for o in q.get("objectives", [])
                          if o.get("status") == "completed")
            progress = f"[{'█' * max(1, int(10 * completed / max(obj_count, 1)))}{'░' * max(0, 10 - int(10 * completed / max(obj_count, 1)))}] {completed}/{obj_count}"
            lines.append(f"**{q['name']}** {progress}")
            for o in q.get("objectives", []):
                icon = {"completed": "✅", "failed": "❌", "active": "🔄",
                       "pending": "⬜"}.get(o["status"], "⬜")
                lines.append(f"  {icon} {o['description'] or o['target']}")
        return "\n".join(lines)
