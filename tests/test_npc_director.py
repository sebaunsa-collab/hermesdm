"""
test_npc_director.py — Tests for NPCDirector module.

Covers:
- Disposition ladder thresholds
- Hostile NPC attacks weakened player
- NPC with quest hook offers quest
- Faction war blocks parley
- Disposition adjustment
- NPC persistence via state
"""

import pytest
from dm.npc_director import NPCDirector, DISPOSITION_THRESHOLDS, AGENDA_TYPES


# ── Disposition Ladder ───────────────────────────────────────────────────


class TestDispositionLadder:
    """Disposition thresholds map values to labels."""

    def test_hostile_threshold(self):
        """-100 to -41 maps to hostile."""
        director = NPCDirector()
        assert director.get_disposition(-100) == "hostile"
        assert director.get_disposition(-41) == "hostile"
        assert director.get_disposition(-50) == "hostile"

    def test_wary_threshold(self):
        """-40 to -11 maps to wary."""
        director = NPCDirector()
        assert director.get_disposition(-40) == "wary"
        assert director.get_disposition(-11) == "wary"

    def test_neutral_threshold(self):
        """-10 to 10 maps to neutral."""
        director = NPCDirector()
        assert director.get_disposition(-10) == "neutral"
        assert director.get_disposition(0) == "neutral"
        assert director.get_disposition(10) == "neutral"

    def test_friendly_threshold(self):
        """11 to 40 maps to friendly."""
        director = NPCDirector()
        assert director.get_disposition(11) == "friendly"
        assert director.get_disposition(40) == "friendly"

    def test_allied_threshold(self):
        """41 to 100 maps to allied."""
        director = NPCDirector()
        assert director.get_disposition(41) == "allied"
        assert director.get_disposition(100) == "allied"

    def test_adjust_disposition(self):
        """Disposition can be adjusted with delta."""
        director = NPCDirector()
        npc = {"name": "Test", "disposition": "neutral", "disposition_value": 0}
        new_val = director.adjust_disposition(npc, 20)
        assert new_val == 20
        assert npc["disposition"] == "friendly"

    def test_adjust_disposition_clamps(self):
        """Disposition value clamps at -100 and 100."""
        director = NPCDirector()
        npc = {"disposition_value": 90}
        val = director.adjust_disposition(npc, 20)
        assert val == 100
        npc["disposition_value"] = -90
        val = director.adjust_disposition(npc, -20)
        assert val == -100


# ── Hostile NPC behavior ─────────────────────────────────────────────────


class TestHostileNPC:
    """Task 3.1: hostile NPC attacks when player HP < 50%."""

    def test_hostile_attacks_weakened_player(self):
        """Hostile NPC attacks when player HP below 50%."""
        state = {
            "player": {"hp_current": 15, "hp_max": 40},  # 37.5%
            "npcs": {
                "orc1": {
                    "name": "Orc Brutal",
                    "disposition": "hostile",
                    "faction": "orcos",
                },
            },
        }
        director = NPCDirector(state)
        actions = director.resolve_actions(state)
        assert len(actions) == 1
        assert actions[0]["action"] == "attack"
        assert actions[0]["agenda"] == "ambush"

    def test_hostile_does_not_attack_healthy_player(self):
        """Hostile NPC doesn't always attack when player is healthy."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},  # 75%
            "npcs": {
                "orc1": {
                    "name": "Orc Brutal",
                    "disposition": "hostile",
                    "faction": "orcos",
                },
            },
        }
        director = NPCDirector(state)
        actions = director.resolve_actions(state)
        # May return None or empty if no faction war
        assert len(actions) == 0 or all(a.get("action") != "attack")


# ── 3.3 Quest hook NPC ──────────────────────────────────────────────────


class TestQuestHookNPC:
    """Task 3.3: NPC with quest hook offers quest."""

    def test_npc_offers_quest(self):
        """Neutral NPC with quest_hook offers quest."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
            "npcs": {
                "npc1": {
                    "name": "Misterioso",
                    "disposition": "neutral",
                    "quest_hook": "rescue_princess",
                    "dialogue_hook": "Necesito tu ayuda...",
                },
            },
        }
        director = NPCDirector(state)
        actions = director.resolve_actions(state)
        assert len(actions) > 0
        # The first neutral NPC with quest_hook should offer quest
        quest_actions = [a for a in actions if a.get("action") == "offer_quest"]
        assert len(quest_actions) > 0

    def test_can_offer_quest(self):
        """can_offer_quest checks for quest_hook."""
        director = NPCDirector()
        assert director.can_offer_quest({"quest_hook": "test"}) is True
        assert director.can_offer_quest({"name": "No quest"}) is False


