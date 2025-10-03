import os
import logging
import asyncio
import requests
import feedparser
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv

load_dotenv()

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FreeGamesBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.sent_games = set()  # Evita duplicati

    async def get_epic_games(self):
        """Ottiene giochi gratuiti Epic Games"""
        try:
            url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
            response = requests.get(url)
            data = response.json()
            
            free_games = []
            for game in data.get('data', {}).get('Catalog', {}).get('searchStore', {}).get('elements', []):
                if game.get('promotions'):
                    for promo in game['promotions']['promotionalOffers']:
                        if promo['promotionalOffers']:
                            title = game.get('title', 'Gioco senza titolo')
                            description = game.get('description', '')[:200] + "..."
                            
                            # Link Epic Games Store  
                            store_url = f"https://store.epicgames.com/it/p/{game.get('productSlug', '')}"
                            
                            free_games.append({
                                'title': title,
                                'description': description, 
                                'url': store_url,
                                'platform': 'Epic Games',
                                'end_date': promo['promotionalOffers'][0].get('endDate', '')
                            })
            
            return free_games
        except Exception as e:
            logger.error(f"Errore Epic Games: {e}")
            return []

    async def get_steam_free_games(self):
        """Ottiene giochi gratuiti Steam via RSS"""
        try:
            # Feed RSS di SteamDB per giochi gratuiti
            feed_url = "https://steamcommunity.com/groups/freegamesfinders/rss/"
            feed = feedparser.parse(feed_url)
            
            free_games = []
            for entry in feed.entries[:5]:  # Ultimi 5
                if 'steam' in entry.title.lower() or 'free' in entry.title.lower():
                    free_games.append({
                        'title': entry.title,
                        'description': entry.summary[:200] + "...",
                        'url': entry.link,
                        'platform': 'Steam',
                        'published': entry.published
                    })
            
            return free_games
        except Exception as e:
            logger.error(f"Errore Steam: {e}")
            return []

    async def get_gamerpower_games(self):
        """Ottiene giochi da GamerPower RSS"""
        try:
            feed_url = "https://www.gamerpower.com/rss/pc"
            feed = feedparser.parse(feed_url)
            
            free_games = []
            for entry in feed.entries[:3]:  # Ultimi 3
                free_games.append({
                    'title': entry.title,
                    'description': entry.summary[:200] + "...",
                    'url': entry.link,
                    'platform': 'Varie Piattaforme',
                    'published': entry.published
                })
            
            return free_games
        except Exception as e:
            logger.error(f"Errore GamerPower: {e}")
            return []

    def format_game_message(self, game):
        """Formatta messaggio per Telegram"""
        message = f"🎮 **{game['title']}**\n\n"
        message += f"📝 {game['description']}\n\n"
        message += f"🏷️ Piattaforma: {game['platform']}\n"
        
        if game.get('end_date'):
            message += f"⏰ Scade: {game['end_date']}\n"
        
        message += f"\n🔗 [Ottieni Gratis]({game['url']})\n\n"
        message += f"💬 @giochipcgratisitalia"
        
        return message

    async def send_weekly_update(self):
        """Invia aggiornamento settimanale"""
        try:
            # Ottieni giochi da tutte le fonti
            epic_games = await self.get_epic_games()
            steam_games = await self.get_steam_free_games()
            gamerpower_games = await self.get_gamerpower_games()
            
            all_games = epic_games + steam_games + gamerpower_games
            
            if not all_games:
                return
            
            # Messaggio header
            header = f"🎮 **GIOCHI PC GRATUITI - {datetime.now().strftime('%d/%m/%Y')}**\n\n"
            header += f"📅 Aggiornamento settimanale automatico\n"
            header += f"🎯 {len(all_games)} giochi trovati questa settimana\n\n"
            header += "➖➖➖➖➖➖➖➖➖➖\n\n"
            
            await self.bot.send_message(
                chat_id=CHANNEL_USERNAME,
                text=header,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Invia ogni gioco
            for game in all_games:
                game_id = f"{game['title']}_{game['platform']}"
                if game_id not in self.sent_games:
                    message = self.format_game_message(game)
                    
                    await self.bot.send_message(
                        chat_id=CHANNEL_USERNAME,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=False
                    )
                    
                    self.sent_games.add(game_id)
                    await asyncio.sleep(2)  # Evita rate limit
            
            # Footer
            footer = "\n➖➖➖➖➖➖➖➖➖➖\n\n"
            footer += "🔔 Seguici per aggiornamenti automatici ogni settimana!\n"
            footer += "💬 Gruppo: @giochipcgratisitalia_chat\n"
            footer += "🤖 Bot gestito da AI"
            
            await self.bot.send_message(
                chat_id=CHANNEL_USERNAME,
                text=footer,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"Inviati {len(all_games)} giochi al canale")
            
        except Exception as e:
            logger.error(f"Errore invio: {e}")

async def main():
    bot = FreeGamesBot()
    await bot.send_weekly_update()

if __name__ == "__main__":
    asyncio.run(main())