import os
import asyncio
import aiohttp
import sqlite3
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from mollie.api.client import Client
from bs4 import BeautifulSoup

# --- CONFIG (Берем из переменных окружения Railway) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MOLLIE_API_KEY = os.getenv("MOLLIE_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") 
BOT = Bot(token=TELEGRAM_TOKEN)
DP = Dispatcher()
APP = FastAPI()
MOLLIE = Client(api_key=MOLLIE_API_KEY)

# --- DATABASE (Используем /app/data для Volume) ---
DB_PATH = "/app/data/bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, subscription_end TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS seen_ads(link TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

# --- PARSING ---
async def parse_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    urls = [("https://www.pararius.com/apartments/eindhoven", "a.property-listing-link", "https://www.pararius.com"),
            ("https://kamernet.nl/en/for-rent/rooms-eindhoven", "a.tile", "https://kamernet.nl")]
    ads = []
    async with aiohttp.ClientSession(headers=headers) as session:
        for url, selector, base in urls:
            try:
                resp = await session.get(url)
                soup = BeautifulSoup(await resp.text(), "html.parser")
                for item in soup.select(selector):
                    link = (base + item["href"]) if item["href"].startswith("/") else item["href"]
                    ads.append((item.get_text(strip=True), link))
            except: continue
    return ads

# --- BOT HANDLERS ---
@DP.message(CommandStart())
async def start(message: types.Message):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO users(id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="2 weeks - €19.90")
    builder.button(text="4 weeks - €29.90")
    await message.answer("Welcome! Select a plan:", reply_markup=builder.as_markup(resize_keyboard=True))

# --- WEBHOOK & STARTUP ---
@APP.post("/webhook")
async def handle_webhook(req: Request):
    data = await req.json()
    await DP.feed_update(BOT, types.Update(**data))
    return {"ok": True}

@APP.on_event("startup")
async def on_startup():
    init_db()
    await BOT.set_webhook(f"{WEBHOOK_URL}/webhook")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(APP, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
