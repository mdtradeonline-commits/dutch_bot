import logging
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

API_TOKEN = '8646275203:AAFenGqJIBpvk1DXrbBqDIOPiOILz3Zyllg'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Кнопки городов (те самые, которые пропали)
def get_city_menu():
    menu = ReplyKeyboardMarkup(resize_keyboard=True)
    menu.add(KeyboardButton('🇳🇱 Eindhoven'), KeyboardButton('🇳🇱 Amsterdam'))
    menu.add(KeyboardButton('🇳🇱 Rotterdam'), KeyboardButton('🇳🇱 The Hague'))
    menu.add(KeyboardButton('🎓 Delft'), KeyboardButton('🎓 Leiden'))
    menu.add(KeyboardButton('🌍 All NL/BE'))
    return menu

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    # Принудительно выводим меню городов сразу после старта
    await message.answer("Привет! Выбери город для поиска жилья:", reply_markup=get_city_menu())

@dp.message_handler(lambda m: 'Eindhoven' in m.text or 'Amsterdam' in m.text or 'Rotterdam' in m.text or 'Hague' in m.text)
async def handle_city(message: types.Message):
    await message.answer(f"Ты выбрал {message.text}. Поиск скоро будет доступен!")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
