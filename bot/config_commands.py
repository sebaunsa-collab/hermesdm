"""
config_commands.py — Campaign settings via /configuracion command.

Usage:
    /configuracion                        → show all settings
    /configuracion free on|off           → ASCII art vs MiniMax images
    /configuracion dificultad easy|normal|hard
    /configuracion tono serious|funny|dark|epic
    /configuracion timer <seconds>        → 0 = off
    /configuracion suerte <+/-bonus>      → luck bonus to all checks
    /configuracion dados on|off           → dramatic dice narration
"""

from __future__ import annotations

import textwrap

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from state.state_manager import get_settings, update_settings

HELP_TEXT = textwrap.dedent("""
    ⚙️ */configuracion* — Configurar campaign

    Sin argumentos → muestra configuración actual

    Con argumento → cambia un setting:
    `/configuracion imagen on`     → generar imagen de cada escena (Pollinations, gratis)
    `/configuracion imagen off`    → no generar imágenes automáticamente
    `/configuracion dificultad normal`  → easy | normal | hard
    `/configuracion tono serious` → serious | funny | dark | epic
    `/configuracion timer 120`    → segundos/turno (0=off)
    `/configuracion suerte +1`    → bonus a todos los checks
    `/configuracion dados on`     → narración dramática de dados
""").strip()


async def cmd_configuracion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /configuracion [key] [value].
    Shows current settings or updates one.
    """
    try:
        chat_data = context.chat_data
        cs = chat_data.get("_hermes_state")

        if cs is None or cs.active_campaign is None:
            await update.message.reply_text(
                "No hay campaign activa. Usa /newgame para crear una.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        campaign_id = cs.active_campaign

        # No args → show current settings
        if not context.args:
            settings = get_settings(campaign_id)
            await update.message.reply_text(
                settings.summary(),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Parse: /configuracion <key> [value]
        key = context.args[0].lower()
        value = context.args[1].lower() if len(context.args) > 1 else ""

        # Special case: help alias
        if key in ("help", "ayuda", "?"):
            await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN)
            return

        # Without value, explain the setting
        if not value:
            explain = {
                "imagen": "`/configuracion imagen on` → activa generación de imágenes (Pollinations, gratis)\n`/configuracion imagen off` → desactiva",
                "image_gen": "`/configuracion imagen on` → activa generación de imágenes (Pollinations, gratis)\n`/configuracion imagen off` → desactiva",
                "free": "`/configuracion free on` → activa imágenes (Pollinations)\n`/configuracion free off` → desactiva",
                "dificultad": "`/configuracion dificultad normal` → easy | normal | hard",
                "difficulty": "`/configuracion difficulty normal` → easy | normal | hard",
                "tono": "`/configuracion tono serious` → serious | funny | dark | epic",
                "tone": "`/configuracion tone epic` → serious | funny | dark | epic",
                "timer": "`/configuracion timer 120` → segundos (0=off)",
                "turn_timer": "`/configuracion turn_timer 0` → segundos (0=off)",
                "suerte": "`/configuracion suerte +1` → bonus a checks",
                "luck": "`/configuracion luck -1` → bonus a checks",
                "dados": "`/configuracion dados on` → on | off",
            }
            if key in explain:
                await update.message.reply_text(
                    f"Cambiar *{key}*:\n{explain[key]}",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await update.message.reply_text(
                    f"Opción desconocida: *{key}*\n\n{HELP_TEXT}",
                    parse_mode=ParseMode.MARKDOWN,
                )
            return

        # Apply update
        success, message, settings = update_settings(campaign_id, key, value)

        if success:
            await update.message.reply_text(
                f"✅ {message}",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(
                f"❌ {message}\n\n{HELP_TEXT}",
                parse_mode=ParseMode.MARKDOWN,
            )

    except Exception as e:
        import logging
        logging.exception("cmd_configuracion error")
        try:
            await update.message.reply_text(f"Error: {e}")
        except Exception:
            pass
