"""
action_router.py — Orchestrates /j action → narrative → broadcast for Mode B async.

Recibe "/j <acción>" del jugador y orquesta:
  1. Parse del intent
  2. Resolución (dados, daño) con stats REALES del personaje
  3. Clasificación de escena (EXPLORATION, COMBAT, etc.)
  4. Generación de narración via NarrativeGenerator (template o LLM)
  5. Broadcast del resultado al grupo

Flow:
  "/j Ataco al dragón"
    → route() → ActionResult(narrative, mechanic_inline, image_url)
    → telegram_handler envia resultado al grupo
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram import Update

# ------------------------------------------------------------------#
# Engine imports (para _resolve)
# ------------------------------------------------------------------#

# Añadir el path del proyecto para poder importar los módulos del motor
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from bot.dice_engine import roll as _roll_dice

# ------------------------------------------------------------------#
# Data classes
# ------------------------------------------------------------------#


class SceneType(str, Enum):
    """Tipos de escena para generación de narración."""
    EXPLORATION = "EXPLORATION"
    COMBAT = "COMBAT"
    DIALOGUE = "DIALOGUE"
    STORY_BEAT = "STORY_BEAT"
    REST = "REST"


@dataclass
class ActionIntent:
    """Parsed intent de la acción del jugador."""
    action_type: str  # "attack", "skill", "dialogue", "cast", "rest", "explore"
    target: str | None
    params: dict = field(default_factory=dict)


@dataclass
class ActionResolution:
    """Resultado de resolver la acción (dados, daño, etc.)."""
    success: bool
    hit: bool | None = None
    damage: int | None = None
    nat_20: bool = False
    nat_1: bool = False
    kill: bool = False
    roll: int | None = None
    dc: int | None = None
    mechanic_inline: str = ""
    attack_roll: int = 0  # total including mods


@dataclass
class ActionResult:
    """Resultado final del router: narración + mecánica + imagen."""
    narrative: str
    mechanic_inline: str
    action_type: str = ""
    nat_20: bool = False
    nat_1: bool = False
    image_path: str | None = None  # Local path to generated image (if any)


# ------------------------------------------------------------------#
# NarrativeGenerator wrapper (para _narrate)
# ------------------------------------------------------------------#

def _generate_narrative(scene_type: SceneType, context: dict, milestone_context: dict | None = None) -> str:
    """
    Genera narración via NarrativeGenerator (template o LLM).
    Si no hay LLM client, usa template mode automáticamente.
    """
    try:
        from dm.narrative_generator import Language, NarrativeGenerator

        # Build minimal state dict
        state = {
            "campaign": context.get("campaign", {}),
            "characters": context.get("characters", {}),
            "npcs": context.get("npcs", {}),
        }

        ng = NarrativeGenerator()
        result = ng.generate_scene(
            state=state,
            scene_type=scene_type,
            context=context,
            language=Language.ES,
            milestone_context=milestone_context,
        )
        return result.get("narrative", "La escena continúa...")
    except Exception:
        # Fallback: usar templates inline simples
        return _fallback_narrative(scene_type, context)


def _fallback_narrative(scene_type: SceneType, ctx: dict) -> str:
    """Fallback simple si NarrativeGenerator falla."""
    attacker = ctx.get("attacker", "El personaje")
    defender = ctx.get("defender", "el objetivo")
    location = ctx.get("location", "el dungeon")
    situation = ctx.get("situation", "La historia continúa.")

    if scene_type == SceneType.COMBAT:
        return f"El acero corta el aire cuando {attacker} ataca a {defender}. {situation}"
    elif scene_type == SceneType.DIALOGUE:
        return f"{attacker} se dirige a {defender}. {situation}"
    elif scene_type == SceneType.STORY_BEAT:
        return f"Un momento clave: {attacker} toma una decisión crucial. {situation}"
    elif scene_type == SceneType.REST:
        return f"{attacker} descansa en {location}. La calma es breve."
    else:
        return f"{attacker} actúa en {location}. {situation}"


# ------------------------------------------------------------------#
# ActionRouter
# ------------------------------------------------------------------#


class ActionRouter:
    """
    Router principal para acciones del Modo B.

    Uso:
        router = ActionRouter(state=game_state, character=char)
        result = router.route(update, "ataco al dragon con mi espada")
        # result.narrative → narración del DM
        # result.mechanic_inline → "⚔️ 18 damage"
        # result.image_url → None (por ahora)
    """

    def __init__(self, state=None, character=None):
        """
        Args:
            state: GameState opcional para contexto de mundo.
            character: Character object con stats reales del jugador.
        """
        self.state = state or {}
        self.char = character

    def route(self, update: Update, action_text: str, scene_type_override: SceneType | None = None, milestone_context: dict | None = None) -> ActionResult:
        """
        Flujo principal: parse → resolve → classify → narrate.

        Args:
            update: Telegram Update (para extraer user info si se necesita)
            action_text: texto de la acción sin el prefijo "/j "
            scene_type_override: Optional SceneType from PacingEngine
            milestone_context: Optional dict from PacingEngine with milestone info

        Returns:
            ActionResult con narration, mechanic_inline, y image_url
        """
        intent = self._parse(action_text)

        resolution = self._resolve(intent)
        scene_type = scene_type_override or self._classify(intent, resolution)
        ctx = self._build_context(intent, resolution, scene_type, action_text)
        narrative = _generate_narrative(scene_type, ctx, milestone_context)

        return ActionResult(
            narrative=narrative,
            mechanic_inline=resolution.mechanic_inline,
            action_type=intent.action_type,
            nat_20=resolution.nat_20,
            nat_1=resolution.nat_1,
            image_path=None,  # Image generation handled in telegram_handler
        )

    def _parse(self, action_text: str) -> ActionIntent:
        """
        Parsea el texto libre del jugador → ActionIntent.
        PRIORIDAD: attack > cast > shove > hide > disengage > dodge > help >
        dash > ready > intimidate > persuade > deceive > skill >
        investigate > medicine > knowledge > survival > sleight >
        athletics > acrobatics > animal > use_object > dialogue > rest
        """
        text = action_text.lower()

        # Keywords por tipo de acción (ORDEN DE PRIORIDAD)
        attack_kw = [
            "ataco", "atacar", "golpeo", "golpear", "pego", "pegar",
            "strike", "hit", "attack", "ataco al", "le pego",
        ]
        cast_kw = [
            "lanzo", "lanzar", "cast", "spell", "hechizo", "conjuro",
        ]
        shove_kw = [
            "empujar", "derribar", "shove", "tirar al suelo", "tirame al",
        ]
        hide_kw = [
            "esconderse", "ocultarme", "hide", "escondeme", "me escondo",
        ]
        disengage_kw = [
            "desenganchar", "desengage", "escabullirse", "evadir", "disengage",
        ]
        dodge_kw = [
            "esquivar", "dodge", "evadir", "defender", "esquivo",
        ]
        help_kw = [
            "ayudar", "help", "asistir", "apoyar", "ayudo",
        ]
        dash_kw = [
            "correr", "dash", "esprintar", "desbordar", "corro",
        ]
        ready_kw = [
            "preparar", "ready", "esperar", "si cuando", "cuando",
        ]
        intimidate_kw = [
            "intimidar", "amenazar", "asustar", "intimidate", "threaten",
        ]
        persuade_kw = [
            "persuadir", "convencer", "diplomacia", "persuade", "convenzo",
        ]
        deceive_kw = [
            "engañar", "mentir", "engaño", "deceive", "lie", "miento",
        ]
        investigate_kw = [
            "investigar", "buscar", "escrutar", "investigate", "search",
        ]
        medicine_kw = [
            "medicina", "sanar", "estabilizar", "primeros aux", "medicine",
        ]
        history_kw = [
            "historia", "recordar", "historia", "history",
        ]
        arcana_kw = [
            "arcano", "magia", "arcanos", "arcana",
        ]
        religion_kw = [
            "religión", "dios", "religión", "religion",
        ]
        survival_kw = [
            "supervivencia", "rastrear", "orientarme", "cazar",
            "survival", "track", "hunt",
        ]
        sleight_kw = [
            "juego de manos", "robar", "prestidigitación",
            "sleight", "pickpocket",
        ]
        athletics_kw = [
            "atletismo", "saltar", "escalar", "nadar",
            "athletics", "jump", "climb",
        ]
        acrobatics_kw = [
            "acrobacias", "equilibrio", "voltereta",
            "acrobatics", "flip",
        ]
        animal_kw = [
            "animales", "montar", "cabalgar", "calmar bestia",
            "animal", "mount", "calm",
        ]
        perception_kw = [
            "perc", "observ", "oigo", "vista", "sentido", "escuch",
            "perception", "spot", "notice", "look", "listen", "hear",
        ]
        use_object_kw = [
            "usar", "objeto", "poción", "pocion", "herramienta",
            "potion", "tool",
        ]
        dialogue_kw = [
            "digo", "hablo", "le digo", "pregunto", "tell", "say", "talk",
        ]
        rest_kw = [
            "descanso", "descansar", "rest", "dormir", "sleep",
        ]

        action_type = "explore"
        target = None
        params = {}

        if any(kw in text for kw in attack_kw):
            action_type = "attack"
            target = self._extract_target(text, attack_kw)
        elif any(kw in text for kw in cast_kw):
            action_type = "cast"
            target = self._extract_spell_target(text, cast_kw)
        elif any(kw in text for kw in shove_kw):
            action_type = "shove"
            target = self._extract_target(text, shove_kw)
        elif any(kw in text for kw in hide_kw):
            action_type = "hide"
        elif any(kw in text for kw in disengage_kw):
            action_type = "disengage"
        elif any(kw in text for kw in dodge_kw):
            action_type = "dodge"
        elif any(kw in text for kw in help_kw):
            action_type = "help"
            target = self._extract_help_target(text)
        elif any(kw in text for kw in dash_kw):
            action_type = "dash"
        elif any(kw in text for kw in ready_kw):
            action_type = "ready"
            trigger = self._extract_ready_trigger(text)
            params = {"action_text": action_text, "trigger": trigger}
            target = trigger
        elif any(kw in text for kw in intimidate_kw):
            action_type = "intimidate"
            target = self._extract_target(text, intimidate_kw)
        elif any(kw in text for kw in persuade_kw):
            action_type = "persuade"
            target = self._extract_target(text, persuade_kw)
        elif any(kw in text for kw in deceive_kw):
            action_type = "deceive"
            target = self._extract_target(text, deceive_kw)
        elif any(kw in text for kw in investigate_kw):
            action_type = "investigate"
        elif any(kw in text for kw in medicine_kw):
            action_type = "medicine"
        elif any(kw in text for kw in history_kw):
            action_type = "history"
        elif any(kw in text for kw in arcana_kw):
            action_type = "arcana"
        elif any(kw in text for kw in religion_kw):
            action_type = "religion"
        elif any(kw in text for kw in survival_kw):
            action_type = "survival"
        elif any(kw in text for kw in sleight_kw):
            action_type = "sleight"
        elif any(kw in text for kw in athletics_kw):
            action_type = "athletics"
        elif any(kw in text for kw in acrobatics_kw):
            action_type = "acrobatics"
        elif any(kw in text for kw in animal_kw):
            action_type = "animal"
        elif any(kw in text for kw in perception_kw):
            action_type = "perception"
        elif any(kw in text for kw in use_object_kw):
            action_type = "use_object"
            target = self._extract_object_target(text)
        elif any(kw in text for kw in dialogue_kw):
            action_type = "dialogue"
        elif any(kw in text for kw in rest_kw):
            action_type = "rest"

        return ActionIntent(action_type=action_type, target=target, params=params)

    def _extract_target(self, text: str, verbs: list) -> str | None:
        """Extrae el objetivo de una acción."""
        skip_kw = {
            "ataco", "atacar", "golpeo", "golpear", "pego", "pegar",
            "strike", "hit", "attack",
            "intimidar", "amenazar", "asustar", "intimidate",
            "persuadir", "convencer", "diplomacia",
            "engañar", "mentir", "engaño",
            "empujar", "derribar", "shove",
            "con", "del", "las", "los", "una", "unos", "uno", "al", "el", "la",
            "mi", "tu", "su", "a", "de", "en", "lo",
            "the", "a", "an", "with", "to", "my", "your", "his", "her", "its",
            "our", "their", "on", "in", "at", "by",
        }
        words = text.split()
        for i, word in enumerate(words):
            if word in verbs and i + 1 < len(words):
                target_words = [w for w in words[i + 1:] if w not in skip_kw]
                if target_words:
                    return target_words[0].capitalize()
        for word in words:
            if word not in verbs and word not in skip_kw:
                return word.capitalize()
        return "el objetivo"  # default en lugar de None

    def _extract_spell_target(self, text: str, verbs: list) -> str | None:
        skip_kw = {
            "lanzo", "lanzar", "cast", "spell", "hechizo", "conjuro",
            "con", "del", "las", "los", "una", "a", "el", "la", "mi", "tu", "su",
            "the", "a", "an", "with", "to", "my",
        }
        words = text.split()
        for i, word in enumerate(words):
            if word in verbs and i + 1 < len(words):
                target_words = [w for w in words[i + 1:] if w not in skip_kw]
                if target_words:
                    return target_words[0].capitalize()
        return None

    def _extract_help_target(self, text: str) -> str | None:
        skip_kw = {"ayudar", "help", "asistir", "apoyar", "a", "al", "el", "la", "my", "your"}
        words = text.split()
        for word in words:
            if word not in skip_kw:
                return word.capitalize()
        return None

    def _extract_ready_trigger(self, text: str) -> str:
        for trigger_word in ["cuando", "si", "when", "if", "preparar", "ready", "esperar"]:
            idx = text.find(trigger_word)
            if idx != -1 and idx + len(trigger_word) < len(text):
                rest = text[idx + len(trigger_word):].strip()
                rest = rest.lstrip(" ,.:;")
                return rest
        return text

    def _extract_object_target(self, text: str) -> str | None:
        skip_kw = {"usar", "objeto", "poción", "pocion", "herramienta", "potion", "tool", "mi", "tu", "el", "la"}
        words = text.split()
        for word in words:
            if word not in skip_kw:
                return word.capitalize()
        return None

    def _resolve(self, intent: ActionIntent) -> ActionResolution:
        """
        Resuelve la acción usando el dice engine real y stats del personaje.
        Dispatcher: llama al método _resolve_<action_type> específico.
        """
        method_name = f"_resolve_{intent.action_type}"
        resolver = getattr(self, method_name, self._resolve_generic)
        return resolver(intent)

    def _resolve_attack(self, intent: ActionIntent) -> ActionResolution:
        """Resuelve un ataque: d20 + mods vs AC del objetivo."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        nat_20 = roll == 20
        nat_1 = roll == 1

        # Stats reales del personaje, o defaults
        stat_mod = self._get_mod("str") if self.char else 0
        prof = self._get_prof() if self.char else 2
        attack_bonus = stat_mod + prof
        attack_roll_total = roll + attack_bonus

        # AC objetivo (promedio 14, o del estado si está disponible)
        target_ac = self._get_target_ac(intent.target)

        hit = attack_roll_total >= target_ac

        if nat_20:
            dmg_result = _roll_dice("2d8")
            damage = dmg_result["total"]
            mechanic = (
                f"💥 ¡CRÍTICO! Nat 20! "
                f"D20: {roll}{stat_mod:+d}{prof:+d}={attack_roll_total} vs AC {target_ac} — "
                f"Daño total: *{damage}*"
            )
            return ActionResolution(
                success=True, hit=True, damage=damage,
                nat_20=True, nat_1=False, kill=False,
                roll=roll, dc=target_ac, mechanic_inline=mechanic,
                attack_roll=attack_roll_total,
            )
        elif nat_1:
            mechanic = (
                f"💀 ¡FUMBLE! Nat 1. "
                f"D20: {roll}{stat_mod:+d}{prof:+d}={attack_roll_total} vs AC {target_ac} — "
                f"Ataque completamente fallado."
            )
            return ActionResolution(
                success=False, hit=False, damage=0,
                nat_20=False, nat_1=True, kill=False,
                roll=roll, dc=target_ac, mechanic_inline=mechanic,
                attack_roll=attack_roll_total,
            )
        elif hit:
            dmg_result = _roll_dice("1d8")
            damage = dmg_result["total"]
            target = intent.target or "el objetivo"
            mechanic = (
                f"⚔️ ¡Impacto! "
                f"D20: {roll}{stat_mod:+d}{prof:+d}={attack_roll_total} vs AC {target_ac} — "
                f"{damage} damage a {target}"
            )
            return ActionResolution(
                success=True, hit=True, damage=damage,
                nat_20=False, nat_1=False, kill=False,
                roll=roll, dc=target_ac, mechanic_inline=mechanic,
                attack_roll=attack_roll_total,
            )
        else:
            # Miss (not nat 1, not nat 20, not hit)
            target = intent.target or "el objetivo"
            mechanic = (
                f"❌ El ataque falla. "
                f"D20: {roll}{stat_mod:+d}{prof:+d}={attack_roll_total} vs AC {target_ac} — "
                f"({roll} no alcanza)"
            )
            return ActionResolution(
                success=False, hit=False, damage=0,
                nat_20=False, nat_1=False, kill=False,
                roll=roll, dc=target_ac, mechanic_inline=mechanic,
                attack_roll=attack_roll_total,
            )

    def _resolve_skill(self, intent: ActionIntent) -> ActionResolution:
        """Resuelve una skill check: d20 + ability mod + prof vs DC."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        dc = 14
        stat_mod = self._get_mod("dex") if self.char else 0
        prof = self._get_prof() if self.char else 2
        total = roll + stat_mod + prof
        success = total >= dc

        if success:
            mechanic = (
                f"🎲 Skill Check: {total} ({roll}{stat_mod:+d}{prof:+d}) vs DC {dc} — ✅ Éxito!"
            )
        else:
            mechanic = (
                f"🎲 Skill Check: {total} ({roll}{stat_mod:+d}{prof:+d}) vs DC {dc} — ❌ Fallo"
            )

        return ActionResolution(
            success=success,
            hit=None,
            damage=None,
            roll=roll,
            dc=dc,
            mechanic_inline=mechanic,
            attack_roll=total,
        )

    def _resolve_cast(self, intent: ActionIntent) -> ActionResolution:
        """Resuelve lanzamiento de hechizo: d20 vs DC 10 + save DC del caster."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        dc = 10
        success = roll >= dc
        spell_name = intent.target or "hechizo"
        stat_mod = self._get_mod("int") if self.char else 0
        prof = self._get_prof() if self.char else 2
        save_dc = 8 + prof + stat_mod if self.char else 12

        if success:
            mechanic = (
                f"✨ {spell_name} exitoso! "
                f"Spell Attack: {roll}{stat_mod:+d}{prof:+d} vs DC {save_dc}"
            )
        else:
            mechanic = (
                f"✨ {spell_name} falla! "
                f"Spell Attack: {roll}{stat_mod:+d}{prof:+d} vs DC {save_dc}"
            )

        return ActionResolution(
            success=success,
            hit=None,
            damage=None,
            roll=roll,
            dc=save_dc,
            mechanic_inline=mechanic,
            attack_roll=roll,
        )

    # ------------------------------------------------------------------#
    # Acciones D&D 5e estándar (nuevas)
    # ------------------------------------------------------------------#

    def _resolve_disengage(self, intent: ActionIntent) -> ActionResolution:
        """Disengage: sin tirada, marca flag en personaje."""
        char = self.char
        if char:
            char.has_disengaged = True
        mechanic = "🟡 Sin tirada — Desenganche exitoso. No provocas ataques de oportunidad este turno."
        return ActionResolution(
            success=True, hit=None, damage=None,
            roll=None, dc=None, mechanic_inline=mechanic,
            attack_roll=0,
        )

    def _resolve_dash(self, intent: ActionIntent) -> ActionResolution:
        """Dash: sin tirada, marca flag en personaje."""
        char = self.char
        if char:
            char.has_dashed = True
        mechanic = "🟡 Sin tirada — Sprint exitoso. Movimiento doblado este turno."
        return ActionResolution(
            success=True, hit=None, damage=None,
            roll=None, dc=None, mechanic_inline=mechanic,
            attack_roll=0,
        )

    def _resolve_dodge(self, intent: ActionIntent) -> ActionResolution:
        """Dodge: sin tirada, marca flag en personaje."""
        char = self.char
        if char:
            char.is_dodging = True
        mechanic = "🟡 Sin tirada — Centrado en defensa. Enemigos tienen desventaja atacándote."
        return ActionResolution(
            success=True, hit=None, damage=None,
            roll=None, dc=None, mechanic_inline=mechanic,
            attack_roll=0,
        )

    def _resolve_help(self, intent: ActionIntent) -> ActionResolution:
        """Help: sin tirada, marca flag en personaje."""
        char = self.char
        target = intent.target or "aliado"
        if char:
            char.is_helping = True
            char.helping_target = target
        mechanic = f"🟡 Sin tirada — Ayudas a {target}. Tiene ventaja en su próximo ataque."
        return ActionResolution(
            success=True, hit=None, damage=None,
            roll=None, dc=None, mechanic_inline=mechanic,
            attack_roll=0,
        )

    def _resolve_hide(self, intent: ActionIntent) -> ActionResolution:
        """Hide: Stealth check (DEX) vs DC 13."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        dex_mod = self._get_mod("dex")
        prof = self._get_prof()
        total = roll + dex_mod + prof
        dc = 13
        success = total >= dc
        char = self.char
        if char and success:
            char.is_hiding = True
        verb = "te ocultas" if success else "no puedes ocultarte"
        if success:
            mechanic = f"🎲 Sigilo: {total} ({roll}{dex_mod:+d}{prof:+d}) vs DC {dc} — ✅ {verb}!"
        else:
            mechanic = f"🎲 Sigilo: {total} ({roll}{dex_mod:+d}{prof:+d}) vs DC {dc} — ❌ {verb}."
        return ActionResolution(
            success=success, hit=None, damage=None,
            roll=roll, dc=dc, mechanic_inline=mechanic,
            attack_roll=total,
        )

    def _resolve_ready(self, intent: ActionIntent) -> ActionResolution:
        """Ready: guarda pending_ready en personaje."""
        trigger = intent.target or "el trigger definido"
        char = self.char
        if char:
            action_text = intent.params.get("action_text", "acción")
            char.pending_ready = {"action": action_text, "trigger": trigger}
        mechanic = f"🟡 Preparando acción: '{intent.params.get('action_text', 'acción')}' cuando: '{trigger}'"
        return ActionResolution(
            success=True, hit=None, damage=None,
            roll=None, dc=None, mechanic_inline=mechanic,
            attack_roll=0,
        )

    def _resolve_shove(self, intent: ActionIntent) -> ActionResolution:
        """Shove: Athletics (STR) vs DC 15 — puede knock prone o push 5ft."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        str_mod = self._get_mod("str")
        prof = self._get_prof()
        total = roll + str_mod + prof
        dc = 15
        success = total >= dc
        target = intent.target or "el objetivo"
        if success:
            mechanic = f"🎲 Atletismo (empujar): {total} ({roll}{str_mod:+d}{prof:+d}) vs DC {dc} — ✅ Derribas a {target}! Queda prone."
        else:
            mechanic = f"🎲 Atletismo (empujar): {total} ({roll}{str_mod:+d}{prof:+d}) vs DC {dc} — ❌ No puedes derribar a {target}."
        return ActionResolution(
            success=success, hit=None, damage=None,
            roll=roll, dc=dc, mechanic_inline=mechanic,
            attack_roll=total,
        )

    def _resolve_intimidate(self, intent: ActionIntent) -> ActionResolution:
        """Intimidate: CHA check vs DC 14."""
        return self._resolve_social("intimidate", intent, dc=14)

    def _resolve_persuade(self, intent: ActionIntent) -> ActionResolution:
        """Persuade: CHA check vs DC 12."""
        return self._resolve_social("persuade", intent, dc=12)

    def _resolve_deceive(self, intent: ActionIntent) -> ActionResolution:
        """Deceive: CHA check vs DC 12."""
        return self._resolve_social("deceive", intent, dc=12)

    def _resolve_investigate(self, intent: ActionIntent) -> ActionResolution:
        """Investigate: INT check vs DC 15."""
        return self._resolve_knowledge("investigate", intent, dc=15)

    def _resolve_medicine(self, intent: ActionIntent) -> ActionResolution:
        """Medicine: WIS check vs DC 15 — estabiliza o restaura 1d4 HP."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        wis_mod = self._get_mod("wis")
        prof = self._get_prof()
        total = roll + wis_mod + prof
        dc = 15
        success = total >= dc
        if success:
            heal = _roll_dice("1d4")["total"]
            mechanic = f"🎲 Medicina: {total} ({roll}{wis_mod:+d}{prof:+d}) vs DC {dc} — ✅ Éxito! Estabilizado y curado {heal} HP."
        else:
            mechanic = f"🎲 Medicina: {total} ({roll}{wis_mod:+d}{prof:+d}) vs DC {dc} — ❌ Fallo."
        return ActionResolution(
            success=success, hit=None, damage=None,
            roll=roll, dc=dc, mechanic_inline=mechanic,
            attack_roll=total,
        )

    def _resolve_history(self, intent: ActionIntent) -> ActionResolution:
        """History: INT check vs DC 12."""
        return self._resolve_knowledge("history", intent, dc=12)

    def _resolve_arcana(self, intent: ActionIntent) -> ActionResolution:
        """Arcana: INT check vs DC 12."""
        return self._resolve_knowledge("arcana", intent, dc=12)

    def _resolve_religion(self, intent: ActionIntent) -> ActionResolution:
        """Religion: INT check vs DC 12."""
        return self._resolve_knowledge("religion", intent, dc=12)

    def _resolve_survival(self, intent: ActionIntent) -> ActionResolution:
        """Survival: WIS check vs DC 13."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        wis_mod = self._get_mod("wis")
        prof = self._get_prof()
        total = roll + wis_mod + prof
        dc = 13
        success = total >= dc
        if success:
            mechanic = f"🎲 Supervivencia: {total} ({roll}{wis_mod:+d}{prof:+d}) vs DC {dc} — ✅ Éxito! Rastreado/orientado correctamente."
        else:
            mechanic = f"🎲 Supervivencia: {total} ({roll}{wis_mod:+d}{prof:+d}) vs DC {dc} — ❌ Fallo."
        return ActionResolution(
            success=success, hit=None, damage=None,
            roll=roll, dc=dc, mechanic_inline=mechanic,
            attack_roll=total,
        )

    def _resolve_sleight(self, intent: ActionIntent) -> ActionResolution:
        """Sleight of Hand: DEX check vs DC 14."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        dex_mod = self._get_mod("dex")
        prof = self._get_prof()
        total = roll + dex_mod + prof
        dc = 14
        success = total >= dc
        if success:
            mechanic = f"🎲 Juego de manos: {total} ({roll}{dex_mod:+d}{prof:+d}) vs DC {dc} — ✅ Éxito! Robaste/obrajaste sin que noten."
        else:
            mechanic = f"🎲 Juego de manos: {total} ({roll}{dex_mod:+d}{prof:+d}) vs DC {dc} — ❌ Fallo. Te descubrieron!"
        return ActionResolution(
            success=success, hit=None, damage=None,
            roll=roll, dc=dc, mechanic_inline=mechanic,
            attack_roll=total,
        )

    def _resolve_athletics(self, intent: ActionIntent) -> ActionResolution:
        """Athletics: STR check vs DC 12."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        str_mod = self._get_mod("str")
        prof = self._get_prof()
        total = roll + str_mod + prof
        dc = 12
        success = total >= dc
        if success:
            mechanic = f"🎲 Atletismo: {total} ({roll}{str_mod:+d}{prof:+d}) vs DC {dc} — ✅ Éxito! Saltas/escalas/nadas sin problema."
        else:
            mechanic = f"🎲 Atletismo: {total} ({roll}{str_mod:+d}{prof:+d}) vs DC {dc} — ❌ Fallo."
        return ActionResolution(
            success=success, hit=None, damage=None,
            roll=roll, dc=dc, mechanic_inline=mechanic,
            attack_roll=total,
        )

    def _resolve_acrobatics(self, intent: ActionIntent) -> ActionResolution:
        """Acrobatics: DEX check vs DC 12."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        dex_mod = self._get_mod("dex")
        prof = self._get_prof()
        total = roll + dex_mod + prof
        dc = 12
        success = total >= dc
        if success:
            mechanic = f"🎲 Acrobacias: {total} ({roll}{dex_mod:+d}{prof:+d}) vs DC {dc} — ✅ Éxito! Mantenés el equilibrio."
        else:
            mechanic = f"🎲 Acrobacias: {total} ({roll}{dex_mod:+d}{prof:+d}) vs DC {dc} — ❌ Fallo. Perdés el equilibrio."
        return ActionResolution(
            success=success, hit=None, damage=None,
            roll=roll, dc=dc, mechanic_inline=mechanic,
            attack_roll=total,
        )

    def _resolve_animal(self, intent: ActionIntent) -> ActionResolution:
        """Animal Handling: WIS check vs DC 13."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        wis_mod = self._get_mod("wis")
        prof = self._get_prof()
        total = roll + wis_mod + prof
        dc = 13
        success = total >= dc
        if success:
            mechanic = f"🎲 Trato con animales: {total} ({roll}{wis_mod:+d}{prof:+d}) vs DC {dc} — ✅ Éxito! Animal calmado/dirigido."
        else:
            mechanic = f"🎲 Trato con animales: {total} ({roll}{wis_mod:+d}{prof:+d}) vs DC {dc} — ❌ Fallo. Animal asustado/rebelde."
        return ActionResolution(
            success=success, hit=None, damage=None,
            roll=roll, dc=dc, mechanic_inline=mechanic,
            attack_roll=total,
        )

    def _resolve_use_object(self, intent: ActionIntent) -> ActionResolution:
        """Use Object: sin tirada, consume 1 uso."""
        char = self.char
        object_name = intent.target or "objeto"
        if char and char.object_uses:
            uses = char.object_uses.get(object_name.lower(), 0)
            if uses > 0:
                char.object_uses[object_name.lower()] -= 1
                mechanic = f"🟡 Usaste {object_name}. ({uses - 1} restantes)"
            else:
                mechanic = f"⚠️ No te quedan {object_name}."
        else:
            mechanic = f"🟡 Usaste {object_name}."
        return ActionResolution(
            success=True, hit=None, damage=None,
            roll=None, dc=None, mechanic_inline=mechanic,
            attack_roll=0,
        )

    def _resolve_generic(self, intent: ActionIntent) -> ActionResolution:
        """Generic fallback para actions no resueltas."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        dc = 12
        stat_mod = self._get_mod("str")
        prof = self._get_prof()
        total = roll + stat_mod + prof
        success = total >= dc
        mechanic = f"🎲 {intent.action_type}: {total} ({roll}{stat_mod:+d}{prof:+d}) vs DC {dc} — {'✅' if success else '❌'}"
        return ActionResolution(
            success=success, hit=None, damage=None,
            roll=roll, dc=dc, mechanic_inline=mechanic,
            attack_roll=total,
        )

    def _resolve_dialogue(self, intent: ActionIntent) -> ActionResolution:
        """
        Resuelve una acción de diálogo.
        No tira dados — la resolución es narrativa.
        Busca el NPC objetivo en el estado para generar contexto.
        """
        target = intent.target or "el PNJ"

        # Buscar NPC en el estado para contexto narrativo
        npc_data = None
        if self.state and "npcs" in self.state:
            npcs = self.state["npcs"]
            # Buscar por nombre (case-insensitive)
            target_lower = target.lower()
            for npc_id, npc in npcs.items():
                npc_name = npc.get("name", npc_id).lower()
                if target_lower in npc_name or npc_name in target_lower:
                    npc_data = npc
                    break

        if npc_data:
            npc_name = npc_data.get("name", target)
            npc_role = npc_data.get("role", "")
            disposition = npc_data.get("disposition", "NEUTRAL")

            # Determinar reacción base según disposición
            if disposition == "HOSTILE":
                reaction = f"{npc_name} te mira con hostilidad."
            elif disposition == "FRIENDLY":
                reaction = f"{npc_name} te saluda con una sonrisa."
            else:
                reaction = f"{npc_name} te observa con cautela."

            mechanic = f"🗣️ Diálogo con {npc_name} ({npc_role}). {reaction}"
        else:
            mechanic = f"🗣️ Intentas hablar con {target}. No hay nadie con ese nombre cerca."

        return ActionResolution(
            success=True,  # Diálogo no falla mecánicamente
            hit=None,
            damage=None,
            roll=None,
            dc=None,
            mechanic_inline=mechanic,
            attack_roll=0,
        )

    def _resolve_social(self, action_type: str, intent: ActionIntent, dc: int) -> ActionResolution:
        """Helper para acciones sociales (persuade/deceive/intimidate)."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        cha_mod = self._get_mod("cha")
        prof = self._get_prof()
        total = roll + cha_mod + prof
        success = total >= dc
        target = intent.target or "el PNJ"
        names = {"intimidate": "Intimidación", "persuade": "Persuasión", "deceive": "Engaño"}
        name = names.get(action_type, action_type)
        if success:
            mechanic = f"🎲 {name}: {total} ({roll}{cha_mod:+d}{prof:+d}) vs DC {dc} — ✅ {target} es afectado!"
        else:
            mechanic = f"🎲 {name}: {total} ({roll}{cha_mod:+d}{prof:+d}) vs DC {dc} — ❌ {target} no se deja convencer."
        return ActionResolution(
            success=success, hit=None, damage=None,
            roll=roll, dc=dc, mechanic_inline=mechanic,
            attack_roll=total,
        )

    def _resolve_knowledge(self, action_type: str, intent: ActionIntent, dc: int) -> ActionResolution:
        """Helper para acciones de conocimiento (history/arcana/religion/investigate)."""
        roll_result = _roll_dice("1d20")
        roll = roll_result["total"]
        int_mod = self._get_mod("int")
        prof = self._get_prof()
        total = roll + int_mod + prof
        success = total >= dc
        names = {
            "history": "Historia", "arcana": "Arcanos", "religion": "Religión",
            "investigate": "Investigación",
        }
        name = names.get(action_type, action_type)
        if success:
            mechanic = f"🎲 {name}: {total} ({roll}{int_mod:+d}{prof:+d}) vs DC {dc} — ✅ Recuerdas información relevante!"
        else:
            mechanic = f"🎲 {name}: {total} ({roll}{int_mod:+d}{prof:+d}) vs DC {dc} — ❌ No logras recordar nada útil."
        return ActionResolution(
            success=success, hit=None, damage=None,
            roll=roll, dc=dc, mechanic_inline=mechanic,
            attack_roll=total,
        )

    # ------------------------------------------------------------------#
    # Helpers para stats del personaje
    # ------------------------------------------------------------------#

    def _get_mod(self, stat: str) -> int:
        """Obtiene el modifier de una stat desde el personaje real."""
        if self.char is None:
            return 0
        return self.char.mod(stat)

    def _get_prof(self) -> int:
        """Obtiene el proficiency bonus del personaje real."""
        if self.char is None:
            return 2
        return getattr(self.char, "proficiency_bonus", 2)

    def _get_target_ac(self, target: str | None) -> int:
        """Obtiene el AC del objetivo desde el world state, o usa 14 por defecto."""
        # TODO: buscar AC real del NPC/objetivo en el state
        # Por ahora hardcodeamos 14 (enemigo promedio)
        return 14

    # ------------------------------------------------------------------#
    # Clasificación y contexto
    # ------------------------------------------------------------------#

    def _classify(self, intent: ActionIntent, resolution: ActionResolution) -> SceneType:
        """Mapea intent + resultado → SceneType."""
        # Acciones de combate
        combat_types = {"attack", "cast", "shove"}
        if intent.action_type in combat_types:
            return SceneType.COMBAT
        # Acciones sociales
        social_types = {"intimidate", "persuade", "deceive", "dialogue"}
        if intent.action_type in social_types:
            return SceneType.DIALOGUE
        if intent.action_type == "rest":
            return SceneType.REST
        # Acciones de skill/exploration
        if intent.action_type in {
            "hide", "disengage", "dash", "help", "dodge", "ready",
            "investigate", "medicine", "history", "arcana", "religion",
            "survival", "sleight", "athletics", "acrobatics", "animal",
            "use_object", "explore", "skill",
        }:
            if resolution.success:
                return SceneType.STORY_BEAT
            return SceneType.EXPLORATION
        return SceneType.EXPLORATION

    def _build_context(self, intent: ActionIntent, resolution: ActionResolution, scene_type: SceneType, action_text: str) -> dict:
        """Arma el dict de contexto para NarrativeGenerator."""
        char_name = self.char.name if self.char else "Tu personaje"
        target = intent.target or "el objetivo"

        # Datos del world state (si hay)
        location = "el dungeon"
        location_desc = ""
        npc_name = "Un guerrero"
        emotional_tone = "misterioso"
        campaign_name = "La aventura"
        main_threat = ""

        if self.state:
            camp = self.state.get("campaign", {}) or {}
            # current_location puede ser string (desde cmd_begin) o dict (viejo formato)
            raw_loc = camp.get("current_location")
            if isinstance(raw_loc, dict):
                location = raw_loc.get("name", "el dungeon")
            elif isinstance(raw_loc, str):
                location = raw_loc
            else:
                location = "el dungeon"
            location_desc = camp.get("current_location_desc", "")
            campaign_name = camp.get("name", "La aventura")
            main_threat = camp.get("main_threat", "")
            npcs = self.state.get("npcs", {}) or {}
            if npcs:
                first_npc_id = list(npcs.keys())[0]
                first_npc = npcs[first_npc_id]
                npc_name = first_npc.get("name", first_npc_id)

        ctx: dict = {
            # Meta
            "dc": resolution.dc or 12,
            "roll": resolution.roll or 0,
            "damage": resolution.damage or 0,
            # Base
            "campaign": {"name": campaign_name},
            "location": location,
            "attacker": char_name,
            "defender": target,
            # Combat
            "bystanders_react": "Los presentes contienen el aliento.",
            "situation": "El combate continúa.",
            # Exploration
            "environmental_detail": location_desc or "la oscuridad es interrumpida por antorchas distantes",
            "sensory_detail": location_desc or "un aroma metálico llena el aire",
            "character_present": npc_name,
            "npc_present": npc_name,
            "npc_or_character_present": npc_name,
            "reaction_description": "te observa con recelo",
            "action_description": action_text,
            "obstacle": "El camino adelante permanece abierto.",
            "emotional_tone": emotional_tone,
            # Dialogue
            "speaker": target,
            "character_mood": "te evalúa con cautela",
            "first_words": "¿Qué te trae por aquí?",
            "gesture": "cruza los brazos",
            "opening_line": "No tengo tiempo para preguntas.",
            "speaker_action": "te mira fijamente",
            "tension_point": "Una pausa incómoda se extiende entre ustedes.",
            # Story beat
            "incident_description": "un descubrimiento clave cambia la situación",
            "witness_or_participant": "Todos los presentes",
            "response_to_incident": "reaccionan con asombro",
            "consequence_looming": "Las consecuencias serán inevitables.",
            "revelation": "algo ha cambiado para siempre",
            "affected_party": "El grupo",
            # Rest
            "healing_atmosphere": "La calma del momento es reconfortante.",
            "resources_available": "Hay recursos disponibles para quien los necesite",
            "rest_comforts": "la oscuridad te envuelve protectivamente",
            "party_status": "El grupo está exhausto pero a salvo",
            "ambient_details": "La noche transcurre lentamente",
            "opportunity_available": "Entrenamiento o preparación es posible",
            # Action specifics
            "action": intent.action_type,
            "attack_description": f"{char_name} ataca a {target}",
            "hit": resolution.hit,
            "nat_20": resolution.nat_20,
            "nat_1": resolution.nat_1,
            "player_action": action_text,
            "player_action_type": intent.action_type,
        }

        # Sobrescribir con datos específicos del resultado de combate
        if intent.action_type == "attack":
            if resolution.nat_20:
                ctx["situation"] = (
                    f"{target} cae de rodillas, devastado por el golpe crítico. "
                    "La sangre salpica las piedras del suelo."
                )
                ctx["bystanders_react"] = "Un silencio sepulcral se apodera del lugar."
            elif resolution.nat_1:
                ctx["situation"] = (
                    "Tu arma rebota con un sonido sordo. "
                    "El enemigo sonríe con amargura y contraataca."
                )
                ctx["bystanders_react"] = "Un murmullo de sorpresa recorre a los presentes."
            elif resolution.hit:
                ctx["situation"] = (
                    f"{target} retrocede por el impacto del golpe, "
                    "las chispas vuelan cuando el acero golpea."
                )
                ctx["bystanders_react"] = "Los aliados observan con intensidad."
            else:
                ctx["situation"] = (
                    f"{target} esquiva limpiamente tu ataque, "
                    "moviéndose con una gracia fluida."
                )
                ctx["bystanders_react"] = "El enemigo prepara su contraataque."

        return ctx
