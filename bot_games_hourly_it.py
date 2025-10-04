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
        """Normalizza il titolo per rilevare duplicati cross-platform"""
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
        """Pulisce il titolo per la visualizzazione finale"""
        title = re.sub(r'\s*giveaway\s*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*\((Steam|PC|Epic Games|itchio)\)\s*$', '', title, flags=re.IGNORECASE)
        return title.strip()

    def translate_description(self, text):
        """Traduce descrizioni inglesi in italiano usando regex patterns"""
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
        english_indicators = ['you','the','and','for','this','that','your','have','been']
        if sum(1 for w in english_indicators if w in result.lower()) >= 2:
            return self.get_custom_description_by_title(text)
        return result

    def get_custom_description_by_title(self, text):
        text = text.lower()
        if 'zomborg' in text or 'zombie' in text:
            return "Sparatutto dall'alto ambientato in un mondo pieno di zombie con grafica accattivante."
        if 'nightingale' in text:
            return "Gioco di sopravvivenza cooperativo in prima persona ambientato nei pericolosi Reami delle Fate."
        if 'blue wednesday' in text or 'jazz' in text:
            return "Avventura narrativa 2D che esplora il mondo del jazz con atmosfere uniche."
        if 'whiskey mafia' in text:
            return "Avventura 2D dove vivi la vita nella mafia con una storia coinvolgente."
        if 'train sim' in text:
            return "Simulatore di treni realistico con centro addestramento e diversi treni da imparare."
        if 'ashanti protocol' in text:
            return "Gioco strategico su peacekeepers automatizzati in zone di conflitto."
        if 'will glow' in text or 'wisp' in text:
            return "Avventura luminosa con atmosfere magiche e gameplay coinvolgente."
        if 'bad cat sam' in text:
            return "Platform 2D divertente con un gatto protagonista in avventure dinamiche."
        if 'dungeonloot' in text:
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
                app = resp['items'][0]
                img_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{app['id']}/header.jpg"
                img_resp = requests.get(img_url, timeout=10)
                if img_resp.status_code==200:
                    return Image.open(io.BytesIO(img_resp.content)).resize((300,140))
            placeholder = Image.new('RGB',(300,140),color='#2C2F36')
            draw = ImageDraw.Draw(placeholder)
            font = ImageFont.load_default()
            words = title.split(); lines=[]
            cur=[]
            for w in words:
                tl = ' '.join(cur+[w])
                bb = draw.textbbox((0,0),tl,font=font)
                if bb[2]-bb[0]<250: cur.append(w)
                else:
                    if cur: lines.append(' '.join(cur)); cur=[w]
                    else: lines.append(w)
            if cur: lines.append(' '.join(cur))
            h = len(lines)*20; y0=(140-h)//2
            for i,line in enumerate(lines[:4]):
                bb=draw.textbbox((0,0),line,font=font)
                x=(300-(bb[2]-bb[0]))//2; y=y0+i*20
                draw.text((x,y),line,fill='white',font=font)
            return placeholder
        except Exception as e:
            logger.warning(f"Errore immagine per {title}: {e}")
            p=Image.new('RGB',(300,140),color='#7289DA'); d=ImageDraw.Draw(p)
            d.text((50,60),title[:15],fill='white'); return p

    def create_games_collage(self, games):
        try:
            if not games:
                logger.warning("Nessun gioco per creare collage")
                return None
            cols=2; rows=(len(games)+cols-1)//cols
            cw,ch=300,140; sp=20
            W=cols*cw+(cols-1)*sp+40; H=rows*ch+(rows-1)*sp+100
            collage=Image.new('RGB',(W,H),color='#36393F'); d=ImageDraw.Draw(collage)
            fnt=ImageFont.load_default()
            txt=f"{len(games)} Giochi Gratuiti Disponibili"
            bb=d.textbbox((0,0),txt,font=fnt)
            x0=(W-(bb[2]-bb[0]))//2; d.text((x0,20),txt,fill='white',font=fnt)
            sub=f"Aggiornamento del {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
            bb=d.textbbox((0,0),sub,font=fnt)
            x1=(W-(bb[2]-bb[0]))//2; d.text((x1,45),sub,fill='#B9BBBE',font=fnt)
            for i,g in enumerate(games):
                r=i//cols; c=i%cols
                x=20+c*(cw+sp); y=80+r*(ch+sp)
                cv=self.get_game_cover_image(g['title'],g['platform'])
                if cv: collage.paste(cv,(x,y))
                ov=Image.new('RGBA',(cw,ch),(0,0,0,120))
                od=ImageDraw.Draw(ov)
                t0=self.clean_title(g['title'])
                t0s=t0[:25]+"..." if len(t0)>25 else t0
                od.text((10,10),t0s,fill='white',font=fnt)
                it=f"{g['platform']} - {g['genre']}"
                od.text((10,100),it,fill='#7289DA',font=fnt)
                dt=g['end_date'][:16] if len(g['end_date'])>16 else g['end_date']
                od.text((10,115),f"Scade: {dt}",fill='#FFA500',font=fnt)
                collage.paste(ov,(x,y),ov)
            path="games_collage.png"
            collage.save(path,"PNG",optimize=True,quality=85)
            logger.info(f"Collage creato: {path}")
            return path
        except Exception as e:
            logger.error(f"Errore creazione collage: {e}")
            return None

    def get_genre_from_title(self,title):
        tl=title.lower()
        if any(w in tl for w in ['train','sim']): return "Simulazione"
        if any(w in tl for w in ['zombie','shooter']): return "Azione"
        if any(w in tl for w in ['adventure','mafia']): return "Avventura"
        if any(w in tl for w in ['survival','craft']): return "Sopravvivenza"
        if any(w in tl for w in ['puzzle']): return "Puzzle"
        if any(w in tl for w in ['race','drive']): return "Corse"
        if any(w in tl for w in ['rpg','dungeon']): return "RPG"
        if any(w in tl for w in ['platform']): return "Platform"
        return "Indie"

    async def fetch_epic(self):
        out=[]
        try:
            data=requests.get("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions",timeout=15).json()
            elems=data.get("data",{}).get("Catalog",{}).get("searchStore",{}).get("elements",[])
            for g in elems:
                promos=g.get("promotions") or {}
                for po in promos.get("promotionalOffers",[]):
                    offs=po.get("promotionalOffers") or []
                    if not offs: continue
                    t=g.get("title","").strip(); s=g.get("productSlug","")
                    if not t or not s: continue
                    link=f"https://store.epicgames.com/it/p/{s}"
                    if not self.validate(link): continue
                    nt=self.normalize_title(t); gid=f"game_{nt}"
                    if gid in self.sent: continue
                    desc=g.get("description") or "Gioco gratuito per tempo limitato."
                    desc=self.translate_description(desc)
                    desc=desc[:200]+"..." if len(desc)>200 else desc
                    genre=self.get_genre_from_title(t)
                    cats=g.get("categories",[])
                    for cat in cats:
                        p=cat.get("path","").lower()
                        if "survival" in p: genre="Sopravvivenza"; break
                        if "action" in p: genre="Azione"; break
                    end="Data non specificata"
                    ed=offs[0].get("endDate","")
                    if ed:
                        try: dt=datetime.fromisoformat(ed.replace("Z","+00:00")); end=dt.strftime("%d/%m/%Y alle %H:%M")
                        except: pass
                    out.append({"id":gid,"title":self.clean_title(t),"description":desc,"genre":genre,"url":link,"platform":"Epic Games","end_date":end})
        except Exception as e:
            logger.error(f"Errore Epic Games: {e}")
        return out

    async def fetch_gamer(self):
        out=[]
        try:
            data=requests.get("https://www.gamerpower.com/api/giveaways?platform=pc&type=game",timeout=15).json()
            for g in data[:15]:
                t=g.get("title","").strip()
                if not t: continue
                link=g.get("open_giveaway") or g.get("gamerpower_url")
                if not link or not self.validate(link): continue
                nt=self.normalize_title(t); gid=f"game_{nt}"
                if gid in self.sent: continue
                api_desc=g.get("description","")
                if api_desc and len(api_desc)>20:
                    desc=self.translate_description(api_desc)
                    desc=desc[:200]+"..." if len(desc)>200 else desc
                else:
                    desc=self.get_custom_description_by_title(t)
                genre=self.get_genre_from_title(t)
                end="Data non specificata"
                ed=g.get("end_date","")
                if ed and ed!="N/A":
                    try: dt=datetime.strptime(ed,"%Y-%m-%d %H:%M:%S"); end=dt.strftime("%d/%m/%Y alle %H:%M")
                    except: end=ed
                out.append({"id":gid,"title":self.clean_title(t),"description":desc,"genre":genre,"url":link,"platform":"GamerPower","end_date":end})
        except Exception as e:
            logger.error(f"Errore GamerPower: {e}")
        return out

    async def fetch_steam(self): return []
    async def fetch_prime(self): return []
    async def fetch_gog(self): return []

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

        for g in games: self.sent.add(g["id"])
        self.save_sent()

        logger.info("Creando collage immagini...")
        collage_path = self.create_games_collage(games)
        if not collage_path or not os.path.exists(collage_path):
            logger.error("ERRORE CRITICO: Collage non creato! Interrompo l'invio.")
            return

        # Componi caption e tronca a 900 caratteri
        parts = ["🎮 **Nuovi Giochi Gratuiti** 🎮\n"]
        for g in games:
            parts.append(
                f"🔹 **{g['title']}**\n"
                f"📖 _{g['description']}_\n"
                f"🏷️ _{g['genre']}_ • 🏢 _{g['platform']}_\n"
                f"⏰ _Scade: {g['end_date']}_\n"
                f"▶️ [Scarica Gratis]({g['url']})\n"
            )
        text = "\n".join(parts)
        if len(text) > 900:
            text = text[:897] + "..."

        # Invia collage
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
            logger.info("Messaggio inviato CON collage immagini")
            os.remove(collage_path)
        except Exception as e:
            logger.error(f"Errore invio con immagine: {e}")
            await self._send_text_only(text)

    async def _send_text_only(self, text):
        try:
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
            logger.info("Messaggio inviato SENZA immagine (fallback)")
        except Exception as e:
            logger.error(f"Errore invio fallback: {e}")

async def main():
    bot = FreeGamesBot()
    await bot.send_hourly_update()

if __name__ == "__main__":
    asyncio.run(main())
