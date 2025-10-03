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

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")

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
        with open(self.sent_file,"w") as f:
            json.dump(list(self.sent), f)

    def validate(self,url):
        try:
            p=urlparse(url)
            if not p.scheme or not p.netloc:
                return False
            h={"User-Agent":"Mozilla/5.0"}
            r=requests.head(url,headers=h,timeout=10,allow_redirects=True)
            if r.status_code in (200,301,302,403):
                return True
            r=requests.get(url,headers=h,timeout=10,allow_redirects=True)
            return r.status_code in (200,301,302,403)
        except:
            return False

    async def fetch_epic(self):
        out=[]
        try:
            data=requests.get("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions",timeout=15).json()
            elems=data.get("data",{}).get("Catalog",{}).get("searchStore",{}).get("elements",[])
            for g in elems:
                promotions=g.get("promotions") or {}
                for po in promotions.get("promotionalOffers",[]):
                    offs=po.get("promotionalOffers") or []
                    if not offs:
                        continue
                    title=g.get("title","").strip()
                    slug=g.get("productSlug","")
                    if not title or not slug:
                        continue
                    link=f"https://store.epicgames.com/it/p/{slug}"
                    if not self.validate(link):
                        continue
                    gid=f"epic_{slug}"
                    if gid in self.sent:
                        continue
                    desc=g.get("description") or "Gioco gratuito per tempo limitato."
                    desc=desc[:200]+"..." if len(desc)>200 else desc
                    end=""
                    ed=offs[0].get("endDate","")
                    if ed:
                        try:
                            dt=datetime.fromisoformat(ed.replace("Z", "+00:00"))
                            end=dt.strftime("%d/%m/%Y alle %H:%M")
                        except:
                            pass
                    out.append({"id":gid,"title":title,"description":desc,"url":link,"platform":"Epic Games","end_date":end})
        except Exception as e:
            logger.error(f"Errore Epic Games: {e}")
        return out

    async def fetch_steam(self):
        out=[]
        try:
            feed=feedparser.parse("https://isthereanydeal.com/rss/deals/free/")
            for e in feed.entries[:5]:
                t=e.title.strip()
                soup=BeautifulSoup(e.summary,"html.parser")
                links=[a["href"] for a in soup.find_all("a", href=True) if "store.steampowered.com" in a["href"]]
                if not links:
                    continue
                link=links[0]
                if not self.validate(link):
                    continue
                gid=f"steam_{hash(link)}"
                if gid in self.sent:
                    continue
                out.append({"id":gid,"title":t,"description":"Offerta gratuita disponibile su Steam.","url":link,"platform":"Steam","end_date":"Fino ad esaurimento"})
        except Exception as e:
            logger.error(f"Errore Steam: {e}")
        return out

    async def fetch_gamer(self):
        out=[]
        try:
            data=requests.get("https://www.gamerpower.com/api/giveaways?platform=pc&type=game",timeout=15).json()
            for g in data[:5]:
                t=g.get("title","").strip()
                link=g.get("open_giveaway") or g.get("gamerpower_url")
                if not t or not link:
                    continue
                if not self.validate(link):
                    continue
                gid=f"gp_{g.get('id')}"
                if gid in self.sent:
                    continue
                desc=g.get("description") or "Giveaway gratuito disponibile."
                desc=desc[:200]+"..." if len(desc)>200 else desc
                end="Data non specificata"
                ed=g.get("end_date","")
                if ed and ed!="N/A":
                    try:
                        dt=datetime.strptime(ed,"%Y-%m-%d %H:%M:%S")
                        end=dt.strftime("%d/%m/%Y alle %H:%M")
                    except:
                        end=ed
                out.append({"id":gid,"title":t,"description":desc,"url":link,"platform":"GamerPower","end_date":end})
        except Exception as e:
            logger.error(f"Errore GamerPower: {e}")
        return out

    async def fetch_prime(self):
        url="https://gaming.amazon.com/loot"
        headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"}
        out=[]
        try:
            r=requests.get(url,headers=headers,timeout=15)
            soup=BeautifulSoup(r.text,"html.parser")
            games=soup.find_all("div",class_="loot-item")
            for g in games:
                title_el=g.find("h3")
                desc_el=g.find("p",class_="description")
                link_el=g.find("a",href=True)
                title=title_el.text.strip() if title_el else "Gioco Prime"
                desc=desc_el.text.strip() if desc_el else "Gioco gratis con Prime Gaming"
                link="https://gaming.amazon.com"+link_el['href'] if link_el else url
                gid=f"prime_{title.lower().replace(' ','_')}"
                if gid not in self.sent and self.validate(link):
                    out.append({"id":gid,"title":title,"description":desc,"url":link,"platform":"Twitch Prime Gaming","end_date":"Fino ad esaurimento"})
        except Exception as e:
            logger.error(f"Errore Twitch Prime: {e}")
        return out

    async def fetch_gog(self):
        url="https://www.gog.com/games?price=free"
        headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"}
        out=[]
        try:
            r=requests.get(url,headers=headers,timeout=15)
            soup=BeautifulSoup(r.text,"html.parser")
            games = soup.find_all("div",class_="product-tile")
            for g in games:
                title_el=g.find("h3",class_="product-title")
                link_el=g.find_parent("a",href=True)
                title=title_el.text.strip() if title_el else "Gioco GOG"
                link= link_el['href'] if link_el else url
                full_link = f"https://www.gog.com{link}" if link.startswith("/") else link
                gid = f"gog_{title.lower().replace(' ','_')}"
                if gid not in self.sent and self.validate(full_link):
                    out.append({"id":gid,"title":title,"description":"Offerta gratuita su GOG","url":full_link,"platform":"GOG","end_date":"Fino ad esaurimento"})
        except Exception as e:
            logger.error(f"Errore GOG: {e}")
        return out

    async def fetch_bnet(self):
        return []

    async def fetch_riot(self):
        return []

    async def send_hourly_update(self):
        games=[]
        games+=await self.fetch_epic()
        games+=await self.fetch_steam()
        games+=await self.fetch_gamer()
        games+=await self.fetch_prime()
        games+=await self.fetch_gog()
        games+=await self.fetch_bnet()
        games+=await self.fetch_riot()

        if not games:
            logger.info("Nessun nuovo gioco gratuito trovato.")
            return

        sent=0
        for g in games:
            if g["id"] in self.sent:
                continue
            msg=(f"🎮 **{g['title']}**\n\n"
                 f"📝 {g['description']}\n\n"
                 f"🏷️ Piattaforma: {g['platform']}\n"
                 f"⏰ Scade: {g['end_date']}\n\n"
                 f"🔗 [Scarica Gratis]({g['url']})\n\n"
                 f"💬 {CHANNEL_USERNAME}")
            try:
                await self.bot.send_message(chat_id=CHANNEL_USERNAME,text=msg,parse_mode=ParseMode.MARKDOWN)
                self.sent.add(g["id"])
                sent+=1
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Invio fallito {g['title']}: {e}")
        self.save_sent()
        logger.info(f"Inviati {sent} giochi")

async def main():
    bot=FreeGamesBot()
    await bot.send_hourly_update()

if __name__=="__main__":
    asyncio.run(main())