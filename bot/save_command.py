"""
save_command.py — Saving throw resolution for HermesDM.

Usage:
    /save <stat> [dc]
    /save con       → CON save vs DC 10 (default)
    /save wis 15    → WIS save vs DC 15

Supports: str, dex, con, int, wis, cha
"""

from __future__ import annotations

import textwrap

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.dice_engine import resolve_check, roll
from campaign_settings import Difficulty_get_dc
from state.state_manager import get_settings, load_state

STATS = {
    "str": "Strength",
    "dex": "Dexterity",
    "con": "Constitution",
    "int": "Intelligence",
    "wis": "Wisdom",
    "cha": "Charisma",
}

DEFAULT_DC = 10

HELP_TEXT = textwrap.dedent("""
    🎲 *Saving Throws*

    `/save <stat>` — Default DC 10
    `/save dex 15` — DC override

    Supported: str, dex, con, int, wis, cha
    Advantage/disadvantage via context.
""").strip()


async def cmd_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /save <stat> [dc].
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
        state = load_state(campaign_id)

        if state is None:
            await update.message.reply_text("Campaign no encontrada.")
            return

        # Get player character for this user
        user_id = str(update.effective_user.id)
        char = _find_character_for_user(state, user_id)
        if char is None:
            await update.message.reply_text(
                "No tienes personaje en esta campaign. Usa /newgame primero.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Parse arguments
        if not context.args:
            await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN)
            return

        stat = context.args[0].lower()
        if stat not in STATS:
            await update.message.reply_text(
                f"Stat desconocido: *{stat}*\nUsa: str, dex, con, int, wis, cha",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Parse DC
        dc = DEFAULT_DC
        if len(context.args) > 1:
            try:
                dc = int(context.args[1])
            except ValueError:
                await update.message.reply_text(
                    f"DC inválido: *{context.args[1]}*\nUsa un número.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

        # Apply difficulty modifier
        settings = get_settings(campaign_id)
        dc = Difficulty_get_dc(settings.difficulty, dc)

        # Roll
        char_name = char.get("name", "Character")
        char_level = char.get("level", 1)
        stat_value = char.get("stats", {}).get(stat, 10)

        # Proficiency bonus (simplified: +2 at level 1-4, +3 at 5-8, etc.)
        prof_bonus = 2 + (char_level - 1) // 4
        relevant_saves = char.get("saving_throws", [])
        has_proficiency = stat.upper() in relevant_saves

        modifier = (stat_value - 10) // 2
        total_bonus = modifier + (prof_bonus if has_proficiency else 0)

        # Roll d20
        result = roll("d20")
        natural = result["rolls"][0]
        total_roll = result["total"] + total_bonus

        # Resolve
        advantage = False
        disadvantage = False
        check_result = resolve_check(result, dc, advantage, disadvantage)

        # Build response
        char_class = char.get("class", "Unknown").capitalize()
        stat_full = STATS[stat]

        response_lines = [
            f"🎲 *Saving Throw — {stat_full}*\n",
            f"*{char_name}* (Lvl {char_level} {char_class})",
            f"Roll: d20 {'+' if total_bonus >= 0 else ''}{total_bonus}  →  [{natural}] + {total_bonus}",
            f"DC: {dc}",
            f"Resultado: *{total_roll}* vs DC {dc}",
            "",
        ]

        if check_result["success"]:
            if natural == 20:
                response_lines.append("✨ **NATURAL 20!** Éxito crítico!")
            else:
                response_lines.append("✅ *Success!*")
        else:
            if natural == 1:
                response_lines.append("💀 **NATURAL 1!** Fallo crítico!")
            else:
                response_lines.append("❌ *Failed.*")

        # Add luck bonus if any
        if settings.luck_bonus != 0:
            response_lines.append(f"\n🍀 Suerte: {'+' if settings.luck_bonus > 0 else ''}{settings.luck_bonus} (config active)")

        # Dramatic dice mode
        if settings.dramatic_dice:
            response_lines.append("")
            response_lines.append(_dramatic_description(stat, check_result["success"], natural))

        await update.message.reply_text(
            "\n".join(response_lines),
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        import logging
        logging.exception("cmd_save error")
        try:
            await update.message.reply_text(f"Error: {e}")
        except Exception:
            pass


def _find_character_for_user(state: dict, user_id: str) -> dict | None:
    """Find the character belonging to a Telegram user_id in the campaign state."""
    characters = state.get("characters", {})
    for char in characters.values():
        if str(char.get("player_id", "")) == user_id:
            return char
    # Fallback: return first character (single-player mode)
    if characters:
        return next(iter(characters.values()))
    return None


def _dramatic_description(stat: str, success: bool, natural: int) -> str:
    """Flavor text for dramatic dice mode."""
    saves = {
        "str": {
            True: [
                "You brace against the force and hold your ground.",
                "Your muscles strain but you refuse to fall.",
            ],
            False: [
                "The force throws you aside like a ragdoll.",
                "You lose your footing and collapse.",
            ],
        },
        "dex": {
            True: [
                "You dive aside with cat-like reflexes.",
                "You twist mid-air and land on your feet.",
            ],
            False: [
                "You're too slow — the effect catches you full.",
                "You stumble and take the full brunt.",
            ],
        },
        "con": {
            True: [
                "Your body resists the poison/disease/effect.",
                "You shake it off through sheer endurance.",
            ],
            False: [
                "The affliction takes hold. You feel it spreading.",
                "Your constitution fails you.",
            ],
        },
        "int": {
            True: [
                "The pieces fall into place — you understand.",
                "Your mind cuts through the illusion like a blade.",
            ],
            False: [
                "The truth remains just out of reach.",
                "The mind-trick works on you.",
            ],
        },
        "wis": {
            True: [
                "You sense the deception. Something is wrong here.",
                "Your instincts scream a warning.",
            ],
            False: [
                "You believe it — even knowing you shouldn't.",
                "The charm takes hold. Your will wavers.",
            ],
        },
        "cha": {
            True: [
                "Your presence resists the magical domination.",
                "You assert your will and break free.",
            ],
            False: [
                "Your sense of self dissolves. You are not in control.",
                "The compulsion takes root.",
            ],
        },
    }

    from random import choice
    options = saves.get(stat, {}).get(success, ["The outcome is uncertain."])
    return choice(options)
