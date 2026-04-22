"""
tests/test_action_router.py — Tests for Mode B ActionRouter.

Run with: pytest tests/test_action_router.py -v
"""

from unittest.mock import MagicMock

import pytest

from adapters.mode_b.action_router import (
    ActionIntent,
    ActionResolution,
    ActionResult,
    ActionRouter,
    SceneType,
)

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def router():
    """Router sin estado ni personaje (usa defaults)."""
    return ActionRouter()


@pytest.fixture
def router_with_char():
    """Router con personaje mockeado."""
    char = MagicMock()
    char.name = "Valdric"
    char.mod = MagicMock(return_value=3)  # +3 modifier
    char.proficiency_bonus = 2
    return ActionRouter(state={}, character=char)


@pytest.fixture
def router_with_state():
    """Router con game state."""
    state = {
        "campaign": {
            "name": "The Lost Mine",
            "current_location": {"name": "Goblin Cave"},
        },
        "npcs": {
            "Goblin": {"ac": 13, "hp": 20},
        },
    }
    return ActionRouter(state=state)


# ------------------------------------------------------------------
# _parse — detección de tipo de acción
# ------------------------------------------------------------------


class TestParseActionType:
    """Tests para detección del tipo de acción."""

    def test_parse_attack_spanish(self, router):
        intent = router._parse("ataco al dragon")
        assert intent.action_type == "attack"

    def test_parse_attack_golpear(self, router):
        intent = router._parse("golpeo al orco")
        assert intent.action_type == "attack"

    def test_parse_attack_pegar(self, router):
        intent = router._parse("pego al goblin")
        assert intent.action_type == "attack"

    def test_parse_attack_english(self, router):
        intent = router._parse("strike the dragon")
        assert intent.action_type == "attack"

    def test_parse_attack_hit(self, router):
        intent = router._parse("hit the orc")
        assert intent.action_type == "attack"

    def test_parse_attack_attack(self, router):
        intent = router._parse("attack the goblin")
        assert intent.action_type == "attack"

    def test_parse_cast_spanish(self, router):
        intent = router._parse("lanzo un hechizo")
        assert intent.action_type == "cast"

    def test_parse_cast_english(self, router):
        intent = router._parse("cast a spell")
        assert intent.action_type == "cast"

    def test_parse_dialogue_spanish(self, router):
        intent = router._parse("le digo al guardia")
        assert intent.action_type == "dialogue"

    def test_parse_dialogue_english(self, router):
        intent = router._parse("say hello to the guard")
        assert intent.action_type == "dialogue"

    def test_parse_dialogue_talk(self, router):
        intent = router._parse("talk to the merchant")
        assert intent.action_type == "dialogue"

    def test_parse_skill_spanish(self, router):
        intent = router._parse("tirada de percepcion")
        assert intent.action_type == "perception"

    def test_parse_skill_english(self, router):
        intent = router._parse("roll perception")
        assert intent.action_type == "perception"

    def test_parse_rest_spanish(self, router):
        intent = router._parse("descanso en la taberna")
        assert intent.action_type == "rest"

    def test_parse_rest_english(self, router):
        intent = router._parse("rest for the night")
        assert intent.action_type == "rest"

    def test_parse_explore_default(self, router):
        """Sin keywords conocidas → explore."""
        intent = router._parse("me muevo hacia el norte")
        assert intent.action_type == "explore"


# ------------------------------------------------------------------
# _parse — extracción de objetivo
# ------------------------------------------------------------------


