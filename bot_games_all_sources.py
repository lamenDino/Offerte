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
            if not p.scheme or not p.netloc: return False
            h={"User-Agent":"Mozilla/5.0"}
            r=requests.head(url,headers=h,timeout=10,allow_redirects=True)
            if r.status_code in (200,301,302,403): return True
            r=requests.get(url,headers=h,timeout=10,allow_redirects=True)
            return r.status_code in (200,301,302,403)
        except:
            return False

    async def fetch_epic(self):
        out=[]
        url="https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
        data=requests.get(url,timeout=15).json()
        for g in data.get("data",{}).get("Catalog",{}).get("searchStore",{}).get("elements",[]):
            for po in g.get("promotions",{}).get("promotionalOffers",[]):
                if po.get("promotionalOffers"):
                    title=g.get("title","").strip()
                    slug=g.get("productSlug","")
                    if not title or not slug: continue
                    link=f"https://store.epicgames.com/it/p/{slug}"
                    if self.validate(link):
                        gid=f"epic_{slug}"
                        if gid not in self.sent:
                            desc=g.get("description","") or "Gioco gratuito per tempo limitato."
                            desc=desc[:200]+"..." if len(desc)>200 else desc
                            ed=po["promotionalOffers"][0].get("endDate","")
                            end=""
                            if ed:
                                try: end=datetime.fromisoformat(ed.replace("Z","+00:00")).strftime("%d/%m/%Y alle %H:%M")
                                except: pass
                            out.append({"id":gid,"title":title,"description":desc,"url":link,"platform":"Epic Games","end_date":end})
        return out

    async def fetch_steam(self):
        out=[]
        feed=feedparser.parse("https://isthereanydeal.com/rss/deals/free/")
        for e in feed.entries[:5]:
            t=e.title.strip()
            summary=e.summary
            soup=BeautifulSoup(summary,"html.parser")
            links=[a["href"] for a in soup.find_all("a",href=True) if "store.steampowered.com" in a["href"]]
            if not links: continue
            link=links[0]
            if self.validate(link):
                gid=f"steam_{hash(link)}"
                if gid not in self.sent:
                    out.append({"id":gid,"title":t,"description":"Offerta gratuita su Steam.","url":link,"platform":"Steam","end_date":"Fino ad esaurimento"})
        return out

    async def fetch_gamer(self):
        out=[]
        data=requests.get("https://www.gamerpower.com/api/giveaways?platform=pc&type=game",timeout=15).json()
        for g in data[:5]:
            t=g.get("title","").strip()
            link=g.get("open_giveaway") or g.get("gamerpower_url")
            if not t or not link: continue
            if self.validate(link):
                gid=f"gp_{g.get('id')}"
                if gid not in self.sent:
                    desc=g.get("description","") or "Giveaway gratuito."
                    desc=desc[:200]+"..." if len(desc)>200 else desc
                    ed=g.get("end_date","")
                    end="Data non specificata"
                    if ed:
                        try: end=datetime.strptime(ed,"%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y alle %H:%M")
                        except: end=ed
                    out.append({"id":gid,"title":t,"description":desc,"url":link,"platform":"GamerPower","end_date":end})
        return out

    async def fetch_prime(self):
        # TODO: implementa scraping/API Prime Gaming
        return []

    async def fetch_gog(self):
        # TODO: implementa API/scraping GOG
        return []

    async def fetch_bnet(self):
        # TODO: implementa scraping Battle.net
        return []

    async def fetch_riot(self):
        # TODO: implementa scraping Riot Games
        return []

    async def run(self):
        games=[]
        games+=await self.fetch_epic()
        games+=await self.fetch_steam()
        games+=await self.fetch_gamer()
        games+=await self.fetch_prime()
        games+=await self.fetch_gog()
        games+=await self.fetch_bnet()
        games+=await self.fetch_riot()

        sent=0
        for g in games:
            if g["id"] in self.sent: continue
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

if __name__=="__main__":
    asyncio.run(FreeGamesBot().run())
