"""
dungeon_generator.py — Procedural dungeon generation for D&D 5e.

Produces connected rooms with typed assignments (entrance, combat,
trap, puzzle, treasure, boss, secret, rest), enemy placement, and
thematic descriptions. Deterministic given seeded RNG.

Part of Scene Director's content engine suite.

Design: BFS growth from entrance, boss at deepest node,
secret rooms at 10% per dead end, room count bounded by size.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Room:
    """A single room in a dungeon."""
    id: str
    room_type: str
    description: str
    connected_to: List[str] = field(default_factory=list)
    traps: List[str] = field(default_factory=list)
    treasure: Optional[dict] = None
    enemies: List[str] = field(default_factory=list)
    theme_details: dict = field(default_factory=dict)
    visited: bool = False


@dataclass
class Dungeon:
    """A generated dungeon with rooms, theme, and boss."""
    entrance_room_id: str
    boss_room_id: str
    rooms: Dict[str, Room]
    theme: str
    danger_level: int
    size: str


# ── Room count by size ───────────────────────────────────────────────────

SIZE_ROOM_COUNT: dict = {
    "small": (5, 8),
    "medium": (9, 15),
    "large": (16, 25),
}

# ── Type weights by danger level ─────────────────────────────────────────
# (combat, trap, puzzle, treasure, rest, corridor)
TYPE_WEIGHTS: dict = {
    1: [0.15, 0.10, 0.05, 0.10, 0.20, 0.40],
    2: [0.25, 0.15, 0.10, 0.10, 0.10, 0.30],
    3: [0.30, 0.20, 0.10, 0.10, 0.05, 0.25],
    4: [0.35, 0.25, 0.10, 0.10, 0.05, 0.15],
    5: [0.40, 0.30, 0.10, 0.10, 0.00, 0.10],
}

# ── Room descriptions by type and theme ──────────────────────────────────

THEME_DESCRIPTIONS: dict = {
    "crypt": {
        "entrance": "A crumbling stone archway leads into the cold darkness of the crypt.",
        "corridor": "Narrow passage lined with burial niches and cobwebs.",
        "combat": "A chamber where the dead refuse to rest, bones scattered across the floor.",
        "trap": "Pressure plates and razor wire betray ancient tomb defenses.",
        "puzzle": "A stone door inscribed with riddles of the afterlife blocks passage.",
        "treasure": "A vault glittering with funeral offerings and gilded sarcophagi.",
        "boss": "The central mausoleum pulses with necrotic energy.",
        "secret": "A hidden alcove behind a false wall contains forbidden relics.",
        "rest": "A quiet chapel offers meager sanctuary from the restless dead.",
    },
    "shadowfell": {
        "entrance": "A tear in reality reveals the gloom of the Shadowfell beyond.",
        "corridor": "Shadows stretch and twist along the passage, defying the faint light.",
        "combat": "A battlefield frozen in time, shade warriors locked in eternal conflict.",
        "trap": "Ethereal snares and shadow-ward glyphs protect this passage.",
        "puzzle": "A mirror of darkness reflects not your face but your deepest fear.",
        "treasure": "Shadow-stuff coalesces around chests of stolen mortal riches.",
        "boss": "A throne of darkness awaits the master of this shadow domain.",
        "secret": "A thin veil of shadow conceals a passage to a forgotten sanctum.",
        "rest": "A pocket of dim light offers fragile respite from the oppressive gloom.",
    },
    "dark_forest": {
        "entrance": "Gnarled trees form an archway into the heart of the cursed woods.",
        "corridor": "A narrow game trail winds between ancient, hostile oaks.",
        "combat": "A clearing stained with old blood, the hunting ground of forest predators.",
        "trap": "Snare vines and covered pit traps line the forest path.",
        "puzzle": "A faerie ring whispers riddles that must be answered to pass.",
        "treasure": "A hollow tree overflows with lost trinkets and forgotten riches.",
        "boss": "The oldest tree groans as it awakens, heartwood glowing with fury.",
        "secret": "A moss-covered arch leads to a hidden grove untouched by the curse.",
        "rest": "A small brook and sheltered hollow offer a moment of peace.",
    },
    "temple": {
        "entrance": "Massive stone doors carved with divine symbols creak open.",
        "corridor": "A colonnaded hall adorned with fading frescoes of forgotten gods.",
        "combat": "Guardian statues line the walls, some already shattered from battle.",
        "trap": "Consecrated glyphs spark with divine retribution for trespassers.",
        "puzzle": "An altar demands an offering of true faith to unlock the inner sanctum.",
        "treasure": "A reliquary chamber brimming with golden idols and sacred artifacts.",
        "boss": "The high altar, where the fallen high priest waits in eternal vigilance.",
        "secret": "A hidden confessional reveals a stairway to forgotten chambers below.",
        "rest": "A quiet cloister offers sanctuary, faint hymn lingering in the air.",
    },
    "dragon_lair": {
        "entrance": "A cavern maw scorched black by dragonfire, bones littering the entrance.",
        "corridor": "A tunnel smooth as glass, carved by centuries of scales scraping stone.",
        "combat": "A brood chamber where wyrmlings hiss and snap at intruders.",
        "trap": "A treasure pile rigged with poison needles and collapsing floors.",
        "puzzle": "A draconic riddle etched in ignan runes guards the hoard chamber.",
        "treasure": "Gold coins, jewels, and magic items spill from overflowing chests.",
        "boss": "The great hall where the dragon coils atop a mountain of treasure.",
        "secret": "A narrow crevice reveals a passage the dragon cannot fit through.",
        "rest": "A thermal vent provides warmth and an escape from the dragon's notice.",
    },
    "mine": {
        "entrance": "A rickety wooden scaffold marks the entrance to the abandoned mine.",
        "corridor": "A cramped mining tunnel, support beams groaning under the weight above.",
        "combat": "A wide gallery where miners made their last stand against the dark.",
        "trap": "Unstable ceiling and abandoned explosive charges line the shaft.",
        "puzzle": "A locked ore cart mechanism requires a complex sequence to bypass.",
        "treasure": "A rich vein of exposed ore alongside forgotten mining tools of value.",
        "boss": "The deepest excavation, where something ancient was unearthed.",
        "secret": "A collapsed wall hides a natural cavern with glowing crystals.",
        "rest": "The old foreman's office provides a defensible resting spot.",
    },
    "fortress": {
        "entrance": "An iron portcullis, rusted but still imposing, guards the fortress gate.",
        "corridor": "A wide hallway with arrow slits and murder holes overhead.",
        "combat": "A barracks still occupied by the fortress's undying garrison.",
        "trap": "A swinging blade mechanism and boiling oil ports defend this passage.",
        "puzzle": "A war table with a tactical puzzle that reveals the lord's chamber.",
        "treasure": "The armory holds weapons of quality and chests of military payment.",
        "boss": "The throne room, where the undead warlord still sits in command.",
        "secret": "A servant's passage, hidden behind a tapestry, leads to the inner keep.",
        "rest": "A small chapel within the fortress walls offers brief sanctuary.",
    },
    "generic": {
        "entrance": "A dark opening leads downward into the unknown.",
        "corridor": "A narrow passage stretches ahead, the walls damp with moisture.",
        "combat": "A wide chamber scarred by previous battles, promising more to come.",
        "trap": "The floor ahead looks suspiciously clean, too clean.",
        "puzzle": "A strange contraption blocks progress, demanding cleverness.",
        "treasure": "Glints of precious metal catch your eye among scattered debris.",
        "boss": "The air grows heavy. Something powerful awaits in this chamber.",
        "secret": "A draft of air betrays a hidden passage behind the stone.",
        "rest": "This alcove, while not comfortable, is at least defensible.",
    },
}


def _get_description(theme: str, room_type: str) -> str:
    """Get a themed description for a room type."""
    theme_data = THEME_DESCRIPTIONS.get(theme, THEME_DESCRIPTIONS["generic"])
    return theme_data.get(room_type, theme_data.get("corridor", "A dark room."))


def _pick_room_type(danger: int, rng: random.Random) -> str:
    """Pick a room type weighted by danger level."""
    weights = TYPE_WEIGHTS.get(danger, TYPE_WEIGHTS[1])
    types = ["combat", "trap", "puzzle", "treasure", "rest", "corridor"]
    return rng.choices(types, weights=weights, k=1)[0]


# ── Main dungeon generator ───────────────────────────────────────────────

def generate_dungeon(
    size: str = "medium",
    danger_level: int = 2,
    theme: str = "generic",
    rng: Optional[random.Random] = None,
) -> Dungeon:
    """Generate a procedural dungeon.

    Args:
        size: "small" (5-8 rooms), "medium" (9-15), or "large" (16-25)
        danger_level: 1-5, affects room type weighting and enemy CR
        theme: Theme key for descriptions (crypt, shadowfell, etc.)
        rng: Optional seeded Random for deterministic generation

    Returns:
        Dungeon dataclass with entrance, boss, and all rooms.
    """
    rng = rng or random.Random()
    danger_level = max(1, min(5, danger_level))

    # ── Step 1: Determine room count ─────────────────────────────────
    min_rooms, max_rooms = SIZE_ROOM_COUNT.get(size, SIZE_ROOM_COUNT["medium"])
    room_count = rng.randint(min_rooms, max_rooms)

    # ── Step 2: Generate rooms via BFS growth ────────────────────────
    rooms: Dict[str, Room] = {}
    room_id_counter = [0]
    adjacency: Dict[str, List[str]] = {}
    parent_map: Dict[str, Optional[str]] = {}

    def _next_id() -> str:
        room_id_counter[0] += 1
        return f"r{room_id_counter[0]}"

    # Start with entrance room
    entrance_id = _next_id()
    rooms[entrance_id] = Room(
        id=entrance_id,
        room_type="entrance",
        description=_get_description(theme, "entrance"),
    )
    adjacency[entrance_id] = []
    parent_map[entrance_id] = None

    # BFS queue
    queue = deque([entrance_id])

    while len(rooms) < room_count and queue:
        current = queue.popleft()
        # Determine how many connections to add (1-3)
        max_new = min(3, room_count - len(rooms))
        if max_new <= 0:
            break
        connections_to_add = rng.randint(1, max_new)

        for _ in range(connections_to_add):
            if len(rooms) >= room_count:
                break
            new_id = _next_id()
            rooms[new_id] = Room(
                id=new_id,
                room_type="corridor",  # temporary, assigned later
                description=_get_description(theme, "corridor"),
            )
            # Bidirectional connection
            adjacency.setdefault(current, []).append(new_id)
            adjacency.setdefault(new_id, []).append(current)
            parent_map[new_id] = current
            rooms[current].connected_to.append(new_id)
            rooms[new_id].connected_to.append(current)
            queue.append(new_id)

    # ── Step 3: Assign room types ────────────────────────────────────
    room_ids = list(rooms.keys())
    # Exclude entrance from type assignment
    non_entrance = [rid for rid in room_ids if rid != entrance_id]

    # Track which rooms are dead ends (only 1 connection)
    dead_ends = []
    for rid in non_entrance:
        if len(adjacency.get(rid, [])) <= 1:
            dead_ends.append(rid)

    # Assign types to non-entrance rooms
    for rid in non_entrance:
        if rid in dead_ends:
            # Dead ends can be treasure or rest
            if rng.random() < 0.4:
                rooms[rid].room_type = "treasure"
                rooms[rid].description = _get_description(theme, "treasure")
            elif rng.random() < 0.3:
                rooms[rid].room_type = "rest"
                rooms[rid].description = _get_description(theme, "rest")
            else:
                rooms[rid].room_type = _pick_room_type(danger_level, rng)
                rooms[rid].description = _get_description(theme, rooms[rid].room_type)
        else:
            rooms[rid].room_type = _pick_room_type(danger_level, rng)
            rooms[rid].description = _get_description(theme, rooms[rid].room_type)

    # ── Step 4: Place boss at deepest BFS node ───────────────────────
    # BFS from entrance to find distances
    distances: Dict[str, int] = {entrance_id: 0}
    bfs_queue = deque([entrance_id])
    while bfs_queue:
        rid = bfs_queue.popleft()
        dist = distances[rid]
        for conn in adjacency.get(rid, []):
            if conn not in distances:
                distances[conn] = dist + 1
                bfs_queue.append(conn)

    # Find the room(s) with maximum distance
    max_dist = max(distances.values())
    deepest_candidates = [rid for rid, d in distances.items()
                          if d == max_dist and rid != entrance_id]

    if deepest_candidates:
        boss_id = rng.choice(deepest_candidates)
    else:
        # Fallback: pick a random non-entrance room
        boss_id = rng.choice(non_entrance) if non_entrance else entrance_id

    if boss_id in rooms and boss_id != entrance_id:
        rooms[boss_id].room_type = "boss"
        rooms[boss_id].description = _get_description(theme, "boss")

    # ── Step 5: Secret rooms ─────────────────────────────────────────
    # 10% chance per dead-end to have a secret room
    secret_count = 0
    for rid in dead_ends:
        if rng.random() < 0.1 and len(rooms) < room_count + 3:
            secret_id = _next_id()
            rooms[secret_id] = Room(
                id=secret_id,
                room_type="secret",
                description=_get_description(theme, "secret"),
                connected_to=[rid],
            )
            rooms[rid].connected_to.append(secret_id)
            adjacency.setdefault(secret_id, []).append(rid)
            adjacency.setdefault(rid, []).append(secret_id)
            secret_count += 1

    return Dungeon(
        entrance_room_id=entrance_id,
        boss_room_id=boss_id,
        rooms=rooms,
        theme=theme,
        danger_level=danger_level,
        size=size,
    )
