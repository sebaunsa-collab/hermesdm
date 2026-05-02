#!/bin/bash
cd /home/hermes/hermesdm
export PYTHONPATH=/home/hermes/hermesdm:$PYTHONPATH
nohup python3 -m bot.telegram_handler >> /home/hermes/hermesdm/logs/bot.log 2>&1 &
echo "Bot started with PID $!"
