#!/usr/bin/env python3
"""
HermesDM Install Script — Patches Hermes Agent to add D&D group integration.

Usage:
    python install.py                        # interactive
    python install.py --group-id -100123456  # non-interactive
    python install.py --uninstall            # revert patches
    python install.py --verify               # check patch status
    python install.py --dry-run              # show what would be done

Requirements:
    - Hermes Agent already installed (~/.hermes/)
    - HermesDM repo cloned somewhere

This script is IDEMPOTENT — safe to run multiple times.
"""

import argparse
import datetime
import os
import shutil
import sys
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────

HERMESDM_ENV = """# ─── HermesDM Configuration ────────────────────────────────────────────
# Copied by hermesdm/scripts/install.py

# REQUIRED: Telegram group ID for D&D sessions (e.g. -1003916745496)
HERMESDM_GROUP_ID={group_id}

# REQUIRED: Path to hermesdm repo (where you cloned it)
HERMESDM_PATH={hermesdm_path}
"""

# ─── Patch: telegram.py ──────────────────────────────────────────────────────
# Injects: sys.path, DND_GROUP_ID, DND_COMMANDS, D&D message filters

TELEGRAM_PATCH_OLD = """from gateway.config import Platform, PlatformConfig"""

TELEGRAM_PATCH_NEW = """# Add hermesdm to path for D&D command handlers
import os as _os
_hermesdm_path = _os.environ.get("HERMESDM_PATH", "{hermesdm_path}")
if _hermesdm_path not in sys.path:
    sys.path.insert(0, _hermesdm_path)

# D&D group integration — 1 bot (Token A) with internal chat_id filter
_hermesdm_group_raw = _os.environ.get("HERMESDM_GROUP_ID", "{group_id}")
DND_GROUP_ID = int(_hermesdm_group_raw)
DND_COMMANDS = {{
    "newgame", "join", "roll", "attack", "cast", "skill",
    "status", "hp", "inventory", "talk", "map", "quests",
    "recap", "resume", "endturn", "campaign", "save",
    "startcombat", "endcombat", "quit", "audit", "imagen", "me",
    "start", "help",
}}

import bot.telegram_handler as hdm_bot

from gateway.config import Platform, PlatformConfig"""

# The D&D group text drop (in _handle_text_message)
TELEGRAM_TEXT_OLD = """        if not update.message or not update.message.text:
            return

        if not self._should_process_message(update.message):
            return

        event = self._build_message_event(update.message, MessageType.TEXT, update_id=update.update_id)"""

TELEGRAM_TEXT_NEW = """        if not update.message or not update.message.text:
            return

        # ── D&D Group: ignore ALL non-D&D content ─────────────────────────
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id == DND_GROUP_ID:
            logger.info("[D&D-DROP] Text in D&D group dropped: %s", update.message.text[:50] if update.message.text else "no text")
            return  # Silently ignore free text in D&D group

        if not self._should_process_message(update.message):
            return

        event = self._build_message_event(update.message, MessageType.TEXT, update_id=update.update_id)"""

# The D&D command routing (in _handle_command)
TELEGRAM_CMD_OLD = """    async def _handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        \"\"\"Handle incoming command messages.\"\"\"
        if not update.message or not update.message.text:
            return
        if not self._should_process_message(update.message, is_command=True):
            return
        
        event = self._build_message_event(update.message, MessageType.COMMAND, update_id=update.update_id)
        await self.handle_message(event)"""

TELEGRAM_CMD_NEW = """    async def _handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        \"\"\"Handle incoming command messages.\"\"\"
        if not update.message or not update.message.text:
            return
        if not self._should_process_message(update.message, is_command=True):
            return

        # ── D&D Group integration ────────────────────────────────────────
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id == DND_GROUP_ID:
            cmd_text = update.message.text or ""
            if cmd_text.startswith("/"):
                parts = cmd_text[1:].split(None, 1)
                cmd_name = parts[0].lower().split('@')[0]
                logger.info("[D&D-CMD] D&D group cmd=%s text=%s", cmd_name, cmd_text[:50])
                if cmd_name in DND_COMMANDS:
                    handler = getattr(hdm_bot, f"cmd_{cmd_name}", None)
                    if handler:
                        try:
                            await handler(update, context)
                            logger.info("[D&D-CMD] Handler %s succeeded", cmd_name)
                            return  # D&D handled — skip LLM
                        except Exception as e:
                            logger.warning("[D&D-CMD] Handler %s error: %s", cmd_name, e)
                            # Fall through to LLM on error
        # ── Normal LLM command processing ───────────────────────────────

        event = self._build_message_event(update.message, MessageType.COMMAND, update_id=update.update_id)
        await self.handle_message(event)"""


