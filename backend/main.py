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
import os
from dotenv import load_dotenv
from PIL import Image
import io
from aiohttp import ClientSession
import aiohttp
from secrets import token_hex
import uuid
import glob
from pathlib import Path

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

# ... existing code ...

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