class TestParseTarget:
    """Tests para extracción de objetivo en ataques."""

    def test_target_spanish_ataco_al(self, router):
        intent = router._parse("ataco al dragon")
        assert intent.target == "Dragon"

    def test_target_spanish_english_mixed(self, router):
        """Spanish ataque + English objetivo."""
        intent = router._parse("ataco al dragon con mi espada")
        assert intent.target == "Dragon"

    def test_target_english_strike_the(self, router):
        intent = router._parse("strike the goblin with my sword")
        assert intent.target == "Goblin"

    def test_target_english_hit_the(self, router):
        intent = router._parse("hit the orc")
        assert intent.target == "Orc"

    def test_target_english_attack_the(self, router):
        intent = router._parse("attack the troll")
        assert intent.target == "Troll"

    def test_target_strips_prepositions_spanish(self, router):
        """'con', 'del', 'al' no deben quedar en el target."""
        intent = router._parse("ataco al dragon con mi espada")
        assert intent.target == "Dragon"
        assert "al" not in intent.target
        assert "con" not in intent.target

    def test_target_strips_prepositions_english(self, router):
        """English prepositions no deben quedar en el target."""
        intent = router._parse("strike the goblin with my sword")
        assert intent.target == "Goblin"
        assert "with" not in intent.target
        assert "the" not in intent.target

    def test_target_with_possessives_english(self, router):
        intent = router._parse("hit the orc with my axe")
        assert intent.target == "Orc"

    def test_target_fallback_capitalizes(self, router):
        """Si no se detecta target, usa la primera palabra significativa."""
        intent = router._parse("pego al dragon")
        assert intent.target == "Dragon"

    def test_target_default_when_empty(self, router):
        """Sin contexto, usa 'el objetivo'."""
        intent = router._parse("atacar")
        assert intent.target == "el objetivo"


# ------------------------------------------------------------------
# _resolve_attack — resolución de combate
# ------------------------------------------------------------------


class TestResolveAttack:
    """Tests para _resolve_attack con dados mockeados."""

    def test_attack_hit(self, router_with_char):
        """Ataque normal que impacta."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "adapters.mode_b.action_router._roll_dice",
                lambda dice: {"total": 15, "rolls": [15]} if dice == "1d20"
                else {"total": 6, "rolls": [6]},
            )
            intent = router_with_char._parse("ataco al goblin")
            result = router_with_char._resolve_attack(intent)

        assert result.hit is True
        assert result.success is True
        assert result.damage == 6
        assert result.nat_20 is False
        assert result.nat_1 is False
        assert "Impacto" in result.mechanic_inline
        assert "6" in result.mechanic_inline

    def test_attack_miss(self, router_with_char):
        """Ataque que falla (roll bajo)."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "adapters.mode_b.action_router._roll_dice",
                lambda dice: {"total": 5, "rolls": [5]} if dice == "1d20"
                else {"total": 4, "rolls": [4]},
            )
            intent = router_with_char._parse("ataco al dragon")
            result = router_with_char._resolve_attack(intent)

        assert result.hit is False
        assert result.success is False
        assert result.damage == 0
        assert "falla" in result.mechanic_inline

    def test_attack_nat_20_crit(self, router_with_char):
        """Natural 20 = crítico."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "adapters.mode_b.action_router._roll_dice",
                lambda dice: {"total": 20, "rolls": [20]} if dice == "1d20"
                else {"total": 12, "rolls": [6, 6]},  # 2d8 para críticos
            )
            intent = router_with_char._parse("ataco al dragon")
            result = router_with_char._resolve_attack(intent)

        assert result.hit is True
        assert result.nat_20 is True
        assert result.damage == 12
        assert "CRÍTICO" in result.mechanic_inline or "CRITICAL" in result.mechanic_inline

    def test_attack_nat_1_fumble(self, router_with_char):
        """Natural 1 = fumble."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "adapters.mode_b.action_router._roll_dice",
                lambda dice: {"total": 1, "rolls": [1]},
            )
            intent = router_with_char._parse("ataco al dragon")
            result = router_with_char._resolve_attack(intent)

        assert result.hit is False
        assert result.nat_1 is True
        assert result.damage == 0
        assert "FUMBLE" in result.mechanic_inline or "💀" in result.mechanic_inline

    def test_attack_defaults_no_character(self, router):
        """Sin personaje usa stats por defecto (prof=2, mod=0)."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "adapters.mode_b.action_router._roll_dice",
                lambda dice: {"total": 18, "rolls": [18]} if dice == "1d20"
                else {"total": 5, "rolls": [5]},
            )
            intent = router._parse("ataco al dragon")
            result = router._resolve_attack(intent)

        # 18 + 0 + 2 = 20 vs AC 14 → hit
        assert result.hit is True
        assert result.attack_roll == 20


# ------------------------------------------------------------------
# _resolve_skill — tiradas de habilidad
# ------------------------------------------------------------------


class TestResolveSkill:
    """Tests para _resolve_skill."""

    def test_skill_success(self, router_with_char):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "adapters.mode_b.action_router._roll_dice",
                lambda dice: {"total": 15, "rolls": [15]},
            )
            intent = router_with_char._parse("tirada de percepcion")
            result = router_with_char._resolve_skill(intent)

        # 15 + 3 (dex mod) + 2 (prof) = 20 vs DC 14 → éxito
        assert result.success is True
        assert result.dc == 14
        assert "Éxito" in result.mechanic_inline or "éxito" in result.mechanic_inline

    def test_skill_failure(self, router_with_char):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "adapters.mode_b.action_router._roll_dice",
                lambda dice: {"total": 6, "rolls": [6]},
            )
            intent = router_with_char._parse("tirada de percepcion")
            result = router_with_char._resolve_skill(intent)

        # 6 + 3 + 2 = 11 vs DC 14 → fallo
        assert result.success is False
        assert "Fallo" in result.mechanic_inline or "Fallo" in result.mechanic_inline

    def test_skill_no_character(self, router):
        """Sin personaje: 10 + 0 + 2 = 12 vs DC 14 → fallo."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "adapters.mode_b.action_router._roll_dice",
                lambda dice: {"total": 10, "rolls": [10]},
            )
            intent = router._parse("skill check")
            result = router._resolve_skill(intent)

        assert result.success is False


