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

# ================= НАСТРОЙКА ЛОГИРОВАНИЯ =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MOLLIE_API_KEY = os.getenv("MOLLIE_API_KEY")
BOT_USERNAME   = os.getenv("BOT_USERNAME")
RAILWAY_URL    = os.getenv("RAILWAY_URL")

STANDARD_DELAY = 900
CHECK_INTERVAL = 300
DB_PATH = "bot.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# Объект сессии (будет инициализирован в main)
http_session: aiohttp.ClientSession = None

# ================= МОЛЛИ =================
mollie = Client()
if MOLLIE_API_KEY:
    mollie.set_api_key(MOLLIE_API_KEY)

# ================= ТЕКСТЫ И ДАННЫЕ =================
# (Я сократил их здесь для краткости, используй свои полные словари TEXTS и CITIES)
TEXTS = {
    "en": {
        "welcome": "🏠 <b>Housing Bot Netherlands</b>\n\nChoose your language:",
        "choose_city": "📍 Choose your city:",
        "city_set": "✅ City set to: <b>{city}</b>",
        "payment_ok": "✅ <b>Payment confirmed!</b>\nPlan: {plan}\nUntil: {date}",
        "new_listing": "🏠 <b>New listing!</b>\n\n{title}\n\n🔗 {url}",
        "new_listing_premium": "👑 <b>New listing!</b>\n\n{title}\n\n🔗 {url}\n\n✉️ <b>Letter:</b>\n\n{letter}",
        "letter": "Dear landlord, I am interested in your property...",
        "btn_my_sub": "📋 My subscription",
        "btn_change_city": "📍 Change city",
        # ... добавь остальные кнопки из своего первого сообщения
    },
    "ru": {
        "welcome": "🏠 <b>Housing Bot Нидерланды</b>\n\nВыбери язык:",
        "choose_city": "📍 Выбери город:",
        "city_set": "✅ Город выбран: <b>{city}</b>",
        "payment_ok": "✅ <b>Оплата подтверждена!</b>\nПлан: {plan}\nДо: {date}",
        "new_listing": "🏠 <b>Новое объявление!</b>\n\n{title}\n\n🔗 {url}",
        "new_listing_premium": "👑 <b>Новое объявление!</b>\n\n{title}\n\n🔗 {url}\n\n✉️ <b>Письмо:</b>\n\n{letter}",
        "letter": "Geachte verhuurder, я заинтересован в аренде...",
        "btn_my_sub": "📋 Моя подписка",
        "btn_change_city": "📍 Сменить город",
    },
    "nl": {
        "welcome": "🏠 <b>Housing Bot Nederland</b>\n\nKies je taal:",
        "choose_city": "📍 Kies je stad:",
        "city_set": "✅ Stad ingesteld op: <b>{city}</b>",
        "payment_ok": "✅ <b>Betaling bevestigd!</b>\nPlan: {plan}\nTot: {date}",
        "new_listing": "🏠 <b>Nieuwe woning!</b>\n\n{title}\n\n🔗 {url}",
        "new_listing_premium": "👑 <b>Nieuwe woning!</b>\n\n{title}\n\n🔗 {url}\n\n✉️ <b>Brief:</b>\n\n{letter}",
        "letter": "Geachte verhuurder, ik ben geïnteresseerd...",
        "btn_my_sub": "📋 Mijn abonnement",
        "btn_change_city": "📍 Stad wijzigen",
    }
}

CITIES = ["Amsterdam", "Rotterdam", "Den Haag", "Utrecht", "Eindhoven", "Groningen"]
PLAN_PRICES = {
    "std_2w": ("9.90", "Standard", 2),
    "std_4w": ("15.90", "Standard", 4),
    "prm_2w": ("19.90", "Premium", 2),
    "prm_4w": ("29.90", "Premium", 4),
}

# ================= БАЗА ДАННЫХ =================

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

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE id=?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def update_subscription(user_id: int, plan: str, weeks: int):
    user = await get_user(user_id)
    now = datetime.now()
    if user and user['subscription_end']:
        try:
            current_end = datetime.strptime(user['subscription_end'], "%Y-%m-%d %H:%M:%S")
            base_date = max(current_end, now)
        except: base_date = now
    else:
        base_date = now
    new_end = base_date + timedelta(weeks=weeks)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET plan=?, subscription_end=? WHERE id=?", 
                       (plan, new_end.strftime("%Y-%m-%d %H:%M:%S"), user_id))
        await db.commit()
    return new_end

