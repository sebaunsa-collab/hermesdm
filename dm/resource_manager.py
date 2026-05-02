"""
resource_manager.py — Track HP, spell slots, hit dice, death saves.
Part of Scene Director's sub-engine suite. Extended with character
progression integration: spell slot recovery, feature recovery on rests.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple


# D&D 5e Spell Slot Table (full progression)
SPELL_SLOT_TABLE: Dict[int, List[int]] = {
    1: [2, 0, 0, 0, 0, 0, 0, 0, 0],
    2: [3, 0, 0, 0, 0, 0, 0, 0, 0],
    3: [4, 2, 0, 0, 0, 0, 0, 0, 0],
    4: [4, 3, 0, 0, 0, 0, 0, 0, 0],
    5: [4, 3, 2, 0, 0, 0, 0, 0, 0],
    6: [4, 3, 3, 0, 0, 0, 0, 0, 0],
    7: [4, 3, 3, 1, 0, 0, 0, 0, 0],
    8: [4, 3, 3, 2, 0, 0, 0, 0, 0],
    9: [4, 3, 3, 3, 1, 0, 0, 0, 0],
    10: [4, 3, 3, 3, 2, 0, 0, 0, 0],
    11: [4, 3, 3, 3, 2, 1, 0, 0, 0],
    12: [4, 3, 3, 3, 2, 1, 0, 0, 0],
    13: [4, 3, 3, 3, 2, 1, 1, 0, 0],
    14: [4, 3, 3, 3, 2, 1, 1, 0, 0],
    15: [4, 3, 3, 3, 2, 1, 1, 1, 0],
    16: [4, 3, 3, 3, 2, 1, 1, 1, 0],
    17: [4, 3, 3, 3, 2, 1, 1, 1, 1],
    18: [4, 3, 3, 3, 3, 1, 1, 1, 1],
    19: [4, 3, 3, 3, 3, 2, 1, 1, 1],
    20: [4, 3, 3, 3, 3, 2, 2, 1, 1],
}

DEATH_SAVE_THRESHOLD = 10


class ResourceManager:
    """Tracks HP, spell slots, hit dice, death saves per character."""

    def __init__(self, state: dict | None = None) -> None:
        self.state = state or {}

    # ── HP ────────────────────────────────────────────────────────────────

    def get_hp_current(self, state: dict | None = None) -> int:
        state = state or self.state
        return state.get("player", {}).get("hp_current", 10)

    def get_hp_max(self, state: dict | None = None) -> int:
        state = state or self.state
        return state.get("player", {}).get("hp_max", 10)

    def hp_is_critical(self, state: dict | None = None) -> bool:
        state = state or self.state
        current = self.get_hp_current(state)
        max_hp = self.get_hp_max(state)
        if max_hp <= 0:
            return False
        return current <= (max_hp // 4)

    def apply_damage(self, state: dict, damage: int) -> dict:
        player = state.setdefault("player", {})
        current = player.get("hp_current", 10)
        new_hp = max(0, current - damage)
        player["hp_current"] = new_hp

        changes = {"damage_applied": damage, "hp_before": current, "hp_after": new_hp}

        if new_hp <= 0:
            player["is_unconscious"] = True
            changes["triggered_unconscious"] = True
            if "death_saves" not in player:
                player["death_saves"] = {"successes": 0, "failures": 0}
            changes["death_saves_active"] = True

        return changes

    def heal(self, state: dict, amount: int) -> dict:
        player = state.setdefault("player", {})
        max_hp = player.get("hp_max", 10)
        current = player.get("hp_current", 0)

        if current <= 0:
            return {"healed": 0, "hp_after": current, "note": "cannot heal unconscious character"}

        new_hp = min(max_hp, current + amount)
        actual_healed = new_hp - current
        player["hp_current"] = new_hp
        return {"healed": actual_healed, "hp_before": current, "hp_after": new_hp}

    # ── Death Saves ───────────────────────────────────────────────────────

    def roll_death_save(self, state: dict, roll_value: int) -> dict:
        player = state.setdefault("player", {})
        saves = player.setdefault("death_saves", {"successes": 0, "failures": 0})

        result = {"roll": roll_value, "successes": saves["successes"],
                   "failures": saves["failures"], "stabilized": False, "dead": False}

        if roll_value == 1:
            saves["failures"] = min(3, saves["failures"] + 2)
            result["nat1"] = True
        elif roll_value == 20:
            saves["successes"] = 3
            player["hp_current"] = 1
            player["is_unconscious"] = False
            result["nat20"] = True
            result["hp_restored"] = 1
        elif roll_value >= DEATH_SAVE_THRESHOLD:
            saves["successes"] += 1
        else:
            saves["failures"] += 1

        result["successes"] = saves["successes"]
        result["failures"] = saves["failures"]

        if saves["successes"] >= 3:
            result["stabilized"] = True
            player["is_unconscious"] = False

        if saves["failures"] >= 3:
            result["dead"] = True
            player["is_dead"] = True
            state.setdefault("world_flags", {})["player_dead"] = True

        return result

    def reset_death_saves(self, state: dict) -> None:
        player = state.setdefault("player", {})
        player["death_saves"] = {"successes": 0, "failures": 0}
        player.pop("is_unconscious", None)
        player.pop("is_dead", None)

    # ── Spell Slots ───────────────────────────────────────────────────────

    def get_spell_slots(self, state: dict | None = None) -> dict:
        state = state or self.state
        player = state.get("player", {})
        return player.get("spell_slots", {
            "max": [0] * 9, "used": [0] * 9,
        })

    def init_spell_slots(self, state: dict, character_level: int) -> dict:
        if character_level < 1 or character_level > 20:
            character_level = 1
        max_slots = SPELL_SLOT_TABLE.get(character_level, SPELL_SLOT_TABLE[1])
        slots = {"max": list(max_slots), "used": [0] * 9}
        state.setdefault("player", {})["spell_slots"] = slots
        return slots

    def use_spell_slot(self, state: dict, level: int) -> bool:
        if level < 1 or level > 9:
            return False
        slots = self.get_spell_slots(state)
        max_avail = slots["max"][level - 1]
        used = slots["used"][level - 1]
        if used >= max_avail:
            return False
        slots["used"][level - 1] += 1
        state.setdefault("player", {})["spell_slots"] = slots
        return True

    def available_spell_slots(self, state: dict, level: int) -> int:
        slots = self.get_spell_slots(state)
        return max(0, slots["max"][level - 1] - slots["used"][level - 1])

    def recover_spell_slots(self, state: dict, rest_type: str) -> dict:
        """Recover spell slots on short or long rest.

        Long rest: all slots recovered.
        Short rest: only Warlock pact magic (all slots) and Arcane Recovery
        for Wizards (half level rounded up).
        """
        player = state.setdefault("player", {})
        slots = self.get_spell_slots(state)
        old_used = list(slots["used"])
        recovered_count = sum(old_used)

        if rest_type == "long":
            # Full recovery
            slots["used"] = [0] * 9
            player["spell_slots"] = slots
            return {"recovered_slots": recovered_count, "rest_type": "long",
                    "message": f"All {recovered_count} spell slots recovered."}

        elif rest_type == "short":
            # Only Warlock recovers all pact slots on short rest
            player_class = player.get("player_class", "").lower()
            if player_class == "warlock":
                slots["used"] = [0] * 9
                player["spell_slots"] = slots
                return {"recovered_slots": recovered_count, "rest_type": "short",
                        "message": f"Pact Magic: {recovered_count} slots recovered."}
            return {"recovered_slots": 0, "rest_type": "short",
                    "message": "No spell slots recovered on short rest (not Warlock)."}

        return {"recovered_slots": 0, "message": "Unknown rest type."}

    # ── Hit Dice ──────────────────────────────────────────────────────────

    def get_hit_dice(self, state: dict | None = None) -> dict:
        state = state or self.state
        player = state.get("player", {})
        return player.get("hit_dice", {"current": 1, "max": 1, "faces": 8})

    def init_hit_dice(self, state: dict, character_level: int, hit_die_faces: int = 8) -> dict:
        hd = {"current": max(1, character_level), "max": max(1, character_level),
              "faces": hit_die_faces}
        state.setdefault("player", {})["hit_dice"] = hd
        return hd

    def spend_hit_dice(self, state: dict, count: int = 1) -> dict:
        player = state.setdefault("player", {})
        hd = player.setdefault("hit_dice", {"current": 1, "max": 1, "faces": 8})

        if hd["current"] <= 0:
            return {"hp_healed": 0, "dice_remaining": 0, "error": "No hit dice remaining"}

        import random as _random
        max_spend = min(count, hd["current"])
        total_healed = 0
        for _ in range(max_spend):
            total_healed += _random.randint(1, hd.get("faces", 8))
        hd["current"] -= max_spend

        max_hp = player.get("hp_max", 10)
        current_hp = player.get("hp_current", 0)
        actual_heal = min(total_healed, max_hp - current_hp)
        player["hp_current"] = current_hp + actual_heal

        return {"hp_healed": actual_heal, "dice_spent": max_spend,
                "dice_remaining": hd["current"]}

    # ── Rests ─────────────────────────────────────────────────────────────

    def short_rest(self, state: dict, con_mod: int = 0) -> dict:
        """Process a short rest. Cost: spend hit dice for healing.

        Also recovers short-rest features and Warlock spell slots
        when character progression is enabled.
        """
        result = self.spend_hit_dice(state, count=1)
        if "error" in result:
            return result

        extra = {}
        # Character progression: recover short-rest features and spell slots
        if state.get("use_character_progression"):
            slot_result = self.recover_spell_slots(state, "short")
            if slot_result.get("recovered_slots", 0) > 0:
                extra["spell_slots"] = slot_result

            # Recover features with short-rest recovery
            from dm.class_features import recover_features
            player = state.setdefault("player", {})
            if player.get("features"):
                feat_result = recover_features(player, "short")
                if feat_result.get("count", 0) > 0:
                    extra["features"] = feat_result

        return {
            **result,
            "rest_type": "short",
            "message": f"Short rest complete. Recovered {result['hp_healed']} HP. "
                       f"{result['dice_remaining']} hit dice remaining.",
            "progression_effects": extra if extra else None,
        }

    def long_rest(self, state: dict, character_level: int = 1) -> dict:
        """Process a long rest. Full recovery per D&D 5e rules.

        Also recovers all features and spell slots when character
        progression is enabled.
        """
        player = state.setdefault("player", {})
        max_hp = player.get("hp_max", 10)
        old_hp = player.get("hp_current", max_hp)
        player["hp_current"] = max_hp

        # Restore half hit dice (min 1)
        hd = player.setdefault("hit_dice", {"current": 1, "max": 1, "faces": 8})
        hd_restored = max(1, (hd["max"] - hd["current"]) // 2)
        hd["current"] = min(hd["max"], hd["current"] + hd_restored)

        # Restore all spell slots
        slots = player.get("spell_slots", {"max": [0] * 9, "used": [0] * 9})
        slots["used"] = [0] * 9
        player["spell_slots"] = slots

        # Reset death saves
        player["death_saves"] = {"successes": 0, "failures": 0}
        player.pop("is_unconscious", None)

        extra = {}
        # Character progression: recover all features on long rest
        if state.get("use_character_progression"):
            from dm.class_features import recover_features
            if player.get("features"):
                feat_result = recover_features(player, "long")
                if feat_result.get("count", 0) > 0:
                    extra["features"] = feat_result

        return {
            "rest_type": "long",
            "hp_restored": max_hp - old_hp,
            "hp_before": old_hp,
            "hp_after": max_hp,
            "hit_dice_restored": hd_restored,
            "hit_dice_remaining": hd["current"],
            "spell_slots_restored": True,
            "message": f"Long rest complete. Fully healed ({max_hp} HP). "
                       f"Recovered {hd_restored} hit dice. Spell slots restored.",
            "progression_effects": extra if extra else None,
        }

    # ── Per-round flags ───────────────────────────────────────────────────

    def reset_round_flags(self, state: dict) -> None:
        player = state.setdefault("player", {})
        player["per_round_flags"] = {
            "action": False,
            "bonus": False,
            "reaction": False,
            "movement": False,
        }

    def mark_action_used(self, state: dict, action_type: str) -> bool:
        player = state.setdefault("player", {})
        flags = player.setdefault("per_round_flags", {
            "action": False, "bonus": False, "reaction": False,
        })
        if action_type in flags:
            if flags[action_type]:
                return False
            flags[action_type] = True
            return True
        return False

    def is_action_available(self, state: dict, action_type: str) -> bool:
        player = state.get("player", {})
        flags = player.get("per_round_flags", {})
        return not flags.get(action_type, False)
