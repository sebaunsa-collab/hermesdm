"""
encounter_engine.py — Deterministic encounter generation.

EncounterEngine selects enemies by location danger (1-5) + milestone tier (1-3).
Uses seeded RNG for reproducibility: same campaign_id + turn → same encounter.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from dm.enemy_pool import DANGER_TO_CR, ENEMIES_BY_BIOME, Enemy


class EncounterEngine:
    """Generates encounters based on scene context, player level, and location.

    Deterministic given same seed state (campaign_id + turn_number).
    Uses weighted random selection by CR bracket.
    """

    def __init__(self, state: dict | None = None) -> None:
        self.state = state or {}

    def roll_for_encounter(
        self, state: dict,
        rng: Optional[random.Random] = None,
    ) -> Optional[Tuple[str, List[dict], Optional[dict]]]:
        """Generate a random encounter for the current location.

        Args:
            state: Game state dict
            rng: Optional seeded Random for deterministic testing

        Returns:
            (scene_type, enemies_list, npc|None) or None if no encounter
        """
        # Determine location and biome
        location = state.get("campaign", {}).get("current_location", "")
        biome = self._determine_biome(state, location)

        # Get danger level (1-5) and milestone tier (1-3)
        danger = state.get("world", {}).get("danger_level", 2)
        milestone_tier = self._get_milestone_tier(state)

        # Get CR range
        cr_range = self._get_cr_range(danger, milestone_tier)

        # Seeded RNG for determinism
        if rng is None:
            seed_str = state.get("campaign", {}).get("id", "default") + str(state.get("turn", 0))
            rng = random.Random(hash(seed_str))

        # Get eligible enemies for this biome in CR range
        candidates = self._get_candidates(biome, cr_range)

        if not candidates:
            return None  # No matching enemies → exploration

        # Select 1-3 enemies (weighted random)
        num_enemies = rng.randint(1, min(3, len(candidates)))
        selected = rng.sample(candidates, min(num_enemies, len(candidates)))

        # Build enemy dicts
        enemies = [e.to_dict() for e in selected]

        # Determine scene type: combat or social
        # 20% chance of social encounter if NPCs exist in area
        npcs = state.get("npcs", {})
        if npcs and rng.random() < 0.2:
            # Social encounter
            npc_id = rng.choice(list(npcs.keys()))
            npc = npcs.get(npc_id, {})
            return ("social", [], {
                "id": npc_id,
                "name": npc.get("name", npc_id),
                "disposition": npc.get("disposition", "NEUTRAL"),
                "dialogue_hook": npc.get("dialogue_hook", ""),
            })

        return ("combat", enemies, None)

    def _determine_biome(self, state: dict, location: str) -> str:
        """Determine biome from location name or world state."""
        biome = state.get("world", {}).get("biome", "")
        if biome:
            return biome

        # Heuristic: check location keywords
        loc_lower = location.lower()
        if any(w in loc_lower for w in ("bosque", "forest", "wood", "arbol", "tree", "selva", "jungle")):
            return "forest"
        if any(w in loc_lower for w in ("mazmorra", "dungeon", "cueva", "cave", "tumba", "tomb",
                                          "catacumba", "ruina", "ruin", "templo", "temple",
                                          "crypt", "cripta")):
            return "dungeon"
        if any(w in loc_lower for w in ("ciudad", "city", "aldea", "village", "calle", "street",
                                          "mercado", "market", "taberna", "tavern", "gremio", "guild")):
            return "urban"

        # Default to first available biome
        return "forest"

    def _get_milestone_tier(self, state: dict) -> int:
        """Get milestone tier (1-3) from state."""
        # Check story_arc for milestone tier
        story = state.get("story_arc", {})
        milestones = story.get("milestones", [])
        if not milestones:
            return 1

        current = story.get("current_milestone", 0)
        # Tier ramps up as campaign progresses
        total = len(milestones)
        if total <= 0:
            return 1
        progress = current / max(total, 1)
        if progress > 0.66:
            return 3
        if progress > 0.33:
            return 2
        return 1

    def _get_cr_range(self, danger: int, milestone_tier: int) -> Tuple[float, float]:
        """Get CR range [min, max] for danger level + milestone tier."""
        base = DANGER_TO_CR.get(danger, (0.0, 1.0))
        cr_min, cr_max = base
        # Milestone tier adds to CR ceiling
        cr_max += {
            1: 0.0,
            2: 1.0,
            3: 2.0,
        }.get(milestone_tier, 0.0)
        return (cr_min, cr_max)

    def _get_candidates(self, biome: str, cr_range: Tuple[float, float]) -> List[Enemy]:
        """Get eligible enemies for biome within CR range."""
        enemies = ENEMIES_BY_BIOME.get(biome, [])
        if not enemies:
            # Fallback: try forest
            enemies = ENEMIES_BY_BIOME.get("forest", [])

        cr_min, cr_max = cr_range
        return [e for e in enemies if cr_min <= e.cr <= cr_max]
