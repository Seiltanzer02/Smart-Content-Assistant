#!/usr/bin/env python
import os
import sys
import json
import time
import uuid
import asyncio
import logging
import tempfile
import traceback
import requests
from typing import List, Dict, Optional, Any, Union
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form, Query, Header, Depends, Body
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
import httpx
import aiofiles
from dotenv import load_dotenv

# Безопасный импорт PIL - обработка ошибки, если библиотека не установлена
try:
    from PIL import Image
except ImportError:
    # Создаем заглушку для Image, чтобы код мог запускаться без ошибок
    # даже если PIL не установлен
    class DummyImage:
        @staticmethod
        def open(*args, **kwargs):
            logging.warning("PIL/Pillow не установлен. Функции работы с изображениями недоступны.")
            return None
    Image = DummyImage

# Загрузка переменных окружения
load_dotenv(override=True)

# Получение переменных окружения
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

# Канал для обязательной подписки
TARGET_CHANNEL_USERNAME = "smartcontenthelper"

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Создание экземпляра приложения FastAPI
app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Импорт других модулей (если нужно)
# from backend.services.something import some_function

@app.get("/check-channel-subscription", response_model=Dict[str, Any])
async def check_channel_subscription(request: Request):
    """
    Проверяет, подписан ли пользователь на требуемый канал.
    """
    try:
        # Получаем ID пользователя из заголовка
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id or not telegram_user_id.isdigit():
            logger.warning("Запрос проверки подписки без корректного ID пользователя Telegram")
            return {"subscribed": False, "error": "Некорректный ID пользователя Telegram", "reset_url": f"https://t.me/{TARGET_CHANNEL_USERNAME}"}
        
        # Импортируем функцию проверки подписки из telegram_utils
        from backend.telegram_utils import check_user_subscribed_to_channel
        
        # Проверяем подписку
        is_subscribed, error_message = await check_user_subscribed_to_channel(int(telegram_user_id), TARGET_CHANNEL_USERNAME)
        
        if error_message:
            logger.error(f"Ошибка при проверке подписки: {error_message}")
            return {"subscribed": False, "error": error_message, "reset_url": f"https://t.me/{TARGET_CHANNEL_USERNAME}"}
        
        # Отправляем сообщение пользователю в зависимости от результата
        if is_subscribed:
            await send_telegram_message(
                int(telegram_user_id),
                "✅ Вы подписаны на наш канал! Теперь вы можете использовать все функции приложения."
            )
            return {"subscribed": True, "message": "Вы успешно подписаны на канал"}
        else:
            await send_telegram_message(
                int(telegram_user_id),
                f"❌ Для использования приложения необходимо подписаться на наш канал: @{TARGET_CHANNEL_USERNAME}\n\nПосле подписки вернитесь в приложение и нажмите 'Проверить подписку'."
            )
            return {"subscribed": False, "message": "Требуется подписка на канал", "reset_url": f"https://t.me/{TARGET_CHANNEL_USERNAME}"}
    
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки на канал: {e}")
        return {"subscribed": False, "error": f"Внутренняя ошибка сервера: {str(e)}", "reset_url": f"https://t.me/{TARGET_CHANNEL_USERNAME}"}

# Определяем функцию для отправки Telegram сообщений
async def send_telegram_message(chat_id, text, parse_mode="HTML"):
    """Отправляет сообщение через Telegram Bot API"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не найден в окружении")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=payload)
            if response.status_code == 200:
                logger.info(f"Сообщение успешно отправлено пользователю {chat_id}")
                return True
            else:
                logger.error(f"Ошибка отправки сообщения: {response.status_code} {response.text}")
                return False
    except Exception as e:
        logger.error(f"Ошибка при отправке Telegram сообщения: {e}")
        return False

# Корневой эндпоинт
@app.get("/")
async def root():
    return {"message": "Smart Content API работает!"}

