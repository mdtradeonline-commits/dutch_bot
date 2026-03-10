import logging
import cloudscraper
import asyncio
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# --- НАСТРОЙКИ ---
API_TOKEN = '8646275203:AAFenGqJIBpvk1DXrbBqDIOPiOILz3Zyllg'
ADMIN_ID = 6999400196

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- ПАРСЕРЫ ---
def parse_pararius(city):
    # Убираем лишние слова для корректной ссылки
    formatted_city = city.lower().replace("the ", "").replace(" ", "-")
    url = f"https://www.pararius.com/apartments/{formatted_city}"
    scraper = cloudscraper.create_scraper()
    try:
        resp = scraper.get(url, timeout=20)
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select('h2.listing-search-item__title a')
        res = [f"🏠 {i.text.strip()}\n🔗 https://www.pararius.com{i['href']}" for i in items[:5]]
        return res if res else ["На Pararius пока пусто."]
    except Exception as e: 
        return [f"Ошибка Pararius: {e}"]

# --- ФОНОВЫЙ МОНИТОРИНГ ---
seen_links = set()

async def monitor_housing():
    """Фоновая задача: проверяет Pararius каждые 30 минут"""
    while True:
        try:
            # Мониторим Эйндховен как основной город
            results = parse_pararius("eindhoven")
            for item in results:
                if "🔗" in item:
                    link = item.split("🔗 ")[-1]
                    if link not in seen_links:
                        seen_links.add(link)
                        # Отправка уведомления тебе
                        await bot.send_message(ADMIN_ID, f"🔔 Новая квартира в Эйндховене:\n{item}")
        except Exception as e:
            logging.error(f"Ошибка в мониторинге: {e}")
        
        await asyncio.sleep(1800) # 30 минут

# --- ИНТЕРФЕЙС ---
def get_main_menu():
    menu = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    menu.add(KeyboardButton('🏠 Pararius (Квартиры)'), KeyboardButton('⚙️ Сменить город'))
    return menu

def get_city_menu():
    menu = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    cities = ['🇳🇱 Eindhoven', '🇳🇱 Amsterdam', '🇳🇱 Rotterdam', '🇳🇱 The Hague', '🎓 Delft', '🎓 Leiden']
    for city in cities: menu.add(KeyboardButton(city))
    return menu

user_data = {}

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    await message.answer("Привет! Выбери город для поиска жилья:", reply_markup=get_city_menu())

@dp.message_handler(lambda m: '🇳🇱' in m.text or '🎓' in m.text)
async def set_city(message: types.Message):
    clean_city = message.text.split()[-1]
    user_data[message.from_user.id] = clean_city
    await message.answer(f"Город {message.text} зафиксирован.", reply_markup=get_main_menu())

@dp.message_handler(lambda m: m.text == '🏠 Pararius (Квартиры)')
async def search_pararius(message: types.Message):
    city = user_data.get(message.from_user.id, 'Eindhoven')
    await message.answer(f"Ищу квартиры в {city}...")
    res = parse_pararius(city)
    await message.answer("\n\n".join(res))

@dp.message_handler(lambda m: m.text == '⚙️ Сменить город')
async def change_city(message: types.Message):
    await message.answer("Выберите новый город:", reply_markup=get_city_menu())

# --- ЗАПУСК ---
if __name__ == '__main__':
    # Запускаем мониторинг в фоне
    loop = asyncio.get_event_loop()
    loop.create_task(monitor_housing())
    # Запускаем бота
    executor.start_polling(dp, skip_updates=True)
