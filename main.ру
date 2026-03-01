import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru')],
        [InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')],
        [InlineKeyboardButton("🇵🇱 Polski", callback_data='lang_pl')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose language / Wybierz język:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    responses = {
        'lang_ru': "🏠 **Привет! Я твой Dutch Home Hunter.**\n\nИщу жилье в NL 24/7. Скоро начнем!",
        'lang_en': "🏠 **Hi! I'm your Dutch Home Hunter.**\n\nScanning NL market 24/7. Stay tuned!",
        'lang_pl': "🏠 **Cześć! Jestem Dutch Home Hunter.**\n\nSzukam mieszkań w Holandii 24/7. Zaczynamy!"
    }
    
    await query.edit_message_text(text=responses.get(query.data), parse_mode='Markdown')

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()
