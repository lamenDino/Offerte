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
        # ... (unchanged) ...
        return await super().fetch_epic()

    async def fetch_steam(self):
        # ... (unchanged) ...
        return await super().fetch_steam()

    async def fetch_gamer(self):
        # ... (unchanged) ...
        return await super().fetch_gamer()

    async def fetch_prime(self):
        url = "https://gaming.amazon.com/loot"
        headers = {"User-Agent": "Mozilla/5.0"}
        out = []
        try:
            r = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.find_all("div", class_="loot-item")
            for item in items:
                title_el = item.find("h3")
                desc_el = item.find("p", class_="description")
                link_el = item.find("a", href=True)
                title = title_el.text.strip() if title_el else "Gioco Prime"
                desc = desc_el.text.strip() if desc_el else "Gioco gratis con Prime Gaming"
                href = link_el['href'] if link_el else None
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
        url = "https://www.gog.com/en/partner/free_games"
        headers = {"User-Agent": "Mozilla/5.0"}
        out = []
        try:
            r = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            tiles = soup.find_all("div", class_="product-tile")
            for tile in tiles:
                title_el = tile.find("h3", class_="product-title")
                link_el = tile.find_parent("a", href=True)
                title = title_el.text.strip() if title_el else "Gioco GOG"
                href = link_el['href'] if link_el else None
                link = f"https://www.gog.com{href}" if href and href.startswith("/") else href or url
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

        sent = 0
        for g in games:
            if g["id"] in self.sent:
                continue
            msg = (
                f"🎮 **{g['title']}**\n\n"
                f"📝 {g['description']}\n\n"
                f"🏷️ Piattaforma: {g['platform']}\n"
                f"⏰ Scade: {g['end_date']}\n\n"
                f"🔗 [Scarica Gratis]({g['url']})\n\n"
                f"💬 {CHANNEL_USERNAME}"
            )
            try:
                await self.bot.send_message(
                    chat_id=CHANNEL_USERNAME,
                    text=msg,
                    parse_mode=ParseMode.MARKDOWN
                )
                self.sent.add(g["id"])
                sent += 1
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Invio fallito {g['title']}: {e}")
        self.save_sent()
        logger.info(f"Inviati {sent} giochi")

async def main():
    bot = FreeGamesBot()
    await bot.send_hourly_update()

if __name__ == "__main__":
    asyncio.run(main())