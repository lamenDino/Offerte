FROM python:3.11-slim

WORKDIR /app

# Installa dipendenze di sistema
RUN apt-get update && apt-get install -y \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Installa dipendenze Python
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia files applicazione
COPY bot_games_hourly_it.py ./
COPY start_hourly.sh ./

# Rendi eseguibile lo script di avvio
RUN chmod +x start_hourly.sh

# Crea directory per i log
RUN mkdir -p /var/log

EXPOSE 8080

CMD ["./start_hourly.sh"]