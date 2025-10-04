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
        # Rimuovi tutto dopo "Giveaway" se presente (case insensitive)
        title = re.sub(r'\s*giveaway.*$', '', title, flags=re.IGNORECASE)
        
        # Rimuovi parentesi e contenuto
        title = re.sub(r'\s*\([^)]*\)\s*', '', title)
        
        # Rimuovi caratteri speciali e normalizza
        normalized = re.sub(r'[^\w\s]', '', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Rimuovi suffissi comuni
        suffixes = ['free', 'gratis', 'epic games', 'steam', 'edition', 
                   'deluxe', 'premium', 'standard', 'ultimate', 'complete', 'pack']
        for suffix in suffixes:
            if normalized.endswith(' ' + suffix):
                normalized = normalized[:-len(' ' + suffix)]
        
        return normalized

    def clean_title(self, title):
        """Pulisce il titolo per la visualizzazione"""
        # Rimuovi "Giveaway" dalla fine
        title = re.sub(r'\s*giveaway\s*$', '', title, flags=re.IGNORECASE)
        return title.strip()

    def translate_description(self, text):
        """Traduce descrizioni inglesi in italiano usando regex patterns"""
        if not text or len(text) < 10:
            return text
            
        # Pattern comuni inglese -> italiano
        translations = {
            r'\bfree\b': 'gratuito',
            r'\bgame\b': 'gioco',
            r'\bgrab\b': 'scarica',
            r'\bcheck it out\b': 'provalo',
            r'\bdon\'t miss it\b': 'non perdertelo',
            r'\bavailable\b': 'disponibile',
            r'\bdownload\b': 'scarica',
            r'\bfor free\b': 'gratuitamente',
            r'\bright now\b': 'ora',
            r'\bfirst person\b': 'prima persona',
            r'\bopen world\b': 'mondo aperto',
            r'\bsurvival\b': 'sopravvivenza',
            r'\bcrafting\b': 'costruzione',
            r'\badventure\b': 'avventura',
            r'\bdangerous\b': 'pericoloso',
            r'\btop-down shooter\b': 'sparatutto dall\'alto',
            r'\bzombies\b': 'zombie',
            r'\bcool graphics\b': 'grafica accattivante',
            r'\bnarrative\b': 'narrativo',
            r'\bexperience life\b': 'vivi la vita',
            r'\bmafia\b': 'mafia',
            r'\btrains\b': 'treni',
            r'\blearn\b': 'impara',
            r'\binclude\b': 'include',
            r'\btraining center\b': 'centro addestramento',
            r'\bstandalone version\b': 'versione autonoma'
        }
        
        result = text
        for eng_pattern, ita_word in translations.items():
            result = re.sub(eng_pattern, ita_word, result, flags=re.IGNORECASE)
        
        # Se ancora molto inglese, usa descrizione personalizzata
        english_indicators = ['you', 'the', 'and', 'with', 'for', 'this', 'that', 'your']
        english_count = sum(1 for word in english_indicators if word in result.lower())
        
        if english_count >= 3:
            return self.get_custom_description_by_title(text)
        
        return result

    def get_custom_description_by_title(self, original_title_or_desc):
        """Genera descrizioni personalizzate basate sul contenuto"""
        text = original_title_or_desc.lower()
        
        if 'zomborg' in text or 'zombie' in text:
            return "Sparatutto dall'alto ambientato in un mondo pieno di zombie con grafica accattivante."
        elif 'nightingale' in text:
            return "Gioco di sopravvivenza cooperativo in prima persona ambientato nei pericolosi Reami delle Fate."
        elif 'blue wednesday' in text or 'jazz' in text:
            return "Avventura narrativa 2D che esplora il mondo del jazz con atmosfere uniche."
        elif 'whiskey mafia' in text or 'mafia' in text:
            return "Avventura 2D dove vivi la vita nella mafia con una storia coinvolgente."
        elif 'train sim' in text or 'trains' in text:
            return "Simulatore di treni realistico con centro addestramento e diversi treni da imparare."
        else:
            return "Gioco gratuito con contenuti di qualità disponibile per tempo limitato."

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
        """Scarica immagine copertina o crea placeholder"""
        try:
            # Cerca su Steam Store API
            search_url = f"https://store.steampowered.com/api/storesearch/?term={title}&l=italian&cc=IT"
            response = requests.get(search_url, timeout=10)
            data = response.json()
            
            if data.get('items'):
                item = data['items'][0]
                image_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{item['id']}/header.jpg"
                img_response = requests.get(image_url, timeout=10)
                if img_response.status_code == 200:
                    img = Image.open(io.BytesIO(img_response.content))
                    return img.resize((300, 140))
            
            # Placeholder con titolo
            placeholder = Image.new('RGB', (300, 140), color='#2C2F36')
            draw = ImageDraw.Draw(placeholder)
            
            # Usa font di default
            font = ImageFont.load_default()
            
            # Spezza il titolo in più righe se troppo lungo
            words = title.split()
            lines = []
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] - bbox[0] < 250:  # larghezza massima
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)
            
            if current_line:
                lines.append(' '.join(current_line))
            
            # Centra il testo verticalmente
            total_height = len(lines) * 20
            start_y = (140 - total_height) // 2
            
            for i, line in enumerate(lines[:4]):  # Max 4 righe
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                x = (300 - text_width) // 2
                y = start_y + i * 20
                draw.text((x, y), line, fill='white', font=font)
            
            return placeholder
            
        except Exception as e:
            logger.warning(f"Errore immagine per {title}: {e}")
            # Placeholder semplice
            placeholder = Image.new('RGB', (300, 140), color='#7289DA')
            draw = ImageDraw.Draw(placeholder)
            draw.text((50, 60), title[:15], fill='white')
            return placeholder

    def create_games_collage(self, games):
        """Crea collage con copertine"""
        try:
            if not games:
                return None
                
            # Dimensioni
            cols = 2
            rows = (len(games) + cols - 1) // cols
            cover_width, cover_height = 300, 140
            spacing = 20
            
            total_width = cols * cover_width + (cols - 1) * spacing + 40
            total_height = rows * cover_height + (rows - 1) * spacing + 100
            
            # Crea immagine base
            collage = Image.new('RGB', (total_width, total_height), color='#36393F')
            draw = ImageDraw.Draw(collage)
            
            # Titolo
            font = ImageFont.load_default()
            title_text = f"🎮 {len(games)} Giochi Gratuiti Disponibili"
            bbox = draw.textbbox((0, 0), title_text, font=font)
            title_width = bbox[2] - bbox[0]
            title_x = (total_width - title_width) // 2
            draw.text((title_x, 20), title_text, fill='white', font=font)
            
            # Sottotitolo
            subtitle = f"Aggiornamento del {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
            bbox = draw.textbbox((0, 0), subtitle, font=font)
            subtitle_width = bbox[2] - bbox[0]
            subtitle_x = (total_width - subtitle_width) // 2
            draw.text((subtitle_x, 45), subtitle, fill='#B9BBBE', font=font)
            
            # Aggiungi copertine
            for i, game in enumerate(games):
                row = i // cols
                col = i % cols
                
                x = 20 + col * (cover_width + spacing)
                y = 80 + row * (cover_height + spacing)
                
                # Scarica immagine
                cover = self.get_game_cover_image(game['title'], game['platform'])
                if cover:
                    collage.paste(cover, (x, y))
                
                # Overlay con info
                overlay = Image.new('RGBA', (cover_width, cover_height), (0, 0, 0, 120))
                overlay_draw = ImageDraw.Draw(overlay)
                
                # Titolo gioco
                clean_title = self.clean_title(game['title'])
                title_short = clean_title[:25] + "..." if len(clean_title) > 25 else clean_title
                overlay_draw.text((10, 10), title_short, fill='white', font=font)
                
                # Platform e genere  
                info_text = f"{game['platform']} • {game['genre']}"
                overlay_draw.text((10, 100), info_text, fill='#7289DA', font=font)
                
                # Data scadenza
                date_text = f"Scade: {game['end_date'][:10]}"  # Accorcia la data
                overlay_draw.text((10, 115), date_text, fill='#FFA500', font=font)
                
                collage.paste(overlay, (x, y), overlay)
            
            # Salva
            image_path = "games_collage.png"
            collage.save(image_path, "PNG", optimize=True)
            logger.info(f"Collage creato: {image_path}")
            return image_path
            
        except Exception as e:
            logger.error(f"Errore creazione collage: {e}")
            return None

    def get_genre_from_title(self, title):
        """Determina genere dal titolo"""
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['train', 'sim', 'simulator']):
            return "Simulazione"
        elif any(word in title_lower for word in ['zombie', 'war', 'battle', 'fight', 'shooter']):
            return "Azione"
        elif any(word in title_lower for word in ['story', 'adventure', 'mystery', 'narrative', 'mafia']):
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
                    
                    # ID normalizzato
                    normalized_title = self.normalize_title(title)
                    gid = f"game_{normalized_title}"
                    
                    logger.info(f"Epic: '{title}' -> normalizzato: '{normalized_title}' -> ID: '{gid}'")
                    
                    if gid in self.sent:
                        logger.info(f"Epic game già inviato: {title}")
                        continue
                    
                    # Descrizione
                    desc = g.get("description") or "Gioco gratuito per tempo limitato."
                    desc = self.translate_description(desc)[:200] + "..." if len(desc) > 200 else desc
                    
                    # Genere
                    genre = self.get_genre_from_title(title)
                    categories = g.get("categories", [])
                    if categories:
                        for cat in categories:
                            cat_path = cat.get("path", "").lower()
                            if "survival" in cat_path:
                                genre = "Sopravvivenza"
                                break
                            elif "action" in cat_path:
                                genre = "Azione"
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
                        "title": self.clean_title(title),
                        "description": desc,
                        "genre": genre,
                        "url": link,
                        "platform": "Epic Games",
                        "end_date": end
                    })
        except Exception as e:
            logger.error(f"Errore Epic Games: {e}")
        return out

    async def fetch_gamer(self):
        out = []
        try:
            data = requests.get(
                "https://www.gamerpower.com/api/giveaways?platform=pc&type=game",
                timeout=15
            ).json()
            
            for g in data[:10]:  # Aumentato per più varietà
                title = g.get("title", "").strip()
                
                if not title:
                    continue
                
                link = g.get("open_giveaway") or g.get("gamerpower_url")
                if not link or not self.validate(link):
                    continue
                
                # ID normalizzato  
                normalized_title = self.normalize_title(title)
                gid = f"game_{normalized_title}"
                
                logger.info(f"GamerPower: '{title}' -> normalizzato: '{normalized_title}' -> ID: '{gid}'")
                
                if gid in self.sent:
                    logger.info(f"GamerPower game già inviato: {title}")
                    continue
                
                # Descrizione tradotta
                api_desc = g.get("description", "")
                if api_desc and len(api_desc) > 20:
                    desc = self.translate_description(api_desc)
                    desc = desc[:200] + "..." if len(desc) > 200 else desc
                else:
                    desc = self.get_custom_description_by_title(title)
                
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
                    "title": self.clean_title(title),
                    "description": desc,
                    "genre": genre,
                    "url": link,
                    "platform": "GamerPower",
                    "end_date": end
                })
        except Exception as e:
            logger.error(f"Errore GamerPower: {e}")
        return out

    async def fetch_steam(self):
        return []  # Semplificato per focus sui problemi principali

    async def fetch_prime(self):
        return []

    async def fetch_gog(self):
        return []

    async def send_hourly_update(self):
        games = []
        games += await self.fetch_epic()
        games += await self.fetch_gamer()
        games += await self.fetch_steam()
        games += await self.fetch_prime()
        games += await self.fetch_gog()

        if not games:
            logger.info("Nessun nuovo gioco gratuito trovato.")
            return

        # Debug normalizzazioni
        logger.info("=== DEBUG NORMALIZZAZIONI ===")
        for game in games:
            logger.info(f"'{game['title']}' -> ID: '{game['id']}'")
        
        # Aggiungi a sent
        for game in games:
            self.sent.add(game["id"])
        
        self.save_sent()
        logger.info(f"Salvati {len(games)} giochi nel tracking.")

        # Crea collage
        collage_path = self.create_games_collage(games)

        # Messaggio
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

        # Invia con immagine
        if collage_path and os.path.exists(collage_path):
            try:
                with open(collage_path, 'rb') as photo:
                    # Canale principale
                    await self.bot.send_photo(
                        chat_id=CHANNEL_USERNAME,
                        photo=photo,
                        caption=text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    # Chat amici se configurata
                    if FRIENDS_CHAT_ID:
                        photo.seek(0)
                        await self.bot.send_photo(
                            chat_id=FRIENDS_CHAT_ID,
                            photo=photo,
                            caption=text,
                            parse_mode=ParseMode.MARKDOWN
                        )
                
                logger.info("✅ Messaggio inviato CON collage immagini")
                
                # Pulisci file temporaneo
                os.remove(collage_path)
                
            except Exception as e:
                logger.error(f"Errore invio con immagine: {e}")
                await self._send_text_only(text)
        else:
            logger.warning("❌ Collage non creato, invio solo testo")
            await self._send_text_only(text)

    async def _send_text_only(self, text):
        """Fallback senza immagine"""
        await self.bot.send_message(
            chat_id=CHANNEL_USERNAME,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

        if FRIENDS_CHAT_ID:
            await self.bot.send_message(
                chat_id=FRIENDS_CHAT_ID,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
        
        logger.info("✅ Messaggio inviato SENZA immagine")

async def main():
    bot = FreeGamesBot()
    await bot.send_hourly_update()

if __name__ == "__main__":
    asyncio.run(main())