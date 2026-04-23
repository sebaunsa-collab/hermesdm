"""
state_manager.py — Campaign state persistence.
Saves/loads world state as JSON in ~/.hermes/hermesdm/campaigns/{id}/state.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from campaign_settings import CampaignSettings

if TYPE_CHECKING:
    from state.npc_store import NPCRecord, NPCStore

CAMPAIGNS_DIR = Path.home() / ".hermes" / "hermesdm" / "campaigns"


def _ensure_dir(campaign_id: str) -> Path:
    campaign_dir = CAMPAIGNS_DIR / campaign_id
    campaign_dir.mkdir(parents=True, exist_ok=True)
    return campaign_dir


def _state_path(campaign_id: str) -> Path:
    return _ensure_dir(campaign_id) / "state.json"


def new_state(campaign_id: str, name: str, setting: str) -> dict:
    """
    Create a fresh campaign state.
    """
    from datetime import datetime as _dt

    state = {
        "campaign": {
            "id": campaign_id,
            "name": name,
            "setting": setting,
            "created": _dt.utcnow().isoformat(),
            "current_location": None,
            "status": "setup",  # "setup" until DM approves, then "active"
            "completed_at": None,
            "epilogue": None,
            "image_provider": "pollinations",  # pollinations | minimax | flux | nanobanana
        },
        "setup": {
            "description": "",
            "classes": None,  # None = usar defaults D&D. Lista[str] cuando el DM las define.
            "premise": "",
            "hook": "",
            "tone": "serious",
            "setting_type": setting,
            "created": _dt.utcnow().isoformat(),
            "approved": False,
            "lore": {
                "factions": {},
                "main_threat": "",
                "starting_location": "",
                "starting_location_desc": "",
                "npcs": {},
            },
        },
        "world": {},
        "npcs": {},
        "characters": {},
        "combat": {"active": False, "round": 0, "initiative": [], "current_turn": None},
        "quests": {"active": [], "completed": []},
        "history": [],
        "generated_images": [],
        "story_arc": None,
        "settings": CampaignSettings().to_dict(),
    }
    return state


def save_state(campaign_id: str, state: dict) -> None:
    """
    Persist state to JSON file. Creates campaign dir if needed.
    """
    path = _state_path(campaign_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def load_state(campaign_id: str) -> dict | None:
    """
    Load campaign state from JSON. Returns None if not found.
    """
    path = _state_path(campaign_id)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def campaign_exists(campaign_id: str) -> bool:
    return _state_path(campaign_id).exists()


def list_campaigns() -> list[dict]:
    """
    List all campaigns (id, name, setting) sorted by most recent.
    """
    campaigns = []
    if not CAMPAIGNS_DIR.exists():
        return campaigns

    for campaign_dir in CAMPAIGNS_DIR.iterdir():
        if campaign_dir.is_dir():
            state_file = campaign_dir / "state.json"
            if state_file.exists():
                try:
                    with open(state_file, encoding="utf-8") as f:
                        data = json.load(f)
                    campaigns.append(
                        {
                            "id": data.get("campaign", {}).get("id", campaign_dir.name),
                            "name": data.get("campaign", {}).get("name", "Unnamed"),
                            "setting": data.get("campaign", {}).get(
                                "setting", "unknown"
                            ),
                        }
                    )
                except Exception:
                    campaigns.append(
                        {
                            "id": campaign_dir.name,
                            "name": "Unnamed",
                            "setting": "unknown",
                        }
                    )

    # Sort by id descending (most recent first)
    campaigns.sort(key=lambda x: x["id"], reverse=True)
    return campaigns


def apply_world_change(campaign_id: str, key_path: str, value) -> dict:
    """
    Apply a world state change.
    key_path like "npcs.captain_vorn.status" or "world.main_threat"
    Returns updated state.
    """
    state = load_state(campaign_id)
    if state is None:
        raise ValueError(f"Campaign {campaign_id} not found")

    parts = key_path.split(".")
    current = state
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value

    save_state(campaign_id, state)
    return state


def get_settings(campaign_id: str) -> CampaignSettings:
    """
    Load CampaignSettings for a campaign. Returns defaults if not found.
    """
    state = load_state(campaign_id)
    if state is None:
        return CampaignSettings()
    settings_data = state.get("settings", {})
    return CampaignSettings.from_dict(settings_data)


def update_settings(
    campaign_id: str, key: str, value: str
) -> tuple[bool, str, CampaignSettings]:
    """
    Update a single setting for a campaign.
    Returns (success, message, updated_settings).
    """
    state = load_state(campaign_id)
    if state is None:
        return False, f"Campaign {campaign_id} not found", CampaignSettings()

    settings = CampaignSettings.from_dict(state.get("settings", {}))
    success, message = settings.apply_update(key, value)
    if success:
        state["settings"] = settings.to_dict()
        save_state(campaign_id, state)

    return success, message, settings


# ─────────────────────────────────────────────────────────────────────────────
# NPC Persistence Helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_npc_store(campaign_id: str) -> NPCStore:
    """Load NPCStore from campaign state, or return empty store."""
    state = load_state(campaign_id)
    if state is None:
        from state.npc_store import NPCStore
        return NPCStore()
    return NPCStore.from_dict(state.get("npcs", {}))


def save_npc_store(campaign_id: str, store: NPCStore) -> None:
    """Persist NPCStore into campaign state."""
    state = load_state(campaign_id)
    if state is None:
        return
    state["npcs"] = store.to_dict()
    save_state(campaign_id, state)


def add_npc_to_state(campaign_id: str, npc_record: NPCRecord) -> None:
    """Add an NPCRecord to campaign state and save."""
    store = load_npc_store(campaign_id)
    store.add(npc_record)
    save_npc_store(campaign_id, store)


def remove_npc_from_state(campaign_id: str, npc_id: str) -> bool:
    """Remove NPC from campaign state. Returns True if found and removed."""
    store = load_npc_store(campaign_id)
    result = store.remove(npc_id)
    if result:
        save_npc_store(campaign_id, store)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# NPC Memory & World Continuity — delegated to state_validator + world_builder
# ─────────────────────────────────────────────────────────────────────────────


def add_npc_memory(
    campaign_id: str,
    npc_id: str,
    memory_entry: str,
) -> tuple[bool, str]:
    """
    Safely add a memory entry to an NPC's memory log.
    Validates consistency before adding.

    Returns (success, message).
    """
    from state.state_validator import add_npc_memory as _sv_add

    state = load_state(campaign_id)
    return _sv_add(campaign_id, npc_id, memory_entry, state)


def get_world_summary(campaign_id: str) -> str:
    """
    Generate a brief world status summary for /recap and DM prompts.
    """
    from dm.world_builder import get_world_summary as _wb_summary

    return _wb_summary(campaign_id)


# ─────────────────────────────────────────────────────────────────────────────
# ChatState → state.json sync helpers
# ─────────────────────────────────────────────────────────────────────────────


def sync_chatstate_to_state(campaign_id: str, cs) -> dict | None:
    """
    Serialize ChatState (in-memory game state) into campaign state.json.

    Persists:
      - characters (player_name -> Character dict)
      - combat state (initiative order, current turn, round)

    Call this after every state-mutating command (join, attack, cast, etc.)
    so hermesdm-web can read the latest state.
    """
    state = load_state(campaign_id)
    if state is None:
        return None

    # ── Characters ────────────────────────────────────────────────────────────
    state["characters"] = {}
    for key, char in cs.characters.items():
        char_dict = char.to_dict()
        char_dict["player_id"] = key  # store key so web companion can look up
        state["characters"][key] = char_dict

    # ── Combat state ───────────────────────────────────────────────────────────
    if cs.combat_state is not None:
        combatants_data = []
        for c in cs.combat_state.initiative_order:
            combatants_data.append({
                "name": c.name,
                "initiative": c.initiative,
                "is_player": c.is_player,
                "is_active": c.is_active,
                "delayed": c.delayed,
                "held": c.held,
            })
        state["combat"] = {
            "active": cs.combat_state.active,
            "round": cs.combat_state.round,
            "initiative_order": combatants_data,
            "current_index": cs.combat_state.current_index,
            "current_turn": cs.combat_state.current_turn,
        }
    else:
        state["combat"] = {
            "active": False,
            "round": 0,
            "initiative_order": [],
            "current_index": 0,
            "current_turn": None,
        }

    save_state(campaign_id, state)
    return state


def append_history(
    campaign_id: str,
    event_text: str,
    entry_type: str = "narration",
    session: int | None = None,
) -> bool:
    """
    Append a narrative entry to the campaign's history log.

    Args:
        campaign_id: campaign identifier
        event_text: the narration/description text
        entry_type: narration | dice_roll | combat | dialogue | system
        session: optional session number (defaults to 1)

    Returns True on success, False if campaign not found.
    """
    state = load_state(campaign_id)
    if state is None:
        return False

    from datetime import datetime as _dt

    entry = {
        "event": event_text,
        "type": entry_type,
        "timestamp": _dt.utcnow().isoformat(),
    }
    if session is not None:
        entry["session"] = session

    if "history" not in state:
        state["history"] = []
    state["history"].append(entry)

    save_state(campaign_id, state)
    return True


if __name__ == "__main__":
    print("=== state_manager sanity test ===")
    # Test new state
    state = new_state("test_001", "Test Campaign", "fantasy")
    print(f"New state created: {state['campaign']['id']}")

    save_state("test_001", state)
    print(f"Saved to {state['campaign']['id']}")

    loaded = load_state("test_001")
    print(f"Loaded: {loaded['campaign']['name']}")

    print(f"Campaigns: {list_campaigns()}")
