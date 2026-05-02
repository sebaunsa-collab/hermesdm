"""
combat_flow.py — D&D 5e combat turn management: initiative, turn order, action economy.
Extended with concentration check integration for character progression.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional


class CombatFlow:
    """Manages D&D 5e combat flow: initiative, turns, action economy."""

    def __init__(self, state: dict | None = None) -> None:
        self.state = state or {}

    # ── Initiative ────────────────────────────────────────────────────────

    def roll_initiative(self, combatants: List[dict],
                        rng: Optional[random.Random] = None) -> List[dict]:
        rng = rng or random.Random()
        result = []
        for c in combatants:
            dex = c.get("dex_mod", c.get("dex", 10)) if isinstance(c, dict) else 0
            if isinstance(dex, int) and dex > 10:
                dex = (dex - 10) // 2
            elif isinstance(dex, (int, float)) and dex <= 10:
                dex = dex if -5 <= dex <= 5 else 0
            else:
                dex = 0

            roll = rng.randint(1, 20)
            initiative = roll + dex if isinstance(dex, (int, float)) else roll
            result.append({
                **c,
                "initiative_roll": roll,
                "dex_mod": dex,
                "initiative": initiative,
                "action_taken": False,
                "bonus_taken": False,
                "reaction_taken": False,
            })

        result.sort(key=lambda c: (
            -c["initiative"],
            -c.get("dex_mod", 0),
            -rng.randint(1, 20),
        ))
        return result

    # ── Combat Initialization ─────────────────────────────────────────────

    def init_combat(self, state: dict, enemies: List[dict],
                    players: Optional[List[dict]] = None,
                    rng: Optional[random.Random] = None) -> dict:
        rng = rng or random.Random()

        combatants = []
        for enemy in enemies:
            dex = enemy.get("abilities", {}).get("DEX", 10)
            dex_mod = (dex - 10) // 2
            combatants.append({
                "name": enemy.get("name", "Unknown Enemy"),
                "dex_mod": dex_mod,
                "hp": {"current": enemy.get("hp", 10), "max": enemy.get("hp", 10)},
                "ac": enemy.get("ac", 10),
                "attacks": enemy.get("attacks", []),
                "is_player": False,
            })

        if players is None:
            pdata = state.get("player", {})
            dex = pdata.get("stats", {}).get("dex", 10) if isinstance(pdata.get("stats"), dict) else pdata.get("dex", 10)
            dex_mod = (dex - 10) // 2
            combatants.append({
                "name": pdata.get("name", "Player"),
                "dex_mod": dex_mod,
                "hp": {"current": pdata.get("hp_current", 10),
                       "max": pdata.get("hp_max", 10)},
                "is_player": True,
            })
        else:
            for p in players:
                dex = p.get("stats", {}).get("dex", 10) if isinstance(p.get("stats"), dict) else p.get("dex", 10)
                dex_mod = (dex - 10) // 2
                combatants.append({
                    "name": p.get("name", "Player"),
                    "dex_mod": dex_mod,
                    "hp": {"current": p.get("hp_current", 10),
                           "max": p.get("hp_max", 10)},
                    "is_player": True,
                })

        ordered = self.roll_initiative(combatants, rng)

        combat_state = {
            "active": True,
            "round": 1,
            "initiative_order": ordered,
            "current_index": 0,
            "current_turn": ordered[0]["name"] if ordered else None,
            "all_enemies_defeated": False,
        }

        state["combat"] = combat_state
        return combat_state

    # ── Turn Management ───────────────────────────────────────────────────

    def next_turn(self, state: dict) -> dict:
        combat = state.get("combat", {})
        if not combat.get("active", False):
            return {"error": "No active combat"}

        initiative = combat.get("initiative_order", [])
        if not initiative:
            return {"error": "No combatants"}

        current_idx = combat.get("current_index", 0)
        current_idx += 1

        if current_idx >= len(initiative):
            alive_enemies = sum(1 for c in initiative
                              if not c.get("is_player", False)
                              and c.get("hp", {}).get("current", 1) > 0)
            if alive_enemies == 0:
                combat["active"] = False
                combat["all_enemies_defeated"] = True
                # Set world flag if boss was present
                if any(c.get("cr", 0) >= 5 for c in initiative):
                    state.setdefault("world_flags", {})["boss_defeated"] = True
                return {"combat_ended": True, "reason": "all enemies defeated"}

            combat["round"] += 1
            current_idx = 0
            for c in initiative:
                c["action_taken"] = False
                c["bonus_taken"] = False
                c["reaction_taken"] = False

        combat["current_index"] = current_idx
        combat["current_turn"] = initiative[current_idx]["name"]
        state["combat"] = combat

        return {
            "current_turn": initiative[current_idx]["name"],
            "round": combat["round"],
            "index": current_idx,
            "is_player": initiative[current_idx].get("is_player", False),
        }

    def get_current_combatant(self, state: dict) -> Optional[dict]:
        combat = state.get("combat", {})
        initiative = combat.get("initiative_order", [])
        idx = combat.get("current_index", 0)
        if idx < len(initiative):
            return initiative[idx]
        return None

    # ── Action Economy ────────────────────────────────────────────────────

    def can_use_action(self, state: dict) -> bool:
        c = self.get_current_combatant(state)
        return c is not None and not c.get("action_taken", False)

    def can_use_bonus(self, state: dict) -> bool:
        c = self.get_current_combatant(state)
        return c is not None and not c.get("bonus_taken", False)

    def can_use_reaction(self, state: dict) -> bool:
        c = self.get_current_combatant(state)
        return c is not None and not c.get("reaction_taken", False)

    def mark_action(self, state: dict, action_type: str = "action") -> bool:
        combat = state.get("combat", {})
        initiative = combat.get("initiative_order", [])
        idx = combat.get("current_index", 0)
        if idx >= len(initiative):
            return False

        c = initiative[idx]
        flag = f"{action_type}_taken"
        if flag in c and not c[flag]:
            c[flag] = True
            return True
        return False

    def resolve_action(self, state: dict, action_data: dict) -> dict:
        combat = state.get("combat", {})
        initiative = combat.get("initiative_order", [])

        action_type = action_data.get("type", "action")
        if action_type not in ("action", "bonus", "reaction"):
            action_type = "action"

        if not self.mark_action(state, action_type):
            return {"success": False, "error": f"{action_type} ya usado este turno"}

        target_idx = action_data.get("target_index")
        if target_idx is not None and 0 <= target_idx < len(initiative):
            target = initiative[target_idx]
            damage = action_data.get("damage", 0)
            hit = action_data.get("hit", False)
            if hit and damage > 0:
                target_hp = target.setdefault("hp", {"current": 10, "max": 10})
                target_hp["current"] = max(0, target_hp["current"] - damage)

                # Character progression: concentration check
                concentration_result = self._check_concentration(state, target, damage)

                result = {
                    "success": True,
                    "hit": True,
                    "damage": damage,
                    "target": target.get("name", "unknown"),
                    "target_hp_remaining": target_hp["current"],
                    "killed": target_hp["current"] <= 0,
                }
                if concentration_result is not None:
                    result["concentration"] = concentration_result
            else:
                result = {"success": True, "hit": False, "miss": True}
        else:
            result = {"success": True, "target": None}

        state["combat"] = combat
        return result

    def _check_concentration(self, state: dict, target: dict, damage: int) -> Optional[dict]:
        """Check concentration when a concentrating caster takes damage.

        Returns None if no concentration to check, or dict with check result.
        """
        if not state.get("use_character_progression"):
            return None

        # Check if target is player and has active concentration effects
        player = state.get("player", {})
        active_effects = player.get("active_effects", [])
        has_concentration = any(e.get("type") == "concentration" for e in active_effects)

        if not has_concentration:
            return None

        con_stat = player.get("stats", {}).get("con", 10)
        con_mod = (con_stat - 10) // 2

        # Check if player is unconscious — auto fail
        if player.get("is_unconscious", False):
            # Remove all concentration effects
            player["active_effects"] = [e for e in active_effects if e.get("type") != "concentration"]
            return {"saved": False, "dc": 0, "auto_fail": True,
                    "reason": "Unconscious — concentration broken."}

        from dm.spell_engine import concentration_save
        saved, dc = concentration_save(damage_taken=damage, con_mod=con_mod)

        if not saved:
            # Remove all concentration effects
            player["active_effects"] = [e for e in active_effects if e.get("type") != "concentration"]
            return {"saved": False, "dc": dc, "auto_fail": False,
                    "reason": f"Failed concentration save (DC {dc}). Concentration broken."}

        return {"saved": True, "dc": dc, "reason": f"Concentration maintained (DC {dc})."}

    def get_initiative_display(self, state: dict) -> str:
        combat = state.get("combat", {})
        initiative = combat.get("initiative_order", [])
        if not initiative:
            return "No combatants"

        lines = [f"⚔️ **Round {combat.get('round', 1)}**"]
        for i, c in enumerate(initiative):
            marker = " → " if i == combat.get("current_index", 0) else "    "
            name = c.get("name", "???")
            hp_cur = c.get("hp", {}).get("current", 0)
            hp_max = c.get("hp", {}).get("max", 1)
            bar = "█" * max(1, int(10 * hp_cur / hp_max)) + "░" * max(0, 10 - int(10 * hp_cur / hp_max))
            lines.append(f"{marker}**{name}** [{bar}] {hp_cur}/{hp_max} HP")
        return "\n".join(lines)
