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
import hashlib

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
        # Rimuovi tutto dopo "Giveaway" se presente
        if "giveaway" in title.lower():
            title = re.sub(r'\s*giveaway.*$', '', title, flags=re.IGNORECASE)
        
        # Rimuovi parentesi e contenuto
        title = re.sub(r'\s*\([^)]*\)\s*', '', title)
        
        # Normalizza caratteri speciali e spazi
        normalized = re.sub(r'[^\w\s]', '', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Rimuovi suffissi comuni alla fine
        suffixes = ['free', 'gratis', 'epic games', 'steam', 'edition', 
                   'deluxe', 'premium', 'standard', 'ultimate', 'complete']
        for suffix in suffixes:
            if normalized.endswith(' ' + suffix):
                normalized = normalized[:-len(' ' + suffix)]
        
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

    def get_game_cover_image(self, title, platform):
        """Scarica l'immagine di copertina del gioco"""
        try:
            # Prova con Steam Store API
            if platform.lower() != "steam":
                search_url = f"https://store.steampowered.com/api/storesearch/?term={title}&l=italian&cc=IT"
                response = requests.get(search_url, timeout=10)
                data = response.json()
                
                if data.get('items'):
                    item = data['items'][0]
                    image_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{item['id']}/header.jpg"
                    img_response = requests.get(image_url, timeout=10)
                    if img_response.status_code == 200:
                        return Image.open(io.BytesIO(img_response.content))
            
            # Fallback: immagine placeholder
            placeholder = Image.new('RGB', (300, 140), color='#2C2F36')
            draw = ImageDraw.Draw(placeholder)
            
            try:
                font = ImageFont.load_default()
                # Scrivi il titolo del gioco
                bbox = draw.textbbox((0, 0), title, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (300 - text_width) // 2
                y = (140 - text_height) // 2
                draw.text((x, y), title, fill='white', font=font)
            except:
                draw.text((50, 60), title[:20], fill='white')
            
            return placeholder
            
        except Exception as e:
            logger.warning(f"Errore scaricamento immagine per {title}: {e}")
            # Immagine placeholder di emergenza
            placeholder = Image.new('RGB', (300, 140), color='#7289DA')
            return placeholder

    def create_games_collage(self, games):
        """Crea un'immagine collage con le copertine dei giochi"""
        try:
            if not games:
                return None
                
            # Calcola dimensioni
            cols = 2
            rows = (len(games) + cols - 1) // cols
            cover_width, cover_height = 300, 140
            spacing = 20
            
            total_width = cols * cover_width + (cols - 1) * spacing + 40
            total_height = rows * cover_height + (rows - 1) * spacing + 80
            
            # Crea immagine base
            collage = Image.new('RGB', (total_width, total_height), color='#36393F')
            
            # Aggiungi titolo
            draw = ImageDraw.Draw(collage)
            try:
                title_font = ImageFont.load_default()
                title_text = f"🎮 {len(games)} Giochi Gratuiti Disponibili"
                bbox = draw.textbbox((0, 0), title_text, font=title_font)
                title_width = bbox[2] - bbox[0]
                title_x = (total_width - title_width) // 2
                draw.text((title_x, 20), title_text, fill='white', font=title_font)
            except:
                draw.text((20, 20), f"🎮 {len(games)} Giochi Gratuiti", fill='white')
            
            # Aggiungi copertine
            for i, game in enumerate(games):
                row = i // cols
                col = i % cols
                
                x = 20 + col * (cover_width + spacing)
                y = 60 + row * (cover_height + spacing)
                
                # Scarica e ridimensiona immagine
                cover = self.get_game_cover_image(game['title'], game['platform'])
                if cover:
                    cover = cover.resize((cover_width, cover_height))
                    collage.paste(cover, (x, y))
                
                # Aggiungi overlay con info
                overlay = Image.new('RGBA', (cover_width, cover_height), (0, 0, 0, 128))
                overlay_draw = ImageDraw.Draw(overlay)
                
                try:
                    game_font = ImageFont.load_default()
                    # Titolo gioco
                    title_text = game['title'][:25] + "..." if len(game['title']) > 25 else game['title']
                    overlay_draw.text((10, 10), title_text, fill='white', font=game_font)
                    
                    # Platform e genere
                    info_text = f"{game['platform']} • {game['genre']}"
                    overlay_draw.text((10, 100), info_text, fill='#7289DA', font=game_font)
                    
                    # Data scadenza
                    date_text = f"Scade: {game['end_date']}"
                    overlay_draw.text((10, 115), date_text, fill='#FFA500', font=game_font)
                except:
                    overlay_draw.text((10, 10), game['title'][:20], fill='white')
                    overlay_draw.text((10, 100), game['platform'], fill='#7289DA')
                
                collage.paste(overlay, (x, y), overlay)
            
            # Salva immagine
            image_path = "games_collage.png"
            collage.save(image_path, "PNG")
            return image_path
            
        except Exception as e:
            logger.error(f"Errore creazione collage: {e}")
            return None

    def get_real_description(self, title, platform, link):
        """Ottiene la descrizione reale del gioco"""
        try:
            if platform == "Epic Games":
                # Per Epic Games, prova a fare scraping della pagina
                response = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Cerca meta description
                meta_desc = soup.find('meta', {'name': 'description'})
                if meta_desc and meta_desc.get('content'):
                    return meta_desc['content'][:150] + "..."
                
                # Cerca nel contenuto della pagina
                desc_selectors = [
                    '[data-testid="description"]',
                    '.css-1vwkb5k',  # Epic description class
                    '.css-16oh4oq'
                ]
                
                for selector in desc_selectors:
                    desc_elem = soup.select_one(selector)
                    if desc_elem:
                        text = desc_elem.get_text(strip=True)
                        if len(text) > 20:
                            return text[:200] + "..."
            
            elif "steam" in link.lower():
                # Estrai Steam App ID
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
                            return short_desc[:200] + "..." if len(short_desc) > 200 else short_desc
            
            # Descrizioni fallback basate su pattern di titolo
            title_lower = title.lower()
            if any(word in title_lower for word in ['train', 'sim']):
                return "Simulatore di treni realistico con scenari dettagliati e controlli autentici."
            elif any(word in title_lower for word in ['zombie', 'borg']):
                return "Gioco d'azione ambientato in un mondo post-apocalittico pieno di zombie."
            elif 'nightingale' in title_lower:
                return "Gioco di sopravvivenza cooperativo in un mondo fantasy vittoriano pieno di creature magiche."
            elif any(word in title_lower for word in ['whiskey', 'mafia']):
                return "Avventura narrativa ambientata nel mondo della criminalità organizzata."
            elif 'wednesday' in title_lower:
                return "Avventura indie con atmosfere uniche e storytelling coinvolgente."
            else:
                return f"Gioco {self.get_genre_from_title(title).lower()} disponibile gratuitamente per tempo limitato."
                
        except Exception as e:
            logger.warning(f"Errore recupero descrizione per {title}: {e}")
            return f"Gioco {self.get_genre_from_title(title).lower()} gratuito con contenuti di qualità."

    def get_genre_from_title(self, title):
        """Determina il genere dal titolo"""
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['train', 'sim', 'simulator']):
            return "Simulazione"
        elif any(word in title_lower for word in ['zombie', 'war', 'battle', 'fight']):
            return "Azione"
        elif any(word in title_lower for word in ['story', 'adventure', 'mystery']):
            return "Avventura"
        elif any(word in title_lower for word in ['craft', 'build', 'survival']):
            return "Sopravvivenza"
        elif any(word in title_lower for word in ['puzzle', 'brain']):
            return "Puzzle"
        elif any(word in title_lower for word in ['race', 'drive', 'car']):
            return "Corse"
        elif any(word in title_lower for word in ['rpg', 'role']):
            return "RPG"
        else:
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
                        logger.info(f"Epic game già inviato: {title} -> {normalized_title}")
                        continue
                    
                    # Descrizione reale
                    desc = self.get_real_description(title, "Epic Games", link)
                    
                    # Genere
                    categories = g.get("categories", [])
                    genre = self.get_genre_from_title(title)
                    if categories:
                        for cat in categories:
                            cat_path = cat.get("path", "").lower()
                            if "action" in cat_path:
                                genre = "Azione"
                            elif "adventure" in cat_path:
                                genre = "Avventura"
                            elif "rpg" in cat_path:
                                genre = "RPG"
                            elif "strategy" in cat_path:
                                genre = "Strategia"
                            elif "simulation" in cat_path:
                                genre = "Simulazione"
                    
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
                
                # Pulisci il titolo
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
                    logger.info(f"Steam game già inviato: {title} -> {normalized_title}")
                    continue
                
                # Descrizione reale
                desc = self.get_real_description(title, "Steam", link)
                genre = self.get_genre_from_title(title)
                
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
                    logger.info(f"GamerPower game già inviato: {title} -> {normalized_title}")
                    continue
                
                # Descrizione reale
                api_desc = g.get("description", "")
                if api_desc and len(api_desc) > 20:
                    desc = api_desc[:200] + "..." if len(api_desc) > 200 else api_desc
                else:
                    desc = self.get_real_description(title, "GamerPower", link)
                
                genre = self.get_genre_from_title(title)
                
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
        return []  # Semplificato per ora

    async def fetch_gog(self):
        return []  # Semplificato per ora

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

        # Debug: mostra normalizzazioni
        for game in games:
            logger.info(f"Gioco: {game['title']} -> Normalizzato: {self.normalize_title(game['title'])} -> ID: {game['id']}")

        # Aggiungi i nuovi giochi al set dei giochi già inviati
        for game in games:
            self.sent.add(game["id"])
        
        # Salva il file con i giochi già inviati
        self.save_sent()
        logger.info(f"Salvati {len(games)} nuovi giochi nel tracking duplicati.")

        # Crea collage immagini
        collage_path = self.create_games_collage(games)

        # Testo del messaggio senza emojii problematici
        parts = ["*Nuovi Giochi Gratuiti*\n"]
        for g in games:
            parts.append(
                f"*{g['title']}*\n"
                f"_{g['description']}_\n"
                f"{g['genre']} • {g['platform']}\n"
                f"Scade: {g['end_date']}\n"
                f"[Scarica Gratis]({g['url']})\n"
            )

        text = "\n".join(parts)

        # Invia con collage se disponibile
        if collage_path and os.path.exists(collage_path):
            try:
                with open(collage_path, 'rb') as photo:
                    await self.bot.send_photo(
                        chat_id=CHANNEL_USERNAME,
                        photo=photo,
                        caption=text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    if FRIENDS_CHAT_ID:
                        photo.seek(0)
                        await self.bot.send_photo(
                            chat_id=FRIENDS_CHAT_ID,
                            photo=photo,
                            caption=text,
                            parse_mode=ParseMode.MARKDOWN
                        )
                
                # Rimuovi file temporaneo
                os.remove(collage_path)
                logger.info("Inviato messaggio con collage immagini")
                
            except Exception as e:
                logger.error(f"Errore invio con immagine: {e}")
                # Fallback senza immagine
                await self._send_text_only(text)
        else:
            await self._send_text_only(text)

    async def _send_text_only(self, text):
        """Invia solo testo senza immagine"""
        await self.bot.send_message(
            chat_id=CHANNEL_USERNAME,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True  # Disabilita anteprima link
        )

        if FRIENDS_CHAT_ID:
            await self.bot.send_message(
                chat_id=FRIENDS_CHAT_ID,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )

async def main():
    bot = FreeGamesBot()
    await bot.send_hourly_update()

if __name__ == "__main__":
    asyncio.run(main())