
import logging
import datetime
import pytz # библиотека для часовых поясов
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

API_TOKEN = '8646275203:AAFenGqJIBpvk1DXrbBqDIOPiOILz3Zyllg'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# База данных «на коленке» (пока в памяти бота)
users_db = {} 

# Кнопки выбора языка
lang_menu = ReplyKeyboardMarkup(resize_keyboard=True)
lang_menu.add(KeyboardButton('🇷🇺 Русский'), KeyboardButton('🇬🇧 English'), KeyboardButton('🇳🇱 Nederlands'))

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    user_id = message.from_id
    # Определяем время в Эйндховене
    tz_nl = pytz.timezone('Europe/Amsterdam')
    now_nl = datetime.datetime.now(tz_nl)
    
    # Сохраняем пользователя, если его нет
    if user_id not in users_db:
        users_db[user_id] = {
            'join_date': now_nl,
            'lang': None
        }
    
    await message.answer(
        f"Goeiedag! Eindhoven time: {now_nl.strftime('%H:%M')}\n\n"
        "Choose your language / Выберите язык / Kies uw taal:",
        reply_markup=lang_menu
    )

@dp.message_handler(lambda message: message.text in ['🇷🇺 Русский', '🇬🇧 English', '🇳🇱 Nederlands'])
async def set_lang(message: types.Message):
    lang = message.text
    # Тут мы в будущем будем менять язык всех сообщений
    await message.answer(f"Success! / Принято! / Succes!\nSelected: {lang}", reply_markup=types.ReplyKeyboardRemove())
    await message.answer("Теперь я буду присылать тебе жилье. Твои 24 часа демо начались!")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
