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
                    gid = f"epic_{slug}"
                    if gid in self.sent:
                        continue
                    desc = g.get("description") or "Gioco gratuito per tempo limitato."
                    desc = desc[:200] + "..." if len(desc) > 200 else desc
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
                gid = f"steam_{hash(link)}"
                if gid in self.sent:
                    continue
                out.append({
                    "id": gid,
                    "title": title,
                    "description": "Offerta gratuita disponibile su Steam.",
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
                link = g.get("open_giveaway") or g.get("gamerpower_url")
                if not title or not link:
                    continue
                if not self.validate(link):
                    continue
                gid = f"gp_{g.get('id')}"
                if gid in self.sent:
                    continue
                desc = g.get("description") or "Giveaway gratuito disponibile."
                desc = desc[:200] + "..." if len(desc) > 200 else desc
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
                href = link_el["href"] if link_el else None
                link = f"https://gaming.amazon.com{href}" if href else url
                gid = f"prime_{title.lower().replace(' ', '_')}"
                if gid not in self.sent and self.validate(link):
                    out.append({
                        "id": gid,
                        "title": title,
                        "description": desc,
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
                gid = f"gog_{title.lower().replace(' ', '_')}"
                if gid not in self.sent and self.validate(link):
                    out.append({
                        "id": gid,
                        "title": title,
                        "description": "Offerta gratuita su GOG",
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

        parts = ["🎮 *Aggiornamento Giochi Gratuiti* 🎮\n"]
        for g in games:
            parts.append(
                f"*{g['title']}*  \n"
                f"_{g['platform']}_ – Scade: {g['end_date']}  \n"
                f"[Scarica Gratis]({g['url']})\n"
            )
        text = "\n".join(parts)

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
