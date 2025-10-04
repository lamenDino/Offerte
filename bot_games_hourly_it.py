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
from PIL import Image, ImageDraw, ImageFont
import io
from googletrans import Translator

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
        self.translator = Translator()

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
                   'deluxe', 'premium', 'standard', 'ultimate', 'complete']
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

    def translate_to_italian(self, text):
        """Traduce il testo in italiano se necessario"""
        try:
            if len(text) < 10:  # Testi troppo corti spesso non vengono tradotti bene
                return text
            
            # Prova a rilevare la lingua
            detected = self.translator.detect(text)
            if detected.lang == 'it':
                return text
            
            # Traduce in italiano
            translated = self.translator.translate(text, dest='it')
            return translated.text
        except Exception as e:
            logger.warning(f"Errore traduzione: {e}")
            return text

    def get_game_image(self, title, platform, image_url=None):
        """Scarica l'immagine di copertina del gioco"""
        try:
            if image_url:
                response = requests.get(image_url, timeout=10)
                if response.status_code == 200:
                    return Image.open(io.BytesIO(response.content))
            
            # Fallback: cerca su Steam Store API
            search_url = f"https://store.steampowered.com/api/storesearch/?term={title}&l=italian&cc=IT"
            response = requests.get(search_url, timeout=10)
            data = response.json()
            
            if data.get('items'):
                item = data['items'][0]
                image_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{item['id']}/header.jpg"
                response = requests.get(image_url, timeout=10)
                if response.status_code == 200:
                    return Image.open(io.BytesIO(response.content))
            
            return None
        except Exception as e:
            logger.warning(f"Errore scaricamento immagine per {title}: {e}")
            return None

    def create_games_preview_image(self, games):
        """Crea un'immagine collage con le copertine dei giochi"""
        try:
            # Dimensioni base
            img_width = 800
            game_height = 120
            total_height = len(games) * game_height + 50
            
            # Crea immagine base
            image = Image.new('RGB', (img_width, total_height), color='#2C2F36')
            draw = ImageDraw.Draw(image)
            
            # Font (usa font di sistema)
            try:
                font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
                font_desc = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            except:
                font_title = ImageFont.load_default()
                font_desc = ImageFont.load_default()
            
            y_offset = 25
            
            for game in games:
                # Scarica immagine copertina
                cover_image = self.get_game_image(game['title'], game['platform'], game.get('image_url'))
                
                if cover_image:
                    # Ridimensiona copertina
                    cover_image = cover_image.resize((100, 80))
                    image.paste(cover_image, (20, y_offset))
                
                # Testo del gioco
                text_x = 140 if cover_image else 20
                
                # Titolo
                draw.text((text_x, y_offset), game['title'], fill='white', font=font_title)
                
                # Piattaforma
                platform_text = f"{game['platform']} • {game['genre']}"
                draw.text((text_x, y_offset + 20), platform_text, fill='#7289DA', font=font_desc)
                
                # Descrizione (max 2 righe)
                desc_lines = self.wrap_text(game['description'], 50)
                for i, line in enumerate(desc_lines[:2]):
                    draw.text((text_x, y_offset + 40 + i*15), line, fill='#B9BBBE', font=font_desc)
                
                y_offset += game_height
            
            # Salva immagine
            image_path = "games_preview.png"
            image.save(image_path, "PNG")
            return image_path
            
        except Exception as e:
            logger.error(f"Errore creazione immagine preview: {e}")
            return None

    def wrap_text(self, text, width):
        """Spezza il testo in righe di lunghezza massima"""
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line + " " + word) <= width:
                current_line += " " + word if current_line else word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines

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
                    
                    # Descrizione e traduzione
                    desc = g.get("description") or "Gioco gratuito per tempo limitato."
                    desc = self.translate_to_italian(desc)
                    desc = desc[:200] + "..." if len(desc) > 200 else desc
                    
                    # Genere
                    categories = g.get("categories", [])
                    genre = "Azione"  # Default
                    if categories:
                        genre_map = {
                            "Action": "Azione",
                            "Adventure": "Avventura", 
                            "RPG": "RPG",
                            "Strategy": "Strategia",
                            "Simulation": "Simulazione",
                            "Sports": "Sport",
                            "Racing": "Corse"
                        }
                        for cat in categories:
                            cat_path = cat.get("path", "")
                            for eng, ita in genre_map.items():
                                if eng.lower() in cat_path.lower():
                                    genre = ita
                                    break
                    
                    # Immagine copertina
                    image_url = None
                    key_images = g.get("keyImages", [])
                    for img in key_images:
                        if img.get("type") in ["DieselStoreFrontWide", "OfferImageWide"]:
                            image_url = img.get("url")
                            break
                    
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
                        "end_date": end,
                        "image_url": image_url
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
                
                # Cerca dettagli su Steam
                try:
                    # Estrai Steam App ID dal link
                    import re
                    app_id_match = re.search(r'/app/(\d+)', link)
                    if app_id_match:
                        app_id = app_id_match.group(1)
                        steam_api_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=italian"
                        steam_response = requests.get(steam_api_url, timeout=10)
                        steam_data = steam_response.json()
                        
                        if steam_data.get(app_id, {}).get("success"):
                            game_data = steam_data[app_id]["data"]
                            desc = game_data.get("short_description", "Offerta gratuita disponibile su Steam.")
                            desc = self.translate_to_italian(desc)
                            
                            # Genere
                            genres = game_data.get("genres", [])
                            genre = "Vario"
                            if genres:
                                genre = self.translate_to_italian(genres[0].get("description", "Vario"))
                            
                            # Immagine
                            image_url = game_data.get("header_image")
                        else:
                            desc = "Offerta gratuita disponibile su Steam."
                            genre = "Vario"
                            image_url = None
                    else:
                        desc = "Offerta gratuita disponibile su Steam."
                        genre = "Vario"
                        image_url = None
                except:
                    desc = "Offerta gratuita disponibile su Steam."
                    genre = "Vario"
                    image_url = None
                
                out.append({
                    "id": gid,
                    "title": title,
                    "description": desc,
                    "genre": genre,
                    "url": link,
                    "platform": "Steam",
                    "end_date": "Fino ad esaurimento",
                    "image_url": image_url
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
                
                desc = g.get("description") or "Giveaway gratuito disponibile."
                desc = self.translate_to_italian(desc)
                desc = desc[:200] + "..." if len(desc) > 200 else desc
                
                # Genere (mapping dalle piattaforme GamerPower)
                platforms = g.get("platforms", "").lower()
                genre = "Vario"
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
                
                image_url = g.get("image")
                
                out.append({
                    "id": gid,
                    "title": title,
                    "description": desc,
                    "genre": genre,
                    "url": link,
                    "platform": "GamerPower",
                    "end_date": end,
                    "image_url": image_url
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
                desc = self.translate_to_italian(desc)
                
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
                        "end_date": "Fino a esaurimento",
                        "image_url": None
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
                        "description": "Offerta gratuita su GOG",
                        "genre": "PC",
                        "url": link,
                        "platform": "GOG",
                        "end_date": "Fino a esaurimento",
                        "image_url": None
                    })
        except Exception as e:
            logger.error(f"Errore GOG: {e}")
        return out

    async def send_hourly_update(self):
        games = []
        games += await self.fetch_epic()
        games += await self.fetch_steam()
        games += await self.fetch_gamer()
        games += await self.fetch_prime()
        games += await self.fetch_gog()

        if not games:
            logger.info("Nessun nuovo gioco gratuito trovato.")
            return

        # Aggiungi i nuovi giochi al set dei giochi già inviati
        for game in games:
            self.sent.add(game["id"])
        
        # Salva il file con i giochi già inviati
        self.save_sent()
        logger.info(f"Salvati {len(games)} nuovi giochi nel tracking duplicati.")

        # Crea immagine preview
        preview_image_path = self.create_games_preview_image(games)

        # Testo del messaggio
        parts = ["🎮 *Aggiornamento Giochi Gratuiti* 🎮\n"]
        for g in games:
            parts.append(
                f"*{g['title']}*\n"
                f"{g['description']}\n"
                f"🎯 _{g['genre']}_ • _{g['platform']}_ – Scade: {g['end_date']}\n"
                f"[Scarica Gratis]({g['url']})\n"
            )

        text = "\n".join(parts)

        # Invia con immagine preview se disponibile
        if preview_image_path and os.path.exists(preview_image_path):
            with open(preview_image_path, 'rb') as photo:
                await self.bot.send_photo(
                    chat_id=CHANNEL_USERNAME,
                    photo=photo,
                    caption=text,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                if FRIENDS_CHAT_ID:
                    photo.seek(0)  # Reset file pointer
                    await self.bot.send_photo(
                        chat_id=FRIENDS_CHAT_ID,
                        photo=photo,
                        caption=text,
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            # Rimuovi il file temporaneo
            os.remove(preview_image_path)
        else:
            # Fallback senza immagine
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