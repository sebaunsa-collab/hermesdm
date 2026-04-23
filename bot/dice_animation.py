"""
dice_animation.py — Slot machine animation for dice rolls.

Pattern: 6 frames of Unicode dice faces (⚀⚁⚂⚃⚄⚅) rolling at 0.1s intervals,
then final message with real result.

Uses python-telegram-bot job_queue.run_once() — same pattern as countdown.
"""
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram.ext import ContextTypes


_DICE_FACES = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
_FRAME_DELAY = 0.1  # seconds between animation frames
_NUM_FRAMES = 6

# Action types that HAVE a dice roll (→ animate)
ANIMATE_ACTION_TYPES = {
    "attack", "cast", "shove", "hide", "intimidate", "persuade",
    "deceive", "investigate", "medicine", "history", "arcana",
    "religion", "survival", "sleight", "athletics", "acrobatics",
    "animal", "perception", "use_object",
}

# Action types that have NO dice roll (→ skip animation)
SKIP_ANIMATE_ACTION_TYPES = {
    "disengage", "dodge", "dash", "ready", "help", "rest", "dialogue",
}


def _random_frame() -> str:
    """Generate a random dice face sequence for one animation frame."""
    faces = random.choices(_DICE_FACES, k=6)
    return "".join(faces)


def _build_animation_text(frame_index: int, character_name: str) -> str:
    """Build one animation frame text."""
    frame = _random_frame()
    return (
        f"🎲 *{character_name} tira dados...*\n"
        f"`{frame}`  ← #{frame_index + 1}\n"
        f"_rueda...rueda..._"
    )


def _needs_animation(action_type: str) -> bool:
    """Check if this action type has a dice roll (→ should animate)."""
    if not action_type:
        return False
    return action_type in ANIMATE_ACTION_TYPES


def _build_final_text(
    action_type: str,
    character_name: str,
    mechanic_inline: str,
    narrative: str,
    nat_20: bool = False,
    nat_1: bool = False,
) -> str:
    """Build the final rich result message after animation completes."""
    # Determine emoji prefix by action type
    if action_type == "attack" or action_type == "cast":
        primary_icon = "⚔️"
    elif action_type in {"intimidate", "persuade", "deceive"}:
        primary_icon = "🎭"
    elif action_type in {"medicine"}:
        primary_icon = "💚"
    else:
        primary_icon = "🎲"

    # Badge for crit/fumble
    badge = ""
    if nat_20:
        badge = " 🌟"
    elif nat_1:
        badge = " 💀"

    # Format based on success/failure from mechanic_inline
    mechanic_lower = mechanic_inline.lower()
    is_success = "acierto" in mechanic_lower or "exito" in mechanic_lower or "critico" in mechanic_lower
    is_failure = "fal" in mechanic_lower or "fumble" in mechanic_lower or "erra" in mechanic_lower

    if is_success and not is_failure:
        result_icon = "✅"
    elif is_failure:
        result_icon = "❌"
    else:
        result_icon = "🎯"

    return (
        f"{result_icon} *Resultado{badge}*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{primary_icon} {character_name}\n"
        f"{mechanic_inline}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{narrative}"
    )


async def _dice_frame_edit(context: "ContextTypes.DEFAULT_TYPE") -> None:
    """
    Edit one animation frame. If last frame, send the real result.
    Chains to next frame or final text via job_queue.
    """
    job = context.job
    data = job.data or {}

    chat_id = data["chat_id"]
    message_id = data["message_id"]
    frame_index = data["frame_index"]
    character_name = data["character_name"]
    remaining_frames = data.get("remaining_frames", 0)
    final_text = data["final_text"]
    parse_mode = data.get("parse_mode", "Markdown")

    is_last_frame = remaining_frames <= 1

    if is_last_frame:
        # Final frame — show real result
        text = final_text
    else:
        # Animation frame
        text = _build_animation_text(frame_index, character_name)

    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        parse_mode=parse_mode,
    )

    # Schedule next frame if not done
    if not is_last_frame:
        context.application.job_queue.run_once(
            _dice_frame_edit,
            _FRAME_DELAY,
            data={
                "chat_id": chat_id,
                "message_id": message_id,
                "frame_index": frame_index + 1,
                "character_name": character_name,
                "remaining_frames": remaining_frames - 1,
                "final_text": final_text,
                "parse_mode": parse_mode,
            },
            name=f"dice_frame_{message_id}_{frame_index}",
            chat_id=chat_id,
        )


async def animate_dice_roll(
    context: "ContextTypes.DEFAULT_TYPE",
    chat_id: int,
    message_id: int,
    action_type: str,
    character_name: str,
    mechanic_inline: str,
    narrative: str,
    nat_20: bool = False,
    nat_1: bool = False,
) -> None:
    """
    Main entry point: animate dice roll if action_type needs it.

    Flow:
    1. Check if animation needed (skip for disengage/dodge/dash/ready/help/rest)
    2. If NOT needed: edit message directly with final text
    3. If needed: send initial animation message → chain 6 frame edits → final result
    """
    if not _needs_animation(action_type):
        # No animation — send result directly
        final_text = _build_final_text(
            action_type, character_name, mechanic_inline, narrative, nat_20, nat_1
        )
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=final_text,
            parse_mode="Markdown",
        )
        return

    # Build the final result text upfront (we know the roll already)
    final_text = _build_final_text(
        action_type, character_name, mechanic_inline, narrative, nat_20, nat_1
    )

    # Send initial "rolling" message
    initial_text = _build_animation_text(0, character_name)
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=initial_text,
        parse_mode="Markdown",
    )

    # Chain frame edits via job_queue (start from frame 1, 6 remaining)
    context.application.job_queue.run_once(
        _dice_frame_edit,
        _FRAME_DELAY,
        data={
            "chat_id": chat_id,
            "message_id": message_id,
            "frame_index": 1,
            "character_name": character_name,
            "remaining_frames": _NUM_FRAMES,
            "final_text": final_text,
            "parse_mode": "Markdown",
        },
        name=f"dice_roll_{message_id}",
        chat_id=chat_id,
    )
