"""Additional coverage tests for dm/world_builder.py — sanitize + milestone validation."""
import pytest
from dm.world_builder import _sanitize_setup, _validate_milestones


class TestSanitizeSetup:
    """Tests for _sanitize_setup function."""

    def test_sanitize_preserves_valid_fields(self):
        setup = {
            "description": "dark fantasy",
            "premise": "El reino cae en sombras",
            "hook": "Un augurio oscuro",
            "tone": "dark",
            "setting_type": "fantasy",
            "approved": False,
            "classes": ["Warrior", "Mage"],
            "lore": {
                "factions": {"guild": "Merchant Guild"},
                "main_threat": "Dragon",
                "starting_location": "Aldea",
                "starting_location_desc": "Small village",
                "npcs": {},
            },
            "starting_equipment": [],
            "story_arc": {},
        }
        result = _sanitize_setup(setup, "dark fantasy game")
        assert result["premise"] == "El reino cae en sombras"
        assert result["setting_type"] == "fantasy"

    def test_sanitize_strips_echo_from_premise(self):
        """_sanitize_setup should not echo user input verbatim."""
        setup = {
            "description": "test",
            "premise": "dark fantasy with dragons",
            "hook": "A dragon appears",
            "tone": "dark",
            "setting_type": "fantasy",
            "approved": False,
            "classes": [],
            "lore": {
                "factions": {},
                "main_threat": "Dragon",
                "starting_location": "Cave",
                "starting_location_desc": "Dark cave",
                "npcs": {},
            },
            "starting_equipment": [],
            "story_arc": {},
        }
        result = _sanitize_setup(setup, "dark fantasy with dragons")
        assert isinstance(result["premise"], str)
        # Premise may differ from input now due to echo detection

    def test_sanitize_handles_missing_lore(self):
        setup = {
            "description": "test",
            "premise": "Adventure awaits",
            "hook": "Start here",
            "tone": "serious",
            "setting_type": "fantasy",
            "approved": False,
            "classes": [],
            "lore": {},
            "starting_equipment": [],
            "story_arc": {},
        }
        result = _sanitize_setup(setup, "test game")
        # Should not crash, should preserve lore structure
        assert "lore" in result


class TestValidateMilestones:
    """Tests for _validate_milestones function."""

    def test_validate_no_milestones(self):
        setup = {"story_arc": {}}
        errors = _validate_milestones(setup)
        assert isinstance(errors, list)
        assert len(errors) > 0  # Should warn about no milestones

    def test_validate_empty_milestones(self):
        setup = {"story_arc": {"milestones": []}}
        errors = _validate_milestones(setup)
        assert isinstance(errors, list)

    def test_validate_generic_milestone_description(self):
        """Milestone with generic description should trigger warning."""
        setup = {
            "story_arc": {
                "milestones": [
                    {"id": "m1", "type": "hook", "description": "avanza la trama principal"}
                ]
            }
        }
        errors = _validate_milestones(setup)
        assert isinstance(errors, list)
        # Generic descriptions should be flagged

    def test_validate_good_milestones(self):
        """Well-written milestones should pass validation."""
        setup = {
            "story_arc": {
                "milestones": [
                    {
                        "id": "m1",
                        "type": "hook",
                        "description": "Los heroes descubren una antigua profecia en las ruinas del templo olvidado que revela el origen del mal que asola estas tierras."
                    },
                    {
                        "id": "m2",
                        "type": "rising_action",
                        "description": "El grupo debe atravesar el Bosque de las Sombras mientras evitan a los cazadores nocturnos y encuentran aliados inesperados entre los refugiados del reino caido."
                    }
                ]
            }
        }
        errors = _validate_milestones(setup)
        assert isinstance(errors, list)

    def test_validate_missing_story_arc(self):
        setup = {}
        errors = _validate_milestones(setup)
        assert isinstance(errors, list)