# ─── Patch: run.py ───────────────────────────────────────────────────────────
# Registers /j command handler

RUN_PATCH_OLD = """        if canonical == "yolo":
            return await self._handle_yolo_command(event)

        if canonical == "model":"""

RUN_PATCH_NEW = """        if canonical == "yolo":
            return await self._handle_yolo_command(event)

        if canonical == "j":
            return await self._handle_j_command(event)

        if canonical == "model":"""

RUN_HANDLER = """
    async def _handle_j_command(self, event: MessageEvent) -> str:
        \"\"\"Handle /j — start or join a D&D game session (Telegram group).\"\"\"
        args = event.get_command_args().strip()
        chat_id = event.source.chat_id or "unknown"
        
        if args:
            return (
                f"🎲 **Game Session**\\n"
                f"Chat ID: `{chat_id}`\\n"
                f"Action: `{args}`\\n"
                f"_\"Game mode ready — more coming soon.\"_"
            )
        else:
            return (
                f"🎲 **¡Bienvenido a HermesDM!**\\n\\n"
                f"Este grupo está configurado para partidas de D&D.\\n"
                f"Usa `/j new` para crear una nueva partida.\\n"
                f"_\\[experimental\\]_"
            )

"""


# ─── Patch: commands.py ──────────────────────────────────────────────────────
# Adds "j" command definition

COMMANDS_PATCH_OLD = """    # Exit
    CommandDef("quit", "Exit the CLI", "Exit\",
               cli_only=True, aliases=("exit",)),"""

COMMANDS_PATCH_NEW = """    # Game
    CommandDef("j", "Join or start a D&D game session (Telegram group)", "Game",
               gateway_only=True, args_hint="[action]"),

    # Exit
    CommandDef("quit", "Exit the CLI", "Exit",
               cli_only=True, aliases=("exit",)),"""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def find_hermes_agent() -> Path | None:
    """Detect where Hermes Agent is installed."""
    candidates = [
        Path.home() / ".hermes",
        Path.home() / "hermes-agent",
    ]
    for p in candidates:
        if p.exists() and (p / "gateway").exists():
            return p
    return None


def backup_path(original: Path) -> Path:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return original.with_suffix(original.suffix + f".bak.{ts}")


def is_patched(file_path: Path, marker: str) -> bool:
    return marker in file_path.read_text()


def apply_patch(file_path: Path, old: str, new: str, dry_run: bool = False) -> bool:
    """Apply a string replacement patch. Returns True if changed."""
    content = file_path.read_text()
    if old not in content:
        print(f"  [SKIP] Patch marker not found in {file_path.name} — already patched or unexpected file state")
        return False
    if dry_run:
        print(f"  [DRY] Would replace in {file_path.name}: {old[:40]}...")
        return True
    # Backup first time only
    bak = backup_path(file_path)
    shutil.copy2(file_path, bak)
    print(f"  [BAK] {file_path.name} → {bak.name}")
    content = content.replace(old, new, 1)
    file_path.write_text(content)
    print(f"  [OK]  Patched {file_path.name}")
    return True


