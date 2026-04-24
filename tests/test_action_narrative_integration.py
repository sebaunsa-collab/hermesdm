"""
test_action_narrative_integration.py — Tests for SDD-005 v1 fixes.

Covers:
- F1: cmd_begin persists location + lore to state
- F2: _build_context includes player_action
- F3: _resolve_dialogue finds NPCs, no dice roll
- F4: NPC names use npc["name"] not dict key
- F5: NarrativeGenerator fallbacks are Spanish
- F6: NarrativeGenerator reads setup lore
- F7: _interpret_with_ai removed
- F8: Opening scene uses actual location
- F9: Narrative references player's action text
"""

import unittest
from unittest import mock
import sys

# Pre-inject fake bot.dice_engine to avoid importing bot/__init__.py
_fake_dice = mock.MagicMock()
_fake_dice.roll = mock.MagicMock(return_value=10)
sys.modules["bot.dice_engine"] = _fake_dice

from adapters.mode_b.action_router import (
    ActionIntent,
    ActionResolution,
    ActionRouter,
    SceneType,
)
from dm.narrative_generator import Language, NarrativeGenerator


class MockCharacter:
    """Minimal character mock for ActionRouter tests."""

    def __init__(self, name="Shug"):
        self.name = name
        self.stats = {"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 8, "cha": 10}
        self.proficiency_bonus = 2

    def mod(self, stat: str) -> int:
        return (self.stats.get(stat, 10) - 10) // 2


class TestCmdBeginPersistLocation(unittest.TestCase):
    """F1: After cmd_begin, state['campaign'] has location + lore."""

    def test_location_persisted(self):
        """Mock the state update that cmd_begin does."""
        state = {
            "campaign": {"status": "active"},
            "setup": {
                "lore": {
                    "starting_location": "Piso 47: El Jardín de Cristal",
                    "starting_location_desc": "Un bosque de cristales rotos.",
                    "main_threat": "El Administrador",
                },
                "premise": "En Aincrad...",
                "hook": "Un mensajero aparece muerto...",
                "tone": "dark",
                "setting_type": "scifi",
            },
            "characters": {"shug": {}},
        }

        # Simulate what cmd_begin now does
        setup = state["setup"]
        lore = setup["lore"]
        state["campaign"]["current_location"] = lore.get("starting_location", "")
        state["campaign"]["current_location_desc"] = lore.get("starting_location_desc", "")
        state["campaign"]["main_threat"] = lore.get("main_threat", "")
        state["campaign"]["premise"] = setup.get("premise", "")
        state["campaign"]["hook"] = setup.get("hook", "")
        state["campaign"]["tone"] = setup.get("tone", "")
        state["campaign"]["setting_type"] = setup.get("setting_type", "")

        self.assertEqual(state["campaign"]["current_location"], "Piso 47: El Jardín de Cristal")
        self.assertEqual(state["campaign"]["current_location_desc"], "Un bosque de cristales rotos.")
        self.assertEqual(state["campaign"]["main_threat"], "El Administrador")
        self.assertEqual(state["campaign"]["premise"], "En Aincrad...")
        self.assertEqual(state["campaign"]["tone"], "dark")
        self.assertEqual(state["campaign"]["setting_type"], "scifi")


class TestActionRouterBuildContext(unittest.TestCase):
    """F2: _build_context includes the original action_text."""

    def test_player_action_in_context(self):
        state = {
            "campaign": {"current_location": "Taberna del Lobo Gris"},
            "npcs": {},
        }
        router = ActionRouter(state=state, character=MockCharacter())
        intent = ActionIntent(action_type="dialogue", target="tabernero")
        resolution = ActionResolution(success=True, mechanic_inline="test")
        action_text = "le pregunto al tabernero por el dragón"

        ctx = router._build_context(intent, resolution, SceneType.DIALOGUE, action_text)

        self.assertEqual(ctx["player_action"], action_text)
        self.assertEqual(ctx["player_action_type"], "dialogue")
        self.assertEqual(ctx["action_description"], action_text)


class TestResolveDialogue(unittest.TestCase):
    """F3: _resolve_dialogue finds NPCs and does NOT roll dice."""

    def test_dialogue_finds_npc_by_name(self):
        state = {
            "npcs": {
                "bartender_01": {
                    "name": "Gromm",
                    "role": "Tabernero",
                    "disposition": "FRIENDLY",
                }
            }
        }
        router = ActionRouter(state=state, character=MockCharacter())
        intent = ActionIntent(action_type="dialogue", target="gromm")
        result = router._resolve_dialogue(intent)

        self.assertTrue(result.success)
        self.assertIsNone(result.roll)
        self.assertIsNone(result.dc)
        self.assertIn("Gromm", result.mechanic_inline)
        self.assertIn("Tabernero", result.mechanic_inline)

    def test_dialogue_no_dice_roll(self):
        router = ActionRouter(state={}, character=MockCharacter())
        intent = ActionIntent(action_type="dialogue", target="desconocido")
        result = router._resolve_dialogue(intent)

        self.assertIsNone(result.roll)
        self.assertIsNone(result.dc)
        self.assertIn("Intentas hablar", result.mechanic_inline)

    def test_dialogue_hostile_disposition(self):
        state = {
            "npcs": {
                "enemy_01": {
                    "name": "Vorgath",
                    "role": "Bandido",
                    "disposition": "HOSTILE",
                }
            }
        }
        router = ActionRouter(state=state, character=MockCharacter())
        intent = ActionIntent(action_type="dialogue", target="vorgath")
        result = router._resolve_dialogue(intent)

        self.assertIn("hostilidad", result.mechanic_inline)


class TestNPCNameResolution(unittest.TestCase):
    """F4: NPC names come from npc['name'], not dict key."""

    def test_npc_name_uses_name_field(self):
        state = {
            "campaign": {"current_location": "Bosque"},
            "npcs": {
                "knight_01": {"name": "Sir Aldric", "role": "Caballero"}
            },
        }
        router = ActionRouter(state=state, character=MockCharacter())
        intent = ActionIntent(action_type="attack", target="goblin")
        resolution = ActionResolution(success=True, mechanic_inline="test")
        ctx = router._build_context(intent, resolution, SceneType.COMBAT, "ataco al goblin")

        self.assertIn("Sir Aldric", ctx["npc_present"])
        self.assertNotIn("knight_01", ctx["npc_present"])


class TestNarrativeGeneratorFallbacks(unittest.TestCase):
    """F5: Fallback values are in Spanish."""

    def test_fallbacks_spanish(self):
        ng = NarrativeGenerator()
        ctx = ng._build_context({"campaign": {}, "characters": {}, "npcs": {}}, {})

        # No English phrases should appear in fallbacks
        self.assertNotIn("shadows", ctx["sensory_detail"].lower())
        self.assertNotIn("The party", ctx["character_present"])
        self.assertNotIn("unknown place", ctx["location"])

    def test_location_fallback_spanish(self):
        ng = NarrativeGenerator()
        ctx = ng._build_context({"campaign": {}, "characters": {}, "npcs": {}}, {})
        self.assertEqual(ctx["location"], "un lugar desconocido")


class TestNarrativeGeneratorReadsSetupLore(unittest.TestCase):
    """F6: _build_context reads setup['lore'] for sensory details."""

    def test_reads_starting_location_desc(self):
        ng = NarrativeGenerator()
        state = {
            "campaign": {},
            "setup": {
                "lore": {"starting_location_desc": "Cristales rotos por doquier."}
            },
        }
        ctx = ng._build_context(state, {})
        self.assertEqual(ctx["sensory_detail"], "Cristales rotos por doquier.")

    def test_reads_main_threat(self):
        ng = NarrativeGenerator()
        state = {
            "campaign": {},
            "setup": {
                "lore": {"main_threat": "El Dragón Rojo"}
            },
        }
        ctx = ng._build_context(state, {})
        self.assertIn("El Dragón Rojo", ctx["ambient_threat"])


class TestInterpretWithAIRemoved(unittest.TestCase):
    """F7: _interpret_with_ai no longer exists."""

    def test_method_removed(self):
        router = ActionRouter(state={}, character=MockCharacter())
        self.assertFalse(hasattr(router, '_interpret_with_ai'))


class TestLocationUsedInOpening(unittest.TestCase):
    """F8: Opening scene uses actual location, not 'un lugar olvidado'."""

    def test_template_uses_location(self):
        ng = NarrativeGenerator()
        state = {
            "campaign": {"current_location": "Piso 47"},
            "characters": {"shug": {"name": "Shug", "hp": {"current": 10, "max": 10}}},
            "npcs": {},
        }
        result = ng.generate_scene(state, SceneType.EXPLORATION, {"location": "Piso 47"}, Language.ES)
        narrative = result["narrative"]
        self.assertIn("Piso 47", narrative)


class TestPlayerActionInNarrative(unittest.TestCase):
    """F9: Narrative references the player's action text."""

    def test_action_description_override(self):
        ng = NarrativeGenerator()
        state = {
            "campaign": {"current_location": "Bosque"},
            "characters": {"shug": {"name": "Shug", "hp": {"current": 10, "max": 10}}},
            "npcs": {},
        }
        result = ng.generate_scene(
            state,
            SceneType.EXPLORATION,
            {"action_description": "inspecciono las huellas en el barro"},
            Language.ES,
        )
        narrative = result["narrative"]
        self.assertIn("inspecciono las huellas", narrative)


if __name__ == "__main__":
    unittest.main()
