import logging
from aiogram import Bot, Dispatcher, executor, types

# ВСТАВЬ СВОЙ ТОКЕН НИЖЕ В КАВЫЧКИ (БЕЗ ПРОБЕЛОВ)
API_TOKEN = '8646275203:AAFenGqJIBpvk1DXrbBqDIOPiOILz3Zyllg'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler()
async def echo(message: types.Message):
    await message.answer("Я ЖИВОЙ! На связи!")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