def uninstall_patch(file_path: Path, marker: str, new: str, old: str, dry_run: bool = False) -> bool:
    """Revert a patch. Returns True if changed."""
    content = file_path.read_text()
    if new not in content:
        print(f"  [SKIP] Revert marker not found in {file_path.name} — not patched")
        return False
    if dry_run:
        print(f"  [DRY] Would revert in {file_path.name}")
        return True
    content = content.replace(new, old, 1)
    file_path.write_text(content)
    print(f"  [OK]  Reverted {file_path.name}")
    return True


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Install HermesDM D&D integration into Hermes Agent")
    parser.add_argument("--group-id", type=str, default=None,
                        help="Telegram group ID for D&D sessions (e.g. -1003916745496)")
    parser.add_argument("--hermesdm-path", type=str, default=None,
                        help="Path to hermesdm repo (default: auto-detect)")
    parser.add_argument("--with-web", action="store_true",
                        help="Also install and configure the web companion dashboard")
    parser.add_argument("--web-port", type=int, default=8080,
                        help="Port for the web companion (default: 8080)")
    parser.add_argument("--state-dir", type=str, default=None,
                        help="Path to HermesDM campaign state directory (default: ~/.hermes/hermesdm/campaigns)")
    parser.add_argument("--uninstall", action="store_true",
                        help="Revert all patches and remove hermesdm from Hermes Agent")
    parser.add_argument("--verify", action="store_true",
                        help="Check patch status without making changes")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without changing files")
    args = parser.parse_args()

    # ── Auto-detect Hermes Agent ───────────────────────────────────────
    hermes_root = find_hermes_agent()
    if not hermes_root:
        print("ERROR: Cannot find Hermes Agent installation.")
        print("Expected ~/.hermes/ or ~/hermes-agent/")
        print("Make sure Hermes Agent is installed before running this script.")
        sys.exit(1)

    print(f"Found Hermes Agent at: {hermes_root}")

    # ── Auto-detect hermesdm path ─────────────────────────────────────
    if args.hermesdm_path:
        hermesdm_path = Path(args.hermesdm_path).resolve()
    else:
        # Try to find hermesdm relative to this script
        script_dir = Path(__file__).resolve().parent.parent
        hermesdm_path = script_dir

    if not hermesdm_path.exists():
        print(f"ERROR: hermesdm path does not exist: {hermesdm_path}")
        sys.exit(1)

    print(f"HermesDM path: {hermesdm_path}")

    # ── Resolve group ID ───────────────────────────────────────────────
    group_id = args.group_id
    if not group_id:
        group_id = os.environ.get("HERMESDM_GROUP_ID", "")

    # group_id is optional for --verify and --uninstall
    if group_id:
        print(f"D&D Group ID: {group_id}")

    # ── Paths ──────────────────────────────────────────────────────────
    telegram_py = hermes_root / "gateway" / "platforms" / "telegram.py"
    run_py = hermes_root / "gateway" / "run.py"
    commands_py = hermes_root / "hermes_cli" / "commands.py"

    for p in [telegram_py, run_py, commands_py]:
        if not p.exists():
            print(f"ERROR: Required file not found: {p}")
            sys.exit(1)

    # ── Verify mode ────────────────────────────────────────────────────
    if args.verify:
        print("\n=== Patch Status ===")
        checks = [
            ("telegram.py: D&D_GROUP_ID", telegram_py, "DND_GROUP_ID"),
            ("telegram.py: D&D text drop", telegram_py, "D&D-DROP"),
            ("telegram.py: D&D cmd routing", telegram_py, "D&D-CMD"),
            ("run.py: /j handler", run_py, "_handle_j_command"),
            ("run.py: /j dispatch", run_py, 'canonical == "j"'),
            ("commands.py: j command", commands_py, 'CommandDef("j"'),
        ]
        all_ok = True
        for name, path, marker in checks:
            ok = is_patched(path, marker)
            status = "✓ PATCHED" if ok else "✗ MISSING"
            print(f"  {status}  {name}")
            if not ok:
                all_ok = False
        # Verify web companion if installed
        web_env = hermesdm_path / "web" / ".env"
        if web_env.exists() or args.with_web:
            print("\n=== Web Companion Status ===")
            sys.path.insert(0, str(hermesdm_path / "scripts"))
            try:
                import setup_web
                web_ok = setup_web.verify_web(hermesdm_path)
                if not web_ok:
                    all_ok = False
            except Exception as e:
                print(f"  [ERR] Could not verify web: {e}")
                all_ok = False
        sys.exit(0 if all_ok else 1)

    # ── Uninstall mode ─────────────────────────────────────────────────
    if args.uninstall:
        print("\n=== Uninstalling HermesDM patches ===")
        # Uninstall web companion first
        sys.path.insert(0, str(hermesdm_path / "scripts"))
        try:
            import setup_web
            setup_web.uninstall_web(hermesdm_path, dry_run=args.dry_run)
        except Exception as e:
            print(f"  [WARN] Could not uninstall web: {e}")
        # We need to find the original text, not the patched text
        # This is tricky because we don't store the original
        # Best we can do: check backup files exist
        backups = list(hermes_root.glob("**/*.bak.2*"))
        if not backups:
            print("No backup files found. Cannot uninstall automatically.")
            print("You may need to reinstall Hermes Agent or restore from git.")
            sys.exit(1)
        print(f"Found {len(backups)} backup file(s).")
        print("To uninstall, restore from backups manually or run:")
        print("  cd ~/.hermes && git checkout -- gateway/ heremes_cli/")
        sys.exit(0)

    # ── Install mode ───────────────────────────────────────────────────
    if not group_id:
        print("ERROR: --group-id is required for installation.")
        print("Pass --group-id -1003916745496 or set HERMESDM_GROUP_ID env var.")
        sys.exit(1)

    print("\n=== Installing HermesDM patches ===")

    patched_any = False

    # 1. telegram.py — three patches
    print("\n[1/3] Patching telegram.py...")
    t_content = telegram_py.read_text()
    if is_patched(telegram_py, "DND_GROUP_ID"):
        print("  [SKIP] telegram.py already has DND_GROUP_ID — appears patched")
    else:
        if apply_patch(telegram_py, TELEGRAM_PATCH_OLD,
                       TELEGRAM_PATCH_NEW.format(hermesdm_path=hermesdm_path, group_id=group_id),
                       args.dry_run):
            patched_any = True

    if is_patched(telegram_py, "D&D-DROP"):
        print("  [SKIP] telegram.py text drop already applied")
    else:
        if apply_patch(telegram_py, TELEGRAM_TEXT_OLD, TELEGRAM_TEXT_NEW, args.dry_run):
            patched_any = True

    if is_patched(telegram_py, "D&D-CMD"):
        print("  [SKIP] telegram.py command routing already applied")
    else:
        if apply_patch(telegram_py, TELEGRAM_CMD_OLD, TELEGRAM_CMD_NEW, args.dry_run):
            patched_any = True

    # 2. run.py — register /j handler
    print("\n[2/3] Patching run.py...")
    if is_patched(run_py, "_handle_j_command"):
        print("  [SKIP] run.py /j handler already exists")
    else:
        # First add the handler method (before _handle_verbose_command)
        if apply_patch(run_py,
                       "    async def _handle_verbose_command(self, event: MessageEvent) -> str:",
                       RUN_HANDLER + "    async def _handle_verbose_command(self, event: MessageEvent) -> str:",
                       args.dry_run):
            patched_any = True
        # Then add the dispatch
        if apply_patch(run_py, RUN_PATCH_OLD, RUN_PATCH_NEW, args.dry_run):
            patched_any = True

    # 3. commands.py — add j command
    print("\n[3/3] Patching commands.py...")
    if is_patched(commands_py, 'CommandDef("j"'):
        print("  [SKIP] commands.py j command already exists")
    else:
        if apply_patch(commands_py, COMMANDS_PATCH_OLD, COMMANDS_PATCH_NEW, args.dry_run):
            patched_any = True

    # ── Write .env config ─────────────────────────────────────────────
    if not args.dry_run and group_id:
        env_path = hermesdm_path / ".env"
        env_content = env_path.read_text() if env_path.exists() else ""
        if "HERMESDM_GROUP_ID" not in env_content:
            with open(env_path, "a") as f:
                f.write(f"\nHERMESDM_GROUP_ID={group_id}\n")
                f.write(f"HERMESDM_PATH={hermesdm_path}\n")
            print(f"\n[CFG] Updated {env_path}")
        else:
            print(f"\n[CFG] .env already has HERMESDM_GROUP_ID — skipping")

    # ── Web companion setup ────────────────────────────────────────────
    if args.with_web:
        sys.path.insert(0, str(hermesdm_path / "scripts"))
        try:
            import setup_web
            state_dir = args.state_dir or None
            web_ok = setup_web.setup_web(
                hermesdm_path,
                state_dir=state_dir,
                port=args.web_port,
                dry_run=args.dry_run,
            )
            if not web_ok and not args.dry_run:
                print("\n  [WARN] Web companion setup had issues, but bot installation is complete.")
        except Exception as e:
            print(f"\n  [ERR] Web companion setup failed: {e}")

    # ── Summary ────────────────────────────────────────────────────────
    print("\n=== Result ===")
    if args.dry_run:
        print("Dry run — no files were modified.")
        print("Run without --dry-run to apply patches.")
    elif patched_any:
        print("✓ HermesDM patches applied successfully!")
        print("\nNext steps:")
        print(f"  1. Edit ~/{hermesdm_path.name}/.env and set:")
        print(f"       HERMESDM_GROUP_ID={group_id}")
        print(f"       HERMESDM_PATH={hermesdm_path}")
        print("  2. Run: dm gateway start")
        print("  3. Test: send /j to your D&D group")
        if args.with_web:
            print("\n  Web companion:")
            print("  4. Run: hermesdm-web")
            print("  5. Open: http://localhost:8080")
    else:
        print("Nothing to do — all patches already applied.")
        print("Run with --verify to check status.")
        if args.with_web:
            print("\n  Web companion:")
            print("  Run: hermesdm-web")
            print("  Or:  cd web && docker compose up -d")


if __name__ == "__main__":
    main()
