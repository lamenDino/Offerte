FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY bot_games_all_sources.py ./
RUN apt-get update && apt-get install -y cron
COPY start_hourly.sh ./
RUN chmod +x start_hourly.sh
EXPOSE 8080
CMD ["./start_hourly.sh"]
