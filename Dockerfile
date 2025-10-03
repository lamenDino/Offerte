FROM python:3.11-slim

WORKDIR /app

# Installa dipendenze
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia codice aggiornato con traduzioni italiane
COPY bot_games_hourly_it.py ./

# Scheduling con cron
RUN apt-get update && apt-get install -y cron

# Script di avvio ogni ora
COPY start_hourly.sh ./
RUN chmod +x start_hourly.sh

EXPOSE 8080

CMD ["./start_hourly.sh"]