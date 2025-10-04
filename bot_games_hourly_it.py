import os
import logging
import asyncio
import requests
import feedparser
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
FRIENDS_CHAT_ID = os.getenv("FRIENDS_CHAT_ID")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"FRIENDS_CHAT_ID = {FRIENDS_CHAT_ID}")

class FreeGamesBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.sent_file = "sent_games.json"
        self.sent = self.load_sent()

    def load_sent(self):
        try:
            with open(self.sent_file) as f:
                return set(json.load(f))
        except:
            return set()

    def save_sent(self):
        with open(self.sent_file, "w") as f:
            json.dump(list(self.sent), f)

    def normalize_title(self, title):
        """Normalizza il titolo per rilevare duplicati cross-platform"""
        # Rimuovi caratteri speciali, numeri di versione, parentesi
        normalized = re.sub(r'[^\w\s]', '', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Rimuovi suffissi comuni
        suffixes = ['free', 'gratis', 'giveaway', 'epic games', 'steam', 'edition', 
                   'deluxe', 'premium', 'standard', 'ultimate', 'complete', 'game']
        for suffix in suffixes:
            normalized = re.sub(rf'\b{suffix}\b', '', normalized).strip()
        
        return normalized

    def validate(self, url):
        try:
            p = urlparse(url)
            if not p.scheme or not p.netloc:
                return False
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
            if r.status_code in (200, 301, 302, 403):
                return True
            r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            return r.status_code in (200, 301, 302, 403)
        except:
            return False

    def simple_translate_to_italian(self, text):
        """Traduzione semplice senza dipendenze esterne"""
        # Dizionario base per traduzioni comuni
        translations = {
            'action': 'Azione',
            'adventure': 'Avventura', 
            'rpg': 'RPG',
            'role-playing': 'RPG',
            'strategy': 'Strategia',
            'simulation': 'Simulazione',
            'sports': 'Sport',
            'racing': 'Corse',
            'puzzle': 'Puzzle',
            'shooter': 'Sparatutto',
            'free game': 'gioco gratuito',
            'limited time': 'tempo limitato',
            'available': 'disponibile',
            'download': 'scarica',
            'survival': 'sopravvivenza',
            'building': 'costruzione',
            'fantasy': 'fantasy',
            'mystical': 'mistico',
            'creatures': 'creature'
        }
        
        # Sostituzioni semplici
        text_lower = text.lower()
        for eng, ita in translations.items():
            text_lower = text_lower.replace(eng, ita)
        
        # Se il testo è molto lungo e sembra inglese, ritorna una descrizione generica
        if len(text) > 100 and any(word in text.lower() for word in ['the', 'and', 'with', 'for', 'you']):
            return "Gioco gratuito per tempo limitato con contenuti esclusivi."
        
        return text_lower.capitalize() if text_lower != text.lower() else text

    def get_genre_from_categories(self, categories):
        """Estrae il genere dalle categorie"""
        if not categories:
            return "Azione"
        
        genre_map = {
            "action": "Azione",
            "adventure": "Avventura", 
            "rpg": "RPG",
            "role-playing": "RPG",
            "strategy": "Strategia",
            "simulation": "Simulazione",
            "sports": "Sport",
            "racing": "Corse",
            "puzzle": "Puzzle",
            "shooter": "Sparatutto",
            "survival": "Sopravvivenza",
            "building": "Costruzione",
            "indie": "Indie"
        }
        
        for cat in categories:
            cat_path = cat.get("path", "").lower() if isinstance(cat, dict) else str(cat).lower()
            for eng, ita in genre_map.items():
                if eng in cat_path:
                    return ita
        
        return "Azione"

    async def fetch_epic(self):
        out = []
        try:
            data = requests.get(
                "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions",
                timeout=15
            ).json()
            
            elems = data.get("data", {})\
                .get("Catalog", {})\
                .get("searchStore", {})\
                .get("elements", [])
            
            for g in elems:
                promotions = g.get("promotions") or {}
                for po in promotions.get("promotionalOffers", []):
                    offs = po.get("promotionalOffers") or []
                    if not offs:
                        continue
                    
                    title = g.get("title", "").strip()
                    slug = g.get("productSlug", "")
                    if not title or not slug:
                        continue
                    
                    link = f"https://store.epicgames.com/it/p/{slug}"
                    if not self.validate(link):
                        continue
                    
                    # ID basato su titolo normalizzato
                    normalized_title = self.normalize_title(title)
                    gid = f"game_{normalized_title}"
                    if gid in self.sent:
                        continue
                    
                    # Descrizione e traduzione semplice
                    desc = g.get("description") or "Gioco gratuito per tempo limitato."
                    desc = self.simple_translate_to_italian(desc)
                    desc = desc[:200] + "..." if len(desc) > 200 else desc
                    
                    # Genere
                    categories = g.get("categories", [])
                    genre = self.get_genre_from_categories(categories)
                    
                    # Data fine
                    end = ""
                    ed = offs[0].get("endDate", "")
                    if ed:
                        try:
                            dt = datetime.fromisoformat(ed.replace("Z", "+00:00"))
                            end = dt.strftime("%d/%m/%Y alle %H:%M")
                        except:
                            pass
                    
                    out.append({
                        "id": gid,
                        "title": title,
                        "description": desc,
                        "genre": genre,
                        "url": link,
                        "platform": "Epic Games",
                        "end_date": end
                    })
        except Exception as e:
            logger.error(f"Errore Epic Games: {e}")
        return out

    async def fetch_steam(self):
        out = []
        try:
            feed = feedparser.parse("https://isthereanydeal.com/rss/deals/free/")
            for e in feed.entries[:5]:
                title = e.title.strip()
                
                # Pulisci il titolo da "Free" alla fine
                if title.lower().endswith(" free"):
                    title = title[:-5].strip()
                
                soup = BeautifulSoup(e.summary, "html.parser")
                links = [
                    a["href"]
                    for a in soup.find_all("a", href=True)
                    if "store.steampowered.com" in a["href"]
                ]
                
                if not links:
                    continue
                
                link = links[0]
                if not self.validate(link):
                    continue
                
                # ID basato su titolo normalizzato
                normalized_title = self.normalize_title(title)
                gid = f"game_{normalized_title}"
                if gid in self.sent:
                    continue
                
                # Descrizione
                desc = "Offerta gratuita disponibile su Steam per tempo limitato."
                
                # Cerca dettagli su Steam se possibile
                try:
                    app_id_match = re.search(r'/app/(\d+)', link)
                    if app_id_match:
                        app_id = app_id_match.group(1)
                        steam_api_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=italian"
                        steam_response = requests.get(steam_api_url, timeout=10)
                        steam_data = steam_response.json()
                        
                        if steam_data.get(app_id, {}).get("success"):
                            game_data = steam_data[app_id]["data"]
                            short_desc = game_data.get("short_description", "")
                            if short_desc:
                                desc = self.simple_translate_to_italian(short_desc)
                            
                            # Genere
                            genres = game_data.get("genres", [])
                            genre = "PC"
                            if genres:
                                genre = self.simple_translate_to_italian(genres[0].get("description", "PC"))
                        else:
                            genre = "PC"
                    else:
                        genre = "PC"
                except:
                    genre = "PC"
                
                out.append({
                    "id": gid,
                    "title": title,
                    "description": desc,
                    "genre": genre,
                    "url": link,
                    "platform": "Steam",
                    "end_date": "Fino ad esaurimento"
                })
        except Exception as e:
            logger.error(f"Errore Steam: {e}")
        return out

    async def fetch_gamer(self):
        out = []
        try:
            data = requests.get(
                "https://www.gamerpower.com/api/giveaways?platform=pc&type=game",
                timeout=15
            ).json()
            
            for g in data[:5]:
                title = g.get("title", "").strip()
                
                # Rimuovi "(Epic Games)" dal titolo se presente
                title = re.sub(r'\s*\([^)]*\)\s*', '', title).strip()
                
                link = g.get("open_giveaway") or g.get("gamerpower_url")
                if not title or not link:
                    continue
                
                if not self.validate(link):
                    continue
                
                # ID basato su titolo normalizzato
                normalized_title = self.normalize_title(title)
                gid = f"game_{normalized_title}"
                if gid in self.sent:
                    continue
                
                desc = g.get("description") or "Giveaway gratuito disponibile per tempo limitato."
                desc = self.simple_translate_to_italian(desc)
                desc = desc[:200] + "..." if len(desc) > 200 else desc
                
                # Genere
                platforms = g.get("platforms", "").lower()
                genre = "Azione"
                if "steam" in platforms:
                    genre = "PC"
                elif "epic" in platforms:
                    genre = "Azione"
                
                # Data fine
                end = "Data non specificata"
                ed = g.get("end_date", "")
                if ed and ed != "N/A":
                    try:
                        dt = datetime.strptime(ed, "%Y-%m-%d %H:%M:%S")
                        end = dt.strftime("%d/%m/%Y alle %H:%M")
                    except:
                        end = ed
                
                out.append({
                    "id": gid,
                    "title": title,
                    "description": desc,
                    "genre": genre,
                    "url": link,
                    "platform": "GamerPower",
                    "end_date": end
                })
        except Exception as e:
            logger.error(f"Errore GamerPower: {e}")
        return out

    async def fetch_prime(self):
        out = []
        try:
            url = "https://gaming.amazon.com/loot"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            
            items = soup.find_all("div", class_="loot-item")
            for item in items:
                title_el = item.find("h3")
                desc_el = item.find("p", class_="description")
                link_el = item.find("a", href=True)
                
                title = title_el.text.strip() if title_el else "Gioco Prime"
                desc = desc_el.text.strip() if desc_el else "Gioco gratis con Prime Gaming"
                desc = self.simple_translate_to_italian(desc)
                
                href = link_el["href"] if link_el else None
                link = f"https://gaming.amazon.com{href}" if href else url
                
                # ID basato su titolo normalizzato
                normalized_title = self.normalize_title(title)
                gid = f"game_{normalized_title}"
                if gid not in self.sent and self.validate(link):
                    out.append({
                        "id": gid,
                        "title": title,
                        "description": desc,
                        "genre": "Vario",
                        "url": link,
                        "platform": "Twitch Prime Gaming",
                        "end_date": "Fino a esaurimento"
                    })
        except Exception as e:
            logger.error(f"Errore Twitch Prime: {e}")
        return out

    async def fetch_gog(self):
        out = []
        try:
            url = "https://www.gog.com/en/partner/free_games"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            
            tiles = soup.find_all("div", class_="product-tile")
            for tile in tiles:
                title_el = tile.find("h3", class_="product-title")
                link_el = tile.find_parent("a", href=True)
                
                title = title_el.text.strip() if title_el else "Gioco GOG"
                href = link_el["href"] if link_el else None
                link = (f"https://www.gog.com{href}" if href and href.startswith("/") else href or url)
                
                # ID basato su titolo normalizzato
                normalized_title = self.normalize_title(title)
                gid = f"game_{normalized_title}"
                if gid not in self.sent and self.validate(link):
                    out.append({
                        "id": gid,
                        "title": title,
                        "description": "Offerta gratuita su GOG per tempo limitato.",
                        "genre": "PC",
                        "url": link,
                        "platform": "GOG",
                        "end_date": "Fino a esaurimento"
                    })
        except Exception as e:
            logger.error(f"Errore GOG: {e}")
        return out

    async def fetch_bnet(self):
        return []

    async def fetch_riot(self):
        return []

    async def send_hourly_update(self):
        games = []
        games += await self.fetch_epic()
        games += await self.fetch_steam()
        games += await self.fetch_gamer()
        games += await self.fetch_prime()
        games += await self.fetch_gog()
        games += await self.fetch_bnet()
        games += await self.fetch_riot()

        if not games:
            logger.info("Nessun nuovo gioco gratuito trovato.")
            return

        # Aggiungi i nuovi giochi al set dei giochi già inviati
        for game in games:
            self.sent.add(game["id"])
        
        # Salva il file con i giochi già inviati
        self.save_sent()
        logger.info(f"Salvati {len(games)} nuovi giochi nel tracking duplicati.")
        logger.info(f"Giochi trovati: {[g['title'] for g in games]}")

        # Testo del messaggio migliorato
        parts = ["🎮 *Giochi Gratuiti Disponibili* 🎮\n"]
        for g in games:
            parts.append(
                f"🎯 *{g['title']}*\n"
                f"_{g['description']}_\n"
                f"🏷️ {g['genre']} • 🏪 {g['platform']}\n"
                f"⏰ Scade: {g['end_date']}\n"
                f"[🎮 Scarica Gratis]({g['url']})\n"
            )

        text = "\n".join(parts)

        # Invia messaggio
        await self.bot.send_message(
            chat_id=CHANNEL_USERNAME,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=False
        )

        if FRIENDS_CHAT_ID:
            await self.bot.send_message(
                chat_id=FRIENDS_CHAT_ID,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False
            )

async def main():
    bot = FreeGamesBot()
    await bot.send_hourly_update()

if __name__ == "__main__":
    asyncio.run(main())