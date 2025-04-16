#!/usr/bin/env python
"""
Утилиты для работы с Telegram API через библиотеку Telethon.
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Channel, Message
import os
from dotenv import load_dotenv
import asyncio
import re
from datetime import datetime, timedelta
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

# --- ПЕРЕМЕЩАЕМ Логгирование В НАЧАЛО --- 
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv(override=True)

# Получение конфигурации из переменных окружения
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SESSION_NAME = "telegram_session"

# Проверяем доступность Telethon
try:
    from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
    from telethon.tl.types import PeerChannel, InputPeerChannel
    TELETHON_AVAILABLE = True
except ImportError:
    logger.warning("Telethon не установлен. Функции, требующие Telethon, будут недоступны.")
    TELETHON_AVAILABLE = False

# Создание временного клиента Telegram
client = None

async def init_telegram_client() -> Optional[TelegramClient]:
    """Инициализация клиента Telegram"""
    global client
    
    if client and client.is_connected():
        return client
    
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        logger.error("TELEGRAM_API_ID или TELEGRAM_API_HASH не найдены в переменных окружения")
        return None
    
    try:
        client = TelegramClient(SESSION_NAME, TELEGRAM_API_ID, TELEGRAM_API_HASH)
        await client.start(bot_token=TELEGRAM_BOT_TOKEN)
        logger.info("Клиент Telegram успешно инициализирован")
        return client
    except Exception as e:
        logger.error(f"Ошибка при инициализации клиента Telegram: {e}")
        return None

async def get_telegram_posts_via_telethon(channel_username: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Получает последние посты из Telegram канала с использованием Telethon
    
    Args:
        channel_username: Имя пользователя или канала в Telegram
        limit: Максимальное количество постов для получения
        
    Returns:
        Список словарей с данными постов
    """
    client = await init_telegram_client()
    
    if not client:
        logger.error("Невозможно получить посты без клиента Telegram")
        return []
    
    try:
        # Получаем канал
        channel = await client.get_entity(channel_username)
        
        # Запрашиваем историю сообщений
        posts = []
        async for message in client.iter_messages(channel, limit=limit):
            if not message.text and not getattr(message, 'media', None):
                continue
                
            post_data = {
                'id': str(message.id),
                'date': message.date.isoformat(),
                'text': message.text,
                'views': getattr(message, 'views', 0),
                'has_media': bool(getattr(message, 'media', None)),
                'images': []
            }
            
            # Обработка медиа (фото или документов)
            if message.media:
                if isinstance(message.media, MessageMediaPhoto):
                    # Сохраняем путь к фото
                    photo_path = f"downloaded_media/photo_{message.id}.jpg"
                    await client.download_media(message.media, photo_path)
                    post_data['images'].append(photo_path)
                    
                elif isinstance(message.media, MessageMediaDocument) and message.media.document.mime_type.startswith('image'):
                    # Сохраняем путь к документу (изображению)
                    doc_path = f"downloaded_media/doc_{message.id}_{message.media.document.attributes[0].file_name}"
                    await client.download_media(message.media, doc_path)
                    post_data['images'].append(doc_path)
            
            posts.append(post_data)
            
        logger.info(f"Получено {len(posts)} постов из канала {channel_username}")
        return posts
        
    except Exception as e:
        logger.error(f"Ошибка при получении постов из канала {channel_username}: {e}")
        return []
    finally:
        # Закрываем соединение
        if client:
            await client.disconnect()
            
# Функция-обертка для синхронного вызова
def get_telegram_posts(channel_username: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Синхронная обертка для получения постов из Telegram канала
    
    Args:
        channel_username: Имя пользователя или канала в Telegram
        limit: Максимальное количество постов для получения
        
    Returns:
        Список словарей с данными постов
    """
    import asyncio
    
    try:
        # Используем асинхронную функцию в синхронном контексте
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_telegram_posts_via_telethon(channel_username, limit))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Ошибка при получении постов через синхронную обертку: {e}")
        return []

# Для совместимости с импортом в main.py
def get_mock_telegram_posts(username: str) -> List[Dict[str, Any]]:
    """
    Возвращает заглушку с постами для случаев, когда API не доступно.
    """
    return [
        {"text": "Пример поста 1 из канала " + username, "date": "2023-05-01T12:00:00", "id": "1"},
        {"text": "Пример поста 2 из канала " + username, "date": "2023-05-02T12:00:00", "id": "2"},
        {"text": "Пример поста 3 из канала " + username, "date": "2023-05-03T12:00:00", "id": "3"}
    ] 