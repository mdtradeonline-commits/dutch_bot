import os
import telebot
from telebot import types

# Берем токен из переменных Railway
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_ru = types.InlineKeyboardButton("🇷🇺 Русский", callback_data='ru')
    btn_en = types.InlineKeyboardButton("🇬🇧 English", callback_data='en')
    btn_pl = types.InlineKeyboardButton("🇵🇱 Polski", callback_data='pl')
    markup.add(btn_ru, btn_en, btn_pl)
    
    bot.send_message(message.chat.id, "Choose language / Выберите язык / Wybierz język:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    texts = {
        "ru": "🏠 Привет! Я ищу жилье в Нидерландах. Скоро здесь будут уведомления!",
        "en": "🏠 Hi! I'm hunting for apartments in NL. Notifications are coming soon!",
        "pl": "🏠 Cześć! Szukam mieszkań w Holandii. Powiadomienia już wkrótce!"
    }
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                         text=texts.get(call.data, "Error"))

print("Бот в строю!")
bot.infinity_polling()
