"""Coverage tests for dm/narrative_generator.py — pure functions and edge cases."""
import pytest
from unittest.mock import MagicMock, patch
from dm.narrative_generator import (
    Language,
    NarrativeGenerator,
    SceneType,
)


class TestSceneTypeEnum:
    """Verify SceneType enum values."""
    
    def test_scene_types_exist(self):
        assert SceneType.COMBAT.value == "COMBAT"
        assert SceneType.EXPLORATION.value == "EXPLORATION"
        assert SceneType.DIALOGUE.value == "DIALOGUE"
        assert SceneType.REST.value == "REST"
        assert SceneType.STORY_BEAT.value == "STORY_BEAT"
    
    def test_scene_type_values_match(self):
        assert SceneType.COMBAT.value == "COMBAT"
        assert SceneType.DIALOGUE.value == "DIALOGUE"


class TestNarrativeGeneratorPure:
    """Tests for pure functions in NarrativeGenerator — no LLM needed."""
    
    @pytest.fixture
    def ng(self):
        return NarrativeGenerator(llm_client=None)
    
    def test_pick_template_returns_string(self, ng):
        templates = ["Te encuentras en {location}.", "El grupo llega a {location}."]
        result = ng._pick_template(templates)
        assert isinstance(result, str)
        assert result in templates
    
    def test_pick_template_single_item(self, ng):
        result = ng._pick_template(["Solo template"])
        assert result == "Solo template"
    
    def test_fill_template_placeholders(self, ng):
        template = "{character_present} camina hacia {location}."
        context = {"character_present": "Valdric", "location": "la torre"}
        result = ng._fill_template(template, context)
        assert "Valdric" in result
        assert "la torre" in result
        assert "{character_present}" not in result
    
    def test_fill_template_missing_keys(self, ng):
        template = "Ves {thing} en {location}."
        context = {"location": "el bosque"}
        result = ng._fill_template(template, context)
        assert "el bosque" in result
    
    def test_select_template_combat(self, ng):
        result = ng._select_template(SceneType.COMBAT, Language.ES)
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_select_template_exploration(self, ng):
        result = ng._select_template(SceneType.EXPLORATION, Language.ES)
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_select_template_dialogue(self, ng):
        result = ng._select_template(SceneType.DIALOGUE, Language.ES)
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_should_trigger_image_combat(self, ng):
        ctx = {"location": "cueva", "sensory_detail": "oscura"}
        result = ng._should_trigger_image(SceneType.COMBAT, ctx)
        assert isinstance(result, bool)
    
    def test_should_trigger_image_exploration(self, ng):
        ctx = {"location": "bosque encantado"}
        result = ng._should_trigger_image(SceneType.EXPLORATION, ctx)
        assert isinstance(result, bool)
    
    def test_should_trigger_image_rest(self, ng):
        ctx = {"location": "campamento"}
        result = ng._should_trigger_image(SceneType.REST, ctx)
        assert isinstance(result, bool)

    def test_build_context_populates_fields(self, ng):
        state = {"campaign": {"current_location": "aldea"}, "characters": {}}
        ctx = ng._build_context(state, {})
        assert "location" in ctx
        assert "character_present" in ctx
        assert "sensory_detail" in ctx
    
    def test_language_enum_values(self):
        assert Language.ES.value == "es"
        assert Language.EN.value == "en"
