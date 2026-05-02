"""
enemy_pool.py — Enemy dataclass and organized pools by biome.

Provides 30+ core enemies across 3 biomes (forest, dungeon, urban).
Enemies are frozen dataclasses for type safety and IDE autocomplete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Enemy:
    """A D&D 5e enemy/monster with stats and loot table."""

    name: str
    hp: int
    ac: int
    speed: int = 30
    attacks: List[Dict] = field(default_factory=list)
    cr: float = 0.0  # Challenge Rating: 0, 1/8, 1/4, 1/2, 1, 2, ...
    abilities: Dict[str, int] = field(default_factory=dict)  # STR, DEX, CON, INT, WIS, CHA
    loot: Dict[str, float] = field(default_factory=dict)  # item → drop probability
    biomes: List[str] = field(default_factory=list)
    description: str = ""
    size: str = "Medium"
    creature_type: str = "humanoid"
    alignment: str = "neutral"
    features: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "hp": self.hp,
            "ac": self.ac,
            "speed": self.speed,
            "attacks": self.attacks,
            "cr": self.cr,
            "abilities": self.abilities,
            "loot": self.loot,
            "biomes": self.biomes,
            "description": self.description,
            "size": self.size,
            "creature_type": self.creature_type,
            "features": self.features,
        }


# ── Forest Biomes ──────────────────────────────────────────────────────────

_FOREST_ENEMIES = [
    Enemy(name="Wolf", hp=11, ac=13, speed=40,
          attacks=[{"name": "Bite", "to_hit": 4, "damage": "2d4+2", "type": "piercing"}],
          cr=0.25, abilities={"STR": 12, "DEX": 15, "CON": 12, "INT": 3, "WIS": 12, "CHA": 6},
          loot={"wolf_pelt": 0.5, "wolf_fang": 0.3},
          biomes=["forest"], description="A grey wolf, hunting in packs.",
          features=["Pack Tactics: advantage on attacks if ally is within 5ft"]),
    Enemy(name="Giant Spider", hp=26, ac=14, speed=30,
          attacks=[{"name": "Bite", "to_hit": 5, "damage": "1d8+3", "type": "piercing", "poison_dc": 11}],
          cr=1.0, abilities={"STR": 14, "DEX": 16, "CON": 12, "INT": 2, "WIS": 11, "CHA": 4},
          loot={"spider_silk": 0.7, "venom_sac": 0.4},
          biomes=["forest"], description="A massive arachnid waiting in the trees.",
          features=["Web Walker", "Spider Climb"]),
    Enemy(name="Goblin Scout", hp=7, ac=14, speed=30,
          attacks=[{"name": "Shortbow", "to_hit": 4, "damage": "1d6+2", "type": "piercing"},
                   {"name": "Scimitar", "to_hit": 4, "damage": "1d6+2", "type": "slashing"}],
          cr=0.125, abilities={"STR": 8, "DEX": 14, "CON": 10, "INT": 10, "WIS": 8, "CHA": 8},
          loot={"goblin_ears": 0.4, "crude_dagger": 0.3, "copper_pieces": 0.6},
          biomes=["forest"], description="A small, green-skinned humanoid scout.",
          features=["Nimble Escape: can Disengage or Hide as bonus action"]),
    Enemy(name="Owlbear", hp=59, ac=13, speed=40,
          attacks=[{"name": "Multiattack", "count": 2, "options": [
              {"name": "Beak", "to_hit": 7, "damage": "1d10+5", "type": "piercing"},
              {"name": "Claws", "to_hit": 7, "damage": "2d8+5", "type": "slashing"}]}],
          cr=3.0, abilities={"STR": 20, "DEX": 12, "CON": 17, "INT": 3, "WIS": 12, "CHA": 7},
          loot={"owlbear_pelt": 0.6, "owlbear_claw": 0.4, "owlbear_beak": 0.3},
          biomes=["forest", "mountain"], description="A terrifying cross between owl and bear.",
          features=["Keen Sight and Smell: advantage on Perception checks"]),
    Enemy(name="Dryad", hp=22, ac=11, speed=30,
          attacks=[{"name": "Club", "to_hit": 2, "damage": "1d4", "type": "bludgeoning"}],
          cr=1.0, abilities={"STR": 10, "DEX": 12, "CON": 11, "INT": 14, "WIS": 15, "CHA": 18},
          loot={"enchanted_wood": 0.5, "fey_dust": 0.3},
          biomes=["forest"], description="A beautiful fey spirit bound to a great tree.",
          features=["Fey Charm: charm up to 3 humanoids", "Tree Stride"],
          creature_type="fey"),
    Enemy(name="Treant", hp=138, ac=16, speed=30,
          attacks=[{"name": "Multiattack", "count": 2,
              "options": [{"name": "Slam", "to_hit": 10, "damage": "3d6+6", "type": "bludgeoning"}]}],
          cr=9.0, abilities={"STR": 23, "DEX": 8, "CON": 21, "INT": 12, "WIS": 16, "CHA": 12},
          loot={"ancient_bark": 0.8, "treant_heartwood": 0.5, "enchanted_acorn": 0.2},
          biomes=["forest"], description="An ancient tree given life and purpose.",
          features=["Animate Trees", "Siege Monster"], size="Huge", creature_type="plant"),
    Enemy(name="Pixie", hp=1, ac=15, speed=10,
          attacks=[{"name": "Superior Invisibility", "type": "special"}],
          cr=0.25, abilities={"STR": 2, "DEX": 20, "CON": 8, "INT": 10, "WIS": 14, "CHA": 15},
          loot={"pixie_dust": 0.4, "fey_wing": 0.3},
          biomes=["forest"], description="A tiny, mischievous fey with butterfly wings.",
          features=["Innate Spellcasting", "Magic Resistance"], size="Tiny", creature_type="fey"),
    Enemy(name="Boar", hp=11, ac=11, speed=40,
          attacks=[{"name": "Tusk", "to_hit": 3, "damage": "1d6+1", "type": "slashing"}],
          cr=0.25, abilities={"STR": 13, "DEX": 11, "CON": 12, "INT": 2, "WIS": 9, "CHA": 5},
          loot={"boar_tusk": 0.5, "boar_meat": 0.7},
          biomes=["forest"], description="An aggressive wild boar.",
          features=["Charge: +1d6 damage if moves 20ft", "Relentless: 1 HP left if would die"]),
    Enemy(name="Elf Scout", hp=16, ac=13, speed=30,
          attacks=[{"name": "Longsword", "to_hit": 4, "damage": "1d8+2", "type": "slashing"},
                   {"name": "Longbow", "to_hit": 4, "damage": "1d8+2", "type": "piercing"}],
          cr=0.5, abilities={"STR": 11, "DEX": 14, "CON": 12, "INT": 11, "WIS": 13, "CHA": 11},
          loot={"elven_arrows": 0.5, "silver_coins": 0.6},
          biomes=["forest"], description="An elven ranger patrolling the woods.",
          features=["Keen Hearing and Sight", "Fey Ancestry"]),
    Enemy(name="Basilisk", hp=52, ac=15, speed=20,
          attacks=[{"name": "Bite", "to_hit": 5, "damage": "2d6+3", "type": "piercing"}],
          cr=3.0, abilities={"STR": 16, "DEX": 8, "CON": 15, "INT": 2, "WIS": 8, "CHA": 7},
          loot={"basilisk_eye": 0.4, "basilisk_scale": 0.5, "petrified_victim": 0.1},
          biomes=["forest", "mountain"], description="A reptilian monster whose gaze turns to stone.",
          features=["Petrifying Gaze: DC 12 CON save or petrified"]),
]

# ── Dungeon Biomes ─────────────────────────────────────────────────────────

_DUNGEON_ENEMIES = [
    Enemy(name="Skeleton", hp=13, ac=13, speed=30,
          attacks=[{"name": "Shortsword", "to_hit": 4, "damage": "1d6+2", "type": "piercing"},
                   {"name": "Shortbow", "to_hit": 4, "damage": "1d6+2", "type": "piercing"}],
          cr=0.25, abilities={"STR": 10, "DEX": 14, "CON": 15, "INT": 6, "WIS": 8, "CHA": 5},
          loot={"bone_dust": 0.3, "rusty_weapon": 0.4},
          biomes=["dungeon"], description="An animated skeleton, clattering with each step.",
          features=["Vulnerability: bludgeoning", "Immunity: poison, exhaustion"],
          creature_type="undead"),
    Enemy(name="Zombie", hp=22, ac=8, speed=20,
          attacks=[{"name": "Slam", "to_hit": 3, "damage": "1d6+1", "type": "bludgeoning"}],
          cr=0.25, abilities={"STR": 13, "DEX": 6, "CON": 16, "INT": 3, "WIS": 6, "CHA": 5},
          loot={"rotting_flesh": 0.2, "zombie_hand": 0.1},
          biomes=["dungeon"], description="A shambling corpse animated by dark magic.",
          features=["Undead Fortitude: CON save DC 5+dmg to stay at 1HP"],
          creature_type="undead"),
    Enemy(name="Gelatinous Cube", hp=84, ac=6, speed=15,
          attacks=[{"name": "Engulf", "to_hit": 4, "damage": "3d6", "type": "acid", "save_dc": 12}],
          cr=2.0, abilities={"STR": 14, "DEX": 3, "CON": 20, "INT": 1, "WIS": 6, "CHA": 1},
          loot={"dissolved_items": 0.6, "acid_slime": 0.4},
          biomes=["dungeon"], description="A translucent cube of acidic ooze, almost invisible.",
          features=["Transparent", "Engulf"], size="Large", creature_type="ooze"),
    Enemy(name="Mimic", hp=58, ac=12, speed=15,
          attacks=[{"name": "Pseudopod", "to_hit": 5, "damage": "1d8+3", "type": "bludgeoning"},
                   {"name": "Bite", "to_hit": 5, "damage": "1d8+3", "type": "piercing"}],
          cr=2.0, abilities={"STR": 17, "DEX": 12, "CON": 15, "INT": 5, "WIS": 13, "CHA": 8},
          loot={"mimic_gold": 0.7, "sticky_residue": 0.3},
          biomes=["dungeon"], description="A shapechanger that looks exactly like a treasure chest.",
          features=["Shapechanger", "Adhesive: grappled on hit", "False Appearance"],
          creature_type="monstrosity"),
    Enemy(name="Stone Golem", hp=178, ac=17, speed=30,
          attacks=[{"name": "Multiattack", "count": 2,
              "options": [{"name": "Slam", "to_hit": 10, "damage": "3d8+6", "type": "bludgeoning"}]}],
          cr=10.0, abilities={"STR": 22, "DEX": 9, "CON": 20, "INT": 3, "WIS": 11, "CHA": 1},
          loot={"golem_core": 0.6, "enchanted_stone": 0.4, "gold_coins": 0.5},
          biomes=["dungeon"], description="A towering construct of animated stone.",
          features=["Immutable Form", "Magic Resistance", "Magic Weapons"],
          size="Large", creature_type="construct"),
    Enemy(name="Carrion Crawler", hp=51, ac=13, speed=30,
          attacks=[{"name": "Tentacles", "to_hit": 8, "damage": "1d4+2", "type": "poison", "paralysis_dc": 13},
                   {"name": "Bite", "to_hit": 5, "damage": "2d4+2", "type": "piercing"}],
          cr=2.0, abilities={"STR": 14, "DEX": 13, "CON": 16, "INT": 1, "WIS": 12, "CHA": 5},
          loot={"carrion_ichor": 0.4, "paralysis_venom": 0.3},
          biomes=["dungeon"], description="A massive centipede-like creature smelling of decay.",
          features=["Keen Smell", "Spider Climb"], size="Large", creature_type="monstrosity"),
    Enemy(name="Wraith", hp=67, ac=13, speed=0,
          attacks=[{"name": "Life Drain", "to_hit": 6, "damage": "4d8+3", "type": "necrotic",
                    "max_hp_reduction": True}],
          cr=5.0, abilities={"STR": 6, "DEX": 16, "CON": 16, "INT": 12, "WIS": 14, "CHA": 15},
          loot={"wraith_essence": 0.5, "soul_shard": 0.3},
          biomes=["dungeon"], description="A shadowy specter of pure malice.",
          features=["Incorporeal Movement", "Sunlight Sensitivity", "Life Drain"],
          creature_type="undead"),
    Enemy(name="Ochre Jelly", hp=45, ac=8, speed=10,
          attacks=[{"name": "Pseudopod", "to_hit": 4, "damage": "1d6+2", "type": "acid"}],
          cr=2.0, abilities={"STR": 15, "DEX": 6, "CON": 14, "INT": 2, "WIS": 6, "CHA": 1},
          loot={"ochre_gel": 0.4, "dissolved_metal": 0.3},
          biomes=["dungeon"], description="A yellow-brown ooze sliding along dungeon floors.",
          features=["Split: lightning/slashing splits into 2 smaller jellies", "Amorphous"],
          size="Large", creature_type="ooze"),
    Enemy(name="Lich", hp=135, ac=17, speed=30,
          attacks=[{"name": "Paralyzing Touch", "to_hit": 12, "damage": "3d6", "type": "cold", "paralysis_dc": 18},
                   {"name": "Spellcasting", "type": "special", "slots": {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1}}],
          cr=21.0, abilities={"STR": 11, "DEX": 16, "CON": 16, "INT": 20, "WIS": 14, "CHA": 16},
          loot={"phylactery_fragment": 0.5, "spellbook": 0.7, "lich_robes": 0.4, "artifact_piece": 0.2},
          biomes=["dungeon"], description="A powerful undead spellcaster bound to a phylactery.",
          features=["Legendary Resistance 3/day", "Rejuvenation", "Turn Resistance"],
          creature_type="undead"),
    Enemy(name="Rust Monster", hp=27, ac=14, speed=40,
          attacks=[{"name": "Antennae", "to_hit": 3, "damage": "0", "type": "special", "effect": "rust_metal"},
                   {"name": "Bite", "to_hit": 3, "damage": "1d8+1", "type": "piercing"}],
          cr=0.5, abilities={"STR": 13, "DEX": 12, "CON": 13, "INT": 2, "WIS": 13, "CHA": 6},
          loot={"rust_dust": 0.5, "rust_monster_feeler": 0.2},
          biomes=["dungeon"], description="A insectoid monster that feeds on metal.",
          features=["Rust Metal: nonmagical metal weapons/armor rust on hit", "Iron Scent"],
          creature_type="monstrosity"),
]

# ── Urban Biomes ───────────────────────────────────────────────────────────

_URBAN_ENEMIES = [
    Enemy(name="Thug", hp=32, ac=11, speed=30,
          attacks=[{"name": "Multiattack", "count": 2,
              "options": [{"name": "Mace", "to_hit": 4, "damage": "1d6+2", "type": "bludgeoning"}]}],
          cr=0.5, abilities={"STR": 15, "DEX": 11, "CON": 14, "INT": 10, "WIS": 10, "CHA": 11},
          loot={"silver_coins": 0.7, "thugs_key": 0.3},
          biomes=["urban"], description="A burly street enforcer.",
          features=["Pack Tactics"]),
    Enemy(name="Assassin", hp=78, ac=15, speed=30,
          attacks=[{"name": "Multiattack", "count": 2,
              "options": [{"name": "Shortsword", "to_hit": 6, "damage": "1d6+3", "type": "piercing", "poison_dc": 15}]}],
          cr=8.0, abilities={"STR": 11, "DEX": 16, "CON": 14, "INT": 13, "WIS": 11, "CHA": 10},
          loot={"assassins_blade": 0.5, "poison_vial": 0.6, "gold_coins": 0.4},
          biomes=["urban"], description="A hooded killer striking from the shadows.",
          features=["Assassinate: auto-crit on surprised", "Evasion", "Sneak Attack +4d6"]),
    Enemy(name="Cultist", hp=9, ac=12, speed=30,
          attacks=[{"name": "Dagger", "to_hit": 3, "damage": "1d4+1", "type": "piercing"}],
          cr=0.125, abilities={"STR": 11, "DEX": 12, "CON": 10, "INT": 10, "WIS": 11, "CHA": 10},
          loot={"cult_robe": 0.5, "ritual_candle": 0.3, "cult_symbol": 0.4},
          biomes=["urban"], description="A robed zealot devoted to a dark power.",
          features=["Dark Devotion: advantage on charm/frightened saves"]),
    Enemy(name="Guard", hp=11, ac=16, speed=30,
          attacks=[{"name": "Spear", "to_hit": 3, "damage": "1d6+1", "type": "piercing"},
                   {"name": "Crossbow", "to_hit": 2, "damage": "1d8", "type": "piercing"}],
          cr=0.125, abilities={"STR": 13, "DEX": 12, "CON": 12, "INT": 10, "WIS": 11, "CHA": 10},
          loot={"guard_badge": 0.4, "copper_pieces": 0.5},
          biomes=["urban"], description="A city watchman in chain mail.",
          features=["Protection: impose disadvantage on ally attacks"]),
    Enemy(name="Guild Thief", hp=27, ac=14, speed=30,
          attacks=[{"name": "Shortsword", "to_hit": 5, "damage": "1d6+3", "type": "piercing"},
                   {"name": "Hand Crossbow", "to_hit": 5, "damage": "1d6+3", "type": "piercing"}],
          cr=1.0, abilities={"STR": 10, "DEX": 17, "CON": 14, "INT": 12, "WIS": 10, "CHA": 13},
          loot={"lockpicks": 0.5, "stolen_goods": 0.6, "thieves_tools": 0.4},
          biomes=["urban"], description="A nimble thief trying to earn their guild dues.",
          features=["Cunning Action", "Sneak Attack +2d6", "Evasion"]),
    Enemy(name="Rakshasa", hp=110, ac=16, speed=40,
          attacks=[{"name": "Multiattack", "count": 2,
              "options": [{"name": "Claw", "to_hit": 7, "damage": "2d6+2", "type": "slashing", "curse_dc": 18}]}],
          cr=13.0, abilities={"STR": 14, "DEX": 17, "CON": 18, "INT": 13, "WIS": 16, "CHA": 20},
          loot={"rakshasa_eye": 0.5, "cursed_ring": 0.4, "demon_heart": 0.3},
          biomes=["urban"], description="A shape-shifting fiend disguised as a wealthy noble.",
          features=["Limited Magic Immunity: immune to spells ≤6th level", "Innate Spellcasting"],
          creature_type="fiend"),
    Enemy(name="Wererat", hp=33, ac=13, speed=30,
          attacks=[{"name": "Multiattack (hybrid)", "count": 2,
              "options": [{"name": "Bite", "to_hit": 4, "damage": "1d4+2", "type": "piercing", "lycanthropy_dc": 11},
                         {"name": "Shortsword", "to_hit": 4, "damage": "1d6+2", "type": "piercing"}]}],
          cr=2.0, abilities={"STR": 10, "DEX": 15, "CON": 12, "INT": 11, "WIS": 10, "CHA": 8},
          loot={"wererat_pelt": 0.4, "silvered_dagger": 0.2, "sewer_key": 0.3},
          biomes=["urban"], description="A cursed humanoid who transforms into a rat-like beast.",
          features=["Shapechanger", "Damage Immunity: non-silvered nonmagical"],
          creature_type="humanoid"),
    Enemy(name="Gargoyle", hp=52, ac=15, speed=30,
          attacks=[{"name": "Multiattack", "count": 2,
              "options": [{"name": "Claw", "to_hit": 4, "damage": "1d6+2", "type": "slashing"},
                         {"name": "Bite", "to_hit": 4, "damage": "1d6+2", "type": "piercing"}]}],
          cr=2.0, abilities={"STR": 15, "DEX": 11, "CON": 16, "INT": 6, "WIS": 11, "CHA": 7},
          loot={"gargoyle_stone": 0.5, "gem_eyes": 0.3},
          biomes=["urban"], description="A winged stone statue that springs to life.",
          features=["False Appearance", "Damage Resistance: nonmagical non-adamantine"],
          creature_type="elemental"),
    Enemy(name="Doppelganger", hp=52, ac=14, speed=30,
          attacks=[{"name": "Multiattack", "count": 2,
              "options": [{"name": "Slam", "to_hit": 6, "damage": "1d6+4", "type": "bludgeoning"}]}],
          cr=3.0, abilities={"STR": 11, "DEX": 18, "CON": 14, "INT": 11, "WIS": 12, "CHA": 14},
          loot={"doppelganger_skin": 0.4, "disguise_kit": 0.3},
          biomes=["urban"], description="A shapeshifter who can perfectly mimic any humanoid.",
          features=["Shapechanger", "Read Thoughts: DC 13 WIS save", "Ambusher"],
          creature_type="monstrosity"),
    Enemy(name="Noble Assassin", hp=97, ac=16, speed=30,
          attacks=[{"name": "Multiattack", "count": 3,
              "options": [{"name": "Rapier", "to_hit": 8, "damage": "1d8+4", "type": "piercing"}]}],
          cr=5.0, abilities={"STR": 12, "DEX": 18, "CON": 16, "INT": 14, "WIS": 12, "CHA": 16},
          loot={"signet_ring": 0.6, "poison_ring": 0.5, "gold_pouch": 0.7, "noble_letter": 0.4},
          biomes=["urban"], description="A deadly aristocrat trained in the art of silent killing.",
          features=["Sneak Attack +4d6", "Cunning Action", "Uncanny Dodge"]),
]

# ── Master Pool ────────────────────────────────────────────────────────────

ENEMIES_BY_BIOME: Dict[str, List[Enemy]] = {
    "forest": _FOREST_ENEMIES,
    "dungeon": _DUNGEON_ENEMIES,
    "urban": _URBAN_ENEMIES,
}

ALL_ENEMIES: List[Enemy] = _FOREST_ENEMIES + _DUNGEON_ENEMIES + _URBAN_ENEMIES

# ── Danger to CR mapping ───────────────────────────────────────────────────

# Maps location danger (1-5) to CR range (min, max)
# Milestone tier (1-3) adds +0/+1/+2 to CR ceiling
DANGER_TO_CR: Dict[int, tuple] = {
    1: (0.0, 0.5),      # Safe: CR 0 to 1/2
    2: (0.125, 1.0),    # Wilds: CR 1/8 to 1
    3: (0.5, 3.0),      # Dangerous: CR 1/2 to 3
    4: (2.0, 5.0),      # Deadly: CR 2 to 5
    5: (5.0, 10.0),     # Legendary: CR 5 to 10
}
