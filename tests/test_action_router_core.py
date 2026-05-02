import pytest
from unittest.mock import MagicMock, patch
from adapters.mode_b.action_router import (
    ActionRouter, ActionIntent, ActionResolution, ActionResult, SceneType,
)


class TestCoreGameLoop:
    def test_parse_attack_returns_valid_intent(self):
        router = ActionRouter()
        intent = router._parse('ataco al dragon')
        assert isinstance(intent, ActionIntent)
        assert intent.action_type == 'attack'
        assert intent.target is not None

    def test_parse_dialogue_returns_valid_intent(self):
        router = ActionRouter()
        intent = router._parse('le digo hola al guardia')
        assert intent.action_type == 'dialogue'

    def test_resolve_attack_with_roll_produces_resolution(self):
        char = MagicMock()
        char.name = 'Valdric'
        char.mod = MagicMock(return_value=3)
        char.proficiency_bonus = 2
        router = ActionRouter(state={}, character=char)
        intent = router._parse('ataco al goblin')
        resolution = router._resolve(intent)
        assert isinstance(resolution, ActionResolution)
        assert resolution.hit is not None

    def test_route_attack_returns_action_result(self):
        char = MagicMock()
        char.name = 'Valdric'
        char.mod = MagicMock(return_value=3)
        char.proficiency_bonus = 2
        router = ActionRouter(state={}, character=char)
        mock_update = MagicMock()
        result = router.route(mock_update, 'ataco al dragon')
        assert isinstance(result, ActionResult)
        assert len(result.narrative) > 0
        assert len(result.mechanic_inline) > 0

    def test_route_explore_returns_action_result(self):
        router = ActionRouter()
        mock_update = MagicMock()
        result = router.route(mock_update, 'exploro la caverna')
        assert isinstance(result, ActionResult)
        assert len(result.narrative) > 0

    def test_route_rest_returns_action_result(self):
        router = ActionRouter()
        mock_update = MagicMock()
        result = router.route(mock_update, 'descanso')
        assert isinstance(result, ActionResult)
        assert len(result.narrative) > 0


class TestAutoSuccessPath:
    def test_action_resolution_default_narrative_is_empty_string(self):
        resolution = ActionResolution(success=True)
        assert resolution.narrative == ""
        assert resolution.narrative is not None
        assert resolution.success is True

    def test_action_resolution_with_narrative(self):
        resolution = ActionResolution(
            success=True,
            narrative='Caminas sin dificultad',
        )
        assert resolution.narrative == 'Caminas sin dificultad'

    def test_action_resolution_construction_no_typeerror(self):
        resolution = ActionResolution(
            success=True,
            narrative='test',
            roll=None,
            roll_obj=None,
            mechanic_inline='',
        )
        assert resolution.narrative == 'test'
        assert resolution.success is True

    def test_action_intent_has_action_description(self):
        intent = ActionIntent(
            action_type='explore',
            target=None,
            action_description='caminar al pueblo',
        )
        assert intent.action_description == 'caminar al pueblo'


    def test_auto_success_generic_populates_narrative(self):
        """Auto-success path MUST populate narrative with a non-empty string."""
        router = ActionRouter(state={})
        intent = ActionIntent(
            action_type='walk',
            target=None,
            action_description='caminar al pueblo',
        )
        resolution = router._resolve(intent)
        assert isinstance(resolution, ActionResolution)
        assert resolution.success is not None
        assert resolution.narrative is not None
        assert len(resolution.narrative) > 0
        assert 'caminar' in resolution.narrative or 'walk' in resolution.narrative
    def test_resolve_disengage_returns_no_typeerror(self):
        char = MagicMock()
        char.name = 'Valdric'
        char.mod = MagicMock(return_value=3)
        char.proficiency_bonus = 2
        router = ActionRouter(state={}, character=char)
        intent = ActionIntent(
            action_type='disengage',
            target=None,
            action_description='desenganchar',
        )
        resolution = router._resolve(intent)
        assert isinstance(resolution, ActionResolution)
        assert resolution.success is True
