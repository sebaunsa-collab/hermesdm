"""
dm/image_prompt_builder.py — Image prompt builder for HermesDM scenes.

Builds prompts for D&D image generation based on scene context.
Used by the image generation pipeline (Pollinations.ai or paid providers).

Usage:
    from dm.image_prompt_builder import build_closure_image_prompt

    prompt = build_closure_image_prompt(state, closure_data)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from state.state_manager import GameState


def build_closure_image_prompt(
    state: GameState,
    closure_data: dict,
) -> str:
    """
    Build an image generation prompt for campaign closure.

    Creates an epic, cinematic prompt describing the campaign's final moment
    based on the closure data and campaign state.

    Args:
        state: Full campaign state dict from state_manager
        closure_data: Dict returned by NarrativeGenerator.generate_closure()
            - narrative: str
            - quest_closure: dict
            - npc_fates: dict
            - character_summaries: dict
            - triggered_image: bool

    Returns:
        str: Image prompt suitable for Pollinations.ai or similar
    """
    campaign = state.get("campaign", {})
    world = state.get("world", {})
    characters = state.get("characters", {})
    settings = state.get("settings", {})

    campaign_name = campaign.get("name", "Unknown Campaign")
    setting = campaign.get("setting", "fantasy")
    tone = settings.get("narrative_tone", "epic")

    # Build list of living characters
    living_chars = []
    dead_chars = []
    for char_id, char_data in characters.items():
        if isinstance(char_data, dict):
            status = char_data.get("status", "alive")
            name = char_data.get("name", char_id)
        else:
            status = "alive"
            name = char_id

        if status == "alive":
            living_chars.append(name)
        else:
            dead_chars.append(name)

    # Determine scene type based on setting
    setting_descriptions = {
        "fantasy": "a grand fantasy kingdom, epic final scene, golden sunset, heroes standing tall",
        "scifi": "a futuristic space station, control room, heroes silhouetted against stars",
        "horror": "an abandoned castle, misty graveyard, survivors emerging from darkness",
        "tavern": "a cozy tavern, warm firelight, heroes raising their drinks in victory",
        "dungeon": "a treasure chamber, torches lighting ancient halls, victorious heroes",
    }

    base_scene = setting_descriptions.get(setting, setting_descriptions["fantasy"])

    # Build the image prompt
    tone_prefix = {
        "epic": "epic cinematic dramatic lighting, ",
        "dark": "dark moody atmospheric, ",
        "serious": "realistic cinematic, ",
        "funny": "warm colorful whimsical, ",
    }.get(tone, "cinematic ")

    prompt_parts = [
        tone_prefix,
        base_scene,
        f", campaign: {campaign_name}",
    ]

    # Add living characters to the scene
    if living_chars:
        chars_str = ", ".join(living_chars[:4])  # Max 4 characters
        prompt_parts.append(f", {chars_str} in the scene")

    # Add atmospheric elements
    if dead_chars:
        prompt_parts.append(", memorial candles, fallen heroes remembered")

    # Add world change context
    world_changes = world.get("changes", [])
    if world_changes:
        prompt_parts.append(", world forever changed")

    # Final touch for epic tone
    if tone == "epic":
        prompt_parts.append(", legendary status, monumental")

    prompt = "".join(prompt_parts)

    # Ensure it's a single good prompt
    prompt = prompt.strip()
    if not prompt:
        prompt = f"epic campaign finale {campaign_name}, cinematic, D&D 5e art style"

    return prompt
