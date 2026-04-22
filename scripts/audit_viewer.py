#!/usr/bin/env python3
"""
scripts/audit_viewer.py — CLI tool to read and filter HermesDM audit logs.

Usage:
    python audit_viewer.py                              # last 50 events
    python audit_viewer.py --limit 100                  # last 100 events
    python audit_viewer.py --user hermes                 # filter by username
    python audit_viewer.py --session 2026-04-19          # session date
    python audit_viewer.py --type command_executed       # filter by event type
    python audit_viewer.py --export csv                   # export to CSV
    python audit_viewer.py --export json                  # export to JSON
    python audit_viewer.py --files                        # list audit files
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.audit_logger import AuditLogger


class AuditViewer:
    """Reusable audit log viewer for programmatic access."""

    def __init__(self, state_dir: str | None = None):
        from pathlib import Path
        self.state_dir = Path(state_dir) if state_dir else Path(__file__).parent.parent / "state"

    def get_events(self, limit: int = 20, user: str | None = None,
                    session_ts: str | None = None, event_type: str | None = None) -> list[dict]:
        return AuditLogger.read_events(
            limit=limit, user=user, session_ts=session_ts, event_type=event_type
        )

    def format_report(self, limit: int = 20) -> str:
        """Format audit events as a Telegram-friendly markdown report."""
        events = self.get_events(limit=limit)
        if not events:
            return "📋 *Audit Log*\n\nNo hay eventos registrados."

        lines = [f"📋 *Audit Log* — últimos {len(events)} eventos\n"]
        for e in events:
            ts = e.get("timestamp", "?")
            ts_short = ts[11:19] if len(ts) > 19 else ts
            e.get("event_type", "?")
            username = e.get("username") or str(e.get("user_id", "?"))
            handler = (e.get("metadata") or {}).get("handler", "")
            error = e.get("error") or ""

            inp = e.get("input", "")
            inp_preview = inp[:50] + "..." if len(inp) > 50 else inp

            if error:
                lines.append(f"❌ [{ts_short}] /{handler}")
                lines.append(f"   usuario: {username} | error: {error[:60]}")
            else:
                lines.append(f"✅ [{ts_short}] /{handler}")
                if inp_preview:
                    lines.append(f"   {username}: {inp_preview}")

        return "\n".join(lines)


def _fmt_event(event: dict[str, Any]) -> str:
    """Format a single event as a readable line."""
    ts = event.get("timestamp", "?")
    # Shorten timestamp for display
    ts_short = ts[11:19] if len(ts) > 19 else ts  # HH:MM:SS
    event_type = event.get("event_type", "?")
    username = event.get("username") or event.get("user_id", "?")
    chat_id = event.get("chat_id", "?")
    handler = (event.get("metadata") or {}).get("handler", "")
    error = event.get("error") or ""

    input_preview = ""
    if event.get("input"):
        inp = event["input"]
        input_preview = inp[:60] + ("..." if len(inp) > 60 else "")

    if error:
        return (
            f"[{ts_short}] {event_type:25s} | "
            f"user={username} chat={chat_id} | "
            f"{handler} | ERROR: {error[:60]}"
        )

    return (
        f"[{ts_short}] {event_type:25s} | "
        f"user={username} chat={chat_id} | "
        f"{handler}"
        + (f" | input: {input_preview}" if input_preview else "")
    )


def _list_files() -> None:
    """List all audit files with line counts and size."""
    files = AuditLogger._list_audit_files()
    if not files:
        print("No audit files found.")
        return

    total_lines = 0
    for fpath in reversed(files):
        size_kb = fpath.stat().st_size / 1024
        line_count = 0
        try:
            with open(fpath, encoding="utf-8") as fh:
                line_count = sum(1 for _ in fh)
        except Exception:
            pass
        total_lines += line_count
        print(f"  {fpath.name:30s}  {line_count:>6} lines  {size_kb:>8.1f} KB")

    print(f"\n  Total: {total_lines} events across {len(files)} files")


def _export_csv(events: list[dict[str, Any]], output_path: Path) -> None:
    """Export events to CSV."""
    if not events:
        print("No events to export.")
        return

    fieldnames = ["timestamp", "event_type", "chat_id", "user_id", "username",
                  "input", "output", "error", "handler", "session_uptime"]

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for e in events:
            meta = e.get("metadata") or {}
            row = {
                "timestamp": e.get("timestamp", ""),
                "event_type": e.get("event_type", ""),
                "chat_id": e.get("chat_id", ""),
                "user_id": e.get("user_id", ""),
                "username": e.get("username", ""),
                "input": e.get("input", ""),
                "output": e.get("output", ""),
                "error": e.get("error", ""),
                "handler": meta.get("handler", ""),
                "session_uptime": meta.get("session_uptime_seconds", ""),
            }
            writer.writerow(row)

    print(f"Exported {len(events)} events to {output_path}")


def _export_json(events: list[dict[str, Any]], output_path: Path) -> None:
    """Export events to JSON."""
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(events, fh, ensure_ascii=False, indent=2, default=str)
    print(f"Exported {len(events)} events to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="HermesDM Audit Log Viewer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--limit", "-n", type=int, default=50,
        help="Number of events to show (default: 50)"
    )
    parser.add_argument(
        "--user", "-u", type=str, default=None,
        help="Filter by username (substring match)"
    )
    parser.add_argument(
        "--session", "-s", type=str, default=None,
        help="Filter by session date (YYYY-MM-DD prefix)"
    )
    parser.add_argument(
        "--type", "-t", type=str, default=None,
        dest="event_type",
        help="Filter by event type (e.g. command_executed, error)"
    )
    parser.add_argument(
        "--export", "-e", type=str, default=None,
        choices=["csv", "json"],
        help="Export filtered events to CSV or JSON file"
    )
    parser.add_argument(
        "--files", "-f", action="store_true",
        help="List all audit files with line counts"
    )

    args = parser.parse_args()

    # --files: just list files
    if args.files:
        _list_files()
        return

    # Read events
    events = AuditLogger.read_events(
        limit=args.limit,
        user=args.user,
        session_ts=args.session,
        event_type=args.event_type,
    )

    if not events:
        print("No events found matching the criteria.")
        sys.exit(0)

    # Export mode
    if args.export:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if args.export == "csv":
            out_path = Path(f"audit_export_{timestamp}.csv")
            _export_csv(events, out_path)
        else:
            out_path = Path(f"audit_export_{timestamp}.json")
            _export_json(events, out_path)
        return

    # Display mode
    print(f"Audit Log — {len(events)} event(s)\n")
    print(f"{'Time':8s} {'Event Type':25s} {'User / Chat':40s} {'Handler / Details'}")
    print("-" * 120)

    for event in events:
        print(_fmt_event(event))


if __name__ == "__main__":
    main()
