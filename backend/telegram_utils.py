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
from telethon.tl.types import InputPeerChannel, PeerChannel
from telethon.errors import (
    ChannelPrivateError, ChannelInvalidError, 
    AuthKeyError, FloodWaitError, ApiIdInvalidError
)

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

def init_telegram_client() -> Optional[TelegramClient]:
    """Инициализация клиента Telegram."""
    # Проверка наличия API_ID и API_HASH
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        logger.error("TELEGRAM_API_ID или TELEGRAM_API_HASH не найдены в окружении")
        return None
    
    try:
        # Создание клиента
        client = TelegramClient(SESSION_NAME, int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
        logger.info("Клиент Telegram успешно инициализирован")
        return client
    except ValueError as e:
        logger.error(f"Ошибка при преобразовании TELEGRAM_API_ID в число: {e}")
        return None
    except Exception as e:
        logger.error(f"Ошибка при инициализации клиента Telegram: {e}")
        return None

async def get_telegram_posts_via_telethon(channel_username: str, limit: int = 20) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Получение последних постов из Telegram канала через Telethon API.
    
    Args:
        channel_username: Имя канала без символа '@'
        limit: Максимальное количество постов для получения
    
    Returns:
        Tuple[List[Dict[str, Any]], Optional[str]]: Список постов и сообщение об ошибке (если есть)
    """
    # Инициализация пустого списка постов и сообщения об ошибке
    posts = []
    error = None
    
    # Проверка имени канала
    if not channel_username:
        return [], "Имя канала не указано"
    
    # Удаление символа '@' из имени канала, если он есть
    if channel_username.startswith('@'):
        channel_username = channel_username[1:]
    
    # Инициализация клиента Telegram
    client = init_telegram_client()
    if not client:
        return [], "Не удалось инициализировать клиент Telegram. Проверьте API ключи."
    
    try:
        # Подключение к Telegram
        await client.connect()
        
        if not await client.is_user_authorized():
            # Попытка авторизации через бота (если есть токен)
            if TELEGRAM_BOT_TOKEN:
                await client.sign_in(bot_token=TELEGRAM_BOT_TOKEN)
                logger.info("Авторизация через бота успешна")
            else:
                error = "Требуется авторизация. Токен бота не найден."
                logger.warning(error)
                return [], error
        
        # Получение сущности канала
        try:
            entity = await client.get_entity(channel_username)
            logger.info(f"Сущность канала получена: {entity.id}")
        except (ChannelPrivateError, ChannelInvalidError) as e:
            error = f"Ошибка доступа к каналу {channel_username}: {str(e)}"
            logger.error(error)
            return [], error
        
        # Получение сообщений из канала
        messages = await client.get_messages(entity, limit=limit)
        logger.info(f"Получено {len(messages)} сообщений из канала {channel_username}")
        
        # Обработка сообщений
        for message in messages:
            if message.message:  # Если есть текст сообщения
                post = {"text": message.message, "date": message.date.isoformat()}
                
                # Обработка медиа (фото, документы и т.д.)
                if message.photo:
                    # Получение URL фото
                    post["photo"] = True
                    # Здесь можно добавить логику для получения URL фото
                
                if message.document:
                    # Обработка документов
                    post["document"] = True
                    # Здесь можно добавить логику для получения информации о документе
                
                posts.append(post)
        
        return posts, None
    
    except FloodWaitError as e:
        error = f"Слишком много запросов. Нужно подождать {e.seconds} секунд."
        logger.error(error)
    except ApiIdInvalidError:
        error = "Недействительный API ID или API Hash."
        logger.error(error)
    except AuthKeyError:
        error = "Ошибка авторизации. Возможно, сессия устарела."
        logger.error(error)
    except Exception as e:
        error = f"Непредвиденная ошибка при получении постов: {str(e)}"
        logger.error(error)
    
    finally:
        # Отключение от Telegram
        if client:
            await client.disconnect()
    
    return posts, error

def get_telegram_posts(channel_username: str, limit: int = 20) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Синхронная обертка для асинхронной функции get_telegram_posts_via_telethon.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(get_telegram_posts_via_telethon(channel_username, limit))
        return result
    finally:
        loop.close()

def get_mock_telegram_posts(username: str) -> List[Dict[str, Any]]:
    """
    Возвращает примеры постов, когда API недоступно.
    """
    # Примеры постов для тестирования
    return [
        {
            "text": "Пример поста 1 для канала " + username + ". Это демонстрационные данные, используемые когда API недоступно.",
            "date": "2023-01-01T12:00:00"
        },
        {
            "text": "Пример поста 2 для канала " + username + ". Содержит какую-то полезную информацию и #хэштеги.",
            "date": "2023-01-02T15:30:00"
        },
        {
            "text": "Пример поста 3 с более длинным текстом. Здесь может быть полезная информация, ссылки и т.д. Это демонстрационные данные.",
            "date": "2023-01-03T18:45:00"
        }
    ] 