# ── 3.4 Faction war blocks parley ────────────────────────────────────────


class TestFactionWar:
    """Task 3.4: faction war blocks parley."""

    def test_faction_blocks_social(self):
        """Faction at war blocks social interaction."""
        director = NPCDirector()
        npc = {"faction": "orcos", "disposition": "neutral"}
        state = {
            "player": {"faction": "humanos"},
            "world": {
                "faction_relations": {
                    ("orcos", "humanos"): "war",
                },
            },
        }
        assert director.faction_blocks_parley(state, npc) is True

    def test_no_war_allows_social(self):
        """No faction war allows social interaction."""
        director = NPCDirector()
        npc = {"faction": "elfos", "disposition": "neutral"}
        state = {
            "player": {"faction": "humanos"},
            "world": {"faction_relations": {}},
        }
        assert director.faction_blocks_parley(state, npc) is False


# ── Blocks Social ─────────────────────────────────────────────────────────


class TestBlocksSocial:
    """NPC disposition blocks social resolution."""

    def test_hostile_blocks_social(self):
        """Hostile NPC blocks social interaction."""
        director = NPCDirector()
        assert director.blocks_social("hostile") is True

    def test_neutral_does_not_block(self):
        """Neutral NPC allows social interaction."""
        director = NPCDirector()
        assert director.blocks_social("neutral") is False

    def test_friendly_does_not_block(self):
        """Friendly NPC allows social interaction."""
        director = NPCDirector()
        assert director.blocks_social("friendly") is False


# ── Agenda types ─────────────────────────────────────────────────────────


class TestAgendaTypes:
    """All 5 agenda types exist."""

    def test_agenda_types_exist(self):
        """All 5 agenda types are defined."""
        expected = {"reveal_secret", "offer_quest", "betray", "ambush", "help"}
        assert set(AGENDA_TYPES) == expected


# ── Wary NPC ──────────────────────────────────────────────────────────────


class TestWaryNPC:
    """Wary NPCs observe cautiously."""

    def test_wary_npc_observes(self):
        """Wary NPC observes the player."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
            "npcs": {
                "npc1": {"name": "Suspicaz", "disposition": "wary"},
            },
        }
        director = NPCDirector(state)
        actions = director.resolve_actions(state)
        assert len(actions) == 1
        assert actions[0]["action"] == "observe"


# ── Friendly/Allied NPC ───────────────────────────────────────────────────


class TestFriendlyNPC:
    """Friendly and allied NPCs help."""

    def test_allied_reveals_secret(self):
        """Allied NPC with secret reveals it."""
        state = {
            "player": {"hp_current": 30, "hp_max": 40},
            "npcs": {
                "npc1": {
                    "name": "Aliado",
                    "disposition": "allied",
                    "secret": "El rey es un impostor",
                },
            },
        }
        director = NPCDirector(state)
        actions = director.resolve_actions(state)
        # Allied NPC with secret should reveal it
        reveal_actions = [a for a in actions if a.get("action") == "reveal_secret"]
        assert len(reveal_actions) > 0

    def test_friendly_helps_wounded(self):
        """Friendly NPC helps wounded player."""
        state = {
            "player": {"hp_current": 15, "hp_max": 40},  # 37.5%
            "npcs": {
                "npc1": {"name": "Amigo", "disposition": "friendly"},
            },
        }
        director = NPCDirector(state)
        actions = director.resolve_actions(state)
        help_actions = [a for a in actions if a.get("action") == "help"]
        assert len(help_actions) > 0
        assert help_actions[0].get("heal_amount", 0) > 0
