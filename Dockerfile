FROM python:3.11-slim

WORKDIR /app

# Installa dipendenze di sistema per PIL e font
RUN apt-get update && apt-get install -y \
    cron \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Installa dipendenze Python
COPY requirements_v2.txt ./
RUN pip install --no-cache-dir -r requirements_v2.txt

# Copia files applicazione
COPY bot_games_hourly_it_v2.py ./bot_games_hourly_it.py
COPY start_hourly.sh ./

# Rendi eseguibile lo script di avvio
RUN chmod +x start_hourly.sh

# Crea directory per i log
RUN mkdir -p /var/log

EXPOSE 8080

CMD ["./start_hourly.sh"]