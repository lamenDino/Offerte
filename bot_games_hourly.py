import os
import logging
import asyncio
import requests
import feedparser
import json
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FreeGamesBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.sent_games_file = "sent_games.json"
        self.sent_games = self.load_sent_games()

    def load_sent_games(self):
        try:
            with open(self.sent_games_file, 'r') as f:
                return set(json.load(f))
        except FileNotFoundError:
            return set()

    def save_sent_games(self):
        with open(self.sent_games_file, 'w') as f:
            json.dump(list(self.sent_games), f)

    def validate_url(self, url):
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code in [200, 301, 302]:
                return True
            logger.warning(f"URL non valido (status {response.status_code}): {url}")
            return False
        except requests.RequestException as e:
            logger.warning(f"URL non raggiungibile: {url} - {e}")
            return False

    async def get_epic_games(self):
        try:
            url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
            response = requests.get(url, timeout=15)
            data = response.json()
            free_games = []
            elements = data.get('data', {}).get('Catalog', {}).get('searchStore', {}).get('elements', [])
            for game in elements:
                promotions = game.get('promotions')
                if not promotions:
                    continue
                promotional_offers = promotions.get('promotionalOffers', [])
                if not promotional_offers:
                    continue
                for promo in promotional_offers:
                    offers = promo.get('promotionalOffers', [])
                    if offers:
                        title = game.get('title', '').strip()
                        description = game.get('description', '')
                        slug = game.get('productSlug', '')
                        if not title or not slug:
                            continue
                        store_url = f"https://store.epicgames.com/it/p/{slug}"
                        if self.validate_url(store_url):
                            game_id = f"epic_{title.lower().replace(' ', '_')}"
                            if game_id not in self.sent_games:
                                free_games.append({
                                    'id': game_id,
                                    'title': title,
                                    'description': description[:200] + "..." if len(description) > 200 else description,
                                    'url': store_url,
                                    'platform': 'Epic Games',
                                    'end_date': offers[0].get('endDate', '')
                                })
            return free_games
        except Exception as e:
            logger.error(f"Errore Epic Games: {e}")
            return []

    async def get_steam_free_games(self):
        try:
            feed_url = "https://steamcommunity.com/groups/freegamesfinders/rss/"
            feed = feedparser.parse(feed_url)
            free_games = []
            for entry in feed.entries[:5]:
                title = entry.get('title', '').strip()
                link = entry.get('link', '')
                summary = entry.get('summary', '')
                if not title or not link:
                    continue
                if any(k in title.lower() for k in ['free', 'gratis', 'steam']):
                    if self.validate_url(link):
                        game_id = f"steam_{title.lower().replace(' ', '_')[:50]}"
                        if game_id not in self.sent_games:
                            free_games.append({
                                'id': game_id,
                                'title': title,
                                'description': summary[:200] + "..." if len(summary) > 200 else summary,
                                'url': link,
                                'platform': 'Steam Community',
                                'published': entry.get('published', '')
                            })
            return free_games
        except Exception as e:
            logger.error(f"Errore Steam: {e}")
            return []

    async def get_gamerpower_games(self):
        try:
            feed_url = "https://www.gamerpower.com/rss/pc"
            feed = feedparser.parse(feed_url)
            free_games = []
            for entry in feed.entries[:5]:
                title = entry.get('title', '').strip()
                link = entry.get('link', '')
                summary = entry.get('summary', '')
                if not title or not link:
                    continue
                if self.validate_url(link):
                    game_id = f"gamerpower_{title.lower().replace(' ', '_')[:50]}"
                    if game_id not in self.sent_games:
                        free_games.append({
                            'id': game_id,
                            'title': title,
                            'description': summary[:200] + "..." if len(summary) > 200 else summary,
                            'url': link,
                            'platform': 'PC (Varie Piattaforme)',
                            'published': entry.get('published', '')
                        })
            return free_games
        except Exception as e:
            logger.error(f"Errore GamerPower: {e}")
            return []

    def format_game_message(self, game):
        """Formatta messaggio per Telegram in italiano"""
        message = f"🎮 **{game['title']}**\n\n"
        if game.get('description'):
            message += f"📝 {game['description']}\n\n"
        message += f"🏷️ Piattaforma: {game['platform']}\n"
        if game.get('end_date'):
            try:
                dt = datetime.fromisoformat(game['end_date'].replace('Z', '+00:00'))
                message += f"⏰ Scade: {dt.strftime('%d/%m/%Y')}\n"
            except Exception:
                pass
        elif game.get('published'):
            try:
                dt = datetime.strptime(game['published'], '%a, %d %b %Y %H:%M:%S %Z')
                message += f"📅 Pubblicato: {dt.strftime('%d/%m/%Y')}\n"
            except Exception:
                pass
        message += f"\n🔗 [Scarica Gratis]({game['url']})\n\n"
        message += f"💬 {CHANNEL_USERNAME}"
        return message

    async def send_hourly_update(self):
        logger.info("🔄 Controllo aggiornamenti ogni ora...")
        epic_games = await self.get_epic_games()
        steam_games = await self.get_steam_free_games()
        gamerpower_games = await self.get_gamerpower_games()
        all_games = epic_games + steam_games + gamerpower_games
        if not all_games:
            logger.info("Nessun nuovo gioco trovato.")
            return
        sent_count = 0
        for game in all_games:
            try:
                message = self.format_game_message(game)
                await self.bot.send_message(chat_id=CHANNEL_USERNAME, text=message, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False)
                self.sent_games.add(game['id'])
                sent_count += 1
                logger.info(f"✅ Inviato: {game['title']}")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Errore invio {game['title']}: {e}")
        self.save_sent_games()
        if sent_count > 0:
            logger.info(f"📤 Inviati {sent_count} giochi al canale")

async def main():
    bot = FreeGamesBot()
    await bot.send_hourly_update()

if __name__ == "__main__":
    asyncio.run(main())