"""
telegram_handler.py — Telegram bot handler for HermesDM.

Implements all game commands (/start, /newgame, /join, /roll, /attack,
/cast, /skill, /status, /hp, /inventory, /talk, /map, /quests, /recap,
/resume, /endturn, /campaign, /help, /startcombat, /begincombat, /endcombat)
using python-telegram-bot v20+.

Per-chat state is stored in context.chat_data.
Entry point: ApplicationBuilder startup in __main__.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dm.image_event_handler import ImageEventHandler
    from state.npc_store import NPCStore

import asyncio
import logging
import os
import textwrap
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from pydantic_settings import BaseSettings
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    JobQueue,
    MessageHandler,
    filters,
)

from bot import spell_manager as spell_mgr
from bot.audit_logger import with_audit
from bot.character_sheet import (
    ALL_SKILLS,
    SKILL_BY_STAT,
    STATS,
    Character,
)
from bot.combat_engine import (
    apply_damage,
    resolve_attack,
    resolve_spell,
)
from bot.config_commands import cmd_configuracion

# Local modules
from bot.dice_engine import roll as _roll
from bot.game_commands import register_game_handlers
from bot.save_command import cmd_save as cmd_save_impl
from bot.turn_manager import (
    CombatState,
    combat_summary,
    end_combat,
    next_turn,
    start_combat,
)
from dm.image_prompt_builder import build_closure_image_prompt
from dm.narrative_generator import Language, NarrativeGenerator, SceneType
from state.state_manager import (
    append_history,
    campaign_exists,
    get_settings,
    list_campaigns,
    load_state,
    save_state,
)

log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------

# DEPRECATED — hardcoded group ID removed.
# Set ALLOWED_GROUP_ID in .env to restrict bot to a specific Telegram group.
# If unset, the bot works in any chat (DMs and groups).


class Settings(BaseSettings):
    """Bot configuration via environment variables."""

    TELEGRAM_BOT_TOKEN: str = "8222165892:***"
    ADMIN_USER_IDS: list[int] = []
    MAX_DICE_COUNT: int = 100
    MAX_DICE_SIDES: int = 100
    # Optional: restrict bot to a specific Telegram group.
    # Leave empty to allow DMs and any group (e.g. ALLOWED_GROUP_ID=-1003916745496).
    ALLOWED_GROUP_ID: int | None = None

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()

# ------------------------------------------------------------------
# Per-chat state
# ------------------------------------------------------------------


@dataclass
class ChatState:
    """
    Per-chat (per-group) state kept in context.chat_data.
    """

    active_campaign: str | None = None
    """Campaign ID currently active in this chat."""

    pending_attacks: dict[str, dict] = field(default_factory=dict)
    """
    Pending attacks awaiting /roll confirmation.
    key = label like 'attack_0', value = {
        'attacker_name': str,
        'defender_name': str,
        'weapon': str,
        'defender_ac': int,
        'rage_bonus': int,
        'advantage': bool,
        'disadvantage': bool,
    }
    """

    pending_spell: dict | None = None
    """
    Pending spell awaiting /roll confirmation.
    {
        'caster_name': str,
        'spell_name': str,
        'target_name': str,
        'caster_level': int,
        'spell_data': dict,
    }
    """

    pending_skill_check: dict | None = None
    """
    Pending skill check awaiting /roll confirmation.
    {
        'character': Character,
        'skill': str,
        'dc': int,
        'advantage': bool,
        'disadvantage': bool,
    }
    """

    pending_save: dict | None = None
    """
    Pending saving throw awaiting /roll confirmation.
    {
        'character': Character,
        'stat': str,
        'dc': int,
        'advantage': bool,
        'disadvantage': bool,
    }
    """

    characters: dict[str, Character] = field(default_factory=dict)
    """
    Characters registered in this chat (character_name_lower -> Character).
    """

    telegram_characters: dict[int, str] = field(default_factory=dict)
    """
    Reverse mapping: telegram_user_id -> character_name_lower.
    Populated on /join so /j can find the right character reliably.
    """

    combat_state: CombatState | None = None
    """Active combat state for this chat."""

    countdown_message_id: int | None = None
    """Message ID of the active countdown bar (for editing/deletion)."""

    countdown_remaining: int = 0
    """Seconds remaining on the current turn countdown."""

    setup_mode: bool = False
    """
    When True, non-command text messages from the DM are routed to the
    setup flow handler instead of normal processing.
    """

    pending_setup: dict | None = None
    """
    Setup state in progress. Structure:
    {
        'description': str,       # original DM description
        'premise': str,
        'hook': str,
        'tone': str,
        'setting_type': str,
        'lore': dict,
    }
    """

    setup_state: str = "idle"
    """
    Current step in the setup flow:
    'idle'           — no setup in progress
    'describing'     — waiting for DM to describe campaign
    'generating'     — AI is generating the setup
    'preview'        — showing preview to DM, awaiting edit/approve
    'editing'        — DM is editing a specific field
    """

    def character_for(self, player_name: str) -> Character | None:
        return self.characters.get(player_name.lower())

    def character_for_tg_id(self, tg_id: int) -> Character | None:
        """Find character by Telegram user ID (primary lookup for /j)."""
        char_key = self.telegram_characters.get(tg_id)
        if char_key:
            return self.characters.get(char_key)
        return None

    def active_character_names(self) -> list[str]:
        return list(self.characters.keys())


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _fmt_dice_result(r: dict) -> str:
    """Format a dice roll result as a readable string."""
    parts = [f"Rolling {r['str']}..."]
    parts.append(f"  Rolls: {r['rolls']}")
    if r["modifier"] != 0:
        parts.append(f"  Modifier: {r['modifier']:+d}")
    parts.append(f"  Total: {r['total']}")
    if r.get("is_crit"):
        parts.append("  >> NATURAL 20! CRITICAL! <<")
    elif r.get("is_fumble"):
        parts.append("  >> NATURAL 1! FUMBLE! <<")
    return "\n".join(parts)


RARITY_EMOJI = {
    "common": "⚪",
    "uncommon": "🟢",
    "rare": "🔵",
    "very rare": "🟣",
    "legendary": "🟡",
    "artifact": "🔴",
}


def _rarity_emoji(rarity) -> str:
    """Handle both str and MagicMock (for tests)."""
    try:
        return RARITY_EMOJI.get(str(rarity).lower(), "⚪")
    except (AttributeError, TypeError):
        return "⚪"


def _fmt_character(c: Character) -> str:
    """Format a character sheet as a readable string."""
    stat_lines = ", ".join(f"{s.upper()}: {c.stats[s]} ({c.mod_str(s)})" for s in STATS)
    hp_line = f"{c.hp.current}/{c.hp.max}" + (
        f" (+{c.hp.temp} temp)" if c.hp.temp > 0 else ""
    )
    items = ", ".join(f"{i.name} x{i.quantity}" for i in c.inventory) or "empty"
    conds = ", ".join(c.conditions) if c.conditions else "none"
    death = (
        f"Death saves: {c.death_saves.successes} ✓ / {c.death_saves.failures} ✗"
        if c.hp.current == 0
        else ""
    )

    return "\n".join(
        [
            f"=== {c.name} ===",
            f"Class: {c.player_class.capitalize()} | Level {c.level}",
            f"HP: {hp_line} | AC: {c.ac}",
            f"Stats: {stat_lines}",
            f"Proficiencies: {', '.join(c.proficiencies) or 'none'}",
            f"Conditions: {conds}",
            f"Inventory ({len(c.inventory)}/{c.inventory_slots}): {items}",
            f"Weapon: {c.equipped_weapon or 'none'} | Armor: {c.equipped_armor or 'none'}",
            death,
        ]
    )


# ── Auto-scene image generation ──────────────────────────────────────────────

_AUTO_IMAGE_HANDLER: ImageEventHandler | None = None  # Lazy init


def _get_image_handler() -> ImageEventHandler:
    """Get or create the global ImageEventHandler singleton."""
    global _AUTO_IMAGE_HANDLER
    if _AUTO_IMAGE_HANDLER is None:
        from dm.image_event_handler import ImageEventHandler
        from dm.image_provider import get_provider

        provider_name = os.environ.get("IMAGE_PROVIDER", "pollinations")
        provider = get_provider(provider_name)
        _AUTO_IMAGE_HANDLER = ImageEventHandler(provider=provider, enabled=True)
    return _AUTO_IMAGE_HANDLER


async def _maybe_send_scene_image(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    result: Any,  # ActionResult
    character_name: str,
) -> None:
    """
    Automatically decide if this narrative moment deserves an image,
    generate it, and send to Telegram.

    Called after every /j action completes.
    """
    import os as _os

    try:
        handler = _get_image_handler()

        # Determine scene_type from ActionResult
        scene_type = "other"
        if getattr(result, "nat_20", False):
            scene_type = "nat_20"
        elif getattr(result, "nat_1", False):
            scene_type = "nat_1"

        # Build context
        from dm.image_event_handler import ImageContext

        ctx = ImageContext(
            scene_type=scene_type,
            narrative=result.narrative or "",
            genre="fantasy",  # TODO: pull from campaign settings
            characters=[character_name] if character_name else [],
            mood="epic" if getattr(result, "nat_20", False) else "dramatic",
            is_critical=getattr(result, "nat_20", False),
            is_fumble=getattr(result, "nat_1", False),
        )

        # Check if this should trigger
        if not handler.should_generate(ctx):
            return

        # Generate image
        image_result = await handler.maybe_generate(ctx)
        if image_result is None or not _os.path.exists(image_result.path):
            return

        # Send to Telegram
        with open(image_result.path, "rb") as f:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=f,
                caption=f"🎨 *{image_result.provider_used}* — _Generada automaticamente_",
                parse_mode=ParseMode.MARKDOWN,
            )

    except Exception as e:
        # Never crash narrative flow due to image failures
        log.warning(f"[_maybe_send_scene_image] failed: {e}")


def _fmt_combat_summary(cs: CombatState) -> str:
    """Format active combat state."""
    if cs is None or not cs.active:
        return "No active combat."
    return combat_summary(cs)


# ------------------------------------------------------------------
# Command handlers
# ------------------------------------------------------------------


@with_audit("cmd_start")
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start."""
    try:
        welcome = textwrap.dedent("""
            🎲 *HermesDM — AI Dungeon Master*

            Welcome, adventurer! I am your AI-powered dungeon master,
            ready to run epic tabletop RPG campaigns right here in Telegram.

            *Quick Start:*
            1. /setup — Create a new campaign (describe it in Spanish!)
            2. /join — Add your character to the campaign
            3. /campaign — View campaign details
            4. /help — Full command list

            May fortune favor the bold!
        """).strip()
        await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.exception("cmd_start error")
        try:
            await update.message.reply_text(f"Error: {e}")
        except Exception:
            pass  # Already failing, give up silently


