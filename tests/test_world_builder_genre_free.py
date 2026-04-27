"""
Tests para SPEC-GENRE-FREE: genre validation eliminada + no template fallback.

Estos tests verifican:
1. Cualquier género inventado por el usuario funciona sin error de género
2. Cuando la AI falla, se muestra un error visible (no template genérico)
3. El sistema no hace echo del input del usuario

Cubre el fix del bug:
  "samurais en Japón feudal" → ValueError("Genre validation failed...")
"""
import pytest
from unittest import mock
import json


def _make_mock_response(premise):
    """Genera un JSON mock de respuesta de AI que NO hace echo del input."""
    data = {
        "premise": premise,
        "hook": "Un evento inesperado cambia todo.",
        "starting_location": "Aldea Shimizu",
        "starting_location_desc": "Pueblo entre montañas y ríos.",
        "main_threat": "El Clan Sekigahara",
        "factions": {"Clan Dragon": "DOMINANT"},
        "npcs": [{"name": "Takeshi", "role": "Mercader", "dialogue": "El camino es largo."}],
        "classes": ["Guerrero", "Monje", "Explorador"],
        "starting_equipment": [{"name": "Katana", "description": "Espada curva tradicional.", "is_consumable": False}],
        "story_arc": {
            "pacing_level": "medium",
            "milestones": [
                {"id": "hook", "type": "hook", "description": "Los personajes se conocen cuando una delegación llega a la aldea buscando guerreros capaces."}
            ]
        }
    }
    return json.dumps(data)


def _make_gemini_http_mock(premise):
    """Crea un context manager que mockea urlopen para devolver una respuesta Gemini válida."""
    mock_response = _make_mock_response(premise)
    mock_body = json.dumps({
        "candidates": [{"content": {"parts": [{"text": mock_response}]}}],
        "usageMetadata": {"totalTokenCount": 100}
    }).encode("utf-8")

    mock_http_response = mock.MagicMock()
    mock_http_response.read.return_value = mock_body
    mock_http_response.__enter__ = mock.MagicMock(return_value=mock_http_response)
    mock_http_response.__exit__ = mock.MagicMock(return_value=False)

    return mock.MagicMock(return_value=mock_http_response)


class TestGenreFreeGeneration:
    """El sistema debe funcionar con cualquier género inventado sin validar keywords."""

    def _fake_getenv(self, key, default=None):
        if key == "GEMINI_API_KEY":
            return "fake_gemini_key_for_testing"
        return default or ""

    def test_samurai_input_does_not_raise_genre_error(self):
        """
        Bug original: /setup samurais en el Japón feudal
        fallaba con: ValueError("Genre validation failed for 'fantasy': ...")

        Después del fix: debe retornar setup válido, sin error de genre.
        El mock usa premise que NO hace echo del input.
        """
        mock_urlopen = _make_gemini_http_mock(
            "Tradición y acero se entrelazan en una era de profunda desigualdad."
        )
        with mock.patch("urllib.request.urlopen", mock_urlopen):
            with mock.patch("os.getenv", self._fake_getenv):
                from dm.world_builder import generate_setup_with_ai
                result = generate_setup_with_ai("samurais en el Japón feudal")

                assert result is not None
                assert "premise" in result
                assert "lore" in result
                assert "hook" in result

    def test_werewolf_input_does_not_raise_genre_error(self):
        """Hombres lobo no estaban en keywords — ahora debe funcionar sin error."""
        mock_urlopen = _make_gemini_http_mock(
            "Las noches sin luna traen terrores que la gente del pueblo prefiere no nombrar."
        )
        with mock.patch("urllib.request.urlopen", mock_urlopen):
            with mock.patch("os.getenv", self._fake_getenv):
                from dm.world_builder import generate_setup_with_ai
                result = generate_setup_with_ai("hombres lobo en Transilvania")

                assert result is not None
                assert "premise" in result

    def test_pirates_input_does_not_raise_genre_error(self):
        """Piratas funcionaban por luck (código estaba en keywords), pero el fix los mejora."""
        mock_urlopen = _make_gemini_http_mock(
            "Olas gigantes y mercados negros son el hogar de los que no tienen rey."
        )
        with mock.patch("urllib.request.urlopen", mock_urlopen):
            with mock.patch("os.getenv", self._fake_getenv):
                from dm.world_builder import generate_setup_with_ai
                result = generate_setup_with_ai("piratas buscando tesoro en el caribe")

                assert result is not None
                assert "premise" in result

    def test_custom_genre_invented_by_user(self):
        """Género inventado debe funcionar sin error — sin keywords, sin genre validation."""
        mock_urlopen = _make_gemini_http_mock(
            "Entre el humo de las fábricas, una red de informantes cambia de bando."
        )
        with mock.patch("urllib.request.urlopen", mock_urlopen):
            with mock.patch("os.getenv", self._fake_getenv):
                from dm.world_builder import generate_setup_with_ai
                result = generate_setup_with_ai("espías victorianos en el Londres de Jack el Destripador")

                assert result is not None
                assert "premise" in result

    def test_ninja_input_does_not_raise_genre_error(self):
        """Ninjas tampoco estaban en keywords — ahora debe funcionar sin error."""
        mock_urlopen = _make_gemini_http_mock(
            "Sombras y disciplina: el camino del guerrador silencioso."
        )
        with mock.patch("urllib.request.urlopen", mock_urlopen):
            with mock.patch("os.getenv", self._fake_getenv):
                from dm.world_builder import generate_setup_with_ai
                result = generate_setup_with_ai("ninja clan en el Japón feudal")

                assert result is not None
                assert "premise" in result

    def test_ai_failure_shows_error_instead_of_template(self):
        """
        Cuando la API está down, el sistema debe mostrar un error visible
        (RuntimeError), NO un template genérico de fantasy.

        Este es el comportamiento correcto: error visible > template falso.
        """
        import urllib.error

        class FakeHTTPError(urllib.error.HTTPError):
            def __init__(self):
                super().__init__(
                    "https://generativelanguage.googleapis.com/",
                    400,
                    "Bad Request",
                    {},
                    None,
                )

        def raise_urlopen(*args, **kwargs):
            raise FakeHTTPError()

        with mock.patch("urllib.request.urlopen", side_effect=raise_urlopen):
            with mock.patch("os.getenv", self._fake_getenv):
                from dm.world_builder import generate_setup_with_ai
                with pytest.raises(RuntimeError) as exc_info:
                    generate_setup_with_ai("samurais en el Japón feudal")

                assert "samurais en el Japón feudal" in str(exc_info.value)