# ================= ПАРСЕРЫ =================

async def fetch_html(url: str):
    try:
        async with http_session.get(url, headers=HEADERS, timeout=20) as resp:
            if resp.status == 200:
                return await resp.text()
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
        ads.append((item.get_text(strip=True), "https://www.pararius.com" + item.get("href", "")))
    return ads

async def parse_kamernet(city: str):
    url = f"https://kamernet.nl/en/for-rent/rooms-{city.lower()}" if city else "https://kamernet.nl/en/for-rent/rooms"
    html = await fetch_html(url)
    if not html: return []
    soup = BeautifulSoup(html, "html.parser")
    ads = []
    for item in soup.select("a.search-result-item"):
        ads.append((item.get_text(strip=True)[:100], "https://kamernet.nl" + item.get("href", "")))
    return ads

# ================= ЛОГИКА БОТА =================

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
        await db.commit()
    await message.answer(TEXTS["en"]["welcome"], reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇬🇧 EN", callback_data="lang_en"),
         InlineKeyboardButton(text="🇳🇱 NL", callback_data="lang_nl"),
         InlineKeyboardButton(text="🇷🇺 RU", callback_data="lang_ru")]
    ]), parse_mode="HTML")

# ... (Добавь здесь свои остальные хендлеры: cb_language, cb_city, cb_plan и т.д.)

# ================= WEBHOOK И РАССЫЛКА =================

async def mollie_webhook(request: web.Request):
    try:
        data = await request.post()
        payment_id = data.get("id")
        payment = mollie.payments.get(payment_id)
        if payment.is_paid():
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM payments WHERE payment_id=?", (payment_id,)) as c:
                    info = await c.fetchone()
            if info:
                end_dt = await update_subscription(info['user_id'], info['plan'], info['weeks'])
                user = await get_user(info['user_id'])
                lang = user['language'] if user else "en"
                await bot.send_message(info['user_id'], TEXTS[lang]["payment_ok"].format(
                    plan=info['plan'], date=end_dt.strftime("%d %b %Y")
                ), parse_mode="HTML")
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500)

async def parse_and_send():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as c:
            users = await c.fetchall()
    
    now = datetime.now()
    active_users = [u for u in users if u['subscription_end'] and datetime.strptime(u['subscription_end'], "%Y-%m-%d %H:%M:%S") > now]
    if not active_users: return

    checked_cities = set(u['city'] for u in active_users if u['city'])
    for city in checked_cities:
        ads = await asyncio.gather(parse_pararius(city), parse_kamernet(city), return_exceptions=True)
        all_ads = [item for sublist in ads if isinstance(sublist, list) for item in sublist]
        
        for title, url in all_ads:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT 1 FROM sent_ads WHERE url=?", (url,)) as c:
                    if await c.fetchone(): continue
                await db.execute("INSERT INTO sent_ads (url, sent_at) VALUES (?,?)", (url, now.strftime("%Y-%m-%d %H:%M:%S")))
                await db.commit()

            for u in [user for user in active_users if user['city'] == city]:
                if u['plan'] == "Premium":
                    text = TEXTS[u['language']]["new_listing_premium"].format(title=title, url=url, letter=TEXTS[u['language']]["letter"])
                    await bot.send_message(u['id'], text, parse_mode="HTML", disable_web_page_preview=True)
                else:
                    send_after = (now + timedelta(seconds=STANDARD_DELAY)).strftime("%Y-%m-%d %H:%M:%S")
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("INSERT INTO pending_standard (user_id, title, url, send_after) VALUES (?,?,?,?)",
                                       (u['id'], title, url, send_after))
                        await db.commit()
                await asyncio.sleep(0.05)

async def scheduler():
    while True:
        try:
            await parse_and_send()
            # Добавь сюда логику отправки Standard из таблицы pending_standard
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

# ================= ЗАПУСК =================

async def main():
    await init_db()
    global http_session
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        http_session = session
        
        app = web.Application()
        app.router.add_post("/webhook/mollie", mollie_webhook)
        app.router.add_get("/health", lambda r: web.Response(text="OK"))
        
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080))).start()
        
        asyncio.create_task(scheduler())
        logger.info("Bot is starting...")
        await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
