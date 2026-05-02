"""
scene_director.py — SceneDirector: the DM "brain" that decides WHAT happens.

Inverts the architecture: code decides scene type, LLM narrates.
Extended with character progression: XP award after combat end, level-up tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adapters.mode_b.action_router import ActionResolution
    from dm.encounter_engine import EncounterEngine
    from dm.npc_director import NPCDirector
    from dm.quest_engine import QuestEngine
    from dm.resource_manager import ResourceManager
    from dm.combat_flow import CombatFlow


@dataclass
class SceneDecision:
    """The SOLE interface between game logic and narrative generator."""

    scene_type: str = "exploration"
    narrative_instruction: str = ""
    enemies: list = field(default_factory=list)
    active_npc: dict | None = None
    location: str = ""
    mechanical_setup: str = ""
    world_changes: dict = field(default_factory=dict)
    quest_updates: list = field(default_factory=list)
    is_encounter: bool = False
    requires_combat_init: bool = False


class SceneDirector:
    """The DM brain. Decides scene type deterministically.

    Priority ladder (highest to lowest):
    1. forced_rest — HP <= 25% max
    2. combat_end_xp — combat just ended, award XP
    3. combat gate — active combat
    4. forced_encounter — scene_count % 4 == 0
    5. quest_event — active quest at location
    6. travel_gate — travel resolved
    7. npc_surprise — act_counter % 5 == 0
    8. social_gate — dialogue action
    9. default exploration
    """

    def __init__(self, state: dict | None = None) -> None:
        self.state = state or {}
        self._turn_counter = 0
        self._sub_engines: dict = {}
        self._init_sub_engines()

    def _init_sub_engines(self) -> None:
        from dm.encounter_engine import EncounterEngine
        from dm.npc_director import NPCDirector
        from dm.quest_engine import QuestEngine
        from dm.resource_manager import ResourceManager
        from dm.combat_flow import CombatFlow

        self._sub_engines = {
            "encounter": EncounterEngine(self.state),
            "npc": NPCDirector(self.state),
            "quest": QuestEngine(self.state),
            "resource": ResourceManager(self.state),
            "combat": CombatFlow(self.state),
        }

    @property
    def encounter_engine(self):
        return self._sub_engines.get("encounter")

    @property
    def npc_director(self):
        return self._sub_engines.get("npc")

    @property
    def quest_engine(self):
        return self._sub_engines.get("quest")

    @property
    def resource_manager(self):
        return self._sub_engines.get("resource")

    @property
    def combat_flow(self):
        return self._sub_engines.get("combat")

    def decide(self, state: dict, resolution) -> SceneDecision:
        self.state = state
        self._turn_counter = state.get("turn", 0)
        self._init_sub_engines()

        # 0. Check for just-ended combat — award XP before processing
        combat_just_ended = self._check_combat_just_ended(state)
        if combat_just_ended:
            return combat_just_ended

        # 1. Forced rest — HP critical
        hp_critical = self._resource_hp_is_critical()
        if hp_critical:
            return SceneDecision(
                scene_type="rest",
                narrative_instruction=(
                    "El personaje esta gravemente herido. Describe su agotamiento "
                    "y la necesidad de descansar. La fatiga es abrumadora."
                ),
                is_encounter=False,
                requires_combat_init=False,
            )

        # 2. Combat gate — active combat continues
        combat = state.get("combat", {})
        if combat.get("active", False):
            turn_actor = combat.get("current_turn", "el combatiente")
            enemies_alive = self._count_alive_enemies(state)
            narrative = (
                f"El combate continua. Turno de {turn_actor}. "
                f"Quedan {enemies_alive} enemigos. Narra la tension del momento."
            )
            return SceneDecision(
                scene_type="combat",
                narrative_instruction=narrative,
                enemies=state.get("combat", {}).get("initiative_order", []),
                is_encounter=True,
                requires_combat_init=False,
            )

        # 3. Forced encounter — periodic scene-based (every 8 scenes, not 4)
        scene_count = state.get("scene_count", 0)
        if scene_count > 0 and scene_count % 8 == 0:
            location = state.get("campaign", {}).get("current_location", "unknown")
            danger = state.get("world", {}).get("danger_level", 1)
            encounter_result = self._sub_engines["encounter"].roll_for_encounter(state)
            if encounter_result:
                scene_type, enemies, npc = encounter_result
                narrative = (
                    "Un encuentro! Describe como aparecen los enemigos "
                    "y la escena de combate que se desarrolla."
                )
                return SceneDecision(
                    scene_type=scene_type,
                    narrative_instruction=narrative,
                    enemies=enemies if enemies else [],
                    active_npc=npc,
                    location=location,
                    is_encounter=True,
                    requires_combat_init=(scene_type == "combat" and bool(enemies)),
                )

        # 4. Quest event — active quest objective near completion
        quest_updates = self._sub_engines["quest"].check_advancement(state, resolution)
        if quest_updates:
            narrative = (
                "Un evento relacionado con la mision activa. "
                "Describe pistas, recompensas o consecuencias de la mision."
            )
            return SceneDecision(
                scene_type="event",
                narrative_instruction=narrative,
                quest_updates=quest_updates,
                is_encounter=False,
            )

        # 5. Travel gate — player moved location
        if getattr(resolution, "travel_destination", None):
            destination = resolution.travel_destination
            return SceneDecision(
                scene_type="travel",
                narrative_instruction=f"Describe el viaje hacia {destination}. "
                f"El camino, el paisaje, los encuentros en ruta.",
                location=destination,
                is_encounter=False,
            )

        # 6. NPC surprise — periodic social event (every 6 acts, not 5)
        act_counter = state.get("act_counter", 0)
        if act_counter > 0 and act_counter % 6 == 0:
            npc_actions = self._sub_engines["npc"].resolve_actions(state)
            active_npc_data = None
            if npc_actions:
                active_npc_data = npc_actions[0]
            else:
                # Only pick NPCs that are at the player's current location
                npcs = state.get("npcs", {})
                current_loc = state.get("campaign", {}).get("current_location", "").lower()
                located_npcs = []
                for npc_id, npc_data in npcs.items():
                    npc_location = (npc_data.get("location", "") or "").lower()
                    # Include NPC if: no location set (always present), or matches current
                    if not npc_location or current_loc in npc_location or npc_location in current_loc:
                        located_npcs.append((npc_id, npc_data))
                if located_npcs:
                    import random
                    npc_id, npc_data = random.choice(located_npcs)
                    active_npc_data = {
                        "id": npc_id,
                        "name": npc_data.get("name", npc_id),
                        "disposition": npc_data.get("disposition", "neutral"),
                        "dialogue_hook": npc_data.get("dialogue_hook", ""),
                    }

            narrative = (
                "Un PNJ actua de manera inesperada. "
                "Describe la interaccion social que surge."
            )
            return SceneDecision(
                scene_type="social",
                narrative_instruction=narrative,
                active_npc=active_npc_data,
                is_encounter=False,
            )

        # 7. Social gate — player did dialogue/social action
        if resolution and getattr(resolution, "action_type", "") in (
            "dialogue", "intimidate", "persuade", "deceive"
        ):
            target = getattr(resolution, "target", "el PNJ")
            narrative = f"Describe la respuesta de {target} a la accion social del jugador."
            return SceneDecision(
                scene_type="social",
                narrative_instruction=narrative,
                is_encounter=False,
            )

        # 8. Default — exploration
        location = state.get("campaign", {}).get("current_location", "la zona")
        return SceneDecision(
            scene_type="exploration",
            narrative_instruction=(
                f"Describe la exploracion de {location}. "
                f"Se vivido con los detalles sensoriales y deja pistas para la mision."
            ),
            location=location,
            is_encounter=False,
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _resource_hp_is_critical(self) -> bool:
        try:
            return self._sub_engines["resource"].hp_is_critical(self.state)
        except Exception:
            player_hp = self.state.get("player", {}).get("hp_current", 100)
            max_hp = self.state.get("player", {}).get("hp_max", 100)
            if max_hp <= 0:
                return False
            return player_hp <= 0.25 * max_hp

    @staticmethod
    def _count_alive_enemies(state: dict) -> int:
        combat = state.get("combat", {})
        initiative = combat.get("initiative_order", [])
        alive = 0
        for c in initiative:
            if not c.get("is_player", False) and c.get("hp", {}).get("current", 1) > 0:
                alive += 1
        return alive

    @staticmethod
    def _check_combat_just_ended(state: dict) -> SceneDecision | None:
        """If combat just ended (all enemies defeated), award XP and return
        a SceneDecision with level-up info.

        Returns None if no combat just ended.
        """
        combat = state.get("combat", {})
        # Check if combat just ended (inactive but flagged as all defeated)
        if not combat.get("all_enemies_defeated", False):
            return None
        if combat.get("active", False):
            return None  # Combat still active, don't award yet

        # Character progression: award XP for defeated enemies
        if state.get("use_character_progression"):
            initiative = combat.get("initiative_order", [])
            defeated_enemies = [
                {"name": c.get("name", "enemy"), "cr": c.get("cr", 0)}
                for c in initiative
                if not c.get("is_player", False)
            ]

            if defeated_enemies:
                from dm.xp_engine import award_combat_xp

                # Award XP to the player character(s)
                player = state.get("player", {})
                if player:
                    characters = [player]
                    xp_result = award_combat_xp(characters, defeated_enemies, party_size=1)

                    # Update player state (map xp → xp_current for state compatibility)
                    char_result = xp_result["results"][0]["character"]
                    player["xp_current"] = char_result.get("xp", player.get("xp_current", 0))
                    player["level"] = char_result.get("level", player.get("level", 1))
                    player["proficiency_bonus"] = char_result.get("proficiency_bonus", player.get("proficiency_bonus", 2))

                    # Check for level-ups
                    levels_gained = xp_result["results"][0].get("levels_gained", [])
                    if levels_gained:
                        # Grant class features for new levels
                        class_name = player.get("player_class", "fighter")
                        from dm.class_features import grant_features_at_level
                        from dm.spell_engine import get_spell_slots, CASTER_TYPE_MAP
                        for lvl in levels_gained:
                            new_feats = grant_features_at_level(class_name, lvl)
                            player.setdefault("features", []).extend(new_feats)

                        # Update spell slots if caster
                        new_level = player["level"]
                        caster_type = CASTER_TYPE_MAP.get(class_name, "none")
                        if caster_type != "none":
                            new_slots = get_spell_slots(new_level, caster_type)
                            max_slots = [new_slots.get(i, 0) for i in range(1, 10)]
                            player.setdefault("spell_slots", {"max": [0] * 9, "used": [0] * 9})["max"] = max_slots

                        # Build level-up narrative
                        level_up_narrative = (
                            f"Victoria! Has ganado {xp_result['xp_per_player']} XP "
                            f"(total: {xp_result['total_xp']}). "
                            + ". ".join(xp_result["results"][0].get("messages", []))
                            + " Nuevas habilidades desbloqueadas."
                        )
                    else:
                        level_up_narrative = (
                            f"Victoria! Has ganado {xp_result['xp_per_player']} XP "
                            f"(total: {player.get('xp_current', 0)})."
                        )

                    # Reset the all_enemies_defeated flag
                    combat["all_enemies_defeated"] = False
                    state["combat"] = combat

                    return SceneDecision(
                        scene_type="event",
                        narrative_instruction=level_up_narrative,
                        is_encounter=False,
                        world_changes={
                            "combat_ended": True,
                            "xp_awarded": xp_result["xp_per_player"],
                            "total_xp": xp_result["total_xp"],
                            "level_up": len(levels_gained) > 0,
                            "levels_gained": levels_gained,
                        },
                    )

        # If no character progression or no player, just reset and return exploration
        combat["all_enemies_defeated"] = False
        state["combat"] = combat
        return SceneDecision(
            scene_type="exploration",
            narrative_instruction="El combate ha terminado. Respiras aliviado mientras el polvo se asienta.",
            is_encounter=False,
            world_changes={"combat_ended": True},
        )
