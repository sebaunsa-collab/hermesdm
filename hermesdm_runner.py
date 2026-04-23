#!/usr/bin/env python3
"""
HermesDM Telegram Runner

Invocado por Hermes Agent: python3 hermesdm_runner.py
Heredar environment del gateway → usa el mismo Telegram bot token.

Uso:
    python3 hermesdm_runner.py                    # foreground (dev)
    pm2 start hermesdm_runner.py --name hermesdm # background (prod)

El runner espera comandos del padre via stdin o señales.
Para uso standalone, corre directamente:
    hermesdm
    # o: python -m bot.telegram_handler
"""
import logging
import os
import signal
import sys

BOT_MODULE = "bot.telegram_handler"

log = logging.getLogger("hermesdm.runner")


def run_bot():
    """Ejecuta el bot como subprocess."""
    # Usar sys.executable para obtener el python del venv activo
    log.info("Starting HermesDM bot...")
    os.execv(sys.executable, [sys.executable, "-m", BOT_MODULE])


def signal_handler(signum, frame):
    log.info(f"Received signal {signum}, restarting bot...")
    run_bot()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | hermesdm | %(levelname)s | %(message)s",
    )

    # Registro señales para restart automático
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    run_bot()
