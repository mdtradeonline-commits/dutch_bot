import logging
import datetime
import pytz
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- 1. НАСТРОЙКИ ---
API_TOKEN = '8646275203:AAFenGqJIBpvk1DXrbBqDIOPiOILz3Zyllg'
ADMIN_ID = 6999400196

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- 2. РАБОТА С БАЗОЙ ДАННЫХ (SQLite) ---
def init_db():
    conn = sqlite3.connect('housing.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            join_date TEXT,
            lang TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_or_update_user(user_id, lang=None):
    conn = sqlite3.connect('housing.db')
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Пытаемся добавить, если нет — игнорим
    cursor.execute('INSERT OR IGNORE INTO users (user_id, join_date) VALUES (?, ?)', (user_id, now))
    if lang:
        cursor.execute('UPDATE users SET lang = ? WHERE user_id = ?', (lang, user_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('housing.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

# Запускаем создание базы при старте скрипта
init_db()

# --- 3. КНОПКИ МЕНЮ ---
def get_lang_menu():
    menu = ReplyKeyboardMarkup(resize_keyboard=True)
    menu.add(KeyboardButton('🇷🇺 Русский'), KeyboardButton('🇬🇧 English'), KeyboardButton('🇳🇱 Nederlands'))
    return menu

def get_main_menu(lang):
    menu = ReplyKeyboardMarkup(resize_keyboard=True)
    if lang == '🇷🇺 Русский':
        menu.add(KeyboardButton('⚙️ Настройки языка'), KeyboardButton('🏠 Моя подписка'))
    elif lang == '🇬🇧 English':
        menu.add(KeyboardButton('⚙️ Language Settings'), KeyboardButton('🏠 My Subscription'))
    else:
        menu.add(KeyboardButton('⚙️ Instellingen'), KeyboardButton('🏠 Mijn abonnement'))
    return menu

# --- 4. ОБРАБОТКА КОМАНД ---
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    add_or_update_user(user_id) # Пишем в базу
    
    tz_nl = pytz.timezone('Europe/Amsterdam')
    now_nl = datetime.datetime.now(tz_nl)
    
    await message.answer(
        f"Goeiedag! Eindhoven: {now_nl.strftime('%H:%M')}\nChoose language:",
        reply_markup=get_lang_menu()
    )

# --- 5. ВЫБОР ЯЗЫКА И НАСТРОЙКИ ---
@dp.message_handler(lambda message: message.text in ['🇷🇺 Русский', '🇬🇧 English', '🇳🇱 Nederlands'] or any(x in message.text for x in ["Настройки", "Settings", "Instellingen"]))
async def handle_lang_and_settings(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    if any(x in text for x in ["Настройки", "Settings", "Instellingen"]):
        await message.answer("Select language / Выберите язык:", reply_markup=get_lang_menu())
        return

    # Сохраняем язык в базу
    add_or_update_user(user_id, lang=text)
    
    confirm_text = {
        '🇷🇺 Русский': "Язык установлен! 🇷🇺",
        '🇬🇧 English': "Language set! 🇬🇧",
        '🇳🇱 Nederlands': "Taal ingesteld! 🇳🇱"
    }
    await message.answer(confirm_text.get(text, "OK!"), reply_markup=get_main_menu(text))

# --- 6. АДМИН-ПАНЕЛЬ И РАССЫЛКА ---
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID)
async def admin_msg(message: types.Message):
    if message.text.startswith('/'): return
    
    confirm_menu = InlineKeyboardMarkup()
    confirm_menu.add(InlineKeyboardButton("🚀 РАССЫЛКА (Всем)", callback_data="broadcast"))
    confirm_menu.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    await message.reply(f"Админ, рассылаем это сообщение всем?", reply_markup=confirm_menu)

@dp.callback_query_handler(lambda c: c.data == 'broadcast')
async def process_broadcast(callback_query: types.CallbackQuery):
    msg_text = callback_query.message.reply_to_message.text
    all_users = get_all_users() # Достаем всех из базы!
    count = 0
    for u_id in all_users:
        try:
            await bot.send_message(u_id, f"📢 НОВОЕ ОБЪЯВЛЕНИЕ:\n\n{msg_text}")
            count += 1
        except Exception: pass
    await bot.answer_callback_query(callback_query.id, text=f"Отправлено {count} чел.")
    await bot.send_message(ADMIN_ID, f"✅ Готово! Рассылка завершена ({count} чел.)")

@dp.callback_query_handler(lambda c: c.data == 'cancel')
async def cancel_broadcast(callback_query: types.CallbackQuery):
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
