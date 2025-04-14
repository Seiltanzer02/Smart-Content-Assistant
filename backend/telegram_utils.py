import logging
from typing import List, Dict, Optional, Tuple
from telethon import TelegramClient
import os
from dotenv import load_dotenv
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetHistoryRequest
import telethon.errors

# --- ПЕРЕМЕЩАЕМ Логгирование В НАЧАЛО --- 
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv(override=True)

# Получение конфигурации из переменных окружения
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SESSION_NAME = "telegram_session"

async def get_telegram_posts_via_telethon(username: str) -> Tuple[List[Dict[str, str]], Optional[str]]:
    """Получение постов канала Telegram через Telethon с улучшенной обработкой ошибок."""
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH or not SESSION_NAME:
        error_msg = "Отсутствуют необходимые параметры для работы с Telegram API"
        logger.error(error_msg)
        return [], error_msg

    try:
        # Инициализация клиента
        client = TelegramClient(SESSION_NAME, TELEGRAM_API_ID, TELEGRAM_API_HASH)
        logger.info(f"Инициализирован клиент Telethon для канала @{username}")
        
        # Подключение к Telegram
        await client.connect()
        logger.info("Успешное подключение к Telegram")
        
        # Проверка авторизации
        if not await client.is_user_authorized():
            logger.info("Пользователь не авторизован, пробуем авторизоваться через бота")
            try:
                # Пробуем авторизоваться через бота
                if not TELEGRAM_BOT_TOKEN:
                    error_msg = "Отсутствует токен бота для авторизации"
                    logger.error(error_msg)
                    return [], error_msg
                
                await client.sign_in(bot_token=TELEGRAM_BOT_TOKEN)
                logger.info("Успешная авторизация через бота")
            except Exception as auth_error:
                error_msg = f"Ошибка авторизации через бота: {str(auth_error)}"
                logger.error(error_msg)
                return [], error_msg
        
        # Получение информации о канале
        try:
            channel = await client.get_entity(username)
            logger.info(f"Получена информация о канале @{username}")
        except ValueError as ve:
            error_msg = f"Канал @{username} не найден: {str(ve)}"
            logger.error(error_msg)
            return [], error_msg
        except Exception as e:
            error_msg = f"Ошибка при получении информации о канале @{username}: {str(e)}"
            logger.error(error_msg)
            return [], error_msg
        
        # Получение сообщений
        try:
            messages = await client.get_messages(channel, limit=20)
            logger.info(f"Получено {len(messages)} сообщений из канала @{username}")
        except Exception as e:
            error_msg = f"Ошибка при получении сообщений из канала @{username}: {str(e)}"
            logger.error(error_msg)
            return [], error_msg
        
        # Фильтрация и обработка сообщений
        posts = []
        for msg in messages:
            if msg.text:  # Берем только текстовые сообщения
                posts.append({
                    "text": msg.text,
                    "date": msg.date.isoformat() if msg.date else None,
                    "views": msg.views if hasattr(msg, 'views') else None
                })
        
        logger.info(f"Отфильтровано {len(posts)} текстовых сообщений")
        return posts, None
        
    except Exception as e:
        error_msg = f"Непредвиденная ошибка при работе с Telegram API: {str(e)}"
        logger.error(error_msg)
        return [], error_msg
    finally:
        try:
            await client.disconnect()
            logger.info("Отключение от Telegram API")
        except:
            pass 