"""Campaign settings — configurable options per campaign."""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class Language(str, Enum):
    ES = "es"
    PT = "pt"
    EN = "en"


    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"


class Difficulty(str, Enum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"


# Module-level DC modifier table (outside the enum to avoid __members__ collision)
_DC_MODIFIER: dict[str, int] = {
    "easy": -2,
    "normal": 0,
    "hard": +2,
}


def Difficulty_get_dc(difficulty: Difficulty, base_dc: int) -> int:
    """Apply difficulty modifier to a base DC."""
    return base_dc + _DC_MODIFIER[difficulty.value]


class NarrativeTone(str, Enum):
    SERIOUS = "serious"
    FUNNY = "funny"
    DARK = "dark"
    EPIC = "epic"


@dataclass
class CampaignSettings:
    """
    Configurable settings for a campaign.
    Persisted inside the campaign JSON under the key 'settings'.
    """

    # === Image generation (on/off switch) ===
    # True = generar imagen de cada escena nueva via Pollinations (gratis)
    # False = no generar imágenes automáticamente
    image_generation: bool = True

    # === Combat / Gameplay ===
    difficulty: Difficulty = Difficulty.NORMAL
    turn_timer_seconds: int = 120  # 0 = no timer

    # === Narrative ===
    narrative_tone: NarrativeTone = NarrativeTone.SERIOUS
    language: Language = Language.ES

    # === Advanced ===
    # Bonus to all skill checks (for easier/harder parties)
    luck_bonus: int = 0
    # If True, DM describes dice results narratively
    dramatic_dice: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignSettings":
        # Handle enum conversion from raw strings
        if "difficulty" in data and isinstance(data["difficulty"], str):
            data["difficulty"] = Difficulty(data["difficulty"])
        if "narrative_tone" in data and isinstance(data["narrative_tone"], str):
            data["narrative_tone"] = NarrativeTone(data["narrative_tone"])
        if "language" in data and isinstance(data["language"], str):
            data["language"] = Language(data["language"])
        # Handle legacy free_image_mode → image_generation migration
        if "free_image_mode" in data and "image_generation" not in data:
            data["image_generation"] = data["free_image_mode"]
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def apply_update(self, key: str, value: str) -> tuple[bool, str]:
        """
        Apply a setting update from a command string.
        Returns (success, message).
        """
        key = key.lower().strip()
        value = value.lower().strip()

        match key:
            case "imagen" | "image_gen" | "imágenes":
                if value in ("on", "true", "1", "yes", "enabled", "si"):
                    self.image_generation = True
                    return True, "🎨 Generación de imágenes: activada (Pollinations)"
                elif value in ("off", "false", "0", "no", "disabled"):
                    self.image_generation = False
                    return True, "🎨 Generación de imágenes: desactivada"
                return False, f"Valor inválido: {value}. Usa 'on' u 'off'"

            case "free":
                # Compatibilidad hacia atrás con comando anterior
                if value in ("on", "true", "1", "yes", "ascii"):
                    self.image_generation = True
                    return True, "🎨 Generación de imágenes: activada (Pollinations)"
                elif value in ("off", "false", "0", "no", "paid"):
                    self.image_generation = False
                    return True, "🎨 Generación de imágenes: desactivada"
                return False, f"Valor inválido: {value}. Usa 'on' u 'off'"

            case "dificultad" | "difficulty":
                try:
                    self.difficulty = Difficulty(value)
                    labels = {"easy": "Fácil", "normal": "Normal", "hard": "Difícil"}
                    return True, f"Dificultad: {labels[value]}"
                except ValueError:
                    return False, "Usa: easy, normal, hard"

            case "tono" | "tone" | "narrative_tone":
                try:
                    self.narrative_tone = NarrativeTone(value)
                    labels = {
                        "serious": "Serio",
                        "funny": "Cómico",
                        "dark": "Siniestro",
                        "epic": "Épico",
                    }
                    return True, f"Tono: {labels[value]}"
                except ValueError:
                    return False, "Usa: serious, funny, dark, epic"

            case "timer" | "turn_timer":
                try:
                    seconds = int(value)
                    if seconds < 0:
                        return False, "El timer no puede ser negativo"
                    self.turn_timer_seconds = seconds
                    if seconds == 0:
                        return True, "Timer desactivado"
                    return True, f"Timer: {seconds}s por turno"
                except ValueError:
                    return False, f"Valor inválido: {value}. Usa un número (0=off)"

            case "suerte" | "luck_bonus" | "luck":
                try:
                    bonus = int(value)
                    self.luck_bonus = bonus
                    if bonus >= 0:
                        return True, f"Suerte: +{bonus} a todos los checks"
                    return True, f"Suerte: {bonus} a todos los checks"
                except ValueError:
                    return False, f"Valor inválido: {value}. Usa un número (ej: +2, -1)"

            case "dados" | "dramatic_dice":
                if value in ("on", "true", "1", "yes"):
                    self.dramatic_dice = True
                    return True, "Dados dramáticos: activados"
                elif value in ("off", "false", "0", "no"):
                    self.dramatic_dice = False
                    return True, "Dados dramáticos: desactivados"
                return False, f"Valor inválido: {value}. Usa 'on' u 'off'"

            case "idioma" | "language":
                try:
                    self.language = Language(value)
                    labels = {"es": "Español", "pt": "Português", "en": "English"}
                    return True, f"Idioma: {labels[value]}"
                except ValueError:
                    return False, "Usa: es, pt, en"

            case _:
                return False, f"Opción desconocida: {key}"

    def summary(self) -> str:
        """Human-readable current settings."""
        img_status = (
            "✅ Activada (Pollinations)" if self.image_generation else "❌ Desactivada"
        )
        timer_str = f"{self.turn_timer_seconds}s" if self.turn_timer_seconds else "off"
        labels_tone = {
            "serious": "😑 Serio",
            "funny": "😄 Cómico",
            "dark": "🪶 Siniestro",
            "epic": "⚔️ Épico",
        }
        labels_diff = {"easy": "🟢 Fácil", "normal": "🟡 Normal", "hard": "🔴 Difícil"}
        labels_lang = {"es": "🇪🇸 Español", "pt": "🇧🇷 Português", "en": "🇬🇧 English"}
        return (
            "⚙️ *Configuración actual*\n\n"
            f"  🎨 Imágenes: {img_status}\n"
            f"  ⚔️ Dificultad: {labels_diff[self.difficulty.value]}\n"
            f"  🗣️ Tono: {labels_tone[self.narrative_tone.value]}\n"
            f"  🌐 Idioma: {labels_lang[self.language.value]}\n"
            f"  ⏱️ Timer: {timer_str}\n"
            f"  🎲 Dados dramáticos: {'Sí' if self.dramatic_dice else 'No'}\n"
            f"  🍀 Suerte: {'+' if self.luck_bonus >= 0 else ''}{self.luck_bonus}"
        )
