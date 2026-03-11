import os
import aiohttp
import sqlite3
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from mollie.api.client import Client
from bs4 import BeautifulSoup


# ... твой код ...

token = os.getenv("TELEGRAM_TOKEN")
if not token:
    print("ОШИБКА: Переменная TELEGRAM_TOKEN не найдена в Railway! Проверь вкладку Variables.")
    sys.exit(1) # Бот остановится, если токена нет

BOT = Bot(token=token)
DP = Dispatcher()
APP = FastAPI()
MOLLIE = Client(api_key=os.getenv("MOLLIE_API_KEY"))

# Путь к БД на диске (Volume)
DB_PATH = "/app/data/bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, subscription_end TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS seen_ads(link TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

# --- Логика парсинга ---
async def fetch_housing():
    urls = [("https://www.pararius.com/apartments/eindhoven", "a.property-listing-link", "https://www.pararius.com")]
    ads = []
    async with aiohttp.ClientSession() as session:
        for url, selector, base in urls:
            try:
                resp = await session.get(url, headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(await resp.text(), "html.parser")
                for item in soup.select(selector):
                    link = (base + item["href"]) if item["href"].startswith("/") else item["href"]
                    ads.append((item.get_text(strip=True), link))
            except Exception as e:
                print(f"Error parsing: {e}")
    return ads

# --- Роуты бота ---
@DP.message(CommandStart())
async def start(message: types.Message):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO users(id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="2 weeks - €19.90")
    builder.button(text="4 weeks - €29.90")
    await message.answer("Welcome to Eindhoven Housing Bot! Choose your plan:", 
                         reply_markup=builder.as_markup(resize_keyboard=True))

# --- Вебхуки ---
@APP.post("/webhook")
async def handle_webhook(req: Request):
    data = await req.json()
    await DP.feed_update(BOT, types.Update(**data))
    return {"ok": True}

@APP.on_event("startup")
async def on_startup():
    init_db()
    # Убедись, что WEBHOOK_URL прописан в переменных Railway
    await BOT.set_webhook(f"{os.getenv('WEBHOOK_URL')}/webhook")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(APP, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
