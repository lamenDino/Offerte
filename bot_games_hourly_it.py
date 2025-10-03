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
        """Ottiene giochi gratuiti Epic Games con descrizione italiana"""
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
                                # Traduzione descrizione in italiano
                                if not description:
                                    description = "Gioco gratuito disponibile per un tempo limitato su Epic Games Store."
                                else:
                                    description = description[:200] + "..." if len(description) > 200 else description
                                
                                # Data di fine offerta
                                end_date = offers[0].get('endDate', '')
                                end_date_it = ""
                                if end_date:
                                    try:
                                        dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                        end_date_it = dt.strftime('%d/%m/%Y alle %H:%M')
                                    except:
                                        pass
                                
                                free_games.append({
                                    'id': game_id,
                                    'title': title,
                                    'description': description,
                                    'url': store_url,
                                    'platform': 'Epic Games Store',
                                    'end_date': end_date_it
                                })
            
            return free_games
            
        except Exception as e:
            logger.error(f"Errore Epic Games: {e}")
            return []

    async def get_steam_free_games(self):
        """Ottiene giochi gratuiti Steam da SteamDB con data di fine offerta"""
        try:
            # Usa SteamDB API per promozioni gratuite
            url = "https://steamdb.info/api/GetPriceChanges/?appType=1&hasDiscount=1&isFree=1"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=15)
            
            # Fallback: usa feed RSS di IsThereAnyDeal per offerte gratuite
            if response.status_code != 200:
                feed_url = "https://isthereanydeal.com/rss/deals/free/"
                feed = feedparser.parse(feed_url)
                
                free_games = []
                for entry in feed.entries[:5]:
                    title = entry.get('title', '').strip()
                    link = entry.get('link', '')
                    summary = entry.get('summary', '')
                    
                    if not title or not link or 'steam' not in title.lower():
                        continue
                    
                    # Estrai link Steam dalla descrizione
                    steam_link = link
                    if 'steam' not in link.lower():
                        # Cerca link Steam nella descrizione
                        soup = BeautifulSoup(summary, 'html.parser')
                        steam_links = [a['href'] for a in soup.find_all('a', href=True) if 'store.steampowered.com' in a['href']]
                        if steam_links:
                            steam_link = steam_links[0]
                    
                    if self.validate_url(steam_link):
                        game_id = f"steam_{title.lower().replace(' ', '_')[:50]}"
                        
                        if game_id not in self.sent_games:
                            # Data pubblicazione in italiano
                            published_date = ""
                            if entry.get('published'):
                                try:
                                    dt = datetime.strptime(entry['published'], '%a, %d %b %Y %H:%M:%S %Z')
                                    published_date = dt.strftime('%d/%m/%Y')
                                except:
                                    pass
                            
                            free_games.append({
                                'id': game_id,
                                'title': title,
                                'description': "Offerta gratuita disponibile su Steam per un tempo limitato.",
                                'url': steam_link,
                                'platform': 'Steam',
                                'end_date': "Fino ad esaurimento scorte" if not published_date else f"Dal {published_date}"
                            })
                
                return free_games
            
            return []
            
        except Exception as e:
            logger.error(f"Errore Steam: {e}")
            return []

    async def get_gamerpower_games(self):
        """Ottiene giochi da GamerPower con traduzione italiana"""
        try:
            # API diretta GamerPower per PC games
            url = "https://www.gamerpower.com/api/giveaways?platform=pc&type=game"
            response = requests.get(url, timeout=15)
            data = response.json()
            
            free_games = []
            for game in data[:5]:  # Primi 5
                title = game.get('title', '').strip()
                game_url = game.get('gamerpower_url', '')
                open_url = game.get('open_giveaway', '')
                description = game.get('description', '')
                end_date = game.get('end_date', '')
                
                # Usa il link diretto se disponibile, altrimenti GamerPower
                final_url = open_url if open_url != "N/A" else game_url
                
                if not title or not final_url:
                    continue
                
                if self.validate_url(final_url):
                    game_id = f"gamerpower_{game.get('id', title.lower().replace(' ', '_')[:50])}"
                    
                    if game_id not in self.sent_games:
                        # Traduzione descrizione
                        if not description or description == "N/A":
                            description = "Giveaway gratuito disponibile per un tempo limitato."
                        else:
                            description = description[:200] + "..." if len(description) > 200 else description
                        
                        # Formatta data fine
                        end_date_it = "Data non specificata"
                        if end_date and end_date != "N/A":
                            try:
                                dt = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
                                end_date_it = dt.strftime('%d/%m/%Y alle %H:%M')
                            except:
                                end_date_it = end_date
                        
                        free_games.append({
                            'id': game_id,
                            'title': title,
                            'description': description,
                            'url': final_url,
                            'platform': game.get('platforms', 'PC'),
                            'end_date': end_date_it
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
        
        # Data di scadenza sempre presente
        if game.get('end_date'):
            message += f"⏰ Scade: {game['end_date']}\n"
        else:
            message += f"⏰ Scade: Fino ad esaurimento scorte\n"
        
        message += f"\n🔗 [Scarica Gratis]({game['url']})\n\n"
        message += f"💬 {CHANNEL_USERNAME}"
        
        return message

    async def send_hourly_update(self):
        """Invia aggiornamento ogni ora"""
        try:
            logger.info("🔄 Controllo aggiornamenti ogni ora...")
            
            # Ottieni giochi da tutte le fonti
            epic_games = await self.get_epic_games()
            steam_games = await self.get_steam_free_games()
            gamerpower_games = await self.get_gamerpower_games()
            
            all_games = epic_games + steam_games + gamerpower_games
            
            if not all_games:
                logger.info("Nessun nuovo gioco trovato.")
                return
            
            logger.info(f"Trovati {len(all_games)} nuovi giochi da inviare")
            
            # Invia ogni nuovo gioco
            sent_count = 0
            for game in all_games:
                try:
                    message = self.format_game_message(game)
                    
                    await self.bot.send_message(
                        chat_id=CHANNEL_USERNAME,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=False
                    )
                    
                    # Aggiungi a lista inviati
                    self.sent_games.add(game['id'])
                    sent_count += 1
                    
                    logger.info(f"✅ Inviato: {game['title']}")
                    
                    # Rate limiting
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    logger.error(f"Errore invio {game['title']}: {e}")
            
            # Salva stato
            self.save_sent_games()
            
            if sent_count > 0:
                logger.info(f"📤 Inviati {sent_count} giochi al canale")
                
        except Exception as e:
            logger.error(f"Errore aggiornamento: {e}")

async def main():
    bot = FreeGamesBot()
    await bot.send_hourly_update()

if __name__ == "__main__":
    asyncio.run(main())