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
            if normalized.endswith(' '+s): normalized = normalized[:-len(' '+s)]
        return normalized

    def clean_title(self, title):
        title = re.sub(r'\s*giveaway\s*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*\([^)]*\)\s*', '', title)
        return title.strip()

    def translate_description(self, text):
        patterns = {...}  # regex translations omitted for brevity
        ...