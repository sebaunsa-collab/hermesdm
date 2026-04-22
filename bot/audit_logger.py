"""
bot/audit_logger.py — Audit/telemetry system for HermesDM.

Writes JSON Lines to state/audit_<timestamp>.jsonl with event data.
Rotates: keeps a maximum of 7 audit files.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

log = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Paths
# ------------------------------------------------------------------ #

STATE_DIR = Path(__file__).parent.parent / "state"
STATE_DIR.mkdir(exist_ok=True)

AUDIT_DIR = Path(__file__).parent.parent / "state"
AUDIT_DIR.mkdir(exist_ok=True)

MAX_AUDIT_FILES = 7

# ------------------------------------------------------------------ #
# Event types
# ------------------------------------------------------------------ #

EVENT_TYPES = (
    "command_received",
    "command_executed",
    "response_sent",
    "state_change",
    "mode_transition",
    "error",
    "session_start",
    "session_end",
)


# ------------------------------------------------------------------ #
# AuditLogger
# ------------------------------------------------------------------ #

class AuditLogger:
    """
    Writes structured audit events to a rotating set of JSON Lines files.

    Each event contains:
        timestamp, event_type, chat_id, user_id, username,
        input, output, error, metadata
    """

    def __init__(self) -> None:
        self._current_file: Path | None = None
        self._session_start: float | None = None
        self._ensure_current_file()

    # ------------------------------------------------------------------ #
    # File management
    # ------------------------------------------------------------------ #

    def _ensure_current_file(self) -> Path:
        """Ensure we have a current audit file open for today."""
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        path = AUDIT_DIR / f"audit_{today}.jsonl"

        if self._current_file != path:
            self._current_file = path
            log.info(f"Audit file opened: {path}")

        return path

    def _list_audit_files(self) -> list[Path]:
        """Return sorted list of existing audit files."""
        return sorted(AUDIT_DIR.glob("audit_*.jsonl"))

    def _rotate(self) -> None:
        """Remove oldest audit files if we exceed MAX_AUDIT_FILES."""
        files = self._list_audit_files()
        if len(files) > MAX_AUDIT_FILES:
            to_remove = files[:-MAX_AUDIT_FILES]
            for f in to_remove:
                log.info(f"Rotating out audit file: {f}")
                f.unlink(missing_ok=True)

    # ------------------------------------------------------------------ #
    # Writing
    # ------------------------------------------------------------------ #

    def _write(self, event: dict[str, Any]) -> None:
        """Append a single event dict as a JSON line."""
        self._ensure_current_file()
        path = self._current_file

        line = json.dumps(event, ensure_ascii=False, default=str)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

        self._rotate()

    # ------------------------------------------------------------------ #
    # Public event API
    # ------------------------------------------------------------------ #

    def log_event(
        self,
        event_type: str,
        update: Update | None = None,
        context: ContextTypes.DEFAULT_TYPE | None = None,
        *,
        input: str | None = None,
        output: str | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Build and write an audit event.

        Args:
            event_type: One of EVENT_TYPES
            update: Telegram Update object (used to extract chat/user info)
            context: Telegram context
            input: Human-readable command/input string
            output: Human-readable bot response
            error: Error message if applicable
            metadata: Additional structured data
        """
        now = datetime.now(timezone.utc)

        chat_id: int | None = None
        user_id: int | None = None
        username: str | None = None

        if update is not None:
            chat_id = update.effective_chat.id if update.effective_chat else None
            user_id = update.effective_user.id if update.effective_user else None
            if update.effective_user:
                username = update.effective_user.username or update.effective_user.first_name

        event = {
            "timestamp": now.isoformat(),
            "event_type": event_type,
            "chat_id": chat_id,
            "user_id": user_id,
            "username": username,
            "input": input,
            "output": output,
            "error": error,
            "metadata": metadata or {},
        }

        self._write(event)

    def log_session_start(
        self,
        update: Update | None = None,
        context: ContextTypes.DEFAULT_TYPE | None = None,
    ) -> None:
        """Log a session_start event."""
        self._session_start = time.time()
        self.log_event(
            "session_start",
            update=update,
            context=context,
            metadata={"session_uptime_start": self._session_start},
        )

    def log_session_end(
        self,
        update: Update | None = None,
        context: ContextTypes.DEFAULT_TYPE | None = None,
    ) -> None:
        """Log a session_end event."""
        uptime = None
        if self._session_start is not None:
            uptime = time.time() - self._session_start
        self.log_event(
            "session_end",
            update=update,
            context=context,
            metadata={"session_uptime_seconds": uptime},
        )
        self._session_start = None

    # ------------------------------------------------------------------ #
    # Reading (for audit_viewer)
    # ------------------------------------------------------------------ #

    @staticmethod
    def read_events(
        limit: int = 50,
        user: str | None = None,
        session_ts: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Read events from audit files.

        Args:
            limit: Maximum number of events to return (most recent first)
            user: Filter by username (substring match)
            session_ts: Filter by session timestamp prefix (e.g. "2026-04-19")
            event_type: Filter by event_type

        Returns:
            List of event dicts (most recent last → we reverse for display)
        """
        files = sorted(AuditLogger._list_audit_files())
        events: list[dict[str, Any]] = []

        for fpath in reversed(files):
            with open(fpath, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Filters
                    if event_type and event.get("event_type") != event_type:
                        continue
                    if user:
                        uname = event.get("username") or ""
                        if user.lower() not in uname.lower():
                            continue
                    if session_ts:
                        ts = event.get("timestamp", "")
                        if not ts.startswith(session_ts):
                            continue

                    events.append(event)

                    if len(events) >= limit:
                        return events

        return events

    @staticmethod
    def _list_audit_files() -> list[Path]:
        """Return sorted list of existing audit files."""
        return sorted(AUDIT_DIR.glob("audit_*.jsonl"))


# ------------------------------------------------------------------ #
# Module-level singleton
# ------------------------------------------------------------------ #

_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Return the global AuditLogger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# ------------------------------------------------------------------ #
# Decorator
# ------------------------------------------------------------------ #

def with_audit(handler_name: str | None = None):
    """
    Decorator that wraps a telegram command handler with audit logging.

    Logs:
        - command_received  (before handler)
        - command_executed (after handler, with output)
        - error            (if handler raises)

    Usage:
        @with_audit("cmd_start")
        async def cmd_start(update, context):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
        ) -> None:
            audit = get_audit_logger()
            cmd_name = handler_name or func.__name__

            # ── Before ──────────────────────────────────────────────
            input_text = None
            if update.message:
                input_text = update.message.text
            elif update.edited_message:
                input_text = update.edited_message.text

            audit.log_event(
                "command_received",
                update=update,
                context=context,
                input=input_text,
                metadata={"handler": cmd_name},
            )

            # ── Execute ─────────────────────────────────────────────
            output_text: str | None = None
            error_text: str | None = None

            try:
                await func(update, context)

                # Try to grab the response text that was sent.
                # We capture it via a simple heuristic: the last reply_text call.
                # Since telegram bot API doesn't give us the sent text back,
                # we mark that the handler completed without error.
                output_text = None  # actual response is opaque to us here

            except Exception as exc:
                error_text = str(exc)
                audit.log_event(
                    "error",
                    update=update,
                    context=context,
                    input=input_text,
                    error=error_text,
                    metadata={"handler": cmd_name},
                )
                raise  # re-raise so telegram-ext also handles it

            # ── After ──────────────────────────────────────────────
            audit.log_event(
                "command_executed",
                update=update,
                context=context,
                input=input_text,
                output=output_text,
                metadata={"handler": cmd_name},
            )

        return wrapper
    return decorator
