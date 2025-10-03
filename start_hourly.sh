#!/bin/bash
echo "0 * * * * cd /app && python bot_games_all_sources.py" | crontab -
cron
python bot_games_all_sources.py
tail -f /dev/null
