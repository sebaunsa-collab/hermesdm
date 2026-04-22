"""
HermesDM Plan B — Sub-agente dedicado al grupo de D&D.

Usa el token de HermesDM (NO el de Hermes principal).
Hace polling al grupo "Dungeons and dragons test".
Maneja /j <accion> y broadcast al grupo.

Run: python3 hermesdm_plan_b.py
"""

import logging
import os
import sys

# Add project root
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from adapters.mode_b.action_router import ActionRouter
from bot.telegram_handler import (
    ChatState,
    _handle_setup_text,
    cmd_attack,
    cmd_audit,
    cmd_campaign,
    cmd_cast,
    cmd_endcombat,
    cmd_endturn,
    cmd_help,
    cmd_hp,
    cmd_imagen,
    cmd_inventory,
    cmd_join,
    cmd_map,
    cmd_me,
    cmd_newgame,
    cmd_quests,
    cmd_quit,
    cmd_recap,
    cmd_resume,
    cmd_roll,
    cmd_save,
    cmd_setup,
    cmd_skill,
    cmd_start,
    cmd_startcombat,
    cmd_status,
    cmd_talk,
)
from state.state_manager import load_state

log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Config — TOKEN SEPARADO de Hermes principal
# ------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = "8222165892:AAFdsLM6IEBxAvayetIxBmmfx2I89eVn8zM"
TARGET_CHAT_ID = -1003916745496  # Dungeons and dragons test


# ------------------------------------------------------------------
# Handler de /j — copia del _j_action_handler pero broadcast
# ------------------------------------------------------------------

