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
        self.sent = self._load_sent()

    def _load_sent(self):
        try:
            with open(self.sent_file) as f:
                return set(json.load(f))
        except:
            return set()

    def _save_sent(self):
        with open(self.sent_file, "w") as f:
            json.dump(list(self.sent), f)

    def _validate(self, url):
        try:
            p = urlparse(url)
            if not p.scheme or not p.netloc:
                return False
            h = {"User-Agent": "Mozilla/5.0"}
            r = requests.head(url, headers=h, timeout=10, allow_redirects=True)
            if r.status_code in (200,301,302,403):
                return True
            r = requests.get(url, headers=h, timeout=10, allow_redirects=True)
            return r.status_code in (200,301,302,403)
        except:
            return False

    async def _fetch_epic(self):
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
        data = requests.get(url, timeout=15).json()
        out = []
        for g in data.get("data",{}).get("Catalog",{}).get("searchStore",{}).get("elements",[]):
            promo = g.get("promotions",{}).get("promotionalOffers",[])
            for po in promo:
                offs = po.get("promotionalOffers",[])
                if offs:
                    title = g.get("title","`).strip()
