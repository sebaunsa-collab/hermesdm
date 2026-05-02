"""
class_features.py — Class feature registry, activation, and recovery.
Deterministic engine following D&D 5e SRD rules.
Part of Scene Director's sub-engine suite.

Design: Features are GRANTED on level-up (stored in state), effects are
CALCULATED on-demand when activated.
"""

from typing import Any, Dict, List, Optional

# ── Feature Registry — keyed by (class_name, level) ───────────────────────
# Each feature dict contains:
#   name: str
#   uses: int (0 for passive/always-on features)
#   rest_recovery: "short" | "long" | None
#   passive: bool (True if always active, no activation needed)
#   damage_bonus: int | None
#   damage_dice: str | None
#   resistances: list[str] | None
#   description: str

FEATURES: Dict[tuple, dict] = {
    # ── Barbarian ──────────────────────────────────────────────────────────
    ("barbarian", 1): {
        "name": "Rage",
        "uses": 2,
        "rest_recovery": "long",
        "passive": False,
        "damage_bonus": 2,
        "resistances": ["bludgeoning", "piercing", "slashing"],
        "description": "Bonus action. +2 melee damage, resistance to B/P/S. Lasts 1 minute.",
    },
    ("barbarian", 2): {
        "name": "Reckless Attack",
        "uses": 0,
        "rest_recovery": None,
        "passive": True,
        "damage_bonus": 0,
        "description": "Attack with advantage but enemies have advantage against you.",
    },
    ("barbarian", 5): {
        "name": "Extra Attack",
        "uses": 0,
        "rest_recovery": None,
        "passive": True,
        "description": "Attack twice when taking the Attack action.",
    },
    ("barbarian", 7): {
        "name": "Feral Instinct",
        "uses": 0,
        "rest_recovery": None,
        "passive": True,
        "description": "Advantage on initiative rolls.",
    },
    ("barbarian", 9): {
        "name": "Brutal Critical",
        "uses": 0,
        "rest_recovery": None,
        "passive": True,
        "damage_dice": "1d12",
        "description": "Add 1 extra weapon die on critical hits.",
    },

    # ── Fighter ────────────────────────────────────────────────────────────
    ("fighter", 1): {
        "name": "Second Wind",
        "uses": 1,
        "rest_recovery": "short",
        "passive": False,
        "description": "Bonus action. Heal 1d10 + Fighter level HP.",
    },
    ("fighter", 2): {
        "name": "Action Surge",
        "uses": 1,
        "rest_recovery": "short",
        "passive": False,
        "description": "Take one additional action on your turn.",
    },
    ("fighter", 5): {
        "name": "Extra Attack",
        "uses": 0,
        "rest_recovery": None,
        "passive": True,
        "description": "Attack twice when taking the Attack action.",
    },

    # ── Rogue ──────────────────────────────────────────────────────────────
    ("rogue", 1): {
        "name": "Sneak Attack",
        "uses": 0,
        "rest_recovery": None,
        "passive": True,
        "damage_dice": "1d6",
        "description": "Once per turn, add 1d6 damage if you have advantage or ally within 5ft.",
    },
    ("rogue", 2): {
        "name": "Cunning Action",
        "uses": 0,
        "rest_recovery": None,
        "passive": True,
        "description": "Bonus action: Dash, Disengage, or Hide.",
    },
    ("rogue", 3): {
        "name": "Sneak Attack",
        "uses": 0,
        "rest_recovery": None,
        "passive": True,
        "damage_dice": "2d6",
        "description": "Sneak Attack increases to 2d6 at level 3.",
    },
    ("rogue", 5): {
        "name": "Uncanny Dodge",
        "uses": 0,
        "rest_recovery": None,
        "passive": True,
        "description": "Use reaction to halve damage from an attacker you can see.",
    },

    # ── Wizard ─────────────────────────────────────────────────────────────
    ("wizard", 1): {
        "name": "Spellcasting",
        "uses": 0,
        "rest_recovery": None,
        "passive": True,
        "description": "Full arcane spellcasting (INT-based).",
    },
    ("wizard", 1): {  # Note: same key overwrites, intentional — one per (class,level)
        "name": "Arcane Recovery",
        "uses": 1,
        "rest_recovery": "short",
        "passive": False,
        "description": "Recover spell slots equal to half wizard level (rounded up) on short rest.",
    },

    # ── Cleric ─────────────────────────────────────────────────────────────
    ("cleric", 1): {
        "name": "Spellcasting",
        "uses": 0,
        "rest_recovery": None,
        "passive": True,
        "description": "Full divine spellcasting (WIS-based).",
    },
    ("cleric", 2): {
        "name": "Channel Divinity",
        "uses": 1,
        "rest_recovery": "short",
        "passive": False,
        "description": "Use divine power: Turn Undead or domain-specific effect.",
    },

    # ── Bard ───────────────────────────────────────────────────────────────
    ("bard", 1): {
        "name": "Bardic Inspiration",
        "uses": 0,  # Uses = CHA mod (min 1), dynamic
        "rest_recovery": "long",
        "passive": False,
        "description": "Bonus action. Grant ally +1d6 to ability check, attack, or save.",
    },

    # ── Paladin ────────────────────────────────────────────────────────────
    ("paladin", 1): {
        "name": "Divine Sense",
        "uses": 1,
        "rest_recovery": "long",
        "passive": False,
        "description": "Detect celestials, fiends, undead within 60ft.",
    },
    ("paladin", 2): {
        "name": "Divine Smite",
        "uses": 0,
        "rest_recovery": None,
        "passive": True,
        "description": "Spend spell slot to deal +2d8 radiant damage on hit.",
    },
}

