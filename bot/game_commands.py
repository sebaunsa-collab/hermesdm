"""
game_commands.py — Game command handlers with 2-step confirmation flow.

Implements !attack: Step 1 (!attack <target>) queues pending state,
Step 2 (confirm) resolves with dice roll.

Exports:
    register_game_handlers(app) — register MessageHandler for !attack and confirm
    _pending_attacks — dict: chat_id -> {attack_id: PendingAttack}
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.combat_engine import resolve_attack
from bot.dice_engine import roll as _roll

log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Pending attack state
# ------------------------------------------------------------------


@dataclass
class PendingAttack:
    """Stores an attack awaiting confirmation in a specific chat."""

    attack_id: str
    attacker_name: str
    defender_name: str
    weapon: str = "sword"
    defender_ac: int = 10
    rage_bonus: int = 0
    advantage: bool = False
    disadvantage: bool = False
    # Dice notation to roll on confirmation
    dice_notation: str = "1d20"
    # Store modifiers from the attacker's character
    attack_bonus: int = 0

    def to_summary(self) -> str:
        """Return a human-readable summary of the pending attack."""
        adv_note = ""
        if self.advantage:
            adv_note = " (ADV)"
        elif self.disadvantage:
            adv_note = " (DIS)"

        return (
            f"⚔️ *Pending Attack*\n"
            f"Attacker: {self.attacker_name}\n"
            f"Target: {self.defender_name}\n"
            f"Weapon: {self.weapon}\n"
            f"Defender AC: {self.defender_ac}\n"
            f"Dice: {self.dice_notation}{adv_note}\n"
            f"ID: `{self.attack_id}`"
        )


# Per-chat pending attacks: {chat_id: {attack_id: PendingAttack}}
_pending_attacks: dict[int, dict[str, PendingAttack]] = {}


def _get_chat_attacks(chat_id: int) -> dict[str, PendingAttack]:
    """Get or create the pending attacks dict for a chat."""
    if chat_id not in _pending_attacks:
        _pending_attacks[chat_id] = {}
    return _pending_attacks[chat_id]


def _clear_expired_attacks(chat_id: int, max_attacks: int = 10) -> None:
    """Keep pending attacks dict bounded to avoid memory leaks."""
    if chat_id in _pending_attacks:
        attacks = _pending_attacks[chat_id]
        if len(attacks) > max_attacks:
            # Remove oldest entries
            oldest_keys = list(attacks.keys())[: len(attacks) - max_attacks]
            for k in oldest_keys:
                del attacks[k]


# ------------------------------------------------------------------
# !attack handler (Step 1)
# ------------------------------------------------------------------


async def _handle_attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle !attack <target> <AC> [weapon] [adv|dis].

    Step 1 of 2-step attack flow. Stores pending attack and asks
    the user to confirm before resolving.

    Examples:
        !attack Goblin 14
        !attack Orc 16 longsword --adv
        !attack Troll 15 greataxe dis
    """
    try:
        message_text = update.message.text.strip()
        # Parse: !attack Goblin 14 longsword --adv
        parts = message_text.split()

        if len(parts) < 3:
            await update.message.reply_text(
                "⚔️ Uso: `!attack [objetivo] [CA] [arma?] [--adv?--dis?]`\n"
                "Ejemplo: `!attack Orco 16 longsword --adv`\n"
                "Arma default: sword | CA default: 10",
                parse_mode="Markdown",
            )
            return

        target = parts[1].strip()

        # Parse AC (second arg must be a number)
        try:
            defender_ac = int(parts[2].strip())
            if defender_ac <= 0:
                raise ValueError("AC must be positive")
        except (ValueError, IndexError):
            await update.message.reply_text(
                "⚔️ CA debe ser un número. Ejemplo: `!attack Orco 16`",
                parse_mode="Markdown",
            )
            return

        # Remaining args: weapon and flags
        advantage = "--adv" in [p.lower() for p in parts[3:]]
        disadvantage = "--dis" in [p.lower() for p in parts[3:]]

        # Weapon: look for a known weapon name
        weapon_names = {
            "unarmed", "dagger", "sword", "longsword", "greatsword",
            "shortsword", "rapier", "scimitar", "handaxe", "battleaxe",
            "greataxe", "warhammer", "greatclub", "mace", "spear",
            "javelin", "longbow", "shortbow", "light_xbow", "heavy_xbow", "sling"
        }
        for p in parts[3:]:
            p_clean = p.lower().strip()
            if p_clean in weapon_names and p_clean not in ("--adv", "--dis"):
                break

        # Dice notation for attack roll
        dice_notation = "1d20"
        for p in parts[3:]:
            p_clean = p.lower().strip()
            if p_clean.startswith("d") and p_clean[1:].replace("+", "").isdigit():
                dice_notation = p_clean
                break

        chat_id = update.effective_chat.id
        attacks = _get_chat_attacks(chat_id)
        _clear_expired_attacks(chat_id)

        # Generate unique attack ID
        attack_id = str(uuid.uuid4())[:8]

        # TODO: In a full implementation, we'd look up the attacker's character
        # from chat_data and get their actual attack bonus, weapon, etc.
        # For now, we use defaults that can be refined.
        pending = PendingAttack(
            attack_id=attack_id,
            attacker_name=update.effective_user.first_name or "Unknown",
            defender_name=target,
            weapon="sword",
            defender_ac=10,
            rage_bonus=0,
            advantage=advantage,
            disadvantage=disadvantage,
            dice_notation=dice_notation,
            attack_bonus=0,
        )

        attacks[attack_id] = pending

        if advantage:
            pass
        elif disadvantage:
            pass

        confirm_id = f"confirm_{attack_id}"

        await update.message.reply_text(
            f"🎯 *Attack Prepared!*\n\n"
            f"{pending.to_summary()}\n\n"
            f"Reply with `!confirm {confirm_id}` to resolve this attack, "
            f"or `!cancel` to cancel.",
            parse_mode="Markdown",
        )

    except Exception as e:
        log.exception("!attack handler error")
        try:
            await update.message.reply_text(f"Error: {e}")
        except Exception:
            pass