# ------------------------------------------------------------------
# _resolve_cast — lanzamiento de hechizos
# ------------------------------------------------------------------


class TestResolveCast:
    """Tests para _resolve_cast."""

    def test_cast_success(self, router_with_char):
        r = router_with_char
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "adapters.mode_b.action_router._roll_dice",
                lambda dice: {"total": 15, "rolls": [15]},
            )
            intent = r._parse("lanzo fuego")
            intent.target = "Fire Bolt"
            result = router_with_char._resolve_cast(intent)

        # 15 >= DC 10 → éxito
        assert result.success is True
        assert "exitoso" in result.mechanic_inline or "exitoso" in result.mechanic_inline.lower()

    def test_cast_failure(self, router_with_char):
        r = router_with_char
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "adapters.mode_b.action_router._roll_dice",
                lambda dice: {"total": 7, "rolls": [7]},
            )
            intent = r._parse("lanzo magia")
            intent.target = "Magic Missile"
            result = router_with_char._resolve_cast(intent)

        assert result.success is False
        assert "falla" in result.mechanic_inline.lower()

    def test_cast_uses_int_mod(self, router_with_char):
        """Cast usa INT modifier."""
        r = router_with_char
        r.char.mod = MagicMock(return_value=5)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "adapters.mode_b.action_router._roll_dice",
                lambda dice: {"total": 12, "rolls": [12]},
            )
            intent = r._parse("cast spell")
            intent.target = "Arcane Blast"
            result = router_with_char._resolve_cast(intent)

        # Save DC = 8 + prof(2) + int_mod(5) = 15
        assert result.dc == 15


# ------------------------------------------------------------------
# _classify — mapeo a SceneType
# ------------------------------------------------------------------


class TestClassify:
    """Tests para _classify."""

    def test_classify_attack_combat(self, router):
        intent = ActionIntent(action_type="attack", target="Dragon", params={})
        resolution = ActionResolution(success=True, hit=True, damage=8, roll=18,
                                       dc=14, mechanic_inline="", attack_roll=20)
        scene = router._classify(intent, resolution)
        assert scene == SceneType.COMBAT

    def test_classify_dialogue(self, router):
        intent = ActionIntent(action_type="dialogue", target="Guard", params={})
        resolution = ActionResolution(success=True, roll=10, dc=12,
                                       mechanic_inline="", attack_roll=10)
        scene = router._classify(intent, resolution)
        assert scene == SceneType.DIALOGUE

    def test_classify_rest(self, router):
        intent = ActionIntent(action_type="rest", target=None, params={})
        resolution = ActionResolution(success=True, roll=10, dc=12,
                                       mechanic_inline="", attack_roll=10)
        scene = router._classify(intent, resolution)
        assert scene == SceneType.REST

    def test_classify_skill_success_story_beat(self, router):
        intent = ActionIntent(action_type="skill", target="Perception", params={})
        resolution = ActionResolution(success=True, roll=18, dc=14,
                                       mechanic_inline="", attack_roll=18)
        scene = router._classify(intent, resolution)
        assert scene == SceneType.STORY_BEAT

    def test_classify_skill_failure_exploration(self, router):
        intent = ActionIntent(action_type="skill", target="Stealth", params={})
        resolution = ActionResolution(success=False, roll=8, dc=14,
                                       mechanic_inline="", attack_roll=8)
        scene = router._classify(intent, resolution)
        assert scene == SceneType.EXPLORATION

    def test_classify_cast_combat(self, router):
        intent = ActionIntent(action_type="cast", target="Fireball", params={})
        resolution = ActionResolution(success=True, roll=15, dc=10,
                                       mechanic_inline="", attack_roll=15)
        scene = router._classify(intent, resolution)
        assert scene == SceneType.COMBAT


