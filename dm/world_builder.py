"""
world_builder.py — Generate a new campaign world on /newgame.
Creates setting, starting location, and NPCs from templates.
No game mechanics here — pure world generation.
"""

import random
import uuid
from datetime import datetime

from state.state_manager import new_state, save_state
from state.templates import SETTINGS as TEMPLATES
from state.templates import get_template


def extract_classes_from_text(text: str) -> list[str] | None:
    """
    Extrae la lista de clases del texto del setup.

    Patrones detectados:
    - "clases: Foo, Bar, Baz"
    - "classes: Foo, Bar, Baz"
    - "con las siguientes clases: Foo, Bar, Baz"
    - "las clases son: Foo, Bar"
    """
    import re
    patterns = [
        r'clases?\s*:\s*(.+?)(?:\n|$)',
        r'clases?\s+son\s*:\s*(.+?)(?:\n|$)',
        r'con\s+las?\s+siguientes?\s+clases?\s*:\s*(.+?)(?:\n|$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).strip()
            # Split por coma y limpiar
            classes = [c.strip() for c in raw.split(',') if c.strip()]
            if classes:
                return classes
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Legacy world settings (used as fallback)
# ─────────────────────────────────────────────────────────────────────────────

SETTINGS = {
    "fantasy": {
        "name": "The Kingdom of Valdris",
        "description": (
            "A realm scarred by a war that ended a decade ago. The old king's death "
            "remains shrouded in mystery, and whispers of a returning dragon "
            "have begun to spread from the northern settlements."
        ),
        "starting_location": "The Rusty Anchor Tavern",
        "starting_location_desc": (
            "A weathered tavern at the edge of the capital. Firelight flickers "
            "across worn wooden tables, and the smell of ale and woodsmoke fills the air. "
            "A hooded stranger nurses a drink in the corner."
        ),
        "factions": {
            "royal_guard": "SHADOWED",
            "thieves_guild": "RISING",
            "templars": "DOMINANT"
        },
        "main_threat": "Unknown — rumors of dragon attacks in the north"
    },
    "scifi": {
        "name": "Nexus Station",
        "description": (
            "A massive space station at the crossroads of three trade routes. "
            "Corporate factions compete for control while smuggler crews "
            "slip through the station's labyrinthine docking bays."
        ),
        "starting_location": "The Drift Bar",
        "starting_location_desc": (
            "A dimly lit bar spinning in the station's outer ring. "
            "Holographic ads flicker above the counter, and the hum of "
            "the station's life support is a constant reminder of the void outside."
        ),
        "factions": {
            "megacorp": "DOMINANT",
            "syndicate": "RISING",
            "free_merchants": "WEEKED"
        },
        "main_threat": "Corporate espionage and missing cargo shipments"
    },
    "horror": {
        "name": "Ravenhollow Manor",
        "description": (
            "A fog-shrouded coastal town where the locals speak in whispers. "
            "The old manor on the hill has been abandoned for fifty years, "
            "but lately its windows glow at night."
        ),
        "starting_location": "The Sailor's Rest Inn",
        "starting_location_desc": (
            "A cramped inn near the harbor. The floorboards creak with each step, "
            "and the fireplace casts long, shifting shadows. The innkeeper "
            "refuses to look out the window after dark."
        ),
        "factions": {
            "town_council": "CORRUPT",
            "cultists": "HIDDEN",
            "fishermen": "FRIGHTENED"
        },
        "main_threat": "Something in the manor — unknown and growing"
    }
}


NPC_TEMPLATES = [
    {
        "name": "Captain Vorn",
        "role": "Retired soldier",
        "disposition": "Cautious",
        "location": "tavern",
        "race": "human",
        "appearance": "Grizzled man with a scarred jaw and watchful eyes",
        "secret": "Deserted the royal guard after the old king's death",
        "goals": ["Protect the innocent", "Find the truth about the old king"]
    },
    {
        "name": "Mira the Wise",
        "role": "Scholar",
        "disposition": "Friendly",
        "location": "tavern",
        "race": "elf",
        "appearance": "Silver-haired elf with ancient eyes and ink-stained fingers",
        "secret": "Knows what really happened to the old king",
        "goals": ["Protect ancient knowledge", "Guide worthy adventurers"]
    },
    {
        "name": "Jax the Quick",
        "role": "Thief",
        "disposition": "Sarcastic",
        "location": "tavern",
        "race": "halfling",
        "appearance": "Quick-footed halfling with a grin that's always calculating",
        "secret": "Owes a debt to the thieves guild — dangerous to be seen with her",
        "goals": ["Survive", "Get rich", "Pay off the debt"]
    },
    {
        "name": "Brother Aldric",
        "role": "Templar priest",
        "disposition": "Righteous",
        "location": "town",
        "race": "dwarf",
        "appearance": "Broad-shouldered dwarf in temple armor, holy symbol visible",
        "secret": "His order is corrupt — he's the only honest one left",
        "goals": ["Serve the light", "Reform his order from within"]
    },
    {
        "name": "Sera Nightshade",
        "role": "Mysterious stranger",
        "disposition": "Enigmatic",
        "location": "tavern",
        "race": "tiefling",
        "appearance": "Pale tiefling with dark eyes and a serpentine smile",
        "secret": "Works for the thieves guild — sent to assess the party",
        "goals": ["Complete her mission", "Keep her employers happy"]
    }
]


def generate_npcs(count: int = 3) -> dict:
    """Generate N random NPCs from templates."""
    chosen = random.sample(NPC_TEMPLATES, min(count, len(NPC_TEMPLATES)))
    npcs = {}
    for tmpl in chosen:
        npc_id = tmpl["name"].lower().replace(" ", "_")
        npcs[npc_id] = {
            "name": tmpl["name"],
            "role": tmpl["role"],
            "status": "ALIVE",
            "location": tmpl["location"],
            "disposition": tmpl["disposition"],
            "race": tmpl["race"],
            "disposition_value": 0,  # -100 hostile to +100 friendly
            "relationship_to_party": "stranger",
            "memory": [],
            "goals": tmpl["goals"],
            "mood": tmpl["disposition"].lower(),
            "appearance": tmpl["appearance"],
            "secret": tmpl["secret"],
            "dialogue_style": _get_dialogue_style(tmpl["disposition"])
        }
    return npcs


def generate_setup_with_ai(description: str, tone: str = "serious", setting: str = "fantasy") -> dict:
    """
    Generate campaign setup (premise, hook, lore, factions, NPCs) using AI.
    Falls back to build_world() templates if AI is unavailable.

    Args:
        description: Free-text description from the DM
        tone: Narrative tone (dark, heroic, comedic, epic, serious)
        setting: Setting type (fantasy, scifi, horror)

    Returns:
        dict with keys: premise, hook, tone, setting_type, lore (factions,
        main_threat, starting_location, starting_location_desc, npcs)
    """
    import json
    import os

    # Extraer clases del texto antes de generar
    extract_classes_from_text(description)

    # Try AI generation
    try:
        api_key = os.getenv("MINIMAX_API_KEY", "")
        if not api_key:
            raise ValueError("MINIMAX_API_KEY not set")

        from dm.provider_client import MiniMaxProvider

        provider = MiniMaxProvider(api_key=api_key)

        prompt = f"""Eres un DM de D&D 5e. El DM quiere una campaña con esta descripción:

"{description}"

Tono solicitado: {tone}
Setting: {setting}

Generá:
1. Una "premise" de 2-3 oraciones: qué son los personajes y por qué están juntos
2. Un "hook" narrativo para el primer encuentro: qué pasa, qué deben hacer los PJ
3. Descripción del "starting_location": un lugar específico donde empieza la campaña
4. Una "main_threat": cuál es el conflicto central
5. Facciones: 2-3 facciones en tensión (nombre, estado: DOMINANT/RISING/HIDDEN/etc.)
6. NPCs iniciales: 2-3 NPCs relevantes con nombre, rol, y una línea de diálogo característica

Respondé en español, en JSON con este formato exacto:
{{
  "premise": "...",
  "hook": "...",
  "starting_location": "...",
  "starting_location_desc": "...",
  "main_threat": "...",
  "factions": {{ "nombre_faccion": "ESTADO", ... }},
  "npcs": [{{ "name": "...", "role": "...", "dialogue": "..." }}, ...]
}}
No escribas nada más que el JSON."""

        response = provider.text(
            prompt,
            system="Eres un DM creativo de D&D 5e. Solo respondés en JSON válido.",
            max_tokens=800,
            temperature=0.85,
        )

        # Parse JSON from response
        raw = response.text.strip()
        # Try to extract JSON from markdown code blocks
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

        parsed = json.loads(raw)

        return {
            "description": description,
            "premise": parsed.get("premise", ""),
            "hook": parsed.get("hook", ""),
            "tone": tone,
            "setting_type": setting,
            "approved": False,
            "lore": {
                "factions": parsed.get("factions", {}),
                "main_threat": parsed.get("main_threat", ""),
                "starting_location": parsed.get("starting_location", ""),
                "starting_location_desc": parsed.get("starting_location_desc", ""),
                "npcs": parsed.get("npcs", []),
            },
        }

    except Exception as e:
        # Fallback: use template-based world builder, customized with description
        import warnings
        import re
        warnings.warn(f"AI setup generation failed ({e}), falling back to templates")

        # Parse key elements from the user's description
        desc_lower = description.lower()
        threat = ""
        location = ""

        # Extract threat/antagonist hints from description
        threat_patterns = [
            r"rey demonio",
            r"rey humano",
            r"dragón",
            r"demon[io]",
            r"villano",
            r"corrupto",
            r"tirano",
            r"malvado",
            r"amenaza",
            r"dr.?king",
            r"demon.?king",
        ]
        for pat in threat_patterns:
            m = re.search(pat, desc_lower)
            if m:
                threat = m.group(0).capitalize()
                break

        # Detect setting type from description
        if any(w in desc_lower for w in ["ciudad", "puerto", "reino", "palacio", "castillo"]):
            location = "Ciudad amurallada"
        elif any(w in desc_lower for w in ["bosque", "selva", "montaña", "cueva", "mazmorra"]):
            location = "Tierras salvajes"
        else:
            location = "Un lugar olvidado"

        # Detect tone
        detected_tone = tone
        if any(w in desc_lower for w in ["serio", "político", "oscuro", "dark"]):
            detected_tone = "dark"
        elif any(w in desc_lower for w in ["épico", "heroico", "épico"]):
            detected_tone = "epic"

        # Build customized premise from description
        premise = f"Los personajes son aventureros comprometidos con una misión peligrosa: {description.strip('.')}. Un conflicto de poder y traición los enfrentará a enemigos inesperados."

        # Extract player roles from description if mentioned
        roles = []
        role_patterns = ["mesa redonda", "caballeros", "mercenarios", "espías", "aventu", "héroe"]
        for pat in role_patterns:
            if pat in desc_lower:
                roles.append(pat)
        role_str = ", ".join(roles) if roles else "aventuross"

        hook = (
            f"La amenaza se cierne sobre {location.lower()}. "
            f"Una alianza oculta entre {threat or 'fuerzas oscuras'} y figuras de poder amenaza con destruir todo. "
            f"Los {role_str} deben actuar antes de que sea tarde."
        )

        fallback = build_world(setting)
        factions = fallback["world"].get("factions", {})

        return {
            "description": description,
            "premise": premise,
            "hook": hook,
            "tone": detected_tone,
            "setting_type": setting,
            "approved": False,
            "lore": {
                "factions": factions,
                "main_threat": threat or fallback["world"].get("main_threat", "Una amenaza se cierne sobre el mundo."),
                "starting_location": location,
                "starting_location_desc": f"{location} — {description[:100].strip()}. Un lugar donde el conflicto entre {threat or 'fuerzas oscuras'} y la justicia está a punto de estallar.",
                "npcs": [
                    {
                        "name": "Lady Elara",
                        "role": "Noble神秘",
                        "dialogue": "El poder corrompe... pero la desesperación corrompe más.",
                    },
                    {
                        "name": "Capitán Vorn",
                        "role": "Comandante corrupto",
                        "dialogue": "Órdenes son órdenes. Preguntame después.",
                    },
                ],
            },
        }


def _get_dialogue_style(disposition: str) -> str:
    styles = {
        "Cautious": "Speaks carefully, answers questions with questions",
        "Friendly": "Warm and open, asks about the party's travels",
        "Sarcastic": "Quick with a joke, never takes anything seriously",
        "Righteous": "Speaks with conviction, judges actions",
        "Enigmatic": "Talks in riddles, reveals only what serves her"
    }
    return styles.get(disposition, "Normal and direct")


def build_world(setting: str = "fantasy") -> dict:
    """
    Generate a complete new campaign world.
    Returns a full state dict ready to be saved.

    Uses templates from state/templates.py, with legacy NPCs as fallback.
    Sets up world continuity tracking (timeline, factions).
    """
    # Use new templates if available
    template_available = setting in TEMPLATES
    if template_available:
        tmpl = get_template(setting)
    elif setting in SETTINGS:  # legacy
        tmpl = SETTINGS[setting]
        template_available = False
    else:
        setting = "fantasy"
        tmpl = get_template("fantasy")
        template_available = True

    campaign_id = f"campaign_{uuid.uuid4().hex[:8]}"
    created = datetime.utcnow().isoformat()

    # Base state
    state = new_state(campaign_id, tmpl.get("name", "Unnamed Campaign"), setting)
    state["campaign"]["created"] = created
    state["campaign"]["current_location"] = tmpl.get("starting_location", "Unknown")

    # World — always with continuity fields
    factions = {}
    if template_available and "factions" in tmpl:
        factions = tmpl["factions"]
    elif "factions" in tmpl:
        factions = tmpl["factions"]

    state["world"] = {
        "main_threat": tmpl.get("description", tmpl.get("main_threat", ""))[:100],
        "factions": factions,
        "description": tmpl.get("description", ""),
        "timeline": [],  # world continuity: chronological event log
        "timeline_index": 0,
    }

    # Location
    starting_loc = tmpl.get("starting_location", "Unknown")
    state["world"]["locations"] = {
        starting_loc: {
            "description": tmpl.get("description", ""),
            "npcs": [],
            "visited": True,
        }
    }

    # NPCs — from template or fallback
    if template_available and "npcs" in tmpl and tmpl["npcs"]:
        # Use template NPCs
        npcs = {}
        for npc_data in tmpl["npcs"]:
            npc_id = npc_data.get("id", npc_data.get("name", "npc").lower().replace(" ", "_"))
            npcs[npc_id] = {
                "name": npc_data.get("name", npc_id),
                "role": npc_data.get("role", "NPC"),
                "status": npc_data.get("status", "ALIVE"),
                "location": npc_data.get("location", starting_loc),
                "disposition": npc_data.get("disposition", "NEUTRAL"),
                "mood": npc_data.get("mood", "neutral"),
                "description": npc_data.get("description", ""),
                "disposition_value": 0,
                "relationship_to_party": "stranger",
                "memory": [],  # NPC memory system
                "goals": npc_data.get("quest_hook", ""),
                "quest_hook": npc_data.get("quest_hook"),
                "speaks_to_players": npc_data.get("speaks_to_players", True),
            }
        state["npcs"] = npcs
    else:
        # Use legacy NPCs
        count = min(3, len(NPC_TEMPLATES))
        chosen = random.sample(NPC_TEMPLATES, count)
        npcs = {}
        for tmpl_npc in chosen:
            npc_id = tmpl_npc["name"].lower().replace(" ", "_")
            npcs[npc_id] = {
                "name": tmpl_npc["name"],
                "role": tmpl_npc["role"],
                "status": "ALIVE",
                "location": tmpl_npc["location"],
                "disposition": tmpl_npc["disposition"],
                "race": tmpl_npc["race"],
                "disposition_value": 0,
                "relationship_to_party": "stranger",
                "memory": [],
                "goals": tmpl_npc["goals"],
                "mood": tmpl_npc["disposition"].lower(),
                "appearance": tmpl_npc["appearance"],
                "secret": tmpl_npc["secret"],
                "dialogue_style": _get_dialogue_style(tmpl_npc["disposition"]),
            }
        state["npcs"] = npcs

    # Link NPCs to starting location
    for npc_id, npc in state["npcs"].items():
        loc = npc.get("location", "tavern")
        if loc in state["world"]["locations"]:
            if "npcs" not in state["world"]["locations"][loc]:
                state["world"]["locations"][loc]["npcs"] = []
            state["world"]["locations"][loc]["npcs"].append(npc_id)

    # Starting history entry
    state["history"].append({
        "session": 1,
        "event": f"Campaign created: {tmpl.get('name', 'Unnamed')}. Party meets at {starting_loc}.",
        "timestamp": created,
    })

    return state


def create_campaign(setting: str = "fantasy") -> dict:
    """
    High-level function: build world + persist to disk.
    Returns the campaign_id and state.
    """
    state = build_world(setting)
    campaign_id = state["campaign"]["id"]
    save_state(campaign_id, state)
    return {"campaign_id": campaign_id, "state": state}


# ─────────────────────────────────────────────────────────────────────────────
# World Continuity — timeline tracking and faction management
# ─────────────────────────────────────────────────────────────────────────────

def add_world_event(
    campaign_id: str,
    event: str,
    event_type: str = "story",
    session: int | None = None,
) -> dict:
    """
    Record a world event in the campaign timeline.
    World continuity: events persist and shape future narrative.

    Args:
        campaign_id: Campaign identifier
        event: Description of what happened
        event_type: "story" | "combat" | "npc_action" | "faction" | "discovery"
        session: Optional session number

    Returns:
        Updated world state
    """
    from state.state_manager import load_state, save_state

    state = load_state(campaign_id)
    if state is None:
        raise ValueError(f"Campaign {campaign_id} not found")

    timeline = state.get("world", {}).get("timeline", [])
    timeline_index = state.get("world", {}).get("timeline_index", 0)

    entry = {
        "id": timeline_index,
        "event": event,
        "type": event_type,
        "session": session,
        "timestamp": datetime.utcnow().isoformat(),
    }
    timeline.append(entry)
    state["world"]["timeline"] = timeline
    state["world"]["timeline_index"] = timeline_index + 1
    save_state(campaign_id, state)
    return state


def update_faction(
    campaign_id: str,
    faction: str,
    new_status: str,
) -> dict:
    """
    Update a faction's status in the world.
    Faction statuses: DOMINANT, RISING, HIDDEN, WEAKENED, DESTROYED, UNKNOWN

    Returns updated state.
    """
    from state.state_manager import load_state, save_state

    state = load_state(campaign_id)
    if state is None:
        raise ValueError(f"Campaign {campaign_id} not found")

    factions = state.get("world", {}).get("factions", {})
    old_status = factions.get(faction, "UNKNOWN")
    factions[faction] = new_status
    state["world"]["factions"] = factions

    # Log as world event
    add_world_event(
        campaign_id,
        f"Faction '{faction}' changed: {old_status} → {new_status}",
        event_type="faction",
    )
    save_state(campaign_id, state)
    return state


def get_world_summary(campaign_id: str) -> str:
    """
    Generate a brief world status summary from the campaign state.
    Used by /recap and DM system prompt.
    """
    from state.state_manager import load_state

    state = load_state(campaign_id)
    if state is None:
        return "Campaign not found."

    world = state.get("world", {})
    factions = world.get("factions", {})
    timeline = world.get("timeline", [])
    locations = world.get("locations", {})

    lines = [
        f"📍 Locaciones: {', '.join(locations.keys()) or 'Ninguna'}",
    ]

    if factions:
        faction_str = " | ".join(f"{k}: {v}" for k, v in factions.items())
        lines.append(f"⚔️ Facciones: {faction_str}")

    if timeline:
        last_5 = timeline[-5:]
        lines.append("\n📜 Eventos recientes:")
        for entry in last_5:
            lines.append(f"  [{entry['type']}] {entry['event'][:80]}")

    return "\n".join(lines)


if __name__ == "__main__":
    print("=== world_builder sanity test ===")
    result = create_campaign("fantasy")
    cid = result["campaign_id"]
    state = result["state"]
    print(f"Campaign: {cid}")
    print(f"Name: {state['campaign']['name']}")
    print(f"Setting: {state['campaign']['setting']}")
    print(f"Location: {state['campaign']['current_location']}")
    print(f"NPCs: {list(state['npcs'].keys())}")
    print(f"Factions: {state['world']['factions']}")
