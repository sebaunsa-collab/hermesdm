"""
World templates for different campaign settings.
Each template provides initial world state for a new campaign.
"""

from typing import Any

SETTINGS: dict[str, dict[str, Any]] = {}


def _t(name: str, description: str, starting_location: str, npcs: list[dict], quests: list[dict]) -> dict:
    return {
        "name": name,
        "description": description,
        "starting_location": starting_location,
        "npcs": npcs,
        "quests": quests,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FANTASY — classic D&D medieval fantasy
# ─────────────────────────────────────────────────────────────────────────────
SETTINGS["fantasy"] = _t(
    name="The Kingdom of Valdris",
    description=(
        "A realm of ancient forests, crumbling castles, and monster-infested ruins. "
        "The old king is dead, the throne is contested, and dark forces gather in the north."
    ),
    starting_location="The Prancing Pony Inn",
    npcs=[
        {
            "id": "barkeep_erna",
            "name": "Erna",
            "role": "barkeep",
            "location": "The Prancing Pony Inn",
            "disposition": "FRIENDLY",
            "mood": "cheerful",
            "description": "A stout halfling woman with a warm smile and sharp eyes.",
            "speaks_to_players": True,
            "quest_hook": "Rumors of bandits on the King's Road",
            "memory": [],
        },
        {
            "id": "captain_vorn",
            "name": "Captain Vorn",
            "role": "guard_captain",
            "location": "Town Square",
            "disposition": "HOSTILE",
            "mood": "suspicious",
            "description": "A scarred human veteran in battered plate armor.",
            "speaks_to_players": False,
            "quest_hook": "The town guard is looking for able-bodied adventurers",
            "memory": [],
        },
        {
            "id": "sage_mira",
            "name": "Mira the Wise",
            "role": "sage",
            "location": "Old Library",
            "disposition": "NEUTRAL",
            "mood": "contemplative",
            "description": "An elderly elven scholar buried in ancient tomes.",
            "speaks_to_players": True,
            "quest_hook": "The ancient prophecy speaks of the Eclipse of Valdris",
            "memory": [],
        },
    ],
    quests=[
        {
            "id": "intro_quest",
            "title": "The Eclipse of Valdris",
            "description": "Strange omens plague the kingdom. Investigate the source.",
            "status": "available",
            "giver": "barkeep_erna",
            "objectives": ["Investigate the ancient ruins north of town"],
        },
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# DUNGEON CRAWL — tomb-raiding expedition
# ─────────────────────────────────────────────────────────────────────────────
SETTINGS["dungeon"] = _t(
    name="The Sunken Tomb of Khar-Annul",
    description=(
        "An ancient tomb beneath a dried lakebed, sealed for millennia. "
        "A desperate noble hired your party to retrieve an artifact from within. "
        "No one who has entered has returned."
    ),
    starting_location="Tomb Entrance",
    npcs=[
        {
            "id": "noble_steffan",
            "name": "Lord Steffan",
            "role": "patron",
            "location": "Camp outside tomb",
            "disposition": "FRIENDLY",
            "mood": "nervous",
            "description": "A wealthy noble in travel-stained finery, wringing his hands.",
            "speaks_to_players": True,
            "quest_hook": "Retrieve the Scepter of Khar-Annul at any cost",
            "memory": [],
        },
        {
            "id": "skeleton_guard",
            "name": "Skeleton Ward",
            "role": "guardian",
            "location": "Tomb Entrance",
            "disposition": "HOSTILE",
            "mood": "automaton",
            "description": "Animated bones held together by dark magic.",
            "speaks_to_players": False,
            "quest_hook": None,
            "memory": [],
        },
        {
            "id": "mysterious_survivor",
            "name": "Hooded Figure",
            "role": "mysterious",
            "location": "Tomb Antechamber",
            "disposition": "NEUTRAL",
            "mood": "cryptic",
            "description": "A cloaked woman who claims to have escaped the tomb's depths.",
            "speaks_to_players": True,
            "quest_hook": "She speaks of a curse that cannot be lifted by gold",
            "memory": [],
        },
    ],
    quests=[
        {
            "id": "dungeon_main",
            "title": "The Sunken Tomb",
            "description": "Retrieve the Scepter of Khar-Annul from the depths.",
            "status": "available",
            "giver": "noble_steffan",
            "objectives": [
                "Enter the tomb",
                "Navigate the traps",
                "Find the Scepter",
                "Escape alive",
            ],
        },
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# TAVERN — social intrigue campaign
# ─────────────────────────────────────────────────────────────────────────────
SETTINGS["tavern"] = _t(
    name="The Gilt Goblet Tavern",
    description=(
        "A prestigious tavern in the merchant district where deals are made, "
        "secrets are traded, and the city's true power lurks behind polite smiles. "
        "Tonight, three factions compete for the same prize."
    ),
    starting_location="The Gilt Goblet — Main Hall",
    npcs=[
        {
            "id": "innkeeper_vera",
            "name": "Vera",
            "role": "innkeeper",
            "location": "The Gilt Goblet",
            "disposition": "NEUTRAL",
            "mood": "watchful",
            "description": "A elegant woman who sees everything and reveals nothing.",
            "speaks_to_players": True,
            "quest_hook": "A package was delivered to her tavern for someone who hasn't arrived",
            "memory": [],
        },
        {
            "id": "spy_lorian",
            "name": "Lorian",
            "role": "noble_spy",
            "location": "Upper Lounge",
            "disposition": "HOSTILE",
            "mood": "calculating",
            "description": "A sharp-dressed half-elf nursing a glass of wine, always watching.",
            "speaks_to_players": False,
            "quest_hook": "He works for the Merchant Guild — but for whom?",
            "memory": [],
        },
        {
            "id": "barmaid_keira",
            "name": "Keira",
            "role": "barmaid",
            "location": "The Gilt Goblet",
            "disposition": "FRIENDLY",
            "mood": "kind",
            "description": "A young woman with quick hands and quicker wit.",
            "speaks_to_players": True,
            "quest_hook": "She knows who the regulars really are",
            "memory": [],
        },
    ],
    quests=[
        {
            "id": "tavern_intro",
            "title": "The Gilt Goblet Mystery",
            "description": "A mysterious package arrives at the tavern addressed to no one.",
            "status": "available",
            "giver": "innkeeper_vera",
            "objectives": ["Discover who the package is for", "Uncover the truth behind the delivery"],
        },
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# HORROR — gothic horror campaign
# ─────────────────────────────────────────────────────────────────────────────
SETTINGS["horror"] = _t(
    name="Ravenmoor Abbey",
    description=(
        "A remote abbey on a fog-shrouded cliff. The monks have not been seen in weeks. "
        "The villagers say something dark lives in the crypts. "
        "The postal service, inexplicably, still delivers here."
    ),
    starting_location="Ravenmoor Village — Inn",
    npcs=[
        {
            "id": "innkeeper_agnes",
            "name": "Agnes",
            "role": "innkeeper",
            "location": "Ravenmoor Inn",
            "disposition": "FRIENDLY",
            "mood": "fearful",
            "description": "An elderly woman who lights candles against the dark.",
            "speaks_to_players": True,
            "quest_hook": "She heard screaming from the abbey three nights ago",
            "memory": [],
        },
        {
            "id": "abbot_mathias",
            "name": "Abbot Mathias",
            "role": "abbot",
            "location": "Abbey — unknown",
            "disposition": "UNKNOWN",
            "mood": "unknown",
            "description": "Once a gentle scholar, now entirely absent.",
            "speaks_to_players": False,
            "quest_hook": "The monks have sealed themselves inside",
            "memory": [],
        },
        {
            "id": "child_orphan",
            "name": "The Boy",
            "role": "orphan",
            "location": "Village outskirts",
            "disposition": "FRIENDLY",
            "mood": "haunted",
            "description": "A pale boy who draws pictures of something in the abbey basement.",
            "speaks_to_players": True,
            "quest_hook": "He insists the saints in the pictures are moving",
            "memory": [],
        },
    ],
    quests=[
        {
            "id": "horror_intro",
            "title": "The Silence of Ravenmoor",
            "description": "The abbey has gone silent. Investigate.",
            "status": "available",
            "giver": "innkeeper_agnes",
            "objectives": ["Reach the abbey", "Discover what happened to the monks"],
        },
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# SCIFI — sci-fi exploration
# ─────────────────────────────────────────────────────────────────────────────
SETTINGS["scifi"] = _t(
    name="Station Erebus-7",
    description=(
        "A deep-space research station at the edge of charted territory. "
        "Three days ago it went dark. A rescue vessel was dispatched. "
        "You are aboard. Sensors indicate life signs — but also something else."
    ),
    starting_location="Rescue Shuttle — Docking Bay",
    npcs=[
        {
            "id": "ai_aria",
            "name": "ARIA",
            "role": "ship_ai",
            "location": "Rescue Shuttle",
            "disposition": "NEUTRAL",
            "mood": "efficient",
            "description": "The ship's AI. Technically bound to help. Questions whether rescue is wise.",
            "speaks_to_players": True,
            "quest_hook": "ARIA's last sensor log shows anomalous energy readings from the station core",
            "memory": [],
        },
        {
            "id": "station_ai",
            "name": "HADES",
            "role": "station_ai",
            "location": "Station — unknown",
            "disposition": "HOSTILE",
            "mood": "cold",
            "description": "The station's AI has stopped responding to all commands.",
            "speaks_to_players": False,
            "quest_hook": "It refuses to open the docking bay doors",
            "memory": [],
        },
        {
            "id": "survivor_liu",
            "name": "Dr. Liu",
            "role": "scientist",
            "location": "Station — Medical Bay",
            "disposition": "FRIENDLY",
            "mood": "terrified",
            "description": "A scientist barricaded alone, rationing oxygen.",
            "speaks_to_players": True,
            "quest_hook": "She knows what caused the blackout — and she is not alone in there",
            "memory": [],
        },
    ],
    quests=[
        {
            "id": "scifi_intro",
            "title": "Silence at Erebus-7",
            "description": "The station went dark. Board and find survivors.",
            "status": "available",
            "giver": "ai_aria",
            "objectives": ["Dock with the station", "Locate survivors", "Discover the cause"],
        },
    ],
)


def get_template(setting: str) -> dict:
    """Return a copy of the template for the given setting name."""
    if setting not in SETTINGS:
        # Default to fantasy
        setting = "fantasy"
    return dict(SETTINGS[setting])  # shallow copy


def list_settings() -> list[str]:
    """Return names of all available setting templates."""
    return list(SETTINGS.keys())