# ------------------------------------------------------------------
# _build_context
# ------------------------------------------------------------------


class TestBuildContext:
    """Tests para _build_context."""

    def test_context_includes_attacker_name(self, router_with_char):
        intent = ActionIntent(action_type="attack", target="Dragon", params={})
        resolution = ActionResolution(success=True, hit=True, damage=8, roll=15,
                                       dc=14, mechanic_inline="", attack_roll=20)
        ctx = router_with_char._build_context(intent, resolution, SceneType.COMBAT)
        assert ctx["attacker"] == "Valdric"

    def test_context_includes_target(self, router):
        intent = ActionIntent(action_type="attack", target="Goblin", params={})
        resolution = ActionResolution(success=True, hit=True, damage=5, roll=12,
                                       dc=14, mechanic_inline="", attack_roll=17)
        ctx = router._build_context(intent, resolution, SceneType.COMBAT)
        assert ctx["defender"] == "Goblin"

    def test_context_from_state(self, router_with_state):
        intent = ActionIntent(action_type="attack", target="Goblin", params={})
        resolution = ActionResolution(success=True, hit=True, damage=8, roll=18,
                                       dc=14, mechanic_inline="", attack_roll=22)
        ctx = router_with_state._build_context(intent, resolution, SceneType.COMBAT)
        assert ctx["location"] == "Goblin Cave"
        assert ctx["campaign"]["name"] == "The Lost Mine"

    def test_context_nat_20_situation(self, router):
        intent = ActionIntent(action_type="attack", target="Dragon", params={})
        resolution = ActionResolution(success=True, hit=True, damage=15, roll=20,
                                       dc=14, mechanic_inline="", attack_roll=25,
                                       nat_20=True)
        ctx = router._build_context(intent, resolution, SceneType.COMBAT)
        assert "cae" in ctx["situation"] or "devastado" in ctx["situation"]
        assert ctx["nat_20"] is True

    def test_context_nat_1_situation(self, router):
        intent = ActionIntent(action_type="attack", target="Dragon", params={})
        resolution = ActionResolution(success=False, hit=False, damage=0, roll=1,
                                       dc=14, mechanic_inline="", attack_roll=3,
                                       nat_1=True)
        ctx = router._build_context(intent, resolution, SceneType.COMBAT)
        assert "rebota" in ctx["situation"] or "arma" in ctx["situation"]
        assert ctx["nat_1"] is True


# ------------------------------------------------------------------
# route — integración completa
# ------------------------------------------------------------------


class TestRoute:
    """Tests de integración para route()."""

    def test_route_returns_action_result(self, router):
        mock_update = MagicMock()
        result = router.route(mock_update, "ataco al dragon")

        assert isinstance(result, ActionResult)
        assert result.narrative is not None
        assert result.mechanic_inline is not None
        # image_path es None por ahora (generación automática en telegram_handler)
        assert result.image_path is None

    def test_route_narrative_contains_attacker(self, router_with_char):
        mock_update = MagicMock()
        result = router_with_char.route(mock_update, "golpeo al troll")

        assert "Valdric" in result.narrative or "troll" in result.narrative.lower()

    def test_route_mechanic_inline_has_dice(self, router):
        mock_update = MagicMock()
        result = router.route(mock_update, "ataco al dragon")

        # mechanic_inline debe contener info de dados
        assert len(result.mechanic_inline) > 5

    def test_route_explore_action(self, router):
        mock_update = MagicMock()
        result = router.route(mock_update, "exploro la caverna")

        assert isinstance(result, ActionResult)
        assert result.narrative is not None

    def test_route_dialogue_action(self, router):
        mock_update = MagicMock()
        result = router.route(mock_update, "le digo hola al guardia")

        assert isinstance(result, ActionResult)
        assert result.narrative is not None

    def test_route_rest_action(self, router):
        mock_update = MagicMock()
        result = router.route(mock_update, "descanso")

        assert isinstance(result, ActionResult)
        assert result.narrative is not None
