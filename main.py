import os
import sys
import asyncio
import sqlite3
import aiohttp
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from bs4 import BeautifulSoup

# --- ИНИЦИАЛИЗАЦИЯ ---
# 1. Проверяем наличие токена сразу, до запуска
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    print("КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_TOKEN не найден в настройках Railway!")
    sys.exit(1)

BOT = Bot(token=TOKEN)
DP = Dispatcher()
APP = FastAPI()
DB_PATH = "/app/data/bot.db"

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS seen_ads(link TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

# --- ЛОГИКА ---
async def fetch_ads():
    url = "https://www.pararius.com/apartments/eindhoven"
    async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
        try:
            async with session.get(url) as resp:
                soup = BeautifulSoup(await resp.text(), "html.parser")
                ads = []
                for item in soup.select("a.property-listing-link"):
                    link = "https://www.pararius.com" + item["href"]
                    ads.append((item.get_text(strip=True), link))
                return ads
        except Exception: return []

# --- БОТ ---
@DP.message(CommandStart())
async def start(message: types.Message):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO users(id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()
    await message.answer("Бот активен! Ищу жилье в Эйндховене...")

# --- СЕРВЕР ---
@APP.post("/webhook")
async def handle_webhook(req: Request):
    data = await req.json()
    await DP.feed_update(BOT, types.Update(**data))
    return {"ok": True}

@APP.on_event("startup")
async def on_startup():
    init_db()
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        await BOT.set_webhook(f"{webhook_url}/webhook")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(APP, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
