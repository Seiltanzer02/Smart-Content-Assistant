import os
import asyncio
from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

# --- Логгер ---
logger = logging.getLogger(__name__)

# --- Конфиг из окружения ---
API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
USERBOT_SESSION = os.getenv("TELETHON_SESSION_STRING")  # Получи через Telethon: StringSession
MINI_BOT_USERNAME = os.getenv("MINI_BOT_USERNAME", "YourMiniAppBot")  # username мини-бота

# --- User-бот (Telethon) ---
userbot = None
userbot_ready = False

async def get_star_referral_link():
    global userbot, userbot_ready
    if userbot is None:
        userbot = TelegramClient(StringSession(USERBOT_SESSION), API_ID, API_HASH)
    if not userbot_ready:
        await userbot.start()
        userbot_ready = True
    bot_entity = await userbot.get_entity(MINI_BOT_USERNAME)
    res = await userbot(functions.payments.ConnectStarRefBotRequest(
        peer=types.InputPeerSelf(),
        bot=types.InputUser(bot_entity.id, bot_entity.access_hash)
    ))
    return res.url

# --- Основная функция для вызова из python-telegram-bot ---
async def handle_get_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        link = await get_star_referral_link()
        keyboard = [[InlineKeyboardButton("Открыть реферальную ссылку", url=link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Ваша официальная реферальная ссылка Stars:\n{link}\n\n"
            "Используйте её для продвижения и заработка Stars!",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка при получении реферальной ссылки: {e}")
        await update.message.reply_text(f"Ошибка при получении ссылки: {e}")

# --- Вспомогательная функция для получения строки сессии ---
# Используй только для генерации, не для продакшена!
def generate_telethon_session():
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    api_id = int(input("API_ID: "))
    api_hash = input("API_HASH: ")
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        print("Session string:", client.session.save()) 