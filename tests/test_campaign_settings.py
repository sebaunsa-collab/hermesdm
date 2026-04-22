"""Tests for campaign_settings.py."""


from campaign_settings import (
    CampaignSettings,
    Difficulty,
    NarrativeTone,
)


class TestCampaignSettings:
    def test_defaults(self):
        s = CampaignSettings()
        assert s.image_generation is True
        assert s.difficulty == Difficulty.NORMAL
        assert s.turn_timer_seconds == 120
        assert s.narrative_tone == NarrativeTone.SERIOUS
        assert s.luck_bonus == 0
        assert s.dramatic_dice is True

    def test_to_dict(self):
        s = CampaignSettings()
        d = s.to_dict()
        assert d["image_generation"] is True
        assert d["difficulty"] == "normal"
        assert d["turn_timer_seconds"] == 120
        assert d["narrative_tone"] == "serious"
        assert d["luck_bonus"] == 0
        assert d["dramatic_dice"] is True

    def test_from_dict(self):
        raw = {
            "image_generation": False,
            "difficulty": "hard",
            "turn_timer_seconds": 60,
            "narrative_tone": "epic",
            "luck_bonus": 2,
            "dramatic_dice": False,
        }
        s = CampaignSettings.from_dict(raw)
        assert s.image_generation is False
        assert s.difficulty == Difficulty.HARD
        assert s.turn_timer_seconds == 60
        assert s.narrative_tone == NarrativeTone.EPIC
        assert s.luck_bonus == 2
        assert s.dramatic_dice is False

    def test_from_dict_partial(self):
        raw = {"image_generation": False}
        s = CampaignSettings.from_dict(raw)
        assert s.image_generation is False
        assert s.difficulty == Difficulty.NORMAL  # default

    def test_from_dict_legacy_free_image_mode(self):
        """Test migration from legacy free_image_mode field."""
        raw = {"free_image_mode": False}
        s = CampaignSettings.from_dict(raw)
        assert s.image_generation is False
        assert s.difficulty == Difficulty.NORMAL  # default

    def test_from_dict_unknown_field_ignored(self):
        raw = {"image_generation": True, "unknown_field": 999}
        s = CampaignSettings.from_dict(raw)
        assert s.image_generation is True
        # unknown_field is silently ignored

    def test_apply_update_imagen_on(self):
        s = CampaignSettings(image_generation=False)
        ok, msg = s.apply_update("imagen", "on")
        assert ok is True
        assert "activada" in msg
        assert s.image_generation is True

    def test_apply_update_imagen_off(self):
        s = CampaignSettings(image_generation=True)
        ok, msg = s.apply_update("imagen", "off")
        assert ok is True
        assert "desactivada" in msg
        assert s.image_generation is False

    def test_apply_update_free_on(self):
        s = CampaignSettings(image_generation=False)
        ok, msg = s.apply_update("free", "on")
        assert ok is True
        assert "activada" in msg
        assert s.image_generation is True

    def test_apply_update_free_off(self):
        s = CampaignSettings(image_generation=True)
        ok, msg = s.apply_update("free", "off")
        assert ok is True
        assert "desactivada" in msg
        assert s.image_generation is False

    def test_apply_update_imagen_invalid_value(self):
        s = CampaignSettings()
        ok, msg = s.apply_update("imagen", "maybe")
        assert ok is False
        assert "inválido" in msg.lower()

    def test_apply_update_difficulty_easy(self):
        s = CampaignSettings()
        ok, msg = s.apply_update("dificultad", "easy")
        assert ok is True
        assert "Fácil" in msg
        assert s.difficulty == Difficulty.EASY

    def test_apply_update_difficulty_invalid(self):
        s = CampaignSettings()
        ok, msg = s.apply_update("dificultad", "impossible")
        assert ok is False

    def test_apply_update_tone_funny(self):
        s = CampaignSettings()
        ok, msg = s.apply_update("tono", "funny")
        assert ok is True
        assert "Cómico" in msg
        assert s.narrative_tone == NarrativeTone.FUNNY

    def test_apply_update_tone_dark(self):
        s = CampaignSettings()
        ok, msg = s.apply_update("tone", "dark")
        assert ok is True
        assert s.narrative_tone == NarrativeTone.DARK

    def test_apply_update_timer_zero(self):
        s = CampaignSettings(turn_timer_seconds=120)
        ok, msg = s.apply_update("timer", "0")
        assert ok is True
        assert "desactivado" in msg
        assert s.turn_timer_seconds == 0

    def test_apply_update_timer_positive(self):
        s = CampaignSettings()
        ok, msg = s.apply_update("timer", "60")
        assert ok is True
        assert "60s" in msg
        assert s.turn_timer_seconds == 60

    def test_apply_update_timer_negative_error(self):
        s = CampaignSettings()
        ok, msg = s.apply_update("timer", "-10")
        assert ok is False
        assert "negativo" in msg.lower()

    def test_apply_update_suerte_positive(self):
        s = CampaignSettings(luck_bonus=0)
        ok, msg = s.apply_update("suerte", "+2")
        assert ok is True
        assert "+2" in msg
        assert s.luck_bonus == 2

    def test_apply_update_suerte_negative(self):
        s = CampaignSettings()
        ok, msg = s.apply_update("luck", "-1")
        assert ok is True
        assert "-1" in msg
        assert s.luck_bonus == -1

    def test_apply_update_dados_off(self):
        s = CampaignSettings(dramatic_dice=True)
        ok, msg = s.apply_update("dados", "off")
        assert ok is True
        assert s.dramatic_dice is False

    def test_apply_update_unknown_key(self):
        s = CampaignSettings()
        ok, msg = s.apply_update("velocidad", "rapida")
        assert ok is False
        assert "desconocida" in msg.lower()

    def test_summary(self):
        s = CampaignSettings()
        summary = s.summary()
        assert "Activada" in summary
        assert "Normal" in summary
        assert "Serio" in summary
        assert "120s" in summary
        assert "Sí" in summary

    def test_summary_image_off(self):
        s = CampaignSettings(image_generation=False)
        summary = s.summary()
        assert "Desactivada" in summary

    def test_difficulty_dc_modifier(self):
        from campaign_settings import Difficulty_get_dc
        easy = Difficulty.EASY
        normal = Difficulty.NORMAL
        hard = Difficulty.HARD
        assert Difficulty_get_dc(easy, 15) == 13
        assert Difficulty_get_dc(normal, 15) == 15
        assert Difficulty_get_dc(hard, 15) == 17