# Feature-level overrides: some features scale with level.
# E.g., Sneak Attack damage_dice changes from 1d6 to 2d6 at Rogue 3, etc.
# These are handled by having entries at both levels above.


def _get_features_for_class_level(class_name: str, level: int) -> List[dict]:
    """Get all features for a class up to and including the given level.

    Each (class_name, level) key returns one feature. Accumulate all
    features for levels <= requested level.
    """
    features = []
    for cl in range(1, level + 1):
        key = (class_name, cl)
        if key in FEATURES:
            features.append(dict(FEATURES[key]))  # Copy to avoid mutation
    return features


def get_features(character: dict) -> List[dict]:
    """Get all class features this character has earned based on class + level.

    Args:
        character: dict with 'player_class' and 'level' keys

    Returns:
        list of feature dicts with name, uses, passive, etc.
    """
    class_name = character.get("player_class", "").lower().replace(" ", "_")
    level = character.get("level", 1)
    return _get_features_for_class_level(class_name, level)


def activate_feature(character: dict, feature_name: str) -> dict:
    """Activate a class feature, consuming a use if applicable.

    Searches character['features'] for the named feature, checks if it has
    remaining uses, and consumes one if successful.

    Args:
        character: dict with 'features' list (must be pre-populated)
        feature_name: name of the feature to activate

    Returns:
        {
            "success": bool,
            "effect": dict | None — active effects to apply,
            "reason": str — explanation if failed
        }
    """
    features_list = character.get("features", [])
    name_lower = feature_name.lower()

    matches = [f for f in features_list if f["name"].lower() == name_lower]
    if not matches:
        return {"success": False, "effect": None,
                "reason": f"Feature '{feature_name}' not found for this character."}

    feature = matches[0]

    # For passive features that have no use counter (uses=0), activation is always valid
    if feature.get("passive", False) and feature.get("uses", 0) == 0:
        effect = {
            "active": True,
            "feature": feature["name"],
            "passive": True,
        }
        if "damage_bonus" in feature:
            effect["damage_bonus"] = feature["damage_bonus"]
        if "damage_dice" in feature:
            effect["damage_dice"] = feature["damage_dice"]
        if "resistances" in feature:
            effect["resistances"] = feature["resistances"]
        return {"success": True, "effect": effect}

    # Check for remaining uses
    used = feature.get("used", 0)
    max_uses = feature.get("uses", 0)
    if used >= max_uses:
        return {"success": False, "effect": None,
                "reason": f"Feature '{feature_name}' está agotado (exhausted: {used}/{max_uses})."}

    # Consume a use
    feature["used"] = used + 1

    effect = {
        "active": True,
        "feature": feature["name"],
        "uses_remaining": max_uses - feature["used"],
    }
    if "damage_bonus" in feature:
        effect["damage_bonus"] = feature["damage_bonus"]
    if "damage_dice" in feature:
        effect["damage_dice"] = feature["damage_dice"]
    if "resistances" in feature:
        effect["resistances"] = feature["resistances"]

    return {"success": True, "effect": effect}


def recover_features(character: dict, rest_type: str) -> dict:
    """Recover feature uses on short or long rest.

    Short rest: recovers features with rest_recovery="short"
    Long rest: recovers ALL features (short + long)

    Args:
        character: dict with 'features' list
        rest_type: "short" or "long"

    Returns:
        {
            "recovered": list[str] — names of features recovered,
            "count": int
        }
    """
    features_list = character.get("features", [])
    recovered = []

    for feature in features_list:
        recovery = feature.get("rest_recovery")
        if recovery is None:
            continue

        should_recover = False
        if rest_type == "long":
            # Long rest recovers everything
            should_recover = True
        elif rest_type == "short" and recovery == "short":
            should_recover = True

        if should_recover and feature.get("used", 0) > 0:
            feature["used"] = 0
            recovered.append(feature["name"])

    return {"recovered": recovered, "count": len(recovered)}


def grant_features_at_level(class_name: str, level: int) -> List[dict]:
    """Get features newly granted at a specific level (not accumulated).

    Used during level-up to determine what new features to add.

    Args:
        class_name: normalized class name
        level: the level just reached

    Returns:
        list of feature dicts granted AT this exact level
    """
    key = (class_name, level)
    if key in FEATURES:
        feat = dict(FEATURES[key])
        # Initialize use tracking
        feat["used"] = 0
        return [feat]
    return []