async def j_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /j <action> en el grupo — Plan B async.
    Reemplaza reply_text por send_message al grupo objetivo.
    """
    try:
        text = update.message.text or ""
        if not text.startswith("/act "):
            return

        action_text = text[5:].strip()
        if not action_text:
            await context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text="⚠️ Uso: /j <tu acción>\nEjemplo: /j Ataco al dragón",
            )
            return

        chat_data = context.chat_data
        cs: ChatState = chat_data.get("_hermes_state", ChatState())

        if not cs.active_campaign:
            await context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text="⚠️ No hay campaña activa. Usa /newgame para empezar.",
            )
            return

        # Buscar personaje del jugador
        sender_name = update.effective_user.first_name or ""
        char = cs.character_for(sender_name)
        if char is None:
            for key, c in cs.characters.items():
                if sender_name.lower() in c.name.lower() or c.name.lower() in sender_name.lower():
                    char = c
                    break

        if char is None:
            await context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"⚠️ No encontré personaje para '{sender_name}'.\nUsa /join para registrarte.",
            )
            return

        # Cargar state
        state = load_state(cs.active_campaign) or {"campaign": {}, "characters": {}, "npcs": {}}

        # Route
        router = ActionRouter(state=state, character=char)
        result = router.route(update, action_text)

        # Determinar tipo de acción para formato
        action_lower = action_text.lower()
        is_attack = any(k in action_lower for k in ["atac", "golpe", "espada", "arco", "strike", "hit", "attack"])
        is_cast = any(k in action_lower for k in ["lanz", "hechiz", "magi", "spell", "cast"])
        is_social = any(k in action_lower for k in ["intimidar", "persuadir", "engañar", "amenazar", "intimidate", "persuade", "deceive"])
        is_knowledge = any(k in action_lower for k in ["historia", "religion", "arcano", "investigar", "medicina", "supervivencia", "history", "arcana", "investigate", "medicine", "survival"])
        is_physical = any(k in action_lower for k in ["esquivar", "correr", "esconderse", "ayudar", "empujar", "disengage", "dash", "hide", "help", "shove", "dodge", "desenganchar", "escabullirse"])
        is_heal = any(k in action_lower for k in ["cur", "san", "heal", "restaur"])

        if is_attack:
            prefix = "⚔️"
            reply = f"{prefix} *{char.name} ataca*\n/j {action_text}\n──────────────────────\n{result.mechanic_inline}\n──────────────────────\n📖 {result.narrative}"
        elif is_cast:
            prefix = "✨"
            reply = f"{prefix} *{char.name} lanza un hechizo*\n/j {action_text}\n──────────────────────\n{result.mechanic_inline}\n──────────────────────\n📖 {result.narrative}"
        elif is_heal:
            prefix = "💚"
            from bot.dice_engine import roll as _roll_dice_h
            heal = _roll_dice_h("1d8+2")["total"]
            reply = f"{prefix} *{char.name} canaliza energía curativa*\n/j {action_text}\n──────────────────────\n✨ HP restaurado: *+{heal}*\n──────────────────────\n📖 {result.narrative}"
        elif is_social:
            prefix = "🎭"
            reply = f"{prefix} *{char.name} interactúa*\n/j {action_text}\n──────────────────────\n{result.mechanic_inline}\n──────────────────────\n📖 {result.narrative}"
        elif is_knowledge:
            prefix = "📚"
            reply = f"{prefix} *{char.name} recuerda*\n/j {action_text}\n──────────────────────\n{result.mechanic_inline}\n──────────────────────\n📖 {result.narrative}"
        elif is_physical:
            prefix = "🏃"
            reply = f"{prefix} *{char.name} se mueve*\n/j {action_text}\n──────────────────────\n{result.mechanic_inline}\n──────────────────────\n📖 {result.narrative}"
        else:
            prefix = "🎲"
            reply = f"{prefix} *{char.name} intenta {action_text}*\n/j {action_text}\n──────────────────────\n{result.mechanic_inline}\n──────────────────────\n📖 {result.narrative}"

        await context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=reply,
            parse_mode="Markdown",
        )

    except Exception as e:
        log.exception("j_action_handler error")
        try:
            await context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Error: {e}",
            )
        except Exception:
            pass


# ------------------------------------------------------------------
# App builder separado para Plan B
# ------------------------------------------------------------------

def build_plan_b_app() -> Application:
    """Build app con el token de HermesDM, NO el de Hermes principal."""
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    group_filter = filters.Chat(chat_id=TARGET_CHAT_ID)

    # Registro todos los comandos — reply_text responde en el grupo públicamente
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help, filters=group_filter))
    app.add_handler(CommandHandler("newgame", cmd_newgame, filters=group_filter))
    app.add_handler(CommandHandler("setup", cmd_setup, filters=group_filter))
    app.add_handler(CommandHandler("join", cmd_join, filters=group_filter))
    app.add_handler(CommandHandler("roll", cmd_roll, filters=group_filter))
    app.add_handler(CommandHandler("attack", cmd_attack, filters=group_filter))
    app.add_handler(CommandHandler("cast", cmd_cast, filters=group_filter))
    app.add_handler(CommandHandler("skill", cmd_skill, filters=group_filter))
    app.add_handler(CommandHandler("status", cmd_status, filters=group_filter))
    app.add_handler(CommandHandler("hp", cmd_hp, filters=group_filter))
    app.add_handler(CommandHandler("inventory", cmd_inventory, filters=group_filter))
    app.add_handler(CommandHandler("talk", cmd_talk, filters=group_filter))
    app.add_handler(CommandHandler("map", cmd_map, filters=group_filter))
    app.add_handler(CommandHandler("quests", cmd_quests, filters=group_filter))
    app.add_handler(CommandHandler("recap", cmd_recap, filters=group_filter))
    app.add_handler(CommandHandler("resume", cmd_resume, filters=group_filter))
    app.add_handler(CommandHandler("endturn", cmd_endturn, filters=group_filter))
    app.add_handler(CommandHandler("campaign", cmd_campaign, filters=group_filter))
    app.add_handler(CommandHandler("save", cmd_save, filters=group_filter))
    app.add_handler(CommandHandler("startcombat", cmd_startcombat, filters=group_filter))
    app.add_handler(CommandHandler("endcombat", cmd_endcombat, filters=group_filter))
    app.add_handler(CommandHandler("quit", cmd_quit, filters=group_filter))
    app.add_handler(CommandHandler("audit", cmd_audit, filters=group_filter))
    app.add_handler(CommandHandler("imagen", cmd_imagen, filters=group_filter))
    app.add_handler(CommandHandler("me", cmd_me, filters=group_filter))

    # Setup text handler — intercepta texto del DM durante flujo de setup
    # Debe ir ANTES de j_action_handler (que matched todo TEXT)
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.SUPERGROUP & filters.Chat(chat_id=TARGET_CHAT_ID),
        _handle_setup_text,
    ))

    # /j <accion> — acción libre narrada
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.SUPERGROUP & filters.Chat(chat_id=TARGET_CHAT_ID),
        j_action_handler,
    ))

    return app


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | plan_b | %(levelname)s | %(message)s",
    )
    log.info("🚀 HermesDM Plan B arrancando...")
    log.info(f"   Token: {TELEGRAM_BOT_TOKEN[:20]}...")
    log.info(f"   Grupo: {TARGET_CHAT_ID}")

    app = build_plan_b_app()
    log.info("✅ Handler registrado. Escuchando /j en el grupo...")
    app.run_polling(drop_pending_updates=True)