@with_audit("cmd_help")
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help."""
    try:
        help_text = textwrap.dedent("""
            🎲 *HermesDM — Comandos*

            *🎭 Campaña*
            /setup <descripcion> — Crear nueva campaña (ej: `/setup dark fantasy en un puerto corrupto`)
            /begin — Iniciar la aventura (después de /setup + /join)
            /campaign — Ver detalles de la campaña activa
            /recap — Resumen de la historia hasta ahora
            /resume — Retomar última sesión
            /save — Guardar estado manualmente
            /end — Finalizar campaña (epílogo + cierre)
            /quit /exit — Salir de la campaña

            *👤 Personaje*
            /join <nombre> <clase> [nivel] — Unir personaje (ej: `/join Valdric fighter 3`)
            /status — Ficha resumida de tu personaje
            /hp — HP detallado (current/max/temp/death saves)
            /inventory — Inventario y equipo
            /skill <nombre> <dc> — Tirada de habilidad (ej: `/skill perception 15`)
            /save <stat> <dc> — Tirada de salvación (ej: `/save dex 12`)

            *⚔️ Combate*
            /attack <objetivo> [adv|dis] — Iniciar ataque (luego /roll para resolver)
            /cast <hechizo> <objetivo> — Lanzar hechizo (luego /roll para resolver)
            /j <accion> / /act <accion> — Acción libre del jugador (ej: `/j ataco al dragon`)
            /endturn — Finalizar turno
            /startcombat /begincombat — Iniciar combate con iniciativa
            /endcombat — Finalizar combate
            /countdown <seg> <pj> — Timer de turno con barra

            *🗺️ Mundo*
            /map — Ubicación actual
            /quests — Misiones activas y completadas
            /talk <npc> <mensaje> — Hablar con un PNJ
            /npcs — Listar PNJs conocidos
            /npcsearch <nombre> — Buscar PNJ por nombre
            /npcnote <npc> <nota> — Agregar nota sobre un PNJ
            /npcmemory <npc> — Ver memoria/historial de un PNJ

            *🎨 Otros*
            /me <accion> — Acción narrativa sin dados (ej: `/me se esconde detrás de la roca`)
            /imagen /image <prompt> — Generar imagen de escena
            /roll <dados> — Tirar dados (ej: `/roll 2d6+3`)
            /audit — Ver log de auditoría de la campaña
            /configuracion — Configuración de la campaña
            /help — Mostrar este mensaje
        """).strip()
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.exception("cmd_help error")
        try:
            await update.message.reply_text(f"Error: {e}")
        except Exception:
            pass  # Already failing, give up silently


@with_audit("cmd_newgame")
async def cmd_newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /newgame [setting] — deprecated, use /setup instead."""
    try:
        await update.message.reply_text(
            "⚠️ Este comando está deprecated.\n"
            "Usá `/setup` para crear una nueva campaña con descripción libre y generación AI.\n"
            "Ejemplo: `/setup quiero una campaña dark fantasy en un puerto corrupto`"
        )
    except Exception as e:
        log.exception("cmd_newgame error")
        await update.message.reply_text(f"Error: {e}")


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /setup <descripción> — inicia el flujo de setup de campaña.

    Siempre requiere argumentos (funciona en grupos con Privacy Mode).
    Ejemplo: /setup quiero una campaña dark fantasy en un puerto corrupto
    """
    try:
        from dm.world_builder import generate_setup_with_ai

        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())
        dm_user_id = update.effective_user.id

        # Si hay campaign activa (no en setup) → bloquear
        if cs.active_campaign:
            from state.state_manager import load_state

            state = load_state(cs.active_campaign)
            if state and state.get("campaign", {}).get("status") == "active":
                await update.message.reply_text(
                    "⚠️ Ya hay una campaña activa. Cerrala con /end antes de crear una nueva."
                )
                return

        description = " ".join(context.args).strip() if context.args else ""

        # Extract pacing level from description
        pacing_level = "medium"
        if "--short" in description or "--pacing short" in description:
            pacing_level = "short"
            description = description.replace("--short", "").replace("--pacing short", "").strip()
        elif "--long" in description or "--pacing long" in description:
            pacing_level = "long"
            description = description.replace("--long", "").replace("--pacing long", "").strip()
        elif "--medium" in description or "--pacing medium" in description:
            pacing_level = "medium"
            description = description.replace("--medium", "").replace("--pacing medium", "").strip()

        if not description:
            await update.message.reply_text(
                "⚠️ *Setup de Campaña*\n\n"
                "Usá: `/setup <descripción>`\n\n"
                "Ejemplos:\n"
                "- `/setup dark fantasy en un puerto corrupto`\n"
                "- `/setup oneshot de terror en una mansión abandonada`\n\n"
                "Opciones de duración:\n"
                "- `--short` → ~5 sesiones (one-shot)\n"
                "- `--medium` → ~10 sesiones (default)\n"
                "- `--long` → ~20 sesiones (campaña épica)\n\n"
                "Incluí: tono, setting, tipo de aventura.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Args provistos → generar directamente
        cs.setup_mode = True
        cs.setup_state = "generating"
        cs.pending_setup = {
            "description": description,
            "tone": "serious",
            "setting_type": "fantasy",
            "pacing_level": pacing_level,
        }
        chat_data["_hermes_state"] = cs

        # Mensaje de generando
        gen_msg = await update.message.reply_text("🎲 Generando con AI...")

        try:
            setup_data = generate_setup_with_ai(description, pacing_level=pacing_level)
            setup_data["pacing_level"] = pacing_level
            cs.pending_setup = setup_data
            cs.setup_state = "preview"
            chat_data["_hermes_state"] = cs

            # Guardar campaign en estado setup
            campaign_id = cs.active_campaign or f"campaign_{uuid.uuid4().hex[:8]}"
            if not cs.active_campaign:
                from state.state_manager import new_state, save_state

                new_st = new_state(campaign_id, "Nueva Campaña", "fantasy")
                save_state(campaign_id, new_st)
                cs.active_campaign = campaign_id
                chat_data["_hermes_state"] = cs

            # Guardar setup en state
            from state.state_manager import load_state, save_state

            st = load_state(campaign_id)
            st["setup"] = setup_data
            save_state(campaign_id, st)

            # Editar mensaje de generando → preview
            preview_text = _format_setup_preview(setup_data)
            await gen_msg.edit_text(preview_text, parse_mode=ParseMode.MARKDOWN)

            # Enviar preview al DM por DM también
            await context.bot.send_message(
                chat_id=dm_user_id,
                text=preview_text + "\n\n_Editá o aprobá desde el grupo_",
                parse_mode=ParseMode.MARKDOWN,
            )

            # Pedir aprobación
            await update.message.reply_text(
                "📋 *Preview generado.*\n\n"
                "Editá campos con:\n"
                "`edit premisa: ...`\n"
                "`edit hook: ...`\n"
                "`edit tono: dark`\n\n"
                "Cuando estés listo: `/perfecto` / `/arrancamos`\n"
                "Para cancelar: `/cancel`",
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception as ai_err:
            log.exception("AI generation failed")
            cs.setup_state = "idle"
            cs.setup_mode = False
            chat_data["_hermes_state"] = cs
            await gen_msg.edit_text(
                f"⚠️ No pude conectar con AI. Usando template.\n`{ai_err}`",
                parse_mode=ParseMode.MARKDOWN,
            )

    except Exception as e:
        log.exception("cmd_setup error")
        await update.message.reply_text(f"Error: {e}")


async def _handle_setup_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Maneja texto libre enviado por el DM durante el flujo de setup.
    Solo se activa cuando chat_data["_hermes_state"].setup_mode == True
    y el texto no es un comando.
    """
    try:
        from dm.world_builder import generate_setup_with_ai

        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())
        dm_user_id = update.effective_user.id

        text = update.message.text.strip()
        lower = text.lower()

        # --- COMMANDS during setup ---
        if lower.startswith("edit "):
            # Parse: "edit <campo>: <valor>"
            # Available fields: premise, hook, tone, setting, description
            rest = text[5:].strip()
            if ": " in rest:
                field, value = rest.split(": ", 1)
                field = field.strip().lower()
                value = value.strip()
            else:
                # "edit tono dark" or "edit hook: ..."
                parts = rest.split(" ", 1)
                field = parts[0].strip().lower()
                value = parts[1].strip() if len(parts) > 1 else ""

            valid_fields = {"premise", "hook", "tone", "setting", "descripcion", "description", "clases", "classes"}
            if field not in valid_fields:
                await update.message.reply_text(
                    f"Campo no reconocido: `{field}`. "
                    "Campos editables: premise, hook, tono, setting",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            # Apply edit
            if cs.pending_setup:
                if field in ("descripcion", "description"):
                    cs.pending_setup["description"] = value
                elif field == "premise":
                    cs.pending_setup["premise"] = value
                elif field == "hook":
                    cs.pending_setup["hook"] = value
                elif field == "tone":
                    cs.pending_setup["tone"] = value
                elif field == "setting":
                    cs.pending_setup["setting_type"] = value

                # Save to state
                if cs.active_campaign:
                    from state.state_manager import load_state, save_state

                    st = load_state(cs.active_campaign)
                    st["setup"] = cs.pending_setup
                    save_state(cs.active_campaign, st)

                await update.message.reply_text(
                    f"✅ `{field}` actualizado a: {value}",
                    parse_mode=ParseMode.MARKDOWN,
                )
            return

        # Approve commands
        if lower in ("perfecto", "arrancamos", "approve", "si", "sí", "dale", "ok"):
            await _approve_setup(update, context, cs)
            return

        # Cancel
        if lower in ("cancel", "cancelar", "abort"):
            cs.setup_mode = False
            cs.setup_state = "idle"
            cs.pending_setup = None
            chat_data["_hermes_state"] = cs
            await update.message.reply_text("❌ Setup cancelado.")
            return

        # --- Free text: use as new description and regenerate ---
        if (cs.setup_state == "describing" and (description := text)):
            cs.setup_state = "generating"
            chat_data["_hermes_state"] = cs

            gen_msg = await update.message.reply_text("🎲 Generando con AI...")

            try:
                setup_data = generate_setup_with_ai(description)
                cs.pending_setup = setup_data
                cs.setup_state = "preview"
                chat_data["_hermes_state"] = cs

                # Create or update campaign
                campaign_id = cs.active_campaign or f"campaign_{uuid.uuid4().hex[:8]}"
                if not cs.active_campaign:
                    from state.state_manager import new_state, save_state

                    new_st = new_state(campaign_id, "Nueva Campaña", "fantasy")
                    save_state(campaign_id, new_st)
                    cs.active_campaign = campaign_id
                    chat_data["_hermes_state"] = cs

                # Save setup to state
                from state.state_manager import load_state, save_state

                st = load_state(campaign_id)
                st["setup"] = setup_data
                save_state(campaign_id, st)

                preview_text = _format_setup_preview(setup_data)
                await gen_msg.edit_text(preview_text, parse_mode=ParseMode.MARKDOWN)

                await context.bot.send_message(
                    chat_id=dm_user_id,
                    text=preview_text + "\n\n_Editá o aprobá desde el grupo_",
                    parse_mode=ParseMode.MARKDOWN,
                )

                await update.message.reply_text(
                    "📋 *Preview generado.*\n\n"
                    "Editá: `edit premisa: ...`, `edit tono: dark`\n"
                    "Aprobá: `perfecto` / `arrancamos`\n"
                    "Cancelá: `cancel`",
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception as ai_err:
                log.exception("AI generation failed during describing")
                cs.setup_state = "idle"
                cs.setup_mode = False
                chat_data["_hermes_state"] = cs
                await gen_msg.edit_text(
                    f"⚠️ No pude conectar con AI: {ai_err}",
                    parse_mode=ParseMode.MARKDOWN,
                )
            return

    except Exception as e:
        log.exception("_handle_setup_text error")
        try:
            await update.message.reply_text(f"Error: {e}")
        except Exception:
            pass


async def _cmd_approve_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """CommandHandler wrapper for /perfecto and /arrancamos."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())
        if not cs.setup_mode:
            await update.message.reply_text("No hay un setup activo. Usá /setup para empezar.")
            return
        await _approve_setup(update, context, cs)
    except Exception as e:
        log.exception("_cmd_approve_setup error")
        await update.message.reply_text(f"Error: {e}")


async def _cmd_cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """CommandHandler wrapper for /cancel_setup."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())
        if not cs.setup_mode:
            await update.message.reply_text("No hay un setup activo para cancelar.")
            return
        cs.setup_mode = False
        cs.setup_state = "idle"
        cs.pending_setup = None
        chat_data["_hermes_state"] = cs
        await update.message.reply_text("❌ Setup cancelado.")
    except Exception as e:
        log.exception("_cmd_cancel_setup error")
        await update.message.reply_text(f"Error: {e}")


async def _approve_setup(update: Update, context: ContextTypes.DEFAULT_TYPE, cs: ChatState) -> None:
    """Approve the current setup and publish to group."""
    try:
        from state.state_manager import load_state, save_state

        if not cs.pending_setup or not cs.active_campaign:
            await update.message.reply_text("❌ No hay setup pendiente para aprobar.")
            return

        campaign_id = cs.active_campaign
        setup_data = cs.pending_setup
        setup_data["approved"] = True

        # Update state
        st = load_state(campaign_id)
        st["setup"] = setup_data
        st["campaign"]["status"] = "active"
        st["campaign"]["name"] = setup_data.get("setting_type", "Campaña").capitalize()

        # Sync themed NPCs from setup into campaign state["npcs"]
        setup_npcs = setup_data.get("lore", {}).get("npcs", [])
        if setup_npcs:
            campaign_npcs = st.get("npcs", {})
            for npc_data in setup_npcs:
                npc_id = npc_data.get("name", "npc").lower().replace(" ", "_")
                campaign_npcs[npc_id] = {
                    "name": npc_data.get("name", npc_id),
                    "role": npc_data.get("role", "NPC"),
                    "status": "ALIVE",
                    "location": setup_data.get("lore", {}).get("starting_location", "Unknown"),
                    "disposition": "NEUTRAL",
                    "mood": "neutral",
                    "description": npc_data.get("dialogue", ""),
                    "disposition_value": 0,
                    "relationship_to_party": "stranger",
                    "memory": [],
                    "goals": "",
                    "speaks_to_players": True,
                }
            st["npcs"] = campaign_npcs

        save_state(campaign_id, st)

        # Exit setup mode
        cs.setup_mode = False
        cs.setup_state = "idle"
        cs.pending_setup = None
        chat_data = context.chat_data
        chat_data["_hermes_state"] = cs

        # Publish to group
        await _publish_setup_to_group(context, update.effective_chat.id, setup_data)

        await update.message.reply_text(
            "✅ *Campaña publicada!* "
            "Los jugadores usan /join para registrarse.\n"
            "Cuando todos estén listos, el DM usa /start para iniciar la aventura.",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        log.exception("_approve_setup error")
        await update.message.reply_text(f"Error al aprobar setup: {e}")


def _format_setup_preview(setup_data: dict) -> str:
    """Formatea el preview del setup para mostrar al DM."""
    lore = setup_data.get("lore", {})
    factions = lore.get("factions", {})
    npcs = lore.get("npcs", [])

    factions_str = ""
    if factions:
        factions_str = " | ".join(f"{k} ({v})" for k, v in factions.items())

    npcs_str = ""
    if npcs:
        npcs_str = "\n".join(
            f"• *{n.get('name','?')}* — {n.get('role','?')}: \"{n.get('dialogue','')}\""
            for n in npcs
        )

    classes = setup_data.get("classes")
    classes_str = ""
    if classes:
        classes_str = " | ".join(f"_{c}_" for c in classes)

    equipment = setup_data.get("starting_equipment", [])
    equipment_str = ""
    if equipment:
        equipment_str = "\n".join(
            f"• {eq.get('name','?')} — _{eq.get('description','')[:50]}_"
            for eq in equipment
        )

    # Story arc preview
    story_arc = setup_data.get("story_arc", {})
    arc_str = ""
    if story_arc:
        pacing = story_arc.get("pacing_level", "medium")
        milestones = story_arc.get("milestones", [])
        arc_str = f"\n📜 *Arco narrativo* ({pacing}, {len(milestones)} hitos):\n"
        for i, m in enumerate(milestones, 1):
            arc_str += f"   {i}. {m.get('id', '?')}: {m.get('description', '')[:50]}...\n"

    return (
        f"🎭 *PREVIEW DE CAMPAÑA*\n"
        f"{'━'*20}\n\n"
        f"📝 *Descripción:*\n{setup_data.get('description','')}\n\n"
        f"{'🎭 *Clases:* ' + classes_str if classes_str else ''}\n"
        f"📖 *Premise:*\n{setup_data.get('premise','')}\n\n"
        f"🎯 *Hook:*\n{setup_data.get('hook','')}\n\n"
        f"🌍 *Ubicación:* {lore.get('starting_location','?')}\n"
        f"   _{lore.get('starting_location_desc','')}_\n\n"
        f"⚔️ *Tono:* {setup_data.get('tone','serious')} | "
        f"*Setting:* {setup_data.get('setting_type','fantasy')}\n"
        f"🚨 *Amenaza:* {lore.get('main_threat','?')}\n"
        f"{'⚡ *Facciones:* ' + factions_str if factions_str else ''}\n"
        f"{'👥 *NPCs:*'}{chr(10) + npcs_str if npcs_str else ''}{chr(10)}"
        f"{'🎒 *Equipo inicial:*'}{chr(10) + equipment_str if equipment_str else ''}"
        f"{arc_str}"
    )


async def _publish_setup_to_group(context: ContextTypes.DEFAULT_TYPE, group_chat_id: int, setup_data: dict) -> None:
    """Publica el setup aprobado en el grupo para los jugadores."""
    lore = setup_data.get("lore", {})
    factions = lore.get("factions", {})
    npcs = lore.get("npcs", [])

    factions_str = ""
    if factions:
        factions_str = " | ".join(f"{k} ({v})" for k, v in factions.items())

    npcs_str = ""
    if npcs:
        npcs_str = "\n".join(
            f"• *{n.get('name','?')}* — {n.get('role','?')}"
            for n in npcs
        )

    classes = setup_data.get("classes")
    classes_str = " | ".join(f"_{c}_" for c in classes) if classes else ""

    equipment = setup_data.get("starting_equipment", [])
    equipment_str = ""
    if equipment:
        equipment_str = "\n".join(
            f"• {eq.get('name','?')} — _{eq.get('description','')[:40]}_"
            for eq in equipment
        )

    msg = (
        f"🎭 *Nueva Campaña: {setup_data.get('setting_type','Campaña').capitalize()}*\n"
        f"{'━'*20}\n\n"
        f"📖 *Premisa*\n{setup_data.get('premise','')}\n\n"
        f"🎯 *Hook Inicial*\n{setup_data.get('hook','')}\n\n"
        f"📍 *Ubicación*\n{lore.get('starting_location','?')} — {lore.get('starting_location_desc','')}\n\n"
        f"{'⚡ *Facciones:* ' + factions_str + chr(10) if factions_str else ''}"
        f"{'👥 *NPCs:*'}{chr(10) + npcs_str if npcs_str else ''}{chr(10)}"
        f"{'🎒 *Equipo inicial:*'}{chr(10) + equipment_str + chr(10) if equipment_str else ''}"
        f"{'━'*20}\n\n"
        f"{'🎭 *Clases disponibles:* ' + classes_str + chr(10) + chr(10) if classes_str else ''}"
        f"👥 *Personajes*\nRegistrá tu personaje con `/join <nombre> <clase>`\n\n"
        f"⚙️ *Config*\n🌐 Idioma: ES | 🗣️ Tono: {setup_data.get('tone','serious')} | "
        f"⚔️ Setting: {setup_data.get('setting_type','fantasy')}\n\n"
        f"_El DM usará /start para iniciar la aventura_"
    )

    await context.bot.send_message(
        chat_id=group_chat_id,
        text=msg,
        parse_mode=ParseMode.MARKDOWN,
    )


@with_audit("cmd_begin")
async def cmd_begin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inicia la aventura generando la escena inicial de narrativa."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.active_campaign:
            await update.message.reply_text(
                "⚠️ No hay campaña activa. Usá /setup para crear una."
            )
            return

        from state.state_manager import load_state, save_state

        state = load_state(cs.active_campaign)
        if state is None:
            await update.message.reply_text("⚠️ Campaña no encontrada.")
            return

        campaign_status = state.get("campaign", {}).get("status", "active")
        if campaign_status == "setup":
            await update.message.reply_text(
                "⚠️ La campaña aún está en setup. Aprobalá con `perfecto` primero."
            )
            return

        if state.get("adventure_started"):
            await update.message.reply_text(
                "🎭 La aventura ya comenzó. Usá /recap para recordar o /j para actuar."
            )
            return

        characters = state.get("characters", {})
        if not characters:
            await update.message.reply_text(
                "⚠️ No hay personajes registrados. Usá /join primero."
            )
            return

        # Build context for opening scene
        setup = state.get("setup", {})
        lore = setup.get("lore", {})
        ctx = {
            "premise": setup.get("premise", ""),
            "hook": setup.get("hook", ""),
            "location": lore.get("starting_location", "Ubicación desconocida"),
            "location_desc": lore.get("starting_location_desc", ""),
            "characters": list(characters.keys()),
            "tone": setup.get("tone", "serious"),
            "setting_type": setup.get("setting_type", "fantasy"),
        }

        # Generate opening narrative
        ng = NarrativeGenerator()
        settings = get_settings(cs.active_campaign)
        language = settings.language

        result = ng.generate_scene(
            state=state,
            scene_type=SceneType.STORY_BEAT,
            context=ctx,
            language=language,
        )

        narrative = result.get("narrative", "La aventura comienza...")

        # Mark adventure as started
        state["adventure_started"] = True

        # Persist campaign metadata from setup so all handlers can read it
        state["campaign"]["current_location"] = lore.get("starting_location", "Ubicación desconocida")
        state["campaign"]["current_location_desc"] = lore.get("starting_location_desc", "")
        state["campaign"]["main_threat"] = lore.get("main_threat", "")
        state["campaign"]["premise"] = setup.get("premise", "")
        state["campaign"]["hook"] = setup.get("hook", "")
        state["campaign"]["tone"] = setup.get("tone", "serious")
        state["campaign"]["setting_type"] = setup.get("setting_type", "fantasy")

        # Transfer story_arc from setup to state if present
        setup_arc = setup.get("story_arc")
        if setup_arc and state.get("story_arc") is None:
            state["story_arc"] = setup_arc

        state.setdefault("scenes", []).append({
            "type": "opening",
            "narrative": narrative,
            "timestamp": datetime.utcnow().isoformat(),
            "characters_present": list(characters.keys()),
        })
        save_state(cs.active_campaign, state)

        # Broadcast to group
        msg = (
            f"🎭 *¡La aventura comienza!*\n\n"
            f"{narrative}\n\n"
            f"_Usá /j para describir tu acción._"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        log.exception("cmd_begin error")
        await update.message.reply_text(f"Error al iniciar aventura: {e}")


@with_audit("cmd_join")
async def cmd_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /join <name> <class> [level]."""
    try:
        # Check if campaign is in setup (not yet approved)
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if cs.active_campaign:
            from state.state_manager import load_state

            st = load_state(cs.active_campaign)
            if st and st.get("campaign", {}).get("status") == "setup":
                await update.message.reply_text(
                    "⚠️ La campaña aún no está lista.\n"
                    "Esperá a que el DM la configure y apruebe."
                )
                return

        args = context.args
        if len(args) < 2:
            # Show campaign-specific classes if available
            class_help = "Classes: fighter, wizard, rogue, cleric, ranger, barbarian"
            if cs.active_campaign:
                from state.state_manager import load_state
                st = load_state(cs.active_campaign)
                if st:
                    camp_classes = st.get("setup", {}).get("classes")
                    if camp_classes:
                        class_help = f"Clases para esta campaña: {', '.join(camp_classes)}"
            await update.message.reply_text(
                "Usage: /join <name> <class> [level]\n"
                f"Example: /join Valdric fighter 3\n"
                f"{class_help}"
            )
            return

        name = args[0].strip()
        player_class = args[1]
        level = int(args[2]) if len(args) > 2 and args[2].isdigit() else 1

        # ── Dynamic class resolution ──
        from bot.character_sheet import (
            create_character,
            normalize_class_name,
            resolve_class,
        )

        # Build campaign class catalog from setup["classes"] if available
        campaign_classes = None
        if cs.active_campaign:
            st = load_state(cs.active_campaign)
            class_names = st.get("setup", {}).get("classes")
            if class_names:
                # Build catalog: {normalized_name: {"name": display_name, "hit_die": 10, ...}}
                campaign_classes = {}
                for cn in class_names:
                    norm = normalize_class_name(cn)
                    # Generic defaults: d10 hit die, STR primary, athletics+perception skills
                    campaign_classes[norm] = {
                        "id": norm,
                        "name": cn,
                        "hit_die": 10,
                        "primary_stat": "str",
                        "skills": ["athletics", "perception"],
                        "num_skills": 2,
                    }

        resolved = resolve_class(player_class, campaign_classes)
        if resolved is None:
            # Try to build a helpful error message
            available = list(resolved.keys()) if campaign_classes else []
            from bot.character_sheet import CLASS_DEFINITIONS
            default_names = list(CLASS_DEFINITIONS.keys())
            all_names = available + default_names if available else default_names
            await update.message.reply_text(
                f"❓ Clase desconocida: `{player_class}`\n"
                f"Disponibles: {', '.join(sorted(set(all_names)))}\n"
                f"O definilas con: `edit clases: Foo, Bar` en /setup"
            )
            return

        char = create_character(name, player_class, level, campaign_classes=campaign_classes)

        # ── Starting equipment from campaign theme ──
        if cs.active_campaign:
            from state.state_manager import load_state
            st = load_state(cs.active_campaign)
            starting_equipment = st.get("setup", {}).get("starting_equipment", [])
            if starting_equipment:
                from bot.character_sheet import Item
                for eq_data in starting_equipment:
                    item = Item(
                        name=eq_data.get("name", "Item misterioso"),
                        quantity=eq_data.get("quantity", 1),
                        description=eq_data.get("description", ""),
                        is_consumable=eq_data.get("is_consumable", False),
                        damage_dice=eq_data.get("damage_dice"),
                        armor_class=eq_data.get("armor_class"),
                        weight=eq_data.get("weight", 0.0),
                        is_magic=eq_data.get("is_magic", False),
                    )
                    char.add_item(item)

        char.telegram_id = update.effective_user.id  # type: ignore[attr-defined]
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())
        cs.characters[name.lower()] = char
        cs.telegram_characters[update.effective_user.id] = name.lower()
        chat_data["_hermes_state"] = cs

        # Persist to state.json so hermesdm-web can read it
        if cs.active_campaign:
            from state.state_manager import sync_chatstate_to_state
            sync_chatstate_to_state(cs.active_campaign, cs)

        await update.message.reply_text(
            f"✅ *Character Joined!*\n\n{_fmt_character(char)}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        log.exception("cmd_join error")
        await update.message.reply_text(f"Error joining: {e}")


@with_audit("cmd_roll")
async def cmd_roll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /roll [dice] or confirm pending action."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        # Check for pending attacks
        if cs.pending_attacks:
            label, attack = list(cs.pending_attacks.items())[0]
            del cs.pending_attacks[label]

            raw = context.args[0] if context.args else "d20"
            result = _roll(raw)
            attack_roll = result["total"]

            resolved = resolve_attack(
                attacker_name=attack["attacker_name"],
                defender_name=attack["defender_name"],
                attack_roll=attack_roll,
                weapon=attack.get("weapon", "sword"),
                advantage=attack.get("advantage", False),
                disadvantage=attack.get("disadvantage", False),
                defender_ac=attack.get("defender_ac", 10),
                rage_bonus=attack.get("rage_bonus", 0),
            )

            note = f"🎯 *Attack Result*\n{resolved['note']}"
            if resolved["hit"] and resolved["damage"] > 0:
                # Find character and apply damage to their HP
                char = cs.character_for(attack["attacker_name"])
                if char:
                    dmg_result = apply_damage(char.hp, resolved["damage"])
                    note += f"\n{dmg_result['hp_lost']} damage applied to {attack['attacker_name']}"

            chat_data["_hermes_state"] = cs
            await update.message.reply_text(note, parse_mode=ParseMode.MARKDOWN)
            return

        # Check for pending spell
        if cs.pending_spell:
            spell_info = cs.pending_spell
            cs.pending_spell = None

            raw = context.args[0] if context.args else "d20"
            result = _roll(raw)

            spell_result = resolve_spell(
                caster_level=spell_info["caster_level"],
                spell_name=spell_info["spell_name"],
                spell_save_dc=spell_info["spell_data"].get("dc_base", 15),
                target_count=1,
                spell_data=spell_info["spell_data"],
            )

            note = f"✨ *Spell Result*\n{spell_result['note']}"
            chat_data["_hermes_state"] = cs
            await update.message.reply_text(note, parse_mode=ParseMode.MARKDOWN)
            return

        # Check for pending skill check
        if cs.pending_skill_check:
            check_info = cs.pending_skill_check
            cs.pending_skill_check = None

            raw = context.args[0] if context.args else "d20"
            result = _roll(raw)

            # Re-resolve with actual roll
            stat = None
            for s, skills in SKILL_BY_STAT.items():
                if check_info["skill"] in skills:
                    stat = s
                    break

            if stat:
                char: Character = check_info["character"]
                stat_mod = char.mod(stat)
                prof = char.is_proficient(check_info["skill"])
                prof_bonus = char.proficiency_bonus if prof else 0
                total = result["total"] + stat_mod + prof_bonus
                dc = check_info["dc"]
                success = total >= dc
                margin = total - dc

                note = (
                    f"🎲 *Skill Check*\n"
                    f"{char.name} uses {check_info['skill']} vs DC {dc}\n"
                    f"Roll: {result['rolls'][0]} + {stat_mod:+d}"
                    + (f" + prof {prof_bonus:+d}" if prof else "")
                    + f" = *{total}*\n"
                    f"→ *{'SUCCESS' if success else 'FAILURE'}* (by {margin:+d})"
                )
            else:
                note = f"Unknown skill: {check_info['skill']}"

            chat_data["_hermes_state"] = cs
            await update.message.reply_text(note, parse_mode=ParseMode.MARKDOWN)
            return

        # Check for pending save
        if cs.pending_save:
            save_info = cs.pending_save
            cs.pending_save = None

            raw = context.args[0] if context.args else "d20"
            result = _roll(raw)

            char: Character = save_info["character"]
            stat = save_info["stat"]
            stat_mod = char.mod(stat)
            save_prof = char.is_proficient(stat)
            prof_bonus = char.proficiency_bonus if save_prof else 0
            total = result["total"] + stat_mod + prof_bonus
            dc = save_info["dc"]
            success = total >= dc

            note = (
                f"🛡️ *Saving Throw*\n"
                f"{char.name} vs {stat.upper()} DC {dc}\n"
                f"Roll: {result['rolls'][0]} + {stat_mod:+d}"
                + (f" + prof {prof_bonus:+d}" if save_prof else "")
                + f" = *{total}*\n"
                f"→ *{'SUCCESS' if success else 'FAILURE'}*"
            )

            chat_data["_hermes_state"] = cs
            await update.message.reply_text(note, parse_mode=ParseMode.MARKDOWN)
            return

        # Plain /roll
        dice_str = context.args[0] if context.args else "d20"
        try:
            result = _roll(dice_str)
            await update.message.reply_text(
                _fmt_dice_result(result),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as roll_err:
            await update.message.reply_text(f"Roll error: {roll_err}")

    except Exception as e:
        log.exception("cmd_roll error")
        await update.message.reply_text(f"Error: {e}")


@with_audit("cmd_attack")
async def cmd_attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /attack <target> [adv|dis] — cancels countdown and advances to next turn."""
    try:
        args = context.args
        if not args:
            await update.message.reply_text(
                "Usage: /attack <target_name> [adv|dis]\n"
                "Then use /roll to resolve the attack."
            )
            return

        target = args[0]
        advantage = "adv" in args
        disadvantage = "dis" in args

        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        player_name = update.effective_user.first_name.lower()

        # Use player's active character or default
        char = cs.character_for(player_name)
        if char is None and cs.characters:
            char = list(cs.characters.values())[0]

        if char is None:
            await update.message.reply_text(
                "No character found. Use /join to create one first."
            )
            return

        attacker_name = char.name
        weapon = char.equipped_weapon or "sword"
        chat_id = update.effective_chat.id
        job_queue = getattr(context.application, "job_queue", None)
        timer_seconds = _get_timer_seconds(cs)

        label = f"attack_{len(cs.pending_attacks)}"
        cs.pending_attacks[label] = {
            "attacker_name": attacker_name,
            "defender_name": target,
            "weapon": weapon,
            "defender_ac": 10,  # default AC; bot DM would set actual
            "rage_bonus": 0,
            "advantage": advantage,
            "disadvantage": disadvantage,
        }

        # ── AUTO-START COMBAT if not already in combat ──
        combat_started_msg = ""
        if cs.combat_state is None or not cs.combat_state.active:
            combat_started_msg = "\n\n" + _start_combat_for_participants(
                cs, [target], chat_id, job_queue
            )
            chat_data["_hermes_state"] = cs

            # Send countdown message for first character
            if job_queue is not None and timer_seconds > 0 and cs.combat_state:
                current = cs.combat_state.current_turn or "alguien"
                round_num = cs.combat_state.round
                bar = "█" * 10
                msg = await update.message.reply_text(
                    f"⏱️ Turno de *{current}* — Round {round_num}\n`[{bar}] {timer_seconds}s`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                cs.countdown_message_id = msg.message_id
                cs.countdown_remaining = timer_seconds
                chat_data["_hermes_state"] = cs

                job_queue.run_once(
                    _live_countdown_edit,
                    1,
                    name="turn_countdown",
                    data={
                        "chat_id": chat_id,
                        "character": current,
                        "remaining": timer_seconds - 1,
                        "total": timer_seconds,
                        "round": round_num,
                        "message_id": msg.message_id,
                    },
                )
        else:
            # ── ALREADY IN ACTIVE COMBAT ──
            # Cancel countdown + advance turn + new countdown for next character
            # (This is the action that "uses" the turn)
            if job_queue is not None:
                for job in job_queue.get_jobs_by_name("turn_countdown"):
                    job.schedule_removal()

            old_msg_id = cs.countdown_message_id
            cs.countdown_message_id = None
            if old_msg_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=old_msg_id)
                except Exception:
                    pass

            result = next_turn(cs.combat_state)
            if "error" in result:
                cs.combat_state = None
                chat_data["_hermes_state"] = cs
                await update.message.reply_text(
                    f"Combat ended: {result.get('error', 'No combatants')}"
                )
                return

            chat_data["_hermes_state"] = cs

            # Send new countdown for next character
            if timer_seconds > 0 and cs.combat_state and cs.combat_state.active:
                next_char = cs.combat_state.current_turn
                round_num = cs.combat_state.round
                bar = "█" * 10
                msg = await update.message.reply_text(
                    f"⏱️ Turno de *{next_char}* — Round {round_num}\n`[{bar}] {timer_seconds}s`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                cs.countdown_message_id = msg.message_id
                cs.countdown_remaining = timer_seconds
                chat_data["_hermes_state"] = cs

                job_queue.run_once(
                    _live_countdown_edit,
                    1,
                    name="turn_countdown",
                    data={
                        "chat_id": chat_id,
                        "character": next_char,
                        "remaining": timer_seconds - 1,
                        "total": timer_seconds,
                        "round": round_num,
                        "message_id": msg.message_id,
                    },
                )

        adv_note = " (ADV)" if advantage else (" (DIS)" if disadvantage else "")
        await update.message.reply_text(
            f"⚔️ *Attack queued*\n"
            f"{attacker_name} attacks {target}{adv_note} with {weapon}.\n"
            f"Use /roll <dice> (e.g. /roll d20+5) to resolve." + combat_started_msg,
            parse_mode=ParseMode.MARKDOWN,
        )

        # Persist combat/character state so hermesdm-web stays in sync
        if cs.active_campaign:
            from state.state_manager import sync_chatstate_to_state
            sync_chatstate_to_state(cs.active_campaign, cs)

    except Exception as e:
        log.exception("cmd_attack error")
        await update.message.reply_text(f"Error: {e}")


@with_audit("cmd_cast")
async def cmd_cast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cast <spell> [target] — resolves immediately with spell slot."""
    try:
        args = context.args
        if len(args) < 1:
            # Show spell list with slots
            chat_data = context.chat_data
            cs: ChatState = chat_data.get("_hermes_state", ChatState())
            player_name = update.effective_user.first_name.lower()
            char = cs.character_for(player_name)
            if char is None and cs.characters:
                char = list(cs.characters.values())[0]
            if char:
                spell_list = spell_mgr.format_spell_list(char)
            else:
                spell_list = ", ".join(spell_mgr.SPELLS.keys())
            await update.message.reply_text(
                f"Usage: /cast <spell_name> [target]\n\n"
                f"{spell_list}",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        spell_name = args[0].lower()
        target = " ".join(args[1:]) if len(args) > 1 else ""

        # Validate spell exists
        if spell_name not in spell_mgr.SPELLS:
            await update.message.reply_text(
                f"Unknown spell: `{spell_name}`\n"
                f"Available: {', '.join(spell_mgr.SPELLS.keys())}"
            )
            return

        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        player_name = update.effective_user.first_name.lower()
        char = cs.character_for(player_name)
        if char is None and cs.characters:
            char = list(cs.characters.values())[0]

        if char is None:
            await update.message.reply_text(
                "No character found. Use /join to create one first."
            )
            return

        # Resolve spell with slot consumption
        result = spell_mgr.cast_spell(char, spell_name, target)
        await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)

        # Combat integration: cancel countdown, advance turn
        if cs.combat_state and cs.combat_state.active:
            chat_id = update.effective_chat.id
            job_queue = getattr(context.application, "job_queue", None)
            timer_seconds = _get_timer_seconds(cs)

            if job_queue is not None:
                for job in job_queue.get_jobs_by_name("turn_countdown"):
                    job.schedule_removal()

            old_msg_id = cs.countdown_message_id
            cs.countdown_message_id = None
            if old_msg_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=old_msg_id)
                except Exception:
                    pass

            result_turn = next_turn(cs.combat_state)
            if "error" not in result_turn and timer_seconds > 0 and cs.combat_state.active:
                next_char = cs.combat_state.current_turn
                round_num = cs.combat_state.round
                bar = "█" * 10
                msg = await update.message.reply_text(
                    f"⏱️ Turno de *{next_char}* — Round {round_num}\n`[{bar}] {timer_seconds}s`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                cs.countdown_message_id = msg.message_id
                cs.countdown_remaining = timer_seconds
                chat_data["_hermes_state"] = cs

                job_queue.run_once(
                    _live_countdown_edit,
                    1,
                    name="turn_countdown",
                    data={
                        "chat_id": chat_id,
                        "character": next_char,
                        "remaining": timer_seconds - 1,
                        "total": timer_seconds,
                        "round": round_num,
                        "message_id": msg.message_id,
                    },
                )
            chat_data["_hermes_state"] = cs
        else:
            chat_data["_hermes_state"] = cs

        # Persist character + combat state so hermesdm-web stays in sync
        if cs.active_campaign:
            from state.state_manager import sync_chatstate_to_state
            sync_chatstate_to_state(cs.active_campaign, cs)

    except Exception as e:
        log.exception("cmd_cast error")
        await update.message.reply_text(f"Error: {e}")


@with_audit("cmd_skill")
async def cmd_skill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /skill <skill_name> <dc>."""
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: /skill <skill_name> <dc> [adv|dis]\n"
                f"Skills: {', '.join(sorted(ALL_SKILLS))}"
            )
            return

        skill = args[0].lower().replace(" ", "_")
        try:
            dc = int(args[1])
        except ValueError:
            await update.message.reply_text(f"Invalid DC: `{args[1]}`")
            return

        advantage = "adv" in args
        disadvantage = "dis" in args

        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        player_name = update.effective_user.first_name.lower()
        char = cs.character_for(player_name)
        if char is None and cs.characters:
            char = list(cs.characters.values())[0]

        if char is None:
            await update.message.reply_text(
                "No character found. Use /join to create one first."
            )
            return

        if skill not in ALL_SKILLS:
            await update.message.reply_text(f"Unknown skill: `{skill}`")
            return

        cs.pending_skill_check = {
            "character": char,
            "skill": skill,
            "dc": dc,
            "advantage": advantage,
            "disadvantage": disadvantage,
        }
        chat_data["_hermes_state"] = cs

        # If in active combat, cancel countdown and advance turn
        if cs.combat_state and cs.combat_state.active:
            chat_id = update.effective_chat.id
            job_queue = getattr(context.application, "job_queue", None)
            timer_seconds = _get_timer_seconds(cs)

            if job_queue is not None:
                for job in job_queue.get_jobs_by_name("turn_countdown"):
                    job.schedule_removal()

            old_msg_id = cs.countdown_message_id
            cs.countdown_message_id = None
            if old_msg_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=old_msg_id)
                except Exception:
                    pass

            result = next_turn(cs.combat_state)
            if "error" not in result and timer_seconds > 0 and cs.combat_state.active:
                next_char = cs.combat_state.current_turn
                round_num = cs.combat_state.round
                bar = "█" * 10
                msg = await update.message.reply_text(
                    f"⏱️ Turno de *{next_char}* — Round {round_num}\n`[{bar}] {timer_seconds}s`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                cs.countdown_message_id = msg.message_id
                cs.countdown_remaining = timer_seconds
                chat_data["_hermes_state"] = cs

                job_queue.run_once(
                    _live_countdown_edit,
                    1,
                    name="turn_countdown",
                    data={
                        "chat_id": chat_id,
                        "character": next_char,
                        "remaining": timer_seconds - 1,
                        "total": timer_seconds,
                        "round": round_num,
                        "message_id": msg.message_id,
                    },
                )

        await update.message.reply_text(
            f"🎲 *Skill Check Queued*\n"
            f"{char.name} attempts *{skill}* vs DC {dc}.\n"
            f"Use /roll to resolve.",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        log.exception("cmd_skill error")
        await update.message.reply_text(f"Error: {e}")


@with_audit("cmd_status")
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status — show character summary."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.characters:
            await update.message.reply_text(
                "No characters in this campaign. Use /join to add one."
            )
            return

        lines = ["*Party Status*\n"]
        for char in cs.characters.values():
            hp_line = f"{char.hp.current}/{char.hp.max}" + (
                f" (+{char.hp.temp} temp)" if char.hp.temp > 0 else ""
            )
            lines.append(
                f"  {char.name} — {char.player_class.capitalize()} Lv{char.level} | "
                f"HP: {hp_line} | AC: {char.ac}"
            )

        combat = _fmt_combat_summary(cs.combat_state)
        if combat != "No active combat.":
            lines.append(f"\n{combat}")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.exception("cmd_status error")
        await update.message.reply_text(f"Error: {e}")


@with_audit("cmd_hp")
async def cmd_hp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /hp — detailed HP info for the caller's character."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        player_name = update.effective_user.first_name.lower()
        char = cs.character_for(player_name)
        if char is None and cs.characters:
            char = list(cs.characters.values())[0]

        if char is None:
            await update.message.reply_text(
                "No character found. Use /join to create one first."
            )
            return

        hp_info = (
            f"*HP Report — {char.name}*\n"
            f"Current: {char.hp.current} / {char.hp.max}\n"
            f"Temp HP: {char.hp.temp}\n"
        )
        if char.hp.current == 0:
            ds = char.death_saves
            hp_info += (
                f"\n*Death Saves*\n"
                f"Successes: {'✓ ' * ds.successes}{(3 - ds.successes) * '_ '}\n"
                f"Failures: {'✗ ' * ds.failures}{(3 - ds.failures) * '_ '}"
            )

        # Send privately to the user (HP is private info)
        target_id = update.effective_user.id
        await context.bot.send_message(
            chat_id=target_id,
            text=hp_info,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        log.exception("cmd_hp error")
        await update.message.reply_text(f"Error: {e}")


@with_audit("cmd_inventory")
async def cmd_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /inventory — view inventory of the caller's character."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        player_name = update.effective_user.first_name.lower()
        char = cs.character_for(player_name)
        if char is None and cs.characters:
            char = list(cs.characters.values())[0]

        if char is None:
            await update.message.reply_text(
                "No character found. Use /join to create one first."
            )
            return

        if not char.inventory:
            await update.message.reply_text(f"*Inventory — {char.name}*\n(empty)")
            return

        lines = [
            f"*Inventory — {char.name}* ({len(char.inventory)}/{char.inventory_slots})\\n"
            f"💰 {char.carried_gold} gp | ⚖️ {char.get_weight_carried():.1f}/{char.get_carrying_capacity():.0f} lbs\n"
        ]
        for item in char.inventory:
            eq = " [EQUIPPED]" if item.is_equipped else ""
            rarity_emoji = _rarity_emoji(item.rarity)
            lines.append(f"  {rarity_emoji} {item.name} x{item.quantity}{eq}")
            if item.description:
                lines.append(f"    _{item.description[:60]}_")
            extra = []
            if item.is_equipped:
                extra.append("EQUIPPED")
            if item.weight and float(item.weight) > 0:
                extra.append(f"{item.weight} lbs")
            if item.armor_class:
                extra.append(f"AC {item.armor_class}")
            if item.damage_dice:
                extra.append(str(item.damage_dice))
            if extra:
                lines.append(f"    [{', '.join(extra)}]")

        # Send privately to the user (inventory is private info)
        target_id = update.effective_user.id
        await context.bot.send_message(
            chat_id=target_id,
            text="\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        log.exception("cmd_inventory error")
        await update.message.reply_text(f"Error: {e}")


@with_audit("cmd_give")
async def cmd_give(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /give <character> <item> [qty] — transfer item to another player."""
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "🎁 *Transferencia de item*\n\n"
                "Uso: /give <personaje> <item> [cantidad]\n"
                "Ejemplo: /give Valdric Espada Larga\n"
                "Usa /inventory para ver tu inventario."
            )
            return

        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.active_campaign:
            await update.message.reply_text(
                "⚠️ No hay campaña activa. Usa /newgame primero."
            )
            return

        # Find receiver character
        receiver_name = args[0]
        receiver_char = None
        for key, char in cs.characters.items():
            if char.name.lower() == receiver_name.lower():
                receiver_char = char
                break

        if receiver_char is None:
            available = ", ".join(c.name for c in cs.characters.values())
            await update.message.reply_text(
                f"⚠️ Personaje '{receiver_name}' no encontrado en la party.\n"
                f"Disponibles: {available}"
            )
            return

        # Find item in giver's inventory
        sender_name = update.effective_user.first_name or ""
        giver_char = cs.character_for(sender_name)

        if giver_char is None:
            # Try partial match
            for key, char in cs.characters.items():
                if sender_name.lower() in char.name.lower() or char.name.lower() in sender_name.lower():
                    giver_char = char
                    break

        if giver_char is None:
            await update.message.reply_text(
                "⚠️ No se encontró tu personaje. Usa /join para registrarte."
            )
            return

        # Parse item name (rest of args after receiver name)
        item_name = " ".join(args[1:])

        # Parse quantity (last arg if it's a number)
        qty = 1
        potential_qty = args[-1]
        if potential_qty.isdigit() and int(potential_qty) > 0:
            qty = int(potential_qty)
            item_name = " ".join(args[1:-1])  # exclude qty from item name

        if not item_name:
            await update.message.reply_text(
                "⚠️ Debes especificar qué item quieres dar.\n"
                "Ejemplo: /give Valdric Espada Larga"
            )
            return

        # Find item in giver's inventory
        item_found = None
        for item in giver_char.inventory:
            if item.name.lower() == item_name.lower():
                item_found = item
                break

        if item_found is None:
            await update.message.reply_text(
                f"⚠️ No tienes '{item_name}' en tu inventario.\n"
                "Usa /inventory para ver tus items."
            )
            return

        if item_found.quantity < qty:
            await update.message.reply_text(
                f"⚠️ Solo tienes {item_found.quantity}x '{item_found.name}'.\n"
                f"No puedes dar {qty}."
            )
            return

        # Check receiver inventory slots
        if len(receiver_char.inventory) >= receiver_char.inventory_slots:
            await update.message.reply_text(
                f"⚠️ El inventario de {receiver_char.name} está lleno "
                f"({receiver_char.inventory_slots}/{receiver_char.inventory_slots})."
            )
            return

        # Perform transfer
        giver_char.remove_item(item_found.name, qty)

        from bot.character_sheet import Item
        transferred = Item(name=item_found.name, quantity=qty, description=item_found.description)
        receiver_char.add_item(transferred)

        # Save state
        state = load_state(cs.active_campaign)
        if state:
            state["characters"][giver_char.name.lower().replace(" ", "_")] = giver_char.to_dict()
            state["characters"][receiver_char.name.lower().replace(" ", "_")] = receiver_char.to_dict()
            save_state(cs.active_campaign, state)

        # Response
        item_label = f"{qty}x {item_found.name}"
        if item_found.description:
            item_label += f" — _{item_found.description[:40]}_"

        await update.message.reply_text(
            f"🎁 *Transferencia realizada*\n\n"
            f"{giver_char.name} le da {item_label} a {receiver_char.name}.\n"
            f"Inventario de {giver_char.name}: {len(giver_char.inventory)}/{giver_char.inventory_slots}\n"
            f"Inventario de {receiver_char.name}: {len(receiver_char.inventory)}/{receiver_char.inventory_slots}",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        log.exception("cmd_give error")
        await update.message.reply_text(f"Error: {e}")


@with_audit("cmd_talk")
async def cmd_talk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /talk <npc_name> <message>."""
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: /talk <npc_name> <message>\n"
                "Use /campaign to see available NPCs."
            )
            return

        npc_name = args[0].lower().replace(" ", "_")
        message = " ".join(args[1:])

        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.active_campaign:
            await update.message.reply_text("No active campaign. Use /newgame first.")
            return

        state = load_state(cs.active_campaign)
        if state is None:
            await update.message.reply_text("Campaign not found.")
            return

        npc_key = None
        for key in state.get("npcs", {}):
            if (
                key == npc_name
                or state["npcs"][key]["name"].lower().replace(" ", "_") == npc_name
            ):
                npc_key = key
                break

        if npc_key is None:
            npc_list = ", ".join(n["name"] for n in state.get("npcs", {}).values())
            await update.message.reply_text(
                f"NPC not found. Available: {npc_list or 'none'}"
            )
            return

        npc = state["npcs"][npc_key]
        player_name = update.effective_user.first_name.lower()
        char = cs.character_for(player_name)
        speaker = char.name if char else "Unknown"

        # Simple disposition-based response (the DM would narrate this in a full implementation)
        disp = npc.get("disposition_value", 0)
        if disp > 50:
            response_tone = "warm and friendly"
        elif disp < -50:
            response_tone = "cold and hostile"
        else:
            response_tone = "cautious and neutral"

        reply = (
            f'*You say to {npc["name"]}:* "{message}"\n\n'
            f"*{npc['name']} ({npc['role']}) responds* — {response_tone}:\n"
            f"_{npc.get('dialogue_style', 'They look at you curiously.')}_"
        )

        # Record in history
        state["history"].append(
            {
                "session": state["history"][-1]["session"] if state["history"] else 1,
                "event": f"{speaker} talked to {npc['name']}: {message}",
            }
        )
        save_state(cs.active_campaign, state)

        await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.exception("cmd_talk error")
        await update.message.reply_text(f"Error: {e}")


# ── NPC Commands ───────────────────────────────────────────────────────────────

def _get_npc_store(campaign_id: str) -> NPCStore:
    """Load NPCStore for campaign (lazy import to avoid circular)."""
    from state.state_manager import load_npc_store
    return load_npc_store(campaign_id)


async def cmd_npcs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /npcs — list all persistent NPCs in the campaign."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())
        if not cs.active_campaign:
            await update.message.reply_text("No active campaign.")
            return

        store = _get_npc_store(cs.active_campaign)
        result = store.format_all()
        await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.exception("cmd_npcs error")
        await update.message.reply_text(f"Error: {e}")


async def cmd_npcsearch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /npcsearch <query> — search NPCs by name, title, description."""
    try:
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /npcsearch <query>")
            return

        query = " ".join(args)
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())
        if not cs.active_campaign:
            await update.message.reply_text("No active campaign.")
            return

        store = _get_npc_store(cs.active_campaign)
        results = store.search(query)
        if not results:
            await update.message.reply_text(f"No NPCs found matching: {query}")
            return

        lines = [f"**NPCs matching \"{query}\"**\n"]
        for npc in results[:5]:
            lines.append(
                f"**{npc.name}** — {npc.title} @ {npc.location}\n"
                f"  _{npc.personality[:80]}_"
            )
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.exception("cmd_npcsearch error")
        await update.message.reply_text(f"Error: {e}")


async def cmd_npcnote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /npcnote <name> <note> — add a DM note to an NPC."""
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: /npcnote <npc_name> <note text>\n"
                "Example: /npcnote Gorin He betrayed the party last session."
            )
            return

        npc_name = args[0]
        note = " ".join(args[1:])
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())
        if not cs.active_campaign:
            await update.message.reply_text("No active campaign.")
            return

        store = _get_npc_store(cs.active_campaign)
        npc = store.find_by_name(npc_name)
        if not npc:
            await update.message.reply_text(f"NPC '{npc_name}' not found. Use /npcs to see all NPCs.")
            return

        npc.notes = note
        store.add(npc)
        from state.state_manager import save_npc_store
        save_npc_store(cs.active_campaign, store)

        await update.message.reply_text(
            f"Note saved for **{npc.name}**.\n"
            f"_Note: {note}_",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        log.exception("cmd_npcnote error")
        await update.message.reply_text(f"Error: {e}")


async def cmd_npcmemory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /npcmemory <name> <key> <value> — add a memory entry to an NPC."""
    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text(
                "Usage: /npcmemory <npc_name> <key> <value>\n"
                "Example: /npcmemory Gorin secret_weakness Afraid of fire"
            )
            return

        npc_name = args[0]
        key = args[1]
        value = " ".join(args[2:])
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())
        if not cs.active_campaign:
            await update.message.reply_text("No active campaign.")
            return

        player = update.effective_user.first_name
        store = _get_npc_store(cs.active_campaign)
        npc = store.find_by_name(npc_name)
        if not npc:
            await update.message.reply_text(f"NPC '{npc_name}' not found. Use /npcs to see all NPCs.")
            return

        npc.add_memory(key, value, added_by=player)
        store.add(npc)
        from state.state_manager import save_npc_store
        save_npc_store(cs.active_campaign, store)

        await update.message.reply_text(
            f"Memory added to **{npc.name}**.\n"
            f"**{key}**: {value}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        log.exception("cmd_npcmemory error")
        await update.message.reply_text(f"Error: {e}")


@with_audit("cmd_map")
async def cmd_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /map — show current location details."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.active_campaign:
            await update.message.reply_text("No active campaign. Use /newgame first.")
            return

        state = load_state(cs.active_campaign)
        if state is None:
            await update.message.reply_text("Campaign not found.")
            return

        location = state["campaign"].get("current_location", "Unknown")
        loc_data = state.get("world", {}).get("locations", {}).get(location, {})
        desc = loc_data.get("description", "No description available.")
        npc_ids = loc_data.get("npcs", [])

        npc_names = [
            state["npcs"].get(nid, {}).get("name", nid)
            for nid in npc_ids
            if nid in state["npcs"]
        ]

        lines = [
            f"*📍 {location}*",
            f"\n_{desc[:300]}_",
        ]
        if npc_names:
            lines.append(f"\n*NPCs here:* {', '.join(npc_names)}")
        else:
            lines.append("\n*NPCs here:* none")

        factions = state.get("world", {}).get("factions", {})
        if factions:
            fact_lines = [f"  {k}: {v}" for k, v in factions.items()]
            lines.append("\n*Factions:*\n" + "\n".join(fact_lines))

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.exception("cmd_map error")
        await update.message.reply_text(f"Error: {e}")


@with_audit("cmd_quests")
async def cmd_quests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /quests — show active and completed quests."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.active_campaign:
            await update.message.reply_text("No active campaign. Use /newgame first.")
            return

        state = load_state(cs.active_campaign)
        if state is None:
            await update.message.reply_text("Campaign not found.")
            return

        active = state.get("quests", {}).get("active", [])
        completed = state.get("quests", {}).get("completed", [])

        lines = ["*Quests*\n"]
        if active:
            lines.append("*Active:*")
            for q in active:
                lines.append(f"  • {q}")
        else:
            lines.append("*Active:* none")

        if completed:
            lines.append("\n*Completed:*")
            for q in completed:
                lines.append(f"  ✓ {q}")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.exception("cmd_quests error")
        await update.message.reply_text(f"Error: {e}")


@with_audit("cmd_recap")
async def cmd_recap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /recap — story recap from campaign history."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.active_campaign:
            await update.message.reply_text("No active campaign. Use /newgame first.")
            return

        state = load_state(cs.active_campaign)
        if state is None:
            await update.message.reply_text("Campaign not found.")
            return

        history = state.get("history", [])
        if not history:
            await update.message.reply_text("No story history yet.")
            return

        lines = ["*Story Recap*\n"]
        for entry in history[-10:]:  # last 10 entries
            event = entry.get("event", str(entry))
            session = entry.get("session", "?")
            lines.append(f"[Session {session}] {event[:200]}")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.exception("cmd_recap error")
        await update.message.reply_text(f"Error: {e}")


@with_audit("cmd_resume")
async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /resume — resume the last campaign."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if cs.active_campaign and campaign_exists(cs.active_campaign):
            state = load_state(cs.active_campaign)
        else:
            # Find most recent campaign
            campaigns = list_campaigns()
            if not campaigns:
                await update.message.reply_text(
                    "No campaigns found. Use /newgame to create one."
                )
                return
            latest = campaigns[0]
            cs.active_campaign = latest["id"]
            state = load_state(cs.active_campaign)

        if state is None:
            await update.message.reply_text("Campaign not found.")
            return

        camp = state["campaign"]
        lines = [
            "*Campaign Resumed*\n",
            f"*{camp['name']}* ({camp['setting']})\n",
            f"Location: {camp.get('current_location', 'Unknown')}\n",
            f"World: {state['world'].get('main_threat', 'Unknown threat')}\n",
        ]

        npcs = state.get("npcs", {})
        if npcs:
            lines.append(f"Known NPCs: {', '.join(n['name'] for n in npcs.values())}")

        chat_data["_hermes_state"] = cs
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.exception("cmd_resume error")
        await update.message.reply_text(f"Error: {e}")


@with_audit("cmd_endturn")
async def cmd_endturn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /endturn — advance combat to the next turn with countdown."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if cs.combat_state is None or not cs.combat_state.active:
            await update.message.reply_text("No active combat. Start one with /attack.")
            return

        job_queue = getattr(context.application, "job_queue", None)
        timer_seconds = _get_timer_seconds(cs)

        if timer_seconds > 0:
            # Cancel existing countdown and advance with new one
            chat_id = update.effective_chat.id

            # Cancel old countdown jobs
            if job_queue is not None:
                for job in job_queue.get_jobs_by_name("turn_countdown"):
                    job.schedule_removal()

            # Delete old countdown message
            old_msg_id = cs.countdown_message_id
            cs.countdown_message_id = None
            if old_msg_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=old_msg_id)
                except Exception:
                    pass

            # Advance turn
            result = next_turn(cs.combat_state)
            if "error" in result:
                cs.combat_state = None
                chat_data["_hermes_state"] = cs
                await update.message.reply_text(
                    f"Combat ended: {result.get('error', 'No combatants')}"
                )
                return

            next_char = cs.combat_state.current_turn
            round_num = cs.combat_state.round

            # Send new countdown
            bar = "█" * 10
            msg = await update.message.reply_text(
                f"⏱️ Turno de *{next_char}* — Round {round_num}\n`[{bar}] {timer_seconds}s`",
                parse_mode=ParseMode.MARKDOWN,
            )

            cs.countdown_message_id = msg.message_id
            cs.countdown_remaining = timer_seconds
            chat_data["_hermes_state"] = cs

            job_queue.run_once(
                _live_countdown_edit,
                1,
                name="turn_countdown",
                data={
                    "chat_id": chat_id,
                    "character": next_char,
                    "remaining": timer_seconds - 1,
                    "total": timer_seconds,
                    "round": round_num,
                    "message_id": msg.message_id,
                },
            )
        else:
            # Timer disabled — legacy behavior
            result = next_turn(cs.combat_state)
            if "error" in result:
                cs.combat_state = None
                chat_data["_hermes_state"] = cs
                await update.message.reply_text(
                    f"Combat ended: {result.get('error', 'No combatants')}"
                )
                return
            chat_data["_hermes_state"] = cs
            summary = _fmt_combat_summary(cs.combat_state)
            await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        log.exception("cmd_endturn error")
        await update.message.reply_text(f"Error: {e}")


async def cmd_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /campaign — show active campaign details."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.active_campaign:
            await update.message.reply_text("No active campaign. Use /newgame first.")
            return

        state = load_state(cs.active_campaign)
        if state is None:
            await update.message.reply_text("Campaign not found.")
            return

        camp = state["campaign"]
        world = state.get("world", {})
        npcs = state.get("npcs", {})

        lines = [
            f"*Campaign: {camp['name']}*",
            f"Setting: {camp['setting'].capitalize()}",
            f"Location: {camp.get('current_location', 'Unknown')}",
            f"Threat: {world.get('main_threat', 'Unknown')}",
        ]

        if npcs:
            lines.append(f"Known NPCs: {', '.join(n['name'] for n in npcs.values())}")

        chars = cs.characters
        if chars:
            lines.append(f"\n*Party ({len(chars)}):*")
            for char in chars.values():
                lines.append(
                    f"  • {char.name} ({char.player_class.capitalize()} Lv{char.level})"
                )

        factions = world.get("factions", {})
        if factions:
            lines.append("\n*Factions:*")
            for name, status in factions.items():
                lines.append(f"  {name}: {status}")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.exception("cmd_campaign error")
        await update.message.reply_text(f"Error: {e}")


# -----------------------------------------------------------------------
# Start command — launch the adventure (opening scene)
# -----------------------------------------------------------------------


@with_audit("cmd_start")
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start — generate and broadcast the opening scene of the campaign.

    Flow:
    1. Verify active campaign with players who joined
    2. Generate opening scene via NarrativeGenerator (EXPLORATION)
    3. Send narrative to group
    4. Record in history
    """
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.active_campaign:
            await update.message.reply_text(
                "No hay campaña activa. Usa /setup para crear una.",
            )
            return

        state = load_state(cs.active_campaign)
        if state is None:
            await update.message.reply_text("Campaña no encontrada.")
            return

        # Verify campaign is active
        campaign_status = state.get("campaign", {}).get("status", "pending")
        if campaign_status == "completed":
            await update.message.reply_text(
                "Esta campaña ya terminó. Usa /newgame para crear una nueva.",
            )
            return

        # Check if players have joined
        characters = state.get("characters", {})
        if not characters:
            await update.message.reply_text(
                "Aún no hay jugadores en la party. Usa /join para registrar tu personaje.",
            )
            return

        # Generate opening scene
        ng = NarrativeGenerator()
        settings = get_settings(cs.active_campaign)
        language = settings.language

        # Build location from campaign setup
        location = state.get("campaign", {}).get("current_location") or "un lugar olvidado"

        opening_result = ng.generate_scene(
            state,
            SceneType.EXPLORATION,
            context={"location": location},
            language=language,
        )

        opening_text = opening_result["narrative"]

        # Record in history
        append_history(
            cs.active_campaign,
            f"🎭 {opening_text}",
            entry_type="opening",
        )

        # Broadcast to group
        party_names = ", ".join(c.get("name", n) for n, c in characters.items())

        await update.message.reply_text(
            f"🎭 *¡LA AVENTURA COMIENZA!*\n\n"
            f"_{opening_text}_\n\n"
            f"👥 Party: {party_names}\n\n"
            f"¿Qué hacen los aventureros?",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        log.exception("cmd_start error")
        await update.message.reply_text(f"Error: {e}")


# -----------------------------------------------------------------------
# Save command handler (saving throw)
# -----------------------------------------------------------------------


# cmd_save is imported from bot.save_command (inline saving throw resolution)
# Re-export for backward compatibility
async def cmd_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delegates to save_command.cmd_save for inline saving throw resolution."""
    await cmd_save_impl(update, context)


# ------------------------------------------------------------------
# Combat helpers & commands
# ------------------------------------------------------------------


def _dex_mod_for_character(char: Character) -> int:
    """Get dex mod from a character for initiative."""
    return char.mod("dex")


def _start_combat_for_participants(
    cs: ChatState,
    enemies: list[str],
    chat_id: int,
    job_queue: JobQueue | None = None,
) -> str:
    """
    Initiate combat with all registered player characters + enemies.
    Returns a formatted message with initiative order.
    """
    # Build participant list
    participants = []

    # All player characters
    for player_name, char in cs.characters.items():
        participants.append(
            {
                "name": char.name,
                "is_player": True,
                "dex_mod": _dex_mod_for_character(char),
            }
        )

    # Enemy NPCs
    for enemy_name in enemies:
        participants.append(
            {
                "name": enemy_name,
                "is_player": False,
                "dex_mod": 0,  # default dex mod for enemies
            }
        )

    if len(participants) < 2:
        return "⚠️ Need at least 2 combatants (players + enemies) to start combat."

    # Roll initiative and order
    cs.combat_state = start_combat(participants)

    # Format initiative list
    lines = ["⚔️ *COMBATE INICIADO!*"]
    lines.append(f"_Round {cs.combat_state.round}_")
    lines.append("")
    lines.append("*Orden de iniciativa:*")
    for i, c in enumerate(cs.combat_state.initiative_order):
        marker = " ◄ (tu turno)" if i == cs.combat_state.current_index else ""
        enemy_tag = " 👹" if not c.is_player else ""
        lines.append(f"  {c.initiative:3d} — {c.name}{enemy_tag}{marker}")

    lines.append("")
    lines.append(f"🎯 *{cs.combat_state.current_turn}* es el primero en actuar.")

    return "\n".join(lines)


async def cmd_startcombat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /startcombat [enemy1] [enemy2] ... — start combat manually."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.characters:
            await update.message.reply_text(
                "⚠️ No hay personajes registrados. Usa /join primero."
            )
            return

        if cs.combat_state is not None and cs.combat_state.active:
            await update.message.reply_text(
                "⚔️ Ya hay combate activo. Usa /endcombat para terminarlo primero."
            )
            return

        enemies = list(context.args) if context.args else []
        job_queue = getattr(context.application, "job_queue", None)

        result_msg = _start_combat_for_participants(
            cs, enemies, update.effective_chat.id, job_queue
        )
        chat_data["_hermes_state"] = cs
        await update.message.reply_text(result_msg, parse_mode=ParseMode.MARKDOWN)

        # Schedule countdown for first character
        timer_seconds = _get_timer_seconds(cs)
        if job_queue is not None and timer_seconds > 0 and cs.combat_state:
            current = cs.combat_state.current_turn or "alguien"
            chat_id = update.effective_chat.id
            round_num = cs.combat_state.round

            # Send countdown message
            bar = "█" * 10
            msg = await update.message.reply_text(
                f"⏱️ Turno de *{current}* — Round {round_num}\n`[{bar}] {timer_seconds}s`",
                parse_mode=ParseMode.MARKDOWN,
            )

            cs.countdown_message_id = msg.message_id
            cs.countdown_remaining = timer_seconds
            chat_data["_hermes_state"] = cs

            job_queue.run_once(
                _live_countdown_edit,
                1,
                name="turn_countdown",
                data={
                    "chat_id": chat_id,
                    "character": current,
                    "remaining": timer_seconds - 1,
                    "total": timer_seconds,
                    "round": round_num,
                    "message_id": msg.message_id,
                },
            )

    except Exception as e:
        log.exception("cmd_startcombat error")
        await update.message.reply_text(f"Error: {e}")


async def cmd_endcombat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /endcombat — end active combat."""
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if cs.combat_state is None or not cs.combat_state.active:
            await update.message.reply_text("⚠️ No hay combate activo.")
            return

        # Cancel any pending countdown jobs
        job_queue = getattr(context.application, "job_queue", None)
        if job_queue is not None:
            for job in job_queue.get_jobs_by_name("turn_countdown"):
                job.schedule_removal()
            for job in job_queue.get_jobs_by_name("turn_timer"):
                job.schedule_removal()

        # Delete countdown message if exists
        old_msg_id = cs.countdown_message_id
        if old_msg_id:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id, message_id=old_msg_id
                )
            except Exception:
                pass
        cs.countdown_message_id = None
        cs.countdown_remaining = 0

        end_combat(cs.combat_state)
        cs.combat_state = None
        chat_data["_hermes_state"] = cs

        await update.message.reply_text(
            "🛑 *Combate finalizado.*\nTodos los participantes han salido del modo combate.",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        log.exception("cmd_endcombat error")
        await update.message.reply_text(f"Error: {e}")


async def cmd_quit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /quit, /end, /exit — exit DM mode gracefully."""
    try:
        await update.message.reply_text(
            "👋 *Saliendo del modo DM.*\n\n"
            "¡Hasta la próxima aventura!\n"
            "El bot seguirá corriendo en el grupo para recibir comandos.\n"
            "Usa /newgame o /resume para volver a jugar.",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        log.exception("cmd_quit error")
        try:
            await update.message.reply_text("👋 Hasta la próxima!")
        except Exception:
            pass


@with_audit("cmd_end")
async def cmd_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /end — closes the campaign.

    Flow:
    1. Verify active campaign
    2. Mark campaign as completed
    3. Reset chat state
    """
    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.active_campaign:
            await update.message.reply_text(
                "⚠️ No hay campaña activa. Usa /newgame para empezar."
            )
            return

        # Load full state
        state = load_state(cs.active_campaign)
        if state is None:
            await update.message.reply_text("⚠️ Campaña no encontrada.")
            return

        # Check if already completed
        campaign_status = state.get("campaign", {}).get("status", "active")
        if campaign_status == "completed":
            await update.message.reply_text(
                "⚠️ Esta campaña ya fue completada. Usa /newgame para crear una nueva."
            )
            return

        # Generate epilogue via NarrativeGenerator
        ng = NarrativeGenerator()
        closure = ng.generate_closure(state, language=Language.ES)
        campaign_name = state.get("campaign", {}).get("name", "La aventura")
        epilogue_text = f"🎭 *EPÍLOGO — {campaign_name}*\n\n{closure['narrative']}"

        # Mark campaign as completed
        state["campaign"]["status"] = "completed"
        state["campaign"]["completed_at"] = datetime.utcnow().isoformat()
        state["campaign"]["epilogue"] = epilogue_text

        # Move any remaining active quests to completed
        active_quests = state.get("quests", {}).get("active", [])
        if active_quests:
            state.setdefault("quests", {}).setdefault("completed", [])
            for quest_id in active_quests:
                if quest_id not in state["quests"]["completed"]:
                    state["quests"]["completed"].append(quest_id)
            state["quests"]["active"] = []

        save_state(cs.active_campaign, state)

        # Send epilogue to group
        await update.message.reply_text(
            epilogue_text,
            parse_mode=ParseMode.MARKDOWN,
        )

        # Reset chat state
        chat_id = cs.active_campaign
        cs.active_campaign = None
        cs.combat_state = None
        cs.characters = {}
        cs.pending_attacks = {}
        cs.pending_spell = None
        cs.pending_skill_check = None
        cs.pending_save = None
        cs.pending_setup = None
        chat_data["_hermes_state"] = cs

        await update.message.reply_text(
            "✅ *Campaña cerrada exitosamente.*\n\n"
            "¡Gracias por jugar! Usa /newgame para comenzar una nueva aventura.",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        log.exception("cmd_end error")
        try:
            await update.message.reply_text(f"Error cerrando campaña: {e}")
        except Exception:
            pass


async def _closure_image_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback to generate closure image after epilogue is sent."""
    try:
        chat_id = context.job.data.get("chat_id")
        prompt = context.job.data.get("prompt")
        campaign_id = context.job.data.get("campaign_id")

        if not prompt or not chat_id:
            return

        # Determine provider from campaign state or env fallback
        from dm.image_event_handler import ImageContext, ImageEventHandler
        from dm.image_provider import get_provider
        from state.state_manager import load_state

        provider_name = os.environ.get("IMAGE_PROVIDER", "pollinations")
        if campaign_id:
            state = load_state(campaign_id)
            if state:
                provider_name = state.get("campaign", {}).get("image_provider", provider_name)

        provider = get_provider(provider_name)
        handler = ImageEventHandler(provider=provider, enabled=True)
        ctx = ImageContext(
            scene_type="session_end",
            narrative=prompt,
            genre="fantasy",
            mood="epic",
        )
        image_result = await handler.maybe_generate(ctx)
        img_path = image_result.path if image_result else None

        if img_path and os.path.exists(img_path):
            with open(img_path, "rb") as f:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=f,
                    caption="🎨 *Cierre de Campaña*\n_Generada automaticamente_",
                    parse_mode=ParseMode.MARKDOWN,
                )
    except Exception as e:
        log.warning(f"Closure image generation failed: {e}")


async def cmd_audit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /audit [limit] — show recent audit events (admin only)."""
    try:
        # Admin check
        user_id = update.effective_user.id
        if settings.ADMIN_USER_IDS and user_id not in settings.ADMIN_USER_IDS:
            await update.message.reply_text("⛔ Solo admins pueden ver el audit log.")
            return

        from scripts.audit_viewer import AuditViewer

        viewer = AuditViewer()
        limit = (
            int(context.args[0]) if context.args and context.args[0].isdigit() else 20
        )
        report = viewer.format_report(limit=limit)
        await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.exception("cmd_audit error")
        await update.message.reply_text(f"Error: {e}")


# ------------------------------------------------------------------
# Combat helpers
# ------------------------------------------------------------------


def _get_timer_seconds(cs: ChatState) -> int:
    """Get turn_timer_seconds from CampaignSettings, fallback to 120."""
    if cs.active_campaign:
        settings = get_settings(cs.active_campaign)
        return settings.turn_timer_seconds
    return 120


def cancel_countdown(
    job_queue: JobQueue | None, chat_id: int, chat_data: dict | None = None, cs: ChatState | None = None
) -> None:
    """
    Cancel all 'turn_countdown' jobs for a chat and delete the countdown message.
    Safe to call even if no jobs/messages exist.
    """
    if job_queue is not None:
        for job in job_queue.get_jobs_by_name("turn_countdown"):
            job.schedule_removal()
    if chat_data is not None and cs is not None and cs.countdown_message_id:
        try:
            # We need the bot to delete — pass chat_data for deletion
            # Bot is accessed via context.bot in the calling command
            pass
        except Exception:
            pass


async def _delete_countdown_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int | None) -> None:
    """Delete the countdown message if it exists."""
    if message_id is None:
        return
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass  # Message may already be deleted or expired


async def _advance_turn_with_countdown(
    context: ContextTypes.DEFAULT_TYPE,
    data: dict,
    chat_data: dict,
    expired: bool = False,
) -> None:
    """
    Advance to the next turn and start a new countdown for the new character.
    Called when countdown expires or when a player acts.
    """
    chat_id = data["chat_id"]
    cs: ChatState = chat_data.get("_hermes_state", ChatState())

    if not cs.combat_state or not cs.combat_state.active:
        return

    # Cancel all existing countdown jobs
    job_queue = getattr(context.application, "job_queue", None)
    if job_queue is not None:
        for job in job_queue.get_jobs_by_name("turn_countdown"):
            job.schedule_removal()

    # Delete old countdown message
    old_msg_id = cs.countdown_message_id
    cs.countdown_message_id = None
    if old_msg_id:
        await _delete_countdown_message(context, chat_id, old_msg_id)

    # Send "expired" message if this was a timeout
    if expired:
        expired_character = data["character"]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ ¡Tiempo agotado!\n🎯 Turno de *{expired_character}* — pasando al siguiente.",
            parse_mode=ParseMode.MARKDOWN,
        )
        await asyncio.sleep(0.5)

    # Advance turn
    result = next_turn(cs.combat_state)

    if "error" in result:
        end_combat(cs.combat_state)
        cs.combat_state = None
        chat_data["_hermes_state"] = cs
        await context.bot.send_message(
            chat_id=chat_id,
            text="⛔ El combate ha terminado.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    next_character = cs.combat_state.current_turn
    timer_seconds = _get_timer_seconds(cs)
    round_num = cs.combat_state.round

    # Resetear estados persistentes de acciones del personaje que acaba de actuar
    for char_key, char in cs.characters.items():
        if char.name.lower() == next_character.lower():
            continue  # No resetear del que va a actuar ahora
        # Reset de flags de acciones que duran 1 turno
        char.has_disengaged = False
        char.has_dashed = False
        char.is_helping = False
        char.helping_target = None
        char.is_dodging = False
        char.is_hiding = False
        # Ready action se pierde si no se usó
        if char.pending_ready:
            char.pending_ready = None

    # If timer is disabled, just send summary and stop
    if timer_seconds <= 0:
        summary = _fmt_combat_summary(cs.combat_state)
        chat_data["_hermes_state"] = cs
        await context.bot.send_message(
            chat_id=chat_id, text=summary, parse_mode=ParseMode.MARKDOWN
        )
        return

    # Send new countdown message
    bar = "█" * 10
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏱️ Turno de *{next_character}* — Round {round_num}\n`[{bar}] {timer_seconds}s`",
        parse_mode=ParseMode.MARKDOWN,
    )

    cs.countdown_message_id = msg.message_id
    cs.countdown_remaining = timer_seconds
    chat_data["_hermes_state"] = cs

    # Schedule countdown: run once at 1s, which then re-schedules itself
    job_queue = getattr(context.application, "job_queue", None)
    if job_queue is not None:
        job_queue.run_once(
            _live_countdown_edit,
            1,
            name="turn_countdown",
            data={
                "chat_id": chat_id,
                "character": next_character,
                "remaining": timer_seconds - 1,
                "total": timer_seconds,
                "round": round_num,
                "message_id": msg.message_id,
            },
        )


async def _live_countdown_edit(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Called every 1 second while a countdown is active.
    Edits the countdown message with updated bar + remaining time.
    When remaining <= 0, advances turn and starts new countdown.
    """
    job = context.job
    data = job.data
    chat_id = data["chat_id"]
    remaining = data["remaining"]
    total = data["total"]
    current_char = data["character"]

    # Decrement remaining
    remaining -= 1
    data["remaining"] = remaining

    # Get chat state
    chat_data = context.application.chat_data.get(chat_id, {})
    cs: ChatState = chat_data.get("_hermes_state", ChatState())

    # Check if combat is still active and this message is still the current one
    if (
        not cs.combat_state
        or not cs.combat_state.active
        or cs.countdown_message_id != data["message_id"]
    ):
        # Combat ended or message was replaced — stop this countdown
        return

    if remaining < 0:
        # Time's up — advance turn
        await _advance_turn_with_countdown(
            context, data, chat_data, expired=True
        )
        return

    # Update remaining in chat state for reference
    cs.countdown_remaining = remaining
    chat_data["_hermes_state"] = cs

    # Calculate bar proportions (10 chars total)
    filled = min(10, max(0, int((remaining / total) * 10)))
    bar = "█" * filled + "░" * (10 - filled)

    # Emoji urgency
    if remaining > 30:
        icon = "⏱️"
    elif remaining > 10:
        icon = "⚠️"
    else:
        icon = "🚨"

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=data["message_id"],
            text=f"{icon} Turno de *{current_char}* — Round {data['round']}\n`[{bar}] {remaining}s`",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        # Message may have been deleted or Telegram rate limit — stop
        return

    # Re-schedule for next second
    job_queue = getattr(context.application, "job_queue", None)
    if job_queue is not None:
        job_queue.run_once(
            _live_countdown_edit,
            1,
            name="turn_countdown",
            data={**data, "remaining": remaining},
        )


async def _turn_timer_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Called when turn timer expires — nudge the group (legacy one-shot)."""
    try:
        chat_id = context.job.chat_id
        current_turn = context.job.data.get("current_turn", "alguien")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ *¡Tiempo de turno agotado!*\n🎯 Turno de *{current_turn}* — pasando al siguiente.",
            parse_mode=ParseMode.MARKDOWN,
        )
        # Advance turn — fetch chat_data state and call next_turn
        chat_data = context.application.chat_data.get(chat_id, {})
        cs: ChatState = chat_data.get("_hermes_state", ChatState())
        if cs.combat_state and cs.combat_state.active:
            result = next_turn(cs.combat_state)
            if "error" in result:
                end_combat(cs.combat_state)
                cs.combat_state = None
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="⚔️ El combate ha terminado.",
                )
            else:
                summary = _fmt_combat_summary(cs.combat_state)
                await context.bot.send_message(
                    chat_id=chat_id, text=summary, parse_mode=ParseMode.MARKDOWN
                )
            chat_data["_hermes_state"] = cs
    except Exception:
        log.exception("_turn_timer_callback error")


# ------------------------------------------------------------------
# Application builder & __main__
# ------------------------------------------------------------------


async def cmd_imagen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /imagen — genera una imagen de la escena actual.
    Si image_generation está desactivado, muestra un mensaje informativo.
    También se llama automáticamente después de cada escena nueva si está activado.
    """
    import os
    import subprocess

    try:
        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.active_campaign:
            await update.message.reply_text(
                "⚠️ No hay campaña activa. Usa /newgame para empezar."
            )
            return

        settings = get_settings(cs.active_campaign)
        if not settings.image_generation:
            await update.message.reply_text(
                "🎨 *Generación de imágenes desactivada.*\n\n"
                "Usa `/configuracion imagen on` para activar.\n"
                "Cuando esté activada, cada escena nueva "
                "generará una imagen automáticamente.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        await update.message.reply_text("🎨 Generando imagen de la escena...")

        # Obtener información de la escena actual
        location = ""
        try:
            state = load_state(cs.active_campaign)
            if state:
                location = state.get("campaign", {}).get("current_location", "")
        except Exception:
            pass

        # Construir prompt desde la ubicación
        if location:
            prompt = f"a fantasy {location} scene, cinematic, D&D 5e art style"
        else:
            prompt = "a fantasy adventure scene, cinematic, D&D 5e art style"

        # Generar imagen
        venv_python = "/home/hermes/hermesdm/venv/bin/python3"
        script_path = "/home/hermes/scripts/image_from_scene.py"
        output_path = f"/tmp/hermesdm_imagen_{cs.active_campaign[:8]}.png"

        os.makedirs("/tmp/hermesdm", exist_ok=True)

        try:
            result = subprocess.run(
                [
                    venv_python,
                    script_path,
                    prompt,
                    "--output",
                    output_path,
                    "--timeout",
                    "60",
                ],
                capture_output=True,
                text=True,
                timeout=70,
            )

            if result.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                if file_size > 5000:
                    # Enviar imagen al chat
                    with open(output_path, "rb") as f:
                        await update.message.reply_photo(
                            photo=f,
                            caption=f"🎨 *{location or 'Escena'}*\n_Generada via Pollinations_",
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    # Guardar referencia en el estado
                    try:
                        state = load_state(cs.active_campaign)
                        if state:
                            generated = state.get("generated_images", [])
                            generated.append(
                                {
                                    "path": output_path,
                                    "prompt": prompt,
                                    "location": location,
                                }
                            )
                            state["generated_images"] = generated[-10:]  # keep last 10
                            save_state(cs.active_campaign, state)
                    except Exception:
                        pass  # No guardar estado no es crítico
                else:
                    await update.message.reply_text(
                        "⚠️ La imagen generada parece estar corrupta. "
                        "Intentá de nuevo en unos segundos."
                    )
            else:
                await update.message.reply_text(
                    f"⚠️ Error generando imagen:\n`{result.stderr[:200]}`",
                    parse_mode=ParseMode.MARKDOWN,
                )
        except subprocess.TimeoutExpired:
            await update.message.reply_text(
                "⚠️ Timeout generando imagen (70s). "
                "El servidor de Pollinations puede estar lento. "
                "Intentá de nuevo."
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error: {e}")

    except Exception as e:
        log.exception("cmd_imagen error")
        try:
            await update.message.reply_text(f"Error: {e}")
        except Exception:
            pass


def build_app() -> Application:
    """Build and configure the Telegram bot application."""
    jq = JobQueue()
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).job_queue(jq).build()
    jq.set_application(app)

    # Register command handlers — D&D commands only work in the allowed group
    # (filtered by chat_id to prevent responses in Sherman's 1:1)
    app.add_handler(CommandHandler("start", cmd_start))  # general, no filter

    # HermesDM game commands — filtered to group only (if ALLOWED_GROUP_ID is set)
    app.add_handler(
        CommandHandler("help", cmd_help, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("newgame", cmd_newgame, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("setup", cmd_setup, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    # Setup approval / cancel commands (work as /perfecto, /arrancamos, /cancel_setup, /cancel)
    app.add_handler(CommandHandler("perfecto", lambda u, c: _cmd_approve_setup(u, c)))
    app.add_handler(CommandHandler("arrancamos", lambda u, c: _cmd_approve_setup(u, c)))
    app.add_handler(CommandHandler("cancel_setup", lambda u, c: _cmd_cancel_setup(u, c)))
    app.add_handler(CommandHandler("cancel", lambda u, c: _cmd_cancel_setup(u, c)))
    app.add_handler(
        CommandHandler("begin", cmd_begin, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("join", cmd_join, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("roll", cmd_roll, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("attack", cmd_attack, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("cast", cmd_cast, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("skill", cmd_skill, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("status", cmd_status, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("hp", cmd_hp, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler(
            "inventory", cmd_inventory, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None
        )
    )
    app.add_handler(
        CommandHandler("give", cmd_give, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("talk", cmd_talk, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("npcs", cmd_npcs, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("npcsearch", cmd_npcsearch, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("npcnote", cmd_npcnote, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("npcmemory", cmd_npcmemory, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("map", cmd_map, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("quests", cmd_quests, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("recap", cmd_recap, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("resume", cmd_resume, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("endturn", cmd_endturn, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("campaign", cmd_campaign, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("start", cmd_start, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("save", cmd_save, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler(
            "configuracion", cmd_configuracion, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None
        )
    )

    # Combat commands
    app.add_handler(
        CommandHandler(
            "startcombat", cmd_startcombat, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None
        )
    )
    app.add_handler(
        CommandHandler(
            "begincombat", cmd_startcombat, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None
        )
    )  # alias
    app.add_handler(
        CommandHandler(
            "endcombat", cmd_endcombat, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None
        )
    )

    # Game commands (!attack, !confirm, !cancel, !attack_status)
    # Filtered to group only
    register_game_handlers(app, settings.ALLOWED_GROUP_ID)

    # Exit DM mode — group only
    app.add_handler(
        CommandHandler("quit", cmd_quit, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("end", cmd_end, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("exit", cmd_quit, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )

    # Admin audit log — group only
    app.add_handler(
        CommandHandler("audit", cmd_audit, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )

    # Narrative actions (no dice roll) — group only
    app.add_handler(
        CommandHandler("me", cmd_me, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )

    # Image generation — group only
    app.add_handler(
        CommandHandler("imagen", cmd_imagen, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )
    app.add_handler(
        CommandHandler("image", cmd_imagen, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )  # English alias
    app.add_handler(
        CommandHandler("countdown", cmd_countdown, filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None)
    )

    # Plan B: /j and /act for async player actions
    # CommandHandler for /j (takes precedence over MessageHandler)
    app.add_handler(
        CommandHandler(
            "j",
            cmd_j,
            filters=filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else None,
        )
    )
    # MessageHandler for /act  prefix (fallback for /act  text style)
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.ChatType.SUPERGROUP & filters.Chat(settings.ALLOWED_GROUP_ID) if settings.ALLOWED_GROUP_ID else filters.TEXT & filters.ChatType.SUPERGROUP,
            _j_action_handler,
        )
    )

    # Catch-all message handler to prevent unknown command errors
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _echo_handler))

    return app


async def cmd_j(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /j <action> — CommandHandler version of player action.
    /j is the shorthand for /act, registered as a native Telegram command
    so it works reliably in groups (CommandHandler intercepts / commands).
    """
    action_text = " ".join(context.args).strip() if context.args else ""
    # Delegate to the shared action handler core
    await _handle_player_action(update, context, action_text)


async def _j_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /act <action> messages in groups — Plan B async player actions.
    Also handles /j <action> as fallback (CommandHandler handles /j natively).
    Delegates to ActionRouter for clean parse → resolve → narrate flow.
    Optionally triggers image generation for dramatic scenes.
    """
    try:
        text = update.message.text or ""
        if text.startswith("/act "):
            action_text = text[5:].strip()
        elif text.startswith("/j "):
            action_text = text[3:].strip()
        else:
            return  # Not a /act or /j action, ignore

        await _handle_player_action(update, context, action_text)
    except Exception as e:
        log.exception("_j_action_handler error")
        try:
            await update.message.reply_text(f"Error procesando acción: {e}")
        except Exception:
            pass


async def _handle_player_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action_text: str) -> None:
    """
    Core shared logic for processing a player action text.
    Used by both cmd_j (CommandHandler) and _j_action_handler (MessageHandler).
    """
    try:
        if not action_text:
            await update.message.reply_text(
                "⚠️ Uso: /j <tu acción> o /act <tu acción>\nEjemplo: /j Ataco al dragón con mi espada"
            )
            return

        chat_data = context.chat_data or {}
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.active_campaign:
            await update.message.reply_text(
                "⚠️ No hay campaña activa. Usa /setup para empezar."
            )
            return

        # ── Reload characters from state if chat_data was lost (bot restart) ───
        if not cs.characters:
            from bot.character_sheet import Character
            st = load_state(cs.active_campaign)
            if st:
                for key, char_data in st.get("characters", {}).items():
                    try:
                        cs.characters[key] = Character.from_dict(char_data)
                    except Exception:
                        pass
                # Rebuild telegram_characters mapping if possible
                # (we can't know tg_id from state, so fallback name matching will be used)

        # ── Find character ────────────────────────────────────────────────────
        # Primary: look up by Telegram user ID (set on /join)
        tg_id = update.effective_user.id
        char = cs.character_for_tg_id(tg_id)

        # Fallback: try by first_name if telegram_id lookup failed
        if char is None:
            sender_name = update.effective_user.first_name or ""
            char = cs.character_for(sender_name)
            # Try partial match if exact fails
            if char is None:
                for key, c in cs.characters.items():
                    if (
                        sender_name.lower() in c.name.lower()
                        or c.name.lower() in sender_name.lower()
                    ):
                        char = c
                        break

        if char is None:
            await update.message.reply_text(
                f"⚠️ No encontré personaje para '{sender_name}'.\n"
                f"Players registrados: {', '.join(cs.active_character_names())}\n"
                f"Usa /join <nombre> <clase> para registrarte."
            )
            return

        # Persist recovered characters back to chat_data
        chat_data["_hermes_state"] = cs

        # ── Load game state ───────────────────────────────────────────────────
        state = load_state(cs.active_campaign) or {
            "campaign": {},
            "characters": {},
            "npcs": {},
        }

        # ── Route action through ActionRouter ─────────────────────────────────
        from adapters.mode_b.action_router import ActionRouter
        from bot.dice_animation import animate_dice_roll
        from dm.pacing_engine import create_pacing_engine

        # Create pacing engine and decide scene type
        pacing = create_pacing_engine(state)
        scene_type = pacing.get_next_scene_type(action_text)
        milestone_ctx = pacing.get_milestone_context()

        router = ActionRouter(state=state, character=char)
        try:
            result = router.route(update, action_text, scene_type_override=scene_type, milestone_context=milestone_ctx)
        except Exception as e:
            log.exception(f"Action routing failed: {e}")
            await edit_text(bot, chat_id, msg_id, "Error procesando acción. Reiniciá la campaña si persiste.")
            return

        if not result:
            await edit_text(bot, chat_id, msg_id, "No se pudo procesar la acción. Probá de nuevo.")
            return

        # ── Check milestone advancement ────────────────────────────────────────
        try:
            if pacing.check_milestone_advance(result.narrative):
                from datetime import datetime as _dt
                pacing.arc.advance_milestone(timestamp=_dt.utcnow().isoformat())
                # If we just advanced, get new milestone info
                new_ctx = pacing.get_milestone_context()
                if not new_ctx.get("campaign_complete"):
                    result.narrative += (
                        f"\n\n🎯 *Avance de trama:* Pasás a '{new_ctx['current_milestone_id']}' — "
                        f"{new_ctx['current_milestone_description'][:60]}..."
                    )
        except Exception:
            log.exception("Pacing milestone check failed")

        # Record this scene in the arc
        pacing.record_scene(scene_type)

        # Save updated story_arc back to state
        state["story_arc"] = pacing.arc.to_dict()
        from state.state_manager import save_state
        save_state(cs.active_campaign, state)

        # ── Send initial message to get message_id ───────────────────────────
        initial_text = (
            f"🎲 *{char.name} tira dados...*\n"
            f"_Procesando acción..._"
        )
        sent_msg = await update.message.reply_text(
            initial_text, parse_mode=ParseMode.MARKDOWN
        )
        message_id = sent_msg.message_id
        chat_id = update.effective_chat.id

        # ── Animate dice roll (handles all formatting + animation) ───────────
        await animate_dice_roll(
            context=context,
            chat_id=chat_id,
            message_id=message_id,
            action_type=result.action_type,
            character_name=char.name,
            mechanic_inline=result.mechanic_inline,
            narrative=result.narrative,
            nat_20=result.nat_20,
            nat_1=result.nat_1,
        )

        # ── Auto-generate scene image if triggered ─────────────────────────────
        await _maybe_send_scene_image(
            context=context,
            chat_id=chat_id,
            result=result,
            character_name=char.name,
        )

        # ── Persist state so hermesdm-web stays in sync ───────────────────────
        from state.state_manager import sync_chatstate_to_state, append_history
        sync_chatstate_to_state(cs.active_campaign, cs)
        append_history(
            cs.active_campaign,
            f"[{char.name}] {result.narrative}",
            entry_type=result.action_type,
        )

    except Exception as e:
        log.exception("_j_action_handler error")
        try:
            await update.message.reply_text(f"Error procesando acción: {e}")
        except Exception:
            pass


# -----------------------------------------------------------------------
# Demo: Turn countdown with live progress bar
# -----------------------------------------------------------------------


async def _countdown_edit(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Edit the countdown message every second."""
    job = context.job
    chat_id = job.chat_id
    message_id = job.data["message_id"]
    remaining = job.data["remaining"]
    character = job.data["character"]
    total = job.data["total"]

    remaining -= 1
    job.data["remaining"] = remaining

    if remaining <= 0:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"⏰ *¡Tiempo agotado!*\n🎯 Turno de *{character}* — pasando al siguiente.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Progress bar: ████████░░ (10 chars = 100%)
    filled = int((remaining / total) * 10)
    bar = "█" * filled + "░" * (10 - filled)

    # Emoji urgency when low
    if remaining <= 10:
        icon = "🚨"
    elif remaining <= 30:
        icon = "⚠️"
    else:
        icon = "⏱️"

    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=(
            f"{icon} *Turno de {character}*\n"
            f"`[{bar}] {remaining}s`"
        ),
        parse_mode=ParseMode.MARKDOWN,
    )

    # Schedule next update
    context.application.job_queue.run_once(
        _countdown_edit,
        1,
        data={
            "message_id": message_id,
            "remaining": remaining,
            "character": character,
            "total": total,
        },
        name=f"countdown_demo_{message_id}",
        chat_id=chat_id,
    )


async def cmd_countdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /countdown <seconds> <character> — demo of live countdown message.
    Shows a progress bar that updates every second via message edits.
    """
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "⏱️ *Demo: Countdown con barra de progreso*\n\n"
                "Uso: /countdown <segundos> <personaje>\n"
                "Ejemplo: /countdown 30 Valdric\n\n"
                "Esto envía un mensaje que se actualiza cada segundo\n"
                "mostrando una barra de progreso visual.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        try:
            seconds = int(args[0])
            if seconds <= 0 or seconds > 120:
                await update.message.reply_text("⏱️ Elegí entre 1 y 120 segundos.")
                return
        except ValueError:
            await update.message.reply_text("⚠️ El primer argumento debe ser un número de segundos.")
            return

        character = " ".join(args[1:]) or "Jugador"
        total = seconds

        # Send initial message
        bar = "█" * 10
        msg = await update.message.reply_text(
            f"⏱️ *Turno de {character}*\n`[{bar}] {seconds}s`",
            parse_mode=ParseMode.MARKDOWN,
        )

        # Schedule first edit in 1 second
        context.application.job_queue.run_once(
            _countdown_edit,
            1,
            data={
                "message_id": msg.message_id,
                "remaining": seconds - 1,
                "character": character,
                "total": total,
            },
            name=f"countdown_demo_{msg.message_id}",
            chat_id=update.effective_chat.id,
        )

    except Exception as e:
        log.exception("cmd_countdown error")
        await update.message.reply_text(f"Error: {e}")


async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /me <action> — broadcast a narrative action without rolling dice."""
    try:
        action_text = " ".join(context.args) if context.args else ""
        if not action_text:
            await update.message.reply_text(
                "Usage: /me <acción narrativa>\n"
                "Ejemplo: /me se esconde detrás de la roca\n"
                "Esto no tira dados — es puramente descriptivo."
            )
            return

        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.active_campaign:
            await update.message.reply_text(
                "⚠️ No hay campaña activa. Usa /newgame para empezar."
            )
            return

        sender_name = update.effective_user.first_name or ""
        char = cs.character_for(sender_name)
        if char is None:
            for key, c in cs.characters.items():
                if (
                    sender_name.lower() in c.name.lower()
                    or c.name.lower() in sender_name.lower()
                ):
                    char = c
                    break

        if char is None:
            await update.message.reply_text(
                f"⚠️ No encontré personaje para '{sender_name}'.\n"
                f"Usa /join <nombre> <clase> para registrarte."
            )
            return

        # Broadcast as italic narrative
        await update.message.reply_text(
            f"*{char.name} {action_text}*",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        log.exception("cmd_me error")
        try:
            await update.message.reply_text(f"Error: {e}")
        except Exception:
            pass


async def _echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch non-command text messages with a friendly nudge."""
    try:
        text = update.message.text or ""

        # OOC comments — ignore silently (e.g. "#pensando", "#hablo con el grupo")
        if text.startswith("#"):
            return

        cs: ChatState = context.chat_data.get("_hermes_state", ChatState())

        # Setup mode: delegate to setup text handler (describing or preview)
        if getattr(cs, "setup_mode", False) and getattr(cs, "setup_state", "") in ("describing", "preview"):
            await _handle_setup_text(update, context)
            return

        # Active campaign: demand a /act action first
        if cs.active_campaign:
            await update.message.reply_text(
                "🎲 Usá /j <tu acción> o /act <tu acción>. Ejemplo: /j ataco al dragón\nPara acciones sin dado: /me <acción>"
            )
            return

        # No active campaign — general help
        await update.message.reply_text(
            "No entendí eso. Escribe /help para ver los comandos disponibles."
        )
    except Exception:
        log.exception("_echo_handler error")


def main() -> None:
    """Entry point for the hermesdm CLI command (pip install -e .)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )
    app = build_app()
    log.info("HermesDM bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
