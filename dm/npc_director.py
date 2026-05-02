"""
npc_director.py — NPC agency: disposition, faction goals, independent actions.

Part of Scene Director's sub-engine suite. NPCs act based on disposition,
faction goals, and world state — not LLM whimsy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# Disposition ladder: range -100 to +100, thresholds define behavior
DISPOSITION_THRESHOLDS = {
    "hostile": (-100, -41),   # Attack on sight
    "wary": (-40, -11),      # Suspicious, won't help
    "neutral": (-10, 10),    # Default, business-like
    "friendly": (11, 40),    # Willing to help
    "allied": (41, 100),     # Actively assists, shares secrets
}

AGENDA_TYPES = [
    "reveal_secret",   # NPC shares a secret with the player
    "offer_quest",     # NPC gives a quest
    "betray",          # NPC turns on the player
    "ambush",           # NPC leads player into trap
    "help",            # NPC provides aid
]


class NPCDirector:
    """Resolves NPC actions independently each turn.

    NPCs act based on disposition, faction goals, and world state.
    Reads/writes state["npcs"] for persistence.
    """

    def __init__(self, state: dict | None = None) -> None:
        self.state = state or {}

    def resolve_actions(self, state: dict) -> List[dict]:
        """Resolve all NPC actions for this turn.

        Returns:
            List of action dicts with {npc_id, name, action, target, ...}
        """
        actions = []
        npcs = state.get("npcs", {})
        if not npcs:
            return actions

        player_hp_pct = self._get_player_hp_pct(state)

        for npc_id, npc in npcs.items():
            action = self._resolve_single(npc_id, npc, state, player_hp_pct)
            if action:
                actions.append(action)

        return actions

    def resolve_single_npc(self, state: dict, npc_id: str) -> Optional[dict]:
        """Resolve actions for a single NPC by ID."""
        npcs = state.get("npcs", {})
        npc = npcs.get(npc_id)
        if not npc:
            return None
        player_hp_pct = self._get_player_hp_pct(state)
        return self._resolve_single(npc_id, npc, state, player_hp_pct)

    def _resolve_single(self, npc_id: str, npc: dict, state: dict,
                        player_hp_pct: float) -> Optional[dict]:
        """Determine and resolve one NPC's action this turn."""
        base = {
            "npc_id": npc_id,
            "name": npc.get("name", npc_id),
            "disposition": npc.get("disposition", "neutral"),
            "faction": npc.get("faction", ""),
            "location": npc.get("location", ""),
        }

        disposition = base["disposition"].lower()

        # ── Hostile NPCs ────────────────────────────────────────
        if disposition == "hostile":
            # Attack if player is weakened (HP < 50%)
            if player_hp_pct < 0.5:
                return {
                    **base,
                    "action": "attack",
                    "target": "player",
                    "reason": f"{base['name']} attacks the weakened player",
                    "agenda": "ambush",
                    "dialogue_hook": "",
                }
            # Attack if faction at war
            if self._faction_at_war(state, npc):
                return {
                    **base,
                    "action": "attack",
                    "target": "player",
                    "reason": f"{base['name']} attacks due to faction war",
                    "agenda": "ambush",
                    "dialogue_hook": "",
                }
            return None  # Hostile but not acting this turn

        # ── Wary NPCs ──────────────────────────────────────────
        if disposition == "wary":
            return {
                **base,
                "action": "observe",
                "target": "player",
                "reason": f"{base['name']} watches cautiously",
                "agenda": "none",
                "dialogue_hook": f"{base['name']} te observa con desconfianza.",
            }

        # ── Neutral NPCs ───────────────────────────────────────
        if disposition == "neutral":
            # Check if NPC has a quest hook
            if npc.get("quest_hook"):
                return {
                    **base,
                    "action": "offer_quest",
                    "target": "player",
                    "reason": f"{base['name']} offers a quest",
                    "agenda": "offer_quest",
                    "quest_id": npc.get("quest_hook"),
                    "dialogue_hook": npc.get("dialogue_hook", "Tengo algo que pedirte."),
                }
            return None

        # ── Friendly / Allied NPCs ─────────────────────────────
        if disposition in ("friendly", "allied"):
            # Share secret or help
            if disposition == "allied" and npc.get("secret"):
                return {
                    **base,
                    "action": "reveal_secret",
                    "target": "player",
                    "reason": f"{base['name']} shares a secret",
                    "agenda": "reveal_secret",
                    "secret": npc.get("secret", ""),
                    "dialogue_hook": "He estado guardando esto...",
                }
            # Offer help if player is hurt
            if player_hp_pct < 0.5:
                return {
                    **base,
                    "action": "help",
                    "target": "player",
                    "reason": f"{base['name']} helps the wounded player",
                    "agenda": "help",
                    "heal_amount": 5,
                    "dialogue_hook": "Dejame ayudarte con esas heridas.",
                }
            return None

        return None

    # ── Utilities ─────────────────────────────────────────────────────────

    def _get_player_hp_pct(self, state: dict) -> float:
        """Get player HP as percentage (0.0 to 1.0)."""
        player = state.get("player", {})
        current = player.get("hp_current", 10)
        max_hp = player.get("hp_max", 10)
        if max_hp <= 0:
            return 1.0
        return current / max_hp

    def _faction_at_war(self, state: dict, npc: dict) -> bool:
        """Check if NPC faction is at war with player faction."""
        npc_faction = npc.get("faction", "")
        player_faction = state.get("player", {}).get("faction", "")
        if not npc_faction or not player_faction:
            return False
        war_map = state.get("world", {}).get("faction_relations", {})
        relation = war_map.get((npc_faction, player_faction), "")
        return relation == "war"

    def get_disposition(self, disposition_value: int) -> str:
        """Convert numeric disposition (-100 to +100) to label."""
        for label, (lo, hi) in DISPOSITION_THRESHOLDS.items():
            if lo <= disposition_value <= hi:
                return label
        return "neutral"

    def adjust_disposition(self, npc: dict, delta: int) -> int:
        """Adjust NPC disposition by delta, returning new value."""
        current = npc.get("disposition_value", 0)
        new_val = max(-100, min(100, current + delta))
        npc["disposition_value"] = new_val
        npc["disposition"] = self.get_disposition(new_val)
        return new_val

    def blocks_social(self, npc_disposition: str) -> bool:
        """Check if NPC disposition blocks social resolution."""
        # Hostile NPCs refuse parley; wary NPCs are suspicious but may be convinced
        return npc_disposition.lower() == "hostile"

    def can_offer_quest(self, npc: dict) -> bool:
        """Check if NPC can offer a quest."""
        return bool(npc.get("quest_hook"))

    def faction_blocks_parley(self, state: dict, npc: dict) -> bool:
        """Check if faction relations block social interaction."""
        npc_faction = npc.get("faction", "")
        player_faction = state.get("player", {}).get("faction", "")
        if not npc_faction or not player_faction:
            return False
        war_map = state.get("world", {}).get("faction_relations", {})
        return war_map.get((npc_faction, player_faction), "") == "war"
