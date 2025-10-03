FROM python:3.11-slim

WORKDIR /app

# Installa dipendenze
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia codice
COPY bot_games_channel.py ./
COPY .env ./

# Scheduling con cron
RUN apt-get update && apt-get install -y cron

# Script di avvio
COPY start.sh ./
RUN chmod +x start.sh

EXPOSE 8080

CMD ["./start.sh"]