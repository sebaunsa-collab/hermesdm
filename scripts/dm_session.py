#!/usr/bin/env python3
"""
dm_session.py — HermesDM Session Runner

CLI que corre polling de Telegram y procesa mensajes de jugadores
usando el game engine de HermesDM.

Uso:
    python3 scripts/dm_session.py                          # polling default
    python3 scripts/dm_session.py --campaign <id>          # iniciar con campaign activa
    python3 scripts/dm_session.py --verbose                 # logging DEBUG
    python3 scripts/dm_session.py --help                    # mostrar usage

Requirements:
    - TELEGRAM_BOT_TOKEN en .env o variable de entorno
    - Virtualenv en hermesdm/venv (el bot usa python-telegram-bot v20)

Nota:
    - NO correr simultáneamente con el bot real (mismo token = conflictos)
    - Ctrl+C para salir cleanly
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path

# Ensure hermesdm package is importable
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from bot.telegram_handler import build_app

log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python3 scripts/dm_session.py",
        description="HermesDM Session Runner — polling de Telegram para sesiones de D&D.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/dm_session.py
  python3 scripts/dm_session.py --campaign my-campaign-001
  python3 scripts/dm_session.py --verbose
  python3 scripts/dm_session.py --verbose --campaign my-campaign-001

Note: Ensure TELEGRAM_BOT_TOKEN is set in .env before running.
        """,
    )
    parser.add_argument(
        "--campaign",
        type=str,
        default=None,
        help="Campaign ID a precargar en memoria (opcional). "
        "Los jugadores podran usar /resume <campaign_id>.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Activa logging DEBUG (muestra todos los updates procesados).",
    )
    parser.add_argument(
        "--drop-pending",
        action="store_true",
        default=True,
        help="Descartar updates pendientes al iniciar (default: True).",
    )
    return parser.parse_args()


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    logging.basicConfig(level=level, format=fmt)
    if not verbose:
        # Silence noisy loggers
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("telegram").setLevel(logging.INFO)


def run_session(campaign_id: str | None, verbose: bool, drop_pending: bool) -> None:
    """Inicializa y corre el bot con polling."""
    setup_logging(verbose)
    log.info("Iniciando HermesDM Session Runner...")
    log.info("Ctrl+C para salir")

    if campaign_id:
        log.info(f"Campaign precargada: {campaign_id}")

    app = build_app()

    # Graceful shutdown
    shutdown_flag = False

    def signal_handler(signum, frame):
        nonlocal shutdown_flag
        if shutdown_flag:
            log.warning("Shutdown ya en progreso...")
            return
        shutdown_flag = True
        log.info("Recibido signal, deteniendo polling...")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # app.post_init se ejecuta cuando el job_queue arranca
    # No necesitamos precargar campaign — los jugadores usan /resume <id>
    try:
        app.run_polling(
            drop_pending_updates=drop_pending,
            allowed_updates=None,  # aceptar todos los tipos de update
        )
    except KeyboardInterrupt:
        log.info("Sesion terminada por el usuario.")
    finally:
        log.info("Sesion finalizada.")


def main() -> None:
    args = parse_args()

    # Verificar que el token esta disponible
    from bot.telegram_handler import settings as bot_settings
    if not bot_settings.TELEGRAM_BOT_TOKEN or bot_settings.TELEGRAM_BOT_TOKEN == "8685005944:***":
        # Tratar de leer del .env
        from pathlib import Path
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            from dotenv import load_dotenv
            load_dotenv(env_path)

        # Re-check after loading .env
        from bot.telegram_handler import Settings
        fresh_settings = Settings()
        if not fresh_settings.TELEGRAM_BOT_TOKEN or fresh_settings.TELEGRAM_BOT_TOKEN == "8685005944:***":
            print("ERROR: TELEGRAM_BOT_TOKEN no esta configurado.")
            print("Edita .env y agrega: TELEGRAM_BOT_TOKEN=tu_token_aqui")
            sys.exit(1)

    run_session(
        campaign_id=args.campaign,
        verbose=args.verbose,
        drop_pending=args.drop_pending,
    )


if __name__ == "__main__":
    main()
