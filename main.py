import asyncio
import aiosqlite
import aiohttp
import logging
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from mollie.api.client import Client

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MOLLIE_API_KEY = os.getenv("MOLLIE_API_KEY")
BOT_USERNAME   = os.getenv("BOT_USERNAME")
RAILWAY_URL    = os.getenv("RAILWAY_URL")

STANDARD_DELAY = 900
CHECK_INTERVAL = 300
DB_PATH = "bot.db"

# Глобальная переменная для сессии
http_session: aiohttp.ClientSession = None

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# (Тексты и Города оставляем без изменений, как в твоем исходнике)
# ... [TEXTS], [CITIES], [PLAN_PRICES] ...

# ================= БАЗА ДАННЫХ (Улучшено) =================

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'en',
                city TEXT,
                plan TEXT,
                subscription_end TEXT,
                demo_used INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sent_ads (
                url TEXT PRIMARY KEY,
                sent_at TEXT
            );
            CREATE TABLE IF NOT EXISTS pending_standard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                url TEXT,
                send_after TEXT
            );
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                user_id INTEGER,
                plan TEXT,
                weeks INTEGER
            );
        """)
        await db.commit()

# Универсальная функция получения данных юзера
async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE id=?", (user_id,)) as cursor:
            return await cursor.fetchone()

# ================= ПАРСЕРЫ (Оптимизировано) =================

async def fetch_html(url: str):
    try:
        async with http_session.get(url, headers=HEADERS, timeout=20) as resp:
            if resp.status == 200:
                return await resp.text()
            logger.warning(f"Failed to fetch {url}: Status {resp.status}")
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
    return None

async def parse_pararius(city: str):
    url = f"https://www.pararius.com/apartments/{city.lower()}" if city else "https://www.pararius.com/apartments/netherlands"
    html = await fetch_html(url)
    if not html: return []
    
    soup = BeautifulSoup(html, "html.parser")
    ads = []
    items = soup.select("section.listing-search-item a[href*='/apartment']")
    for item in items:
        title = item.get_text(strip=True)
        href = item.get("href", "")
        if href and title:
            ads.append((title, "https://www.pararius.com" + href))
    return ads

async def parse_kamernet(city: str):
    url = f"https://kamernet.nl/en/for-rent/rooms-{city.lower()}" if city else "https://kamernet.nl/en/for-rent/rooms"
    html = await fetch_html(url)
    if not html: return []
    
    soup = BeautifulSoup(html, "html.parser")
    ads = []
    items = soup.select("a.search-result-item")
    for item in items:
        title = item.get_text(strip=True)[:100]
        href = item.get("href", "")
        if href:
            ads.append((title, "https://kamernet.nl" + href))
    return ads

# ================= ЛОГИКА РАССЫЛКИ (Исправлено) =================

async def parse_and_send():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, language, city, plan, subscription_end FROM users") as cursor:
            all_users = await cursor.fetchall()

    now = datetime.now()
    active_users = [u for u in all_users if u['subscription_end'] and datetime.strptime(u['subscription_end'], "%Y-%m-%d %H:%M:%S") > now]
    
    if not active_users:
        return

    # Собираем уникальные города активных юзеров
    cities_to_check = list(set(u['city'] for u in active_users if u['city']))
    
    for city in cities_to_check:
        # Запускаем парсеры параллельно для каждого города
        results = await asyncio.gather(
            parse_pararius(city),
            parse_kamernet(city),
            # parse_huurwoningen(city), # добавь по аналогии
            return_exceptions=True
        )
        
        all_city_ads = []
        for res in results:
            if isinstance(res, list):
                all_city_ads.extend(res)

        for title, url in all_city_ads:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT 1 FROM sent_ads WHERE url=?", (url,)) as cursor:
                    if await cursor.fetchone():
                        continue
                
                await db.execute("INSERT OR IGNORE INTO sent_ads (url, sent_at) VALUES (?,?)", 
                               (url, now.strftime("%Y-%m-%d %H:%M:%S")))
                await db.commit()

            # Рассылка по юзерам этого города
            for user in [u for u in active_users if u['city'] == city]:
                if user['plan'] == "Premium":
                    lang = user['language']
                    letter = TEXTS[lang]["letter"]
                    text = TEXTS[lang]["new_listing_premium"].format(title=title, url=url, letter=letter)
                    try:
                        await bot.send_message(user['id'], text, parse_mode="HTML", disable_web_page_preview=True)
                        await asyncio.sleep(0.05) # Анти-спам лимит
                    except Exception as e:
                        logger.error(f"Send error to {user['id']}: {e}")
                
                elif user['plan'] == "Standard":
                    # Кладем в очередь с задержкой
                    send_after = (now + timedelta(seconds=STANDARD_DELAY)).strftime("%Y-%m-%d %H:%M:%S")
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("INSERT INTO pending_standard (user_id, title, url, send_after) VALUES (?,?,?,?)",
                                       (user['id'], title, url, send_after))
                        await db.commit()

# ================= MAIN =================

async def main():
    global http_session
    await init_db()
    
    # Инициализируем сессию один раз
    http_session = aiohttp.ClientSession(headers=HEADERS)
    
    # Web-сервер для Mollie
    app = web.Application()
    app.router.add_post("/webhook/mollie", mollie_webhook)
    app.router.add_get("/health", lambda r: web.Response(text="OK"))
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, "0.0.0.0", port).start()

    # Запуск шедулера и бота
    asyncio.create_task(scheduler())
    
    try:
        await dp.start_polling(bot)
    finally:
        await http_session.close()

if __name__ == "__main__":
    asyncio.run(main())