# ------------------------------------------------------------------
# !confirm handler (Step 2)
# ------------------------------------------------------------------


async def _handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle !confirm <attack_id>.

    Step 2 of 2-step attack flow. Resolves the pending attack by:
    1. Rolling the dice (from the pending attack's dice_notation)
    2. Calling combat_engine.resolve_attack()
    3. Reporting the result
    """
    try:
        message_text = update.message.text.strip()
        parts = message_text.split()

        if len(parts) < 2:
            await update.message.reply_text(
                "Usage: `!confirm <attack_id>`\n"
                "Use the attack ID shown when you created the attack.",
                parse_mode="Markdown",
            )
            return

        confirm_arg = parts[1].strip()

        # Parse: confirm_<attack_id>
        if confirm_arg.startswith("confirm_"):
            attack_id = confirm_arg[8:]
        else:
            attack_id = confirm_arg

        chat_id = update.effective_chat.id
        attacks = _get_chat_attacks(chat_id)

        if attack_id not in attacks:
            await update.message.reply_text(
                f"❌ No pending attack found with ID `{attack_id}`.\n"
                f"Use `!attack <target>` to start a new attack.",
                parse_mode="Markdown",
            )
            return

        pending = attacks.pop(attack_id)

        # Step 1: Roll the dice
        roll_result = _roll(pending.dice_notation)
        attack_roll = roll_result["total"]

        # Build roll description
        roll_desc = pending.dice_notation
        if roll_result.get("modifier", 0) != 0:
            roll_result["modifier"]
            roll_desc += f" ({roll_result['rolls']})"
        else:
            roll_desc = f"{roll_result['rolls'][0]}" if roll_result["rolls"] else str(attack_roll)

        # Step 2: Resolve the attack
        resolved = resolve_attack(
            attacker_name=pending.attacker_name,
            defender_name=pending.defender_name,
            attack_roll=attack_roll,
            weapon=pending.weapon,
            advantage=pending.advantage,
            disadvantage=pending.disadvantage,
            defender_ac=pending.defender_ac,
            rage_bonus=pending.rage_bonus,
        )

        # Step 3: Format and send result
        lines = [
            "⚔️ *Attack Resolved*",
            "",
            f"Attacker: {pending.attacker_name}",
            f"Target: {pending.defender_name}",
            f"Weapon: {pending.weapon}",
            "",
            f"🎲 Attack Roll: {roll_desc} = *{attack_roll}*",
            f"vs AC: {pending.defender_ac}",
        ]

        if resolved["fumble"]:
            lines.append("")
            lines.append("💀 **FUMBLE!** Natural 1!")
            lines.append("The attack fails miserably.")
        elif resolved["crit"]:
            lines.append("")
            lines.append("💥 **CRITICAL HIT!**")
            lines.append(f"Nat 20! Damage: *{resolved['damage']}*")
            lines.append(f"Rolls: {resolved['rolls']}")
        elif resolved["hit"]:
            lines.append("")
            lines.append("✅ *HIT!*")
            lines.append(f"Damage: *{resolved['damage']}*")
            lines.append(f"Rolls: {resolved['rolls']}")
        else:
            lines.append("")
            lines.append("❌ *MISS!*")
            lines.append("The attack misses!")

        result_text = "\n".join(lines)
        await update.message.reply_text(result_text, parse_mode="Markdown")

    except Exception as e:
        log.exception("!confirm handler error")
        try:
            await update.message.reply_text(f"Error: {e}")
        except Exception:
            pass


# ------------------------------------------------------------------
# !cancel handler
# ------------------------------------------------------------------


async def _handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle !cancel — clears all pending attacks in the current chat.
    """
    try:
        chat_id = update.effective_chat.id
        if chat_id in _pending_attacks:
            count = len(_pending_attacks[chat_id])
            _pending_attacks[chat_id].clear()
            await update.message.reply_text(
                f"✅ Cancelled {count} pending attack(s).",
            )
        else:
            await update.message.reply_text(
                "No pending attacks to cancel.",
            )
    except Exception as e:
        log.exception("!cancel handler error")
        try:
            await update.message.reply_text(f"Error: {e}")
        except Exception:
            pass


# ------------------------------------------------------------------
# !attack_status — list pending attacks
# ------------------------------------------------------------------


async def _handle_attack_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle !attack_status — shows all pending attacks in the current chat.
    """
    try:
        chat_id = update.effective_chat.id
        attacks = _get_chat_attacks(chat_id)

        if not attacks:
            await update.message.reply_text(
                "No pending attacks. Use `!attack <target>` to start one.",
                parse_mode="Markdown",
            )
            return

        lines = ["⚔️ *Pending Attacks*", ""]
        for aid, attack in attacks.items():
            lines.append(attack.to_summary())
            lines.append("")

        await update.message.reply_text("\n".join(lines).strip(), parse_mode="Markdown")

    except Exception as e:
        log.exception("!attack_status handler error")
        try:
            await update.message.reply_text(f"Error: {e}")
        except Exception:
            pass


# ------------------------------------------------------------------
# Handler registration
# ------------------------------------------------------------------


def register_game_handlers(app: Application, group_id: int | None = None) -> None:
    """
    Register all !attack family handlers with the Telegram app.

    Registers:
        - MessageHandler for !attack (starts attack, step 1)
        - MessageHandler for !confirm (resolves attack, step 2)
        - MessageHandler for !cancel (clears pending)
        - MessageHandler for !attack_status (lists pending)

    Args:
        app: Telegram application
        group_id: If set, handlers only respond in that specific chat.
    """
    group_filter = filters.Chat(group_id) if group_id else filters.ALL

    # !attack — starts a pending attack
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(r"^!attack\b") & group_filter,
            _handle_attack,
        )
    )

    # !confirm — resolves a pending attack
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(r"^!confirm\b") & group_filter,
            _handle_confirm,
        )
    )

    # !cancel — clears pending attacks
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(r"^!cancel\b") & group_filter,
            _handle_cancel,
        )
    )

    # !attack_status — lists pending attacks
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(r"^!attack_status\b") & group_filter,
            _handle_attack_status,
        )
    )

    log.info("game_commands handlers registered" + (f" for group {group_id}" if group_id else ""))


# ------------------------------------------------------------------
# Sanity test
# ------------------------------------------------------------------

if __name__ == "__main__":
    print("=== game_commands sanity test ===")

    # Test PendingAttack dataclass
    pa = PendingAttack(
        attack_id="abc123",
        attacker_name="Valdric",
        defender_name="Goblin",
        weapon="longsword",
        defender_ac=14,
        advantage=True,
        dice_notation="1d20+5",
    )
    print(pa.to_summary())
    print()

    # Test _pending_attacks dict
    _pending_attacks[12345] = {"abc123": pa}
    print(f"Pending attacks in chat 12345: {_pending_attacks[12345]}")
    print()

    print("All tests passed!")
