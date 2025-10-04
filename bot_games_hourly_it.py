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
        title = re.sub(r'\s*giveaway.*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*\([^)]*\)\s*', '', title)
        normalized = re.sub(r'[^\w\s]', '', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        suffixes = ['free','gratis','epic games','steam','edition','deluxe','premium','standard','ultimate','complete','pack']
        for s in suffixes:
            if normalized.endswith(' '+s):
                normalized = normalized[:-len(' '+s)]
        return normalized

    def clean_title(self, title):
        title = re.sub(r'\s*giveaway\s*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*\((Steam|PC|Epic Games|itchio)\)\s*$', '', title, flags=re.IGNORECASE)
        return title.strip()

    def translate_description(self, text):
        if not text or len(text) < 10:
            return text
        translations = {
            r'\bfree\b': 'gratuito',
            r'\bgame\b': 'gioco',
            r'\bgrab\b': 'scarica',
            r'\bcheck it out\b': 'provalo',
            r'\bdon\'?t miss it\b': 'non perdertelo',
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
            r'\bstandalone version\b': 'versione autonoma',
            r'\bcool 2d\b': 'interessante 2D',
            r'\babout\b': 'su',
            r'\bwhere you\'?ll\b': 'dove potrai',
            r'\bacross\b': 'attraverso',
            r'\bpixel art\b': 'pixel art',
            r'\bnon-linear plot\b': 'trama non lineare',
            r'\bget a\b': 'ottieni una',
            r'\bcopy\b': 'copia',
            r'\bvia\b': 'tramite',
            r'\bwith\b': 'con',
            r'\bis a\b': 'è un',
            r'\bnamed\b': 'chiamato',
            r'\bserious\b': 'serio',
            r'\bplatformer\b': 'platform',
            r'\bcat\b': 'gatto',
            r'\bpeacekeepers\b': 'peacekeepers',
            r'\bamidst conflict\b': 'tra i conflitti',
            r'\bunmanned\b': 'automatizzato'
        }
        result = text.lower()
        for pat, sub in translations.items():
            result = re.sub(pat, sub, result, flags=re.IGNORECASE)
        result = result.capitalize()
        english_count = sum(1 for w in ['you','the','and','for','this','that','your','have','been'] if w in result.lower())
        if english_count >= 2:
            return self.get_custom_description_by_title(text)
        return result

    def get_custom_description_by_title(self, text):
        t = text.lower()
        if 'zomborg' in t or 'zombie' in t:
            return "Sparatutto dall'alto ambientato in un mondo pieno di zombie con grafica accattivante."
        if 'nightingale' in t:
            return "Gioco di sopravvivenza cooperativo in prima persona ambientato nei pericolosi Reami delle Fate."
        if 'blue wednesday' in t or 'jazz' in t:
            return "Avventura narrativa 2D che esplora il mondo del jazz con atmosfere uniche."
        if 'whiskey mafia' in t:
            return "Avventura 2D dove vivi la vita nella mafia con una storia coinvolgente."
        if 'train sim' in t:
            return "Simulatore di treni realistico con centro addestramento e diversi treni da imparare."
        if 'ashanti protocol' in t:
            return "Gioco strategico su peacekeepers automatizzati in zone di conflitto."
        if 'will glow' in t or 'wisp' in t:
            return "Avventura luminosa con atmosfere magiche e gameplay coinvolgente."
        if 'bad cat sam' in t:
            return "Platform 2D divertente con un gatto protagonista in avventure dinamiche."
        if 'dungeonloot' in t:
            return "Gioco di ruolo con esplorazione di dungeon e ricerca di tesori."
        return "Gioco indipendente con contenuti originali disponibile gratuitamente."

    def validate(self, url):
        try:
            p = urlparse(url)
            if not p.scheme or not p.netloc:
                return False
            r = requests.head(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10, allow_redirects=True)
            if r.status_code in (200,301,302,403):
                return True
            r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10, allow_redirects=True)
            return r.status_code in (200,301,302,403)
        except:
            return False

    def get_game_cover_image(self, title, platform):
        try:
            resp = requests.get(f"https://store.steampowered.com/api/storesearch/?term={title}&l=italian&cc=IT", timeout=10).json()
            if resp.get('items'):
                item = resp['items'][0]
                img_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{item['id']}/header.jpg"
                ir = requests.get(img_url, timeout=10)
                if ir.status_code == 200:
                    return Image.open(io.BytesIO(ir.content)).resize((300,140))
            # placeholder
            ph = Image.new('RGB',(300,140),color='#2C2F36')
            dr = ImageDraw.Draw(ph)
            fn = ImageFont.load_default()
            words = title.split(); lines=[]; cur=[]
            for w in words:
                tl = ' '.join(cur+[w]); bb=dr.textbbox((0,0),tl,font=fn)
                if bb[2]-bb[0]<250: cur.append(w)
                else:
                    if cur: lines.append(' '.join(cur)); cur=[w]
                    else: lines.append(w)
            if cur: lines.append(' '.join(cur))
            h=len(lines)*20; y0=(140-h)//2
            for i,l in enumerate(lines[:4]):
                bb=dr.textbbox((0,0),l,font=fn)
                x=(300-(bb[2]-bb[0]))//2; dr.text((x,y0+i*20),l,fill='white',font=fn)
            return ph
        except Exception as e:
            logger.warning(f"Errore immagine {title}: {e}")
            ph = Image.new('RGB',(300,140),color='#7289DA')
            dr = ImageDraw.Draw(ph)
            dr.text((50,60),title[:15],fill='white')
            return ph

    def create_game_image(self, game):
        width, height = 300, 200
        img = Image.new('RGB',(width,height),color='#36393F')
        d = ImageDraw.Draw(img)
        f = ImageFont.load_default()
        cover = self.get_game_cover_image(game['title'],game['platform'])
        if cover: img.paste(cover,(0,0))
        ov = Image.new('RGBA',(width,60),(0,0,0,160))
        od = ImageDraw.Draw(ov)
        t = self.clean_title(game['title'])[:25]+'...' if len(game['title'])>25 else self.clean_title(game['title'])
        od.text((10,5),t,fill='white',font=f)
        od.text((10,25),f"{game['genre']} - {game['platform']}",fill='#7289DA',font=f)
        dt = game['end_date'][:16] if len(game['end_date'])>16 else game['end_date']
        od.text((10,42),f"Scade: {dt}",fill='#FFA500',font=f)
        img.paste(ov,(0,140),ov)
        path=f"img_{self.normalize_title(game['title'])}.png"
        img.save(path,"PNG",optimize=True)
        return path

    async def fetch_epic(self):
        # identical to above...
        return []

    async def fetch_gamer(self):
        # identical to above...
        return []

    async def send_hourly_update(self):
        games = []
        games += await self.fetch_epic()
        games += await self.fetch_gamer()
        # other sources...
        if not games:
            logger.info("Nessun nuovo gioco gratuito trovato.")
            return
        for g in games: self.sent.add(g["id"])
        self.save_sent()
        for g in games:
            img_path = self.create_game_image(g)
            text = (
                f"🔹 **{g['title']}**\n"
                f"📖 _{g['description']}_\n"
                f"▶️ [Scarica Gratis]({g['url']})"
            )
            if len(text)>900: text=text[:897]+"..."
            with open(img_path,'rb') as ph:
                await self.bot.send_photo(
                    chat_id=CHANNEL_USERNAME,
                    photo=ph,
                    caption=text,
                    parse_mode=ParseMode.MARKDOWN
                )
                if FRIENDS_CHAT_ID:
                    ph.seek(0)
                    await self.bot.send_photo(
                        chat_id=FRIENDS_CHAT_ID,
                        photo=ph,
                        caption=text,
                        parse_mode=ParseMode.MARKDOWN
                    )
            os.remove(img_path)

async def main():
    bot = FreeGamesBot()
    await bot.send_hourly_update()

if __name__=="__main__":
    asyncio.run(main())
