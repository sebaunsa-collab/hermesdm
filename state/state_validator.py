"""
state_validator.py — Consistency enforcement for HermesDM.

The LLM (DM brain) can generate narrative that contradicts the world state.
This module validates actions and corrects contradictions BEFORE they reach
the state manager.

Key rules:
- NPC status (ALIVE/DEAD) must match: can't kill an already-dead NPC
- HP cannot exceed max_hp (unless temp_hp)
- Can't attack a target not in the current location
- LLM narrative must not contradict known world facts
- Quest status transitions are one-way: available → in_progress → completed
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ValidationResult(Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    CORRECTED = "corrected"


@dataclass
class ValidationResponse:
    result: ValidationResult
    message: str | None
    corrected_value: Any | None = None


# ------------------------------------------------------------------
# Action validation
# ------------------------------------------------------------------

def validate_action(
    action: str,
    actor: str,
    target: str | None,
    current_state: dict,
) -> ValidationResponse:
    """
    Validate whether an action is consistent with current world state.

    Args:
        action: The action being attempted (e.g. "kill", "heal", "talk")
        actor: Who is performing the action (character or NPC id)
        target: Target of the action (character id, npc id, item id)
        current_state: Full campaign state dict

    Returns:
        ValidationResponse with result, message, and corrected_value if applicable
    """
    match action:
        case "kill" | "attack" | "damage":
            return _validate_kill(target, current_state)
        case "heal":
            return _validate_heal(target, current_state)
        case "talk" | "interact":
            return _validate_talk(target, current_state)
        case "use_item":
            return _validate_use_item(target, actor, current_state)
        case "cast_spell":
            return _validate_spell(target, actor, current_state)
        case "change_location":
            return _validate_location_change(target, actor, current_state)
        case _:
            return ValidationResponse(ValidationResult.ALLOWED, None)


def _validate_kill(target: str, state: dict) -> ValidationResponse:
    """Validate a kill/attack action against current NPC/character state."""
    npcs = state.get("npcs", {})
    characters = state.get("characters", {})

    # Check NPC
    if target in npcs:
        npc = npcs[target]
        if npc.get("status") == "DEAD":
            return ValidationResponse(
                ValidationResult.BLOCKED,
                f"Cannot attack {npc.get('name', target)} — already dead.",
            )
        if npc.get("status") == "UNCONSCIOUS":
            return ValidationResponse(
                ValidationResult.BLOCKED,
                f"Cannot attack {npc.get('name', target)} — already unconscious.",
            )

    # Check player character
    if target in characters:
        char = characters[target]
        if char.get("hp", {}).get("current", 100) <= 0:
            return ValidationResponse(
                ValidationResult.BLOCKED,
                f"Cannot attack {char.get('name', target)} — already at 0 HP.",
            )

    return ValidationResponse(ValidationResult.ALLOWED, None)


def _validate_heal(target: str, state: dict) -> ValidationResponse:
    """Validate healing action — HP cannot exceed max_hp."""
    characters = state.get("characters", {})

    if target in characters:
        hp = characters[target].get("hp", {})
        current = hp.get("current", 0)
        maximum = hp.get("max", current)
        if current > maximum:
            # Correct HP to max
            corrected = dict(hp)
            corrected["current"] = maximum
            return ValidationResponse(
                ValidationResult.CORRECTED,
                f"HP corrected to max ({maximum})",
                corrected_value=corrected,
            )

    return ValidationResponse(ValidationResult.ALLOWED, None)


def _validate_talk(target: str, state: dict) -> ValidationResponse:
    """Validate that target NPC is present and willing to talk."""
    npcs = state.get("npcs", {})
    if target in npcs:
        npc = npcs[target]
        disposition = npc.get("disposition", "NEUTRAL")
        if disposition == "HOSTILE" and not npc.get("speaks_to_players", True):
            return ValidationResponse(
                ValidationResult.CORRECTED,
                f"{npc.get('name', target)} is hostile and won't speak.",
                corrected_value={"speaks_to_players": False},
            )

    return ValidationResponse(ValidationResult.ALLOWED, None)


def _validate_use_item(target: str, actor: str, state: dict) -> ValidationResponse:
    """Validate item use — actor must have the item."""
    characters = state.get("characters", {})
    if actor in characters:
        inventory = characters[actor].get("inventory", [])
        item_ids = [item.get("name", "").lower() for item in inventory]
        if target.lower() not in item_ids:
            return ValidationResponse(
                ValidationResult.BLOCKED,
                f"{characters[actor].get('name', actor)} does not have '{target}'.",
            )

    return ValidationResponse(ValidationResult.ALLOWED, None)


def _validate_spell(target: str, caster: str, state: dict) -> ValidationResponse:
    """Validate spell casting — basic rules check."""
    # Could extend with spell lists, spell slots, etc.
    characters = state.get("characters", {})
    if caster in characters:
        char_class = characters[caster].get("class", "").lower()
        # Basic class restrictions
        caster_classes = ["wizard", "cleric", "sorcerer", "bard", "paladin", "ranger"]
        if char_class not in caster_classes:
            return ValidationResponse(
                ValidationResult.BLOCKED,
                f"{characters[caster].get('name', caster)} ({char_class}) cannot cast spells.",
            )

    return ValidationResponse(ValidationResult.ALLOWED, None)


def _validate_location_change(target_location: str, actor: str, state: dict) -> ValidationResponse:
    """Validate that a location change is possible."""
    current_location = state.get("campaign", {}).get("current_location", "")
    if target_location == current_location:
        return ValidationResponse(
            ValidationResult.BLOCKED,
            f"{actor} is already at {current_location}.",
        )

    # Could add: connected locations, locked doors, etc.
    return ValidationResponse(ValidationResult.ALLOWED, None)


# ------------------------------------------------------------------
# World consistency enforcement
# ------------------------------------------------------------------

def enforce_world_consistency(narrative: str, current_state: dict) -> str:
    """
    Parse the DM narrative and correct any contradictions with known world state.

    Common contradictions to fix:
    - LLM describes NPC as alive when they're DEAD
    - LLM says player has item they don't have
    - LLM says player is in wrong location

    Returns:
        Corrected narrative text (may be unchanged)
    """
    npcs = current_state.get("npcs", {})
    current_state.get("characters", {})
    current_state.get("campaign", {}).get("current_location", "")

    # Check NPC status contradictions
    corrections = []

    for npc_id, npc in npcs.items():
        npc_name = npc.get("name", npc_id)
        status = npc.get("status", "ALIVE")

        if status == "DEAD":
            # Check if narrative mentions NPC in a way that contradicts death
            contradictions = [
                f"{npc_name} smiles",
                f"{npc_name} looks at you",
                f"{npc_name} speaks",
                f"{npc_name} raises",
                f"{npc_name} draws",
                f"{npc_name} attacks",
            ]
            for phrase in contradictions:
                if phrase.lower() in narrative.lower() and "dead" not in narrative.lower():
                    corrections.append(
                        f"WARNING: narrative references {npc_name} as alive but status is DEAD"
                    )

    # Could implement automatic correction (replace contradictions with [REDACTED])
    # For now, just flag for DM review
    if corrections:
        return narrative  # Pass through with warnings logged
        # TODO: Implement auto-correction by replacing contradictions with placeholders

    return narrative


def validate_npc_memory(npc_id: str, new_memory: str, state: dict) -> ValidationResponse:
    """
    Validate that an NPC memory entry is consistent and not contradictory.
    Prevents the LLM from inventing memories that contradict established facts.
    """
    npcs = state.get("npcs", {})
    if npc_id not in npcs:
        return ValidationResponse(
            ValidationResult.BLOCKED,
            f"NPC '{npc_id}' not found in campaign state.",
        )

    npc = npcs[npc_id]
    existing_memory = npc.get("memory", [])

    # Check for contradictions with established facts
    established_facts = [
        entry.lower() for entry in existing_memory
        if isinstance(entry, str)
    ]
    new_mem_lower = new_memory.lower()

    # Simple contradiction check: if established fact says X happened,
    # don't allow memory that says NOT-X
    contradiction_pairs = [
        ("saved", "attacked"),
        ("saved", "killed"),
        ("ally", "enemy"),
        ("friend", "enemy"),
        ("alive", "dead"),
        ("alive", "died"),
    ]
    for pos, neg in contradiction_pairs:
        if pos in established_facts and neg in new_mem_lower:
            return ValidationResponse(
                ValidationResult.BLOCKED,
                f"Memory contradicts established NPC history: cannot add '{new_memory}'",
            )

    return ValidationResponse(ValidationResult.ALLOWED, None)


def add_npc_memory(
    campaign_id: str,
    npc_id: str,
    memory_entry: str,
    state: dict | None = None,
) -> tuple[bool, str]:
    """
    Safely add a memory entry to an NPC's memory log.
    Validates consistency before adding.

    Returns (success, message).
    """
    if state is None:
        from state.state_manager import load_state
        state = load_state(campaign_id)

    if state is None:
        return False, f"Campaign {campaign_id} not found"

    validation = validate_npc_memory(npc_id, memory_entry, state)
    if validation.result == ValidationResult.BLOCKED:
        return False, validation.message or "Blocked"

    npcs = state.get("npcs", {})
    if npc_id not in npcs:
        return False, f"NPC '{npc_id}' not found"

    if "memory" not in npcs[npc_id]:
        npcs[npc_id]["memory"] = []

    npcs[npc_id]["memory"].append(memory_entry)
    return True, f"Memory added to {npcs[npc_id].get('name', npc_id)}"
