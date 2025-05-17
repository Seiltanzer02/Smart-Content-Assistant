# Основные библиотеки
import os
import sys
import json
import logging
import asyncio
import httpx
import tempfile
import shutil
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field
import re
import random

# FastAPI компоненты
from fastapi import FastAPI, Request, File, UploadFile, HTTPException, Query, Path, Response, Header, Depends, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

# Telethon
from telethon import TelegramClient
from telethon.errors import ChannelInvalidError, ChannelPrivateError, UsernameNotOccupiedError
from dotenv import load_dotenv

# Импорт сервиса для проверки подписки на канал
from backend.services.telegram_channel_service import check_channel_subscription, handle_subscription_check_request

# Supabase
from supabase import create_client, Client, AClient
from postgrest.exceptions import APIError
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PhoneNumberInvalidError, AuthKeyError, ApiIdInvalidError
import uuid
import mimetypes
from telethon.errors import RPCError
import getpass
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import time
import requests
from bs4 import BeautifulSoup
import telethon
import aiohttp
from backend.telegram_utils import get_telegram_posts, get_mock_telegram_posts
import move_temp_files
from datetime import datetime, timedelta
import traceback

# Unsplash
from unsplash import Api as UnsplashApi
from unsplash import Auth as UnsplashAuth

# DeepSeek
from openai import AsyncOpenAI, OpenAIError

# PostgreSQL
import asyncpg

# Imports for subscription service
from backend.services.supabase_subscription_service import SupabaseSubscriptionService

# --- ДОБАВЛЯЕМ ИМПОРТЫ для Unsplash --- 
# from pyunsplash import PyUnsplash # <-- УДАЛЯЕМ НЕПРАВИЛЬНЫЙ ИМПОРТ
from unsplash import Api as UnsplashApi # <-- ИМПОРТИРУЕМ ИЗ ПРАВИЛЬНОГО МОДУЛЯ
from unsplash import Auth as UnsplashAuth # <-- ИМПОРТИРУЕМ ИЗ ПРАВИЛЬНОГО МОДУЛЯ
# ---------------------------------------

# --- ПЕРЕМЕЩАЕМ Логгирование В НАЧАЛО --- 
# === ИЗМЕНЕНО: Уровень логирования на DEBUG ===
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
# === КОНЕЦ ИЗМЕНЕНИЯ ===
logger = logging.getLogger(__name__)
# --- КОНЕЦ ПЕРЕМЕЩЕНИЯ --- 

# --- Загрузка переменных окружения (оставляем для других ключей) --- 
# Убираем отладочные print для load_dotenv
dotenv_loaded = load_dotenv(override=True)

# Переменные из Render имеют приоритет над .env файлом
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL") 
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
TARGET_CHANNEL_USERNAME = os.getenv("TARGET_CHANNEL_USERNAME") # Имя канала для проверки подписки 

# --- Константы (включая имя сессии Telegram) --- 
SESSION_NAME = "telegram_session" # <-- Определяем имя файла сессии
IMAGE_SEARCH_COUNT = 15 # Сколько изображений запрашивать у Unsplash
IMAGE_RESULTS_COUNT = 5 # Сколько изображений показывать пользователю

# --- Валидация переменных окружения без аварийного завершения --- 
missing_keys = []
if not OPENROUTER_API_KEY:
    logger.warning("Ключ OPENROUTER_API_KEY не найден! Функции анализа контента будут недоступны.")
    missing_keys.append("OPENROUTER_API_KEY")

if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
    logger.warning("TELEGRAM_API_ID или TELEGRAM_API_HASH не найдены! Функции работы с Telegram API будут недоступны.")
    if not TELEGRAM_API_ID:
        missing_keys.append("TELEGRAM_API_ID")
    if not TELEGRAM_API_HASH:
        missing_keys.append("TELEGRAM_API_HASH")

if not UNSPLASH_ACCESS_KEY:
    logger.warning("Ключ UNSPLASH_ACCESS_KEY не найден! Поиск изображений через Unsplash будет недоступен.")
    missing_keys.append("UNSPLASH_ACCESS_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    logger.warning("SUPABASE_URL или SUPABASE_ANON_KEY не найдены! Функции сохранения данных будут недоступны.")
    if not SUPABASE_URL:
        missing_keys.append("SUPABASE_URL")
    if not SUPABASE_ANON_KEY:
        missing_keys.append("SUPABASE_ANON_KEY")

# Вывод информации о состоянии переменных окружения
if missing_keys:
    logger.warning(f"Отсутствуют следующие переменные окружения: {', '.join(missing_keys)}")
    logger.warning("Некоторые функции приложения могут быть недоступны.")
else:
    logger.info("Все необходимые переменные окружения найдены.")

# --- Инициализация Supabase client ---
logger.info("Инициализация Supabase...")
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")

if not supabase_url or not supabase_key:
    logger.warning("SUPABASE_URL или SUPABASE_ANON_KEY не найдены в окружении.")
    supabase = None
else:
    try:
        # Создаем клиент Supabase
        supabase = create_client(supabase_url, supabase_key)
        logger.info("Supabase успешно инициализирован.")
        
        # Проверяем доступность таблиц
        try:
            # Попытка получить запись из таблицы suggested_ideas для проверки
            result = supabase.table("suggested_ideas").select("id").limit(1).execute()
            logger.info("Таблица suggested_ideas существует и доступна.")
        except Exception as table_err:
            logger.warning(f"Таблица suggested_ideas недоступна: {table_err}. Возможно, миграции не были выполнены.")
    except Exception as e:
        logger.error(f"Ошибка при инициализации Supabase: {e}")
        supabase = None
# ---------------------------------------

# --- Вспомогательная функция для прямых SQL-запросов через API Supabase ---
async def _execute_sql_direct(sql_query: str) -> Dict[str, Any]:
    """Выполняет прямой SQL запрос через Supabase API."""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not supabase_key:
        logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY для прямого SQL")
        return {"status_code": 500, "error": "Missing Supabase credentials"}
        
    url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json" # Используем нашу RPC функцию
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json={"query": sql_query}, headers=headers)
        
        if response.status_code in [200, 204]:
            try:
                return {"status_code": response.status_code, "data": response.json()}
            except json.JSONDecodeError:
                # Для 204 ответа тела может не быть
                return {"status_code": response.status_code, "data": None}
        else:
            logger.error(f"Ошибка при выполнении прямого SQL запроса: {response.status_code} - {response.text}")
            return {"status_code": response.status_code, "error": response.text}
            
    except httpx.RequestError as e:
        logger.error(f"Ошибка HTTP запроса при выполнении прямого SQL: {e}")
        return {"status_code": 500, "error": str(e)}
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при выполнении прямого SQL: {e}")
        return {"status_code": 500, "error": str(e)}
# -------------------------------------------------------------------

# --- Инициализация FastAPI --- 
app = FastAPI(
    title="Smart Content Assistant API",
    description="API для анализа Telegram каналов и генерации контент-планов."
)

# Настройка CORS
origins = [
    "http://localhost", 
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "https://*.onrender.com",  # Для Render
    "https://t.me",            # Для Telegram
    "*"                        # Временно разрешаем все
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Telegram-User-Id"]  # Позволяем читать этот заголовок
)

@app.post("/generate-invoice", response_model=Dict[str, Any])
async def generate_invoice(request: Request):
    """Генерирует invoice_url через Telegram Bot API createInvoiceLink"""
    try:
        data = await request.json()
        if not data.get("user_id") or not data.get("amount"):
            raise HTTPException(status_code=400, detail="Отсутствуют обязательные параметры")
        user_id = data["user_id"]
        amount = int(data["amount"])
        payment_id = f"stars_invoice_{int(time.time())}_{user_id}"
        title = "Подписка Premium"
        description = "Подписка Premium на Smart Content Assistant на 1 месяц"
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        provider_token = os.getenv("PROVIDER_TOKEN")
        if not bot_token or not provider_token:
            raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN или PROVIDER_TOKEN не заданы в окружении")
        url = f"https://api.telegram.org/bot{bot_token}/createInvoiceLink"
        payload = {
            "title": title,
            "description": description,
            "payload": payment_id,
            "provider_token": provider_token,
            "currency": "RUB",
            "prices": [{"label": "Подписка", "amount": amount * 100}],
            "photo_url": "https://smart-content-assistant.onrender.com/static/premium_sub.jpg"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            tg_data = response.json()
            if not tg_data.get("ok"):
                logger.error(f"Ошибка Telegram API: {tg_data}")
                raise HTTPException(status_code=500, detail=f"Ошибка Telegram API: {tg_data}")
            invoice_url = tg_data["result"]
        return {"invoice_url": invoice_url, "payment_id": payment_id}
    except Exception as e:
        logger.error(f"Ошибка при генерации инвойса: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при генерации инвойса: {str(e)}")

@app.post("/send-stars-invoice", response_model=Dict[str, Any])
async def send_stars_invoice(request: Request):
    """Отправляет invoice на оплату Stars через Telegram Bot API sendInvoice (provider_token='', currency='XTR'). amount — это количество Stars (целое число)."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        amount = data.get("amount")
        if not user_id or not amount:
            raise HTTPException(status_code=400, detail="user_id и amount обязательны")
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN не задан в окружении")
        # amount — это количество Stars, Telegram требует amount*100
        stars_amount = int(amount)
        url = f"https://api.telegram.org/bot{bot_token}/sendInvoice"
        payload = {
            "chat_id": user_id,
            "title": "Подписка Premium",
            "description": "Подписка Premium на 1 месяц",
            "payload": f"stars_invoice_{user_id}_{int(time.time())}",
            "provider_token": "",  # ПУСТОЙ для Stars
            "currency": "XTR",
            "prices": [{"label": "XTR", "amount": stars_amount}],  # <--- БЕЗ *100!
            "need_name": False,
            "need_email": False,
            "is_flexible": False,
            "photo_url": "https://smart-content-assistant.onrender.com/static/premium_sub.jpg"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            tg_data = response.json()
            if not tg_data.get("ok"):
                logger.error(f"Ошибка Telegram API sendInvoice: {tg_data}")
                return {"success": False, "message": f"Ошибка Telegram API: {tg_data}"}
        return {"success": True, "message": "Инвойс отправлен в чат с ботом. Проверьте Telegram и оплатите счёт."}
    except Exception as e:
        logger.error(f"Ошибка при отправке Stars-инвойса: {e}")
        return {"success": False, "message": f"Ошибка: {str(e)}"}

@app.post("/generate-stars-invoice-link", response_model=Dict[str, Any])
async def generate_stars_invoice_link(request: Request):
    """Генерирует invoice_link для оплаты Stars через Telegram Bot API createInvoiceLink (provider_token='', currency='XTR')."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        amount = 1 # <--- УСТАНОВЛЕНО В 1 Star
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id обязателен")
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN не задан в окружении")
        url = f"https://api.telegram.org/bot{bot_token}/createInvoiceLink"
        payload = {
            "title": "Подписка Premium",
            "description": "Подписка Premium на 1 месяц",
            "payload": f"stars_invoice_{user_id}_{int(time.time())}",
            "provider_token": "",
            "currency": "XTR",
            "prices": [{"label": "XTR", "amount": amount}], # <--- Цена теперь 1
            "photo_url": "https://smart-content-assistant.onrender.com/static/premium_sub.jpg"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            tg_data = response.json()
            if not tg_data.get("ok"):
                logger.error(f"Ошибка Telegram API createInvoiceLink: {tg_data}")
                return {"success": False, "error": tg_data}
            invoice_link = tg_data["result"]
        return {"success": True, "invoice_link": invoice_link}
    except Exception as e:
        logger.error(f"Ошибка при генерации Stars invoice link: {e}")
        return {"success": False, "error": str(e)}

def normalize_db_url(url: str) -> str:
    """
    Преобразует URL базы данных в формат, совместимый с PostgreSQL.
    Если URL начинается с https://, преобразует его в формат postgresql://.
    """
    if not url:
        logger.warning("URL базы данных пустой!")
        return url
        
    logger.info(f"Исходный URL базы данных начинается с: {url[:10]}...")
    
    # Если URL - это строка подключения Postgres, которую предоставляет Supabase
    # Пример: postgres://postgres:[YOUR-PASSWORD]@db.vgffoerxbaqvzqgkaabq.supabase.co:5432/postgres
    if url.startswith('postgres://') and 'supabase.co' in url:
        logger.info("Обнаружен URL подключения к Supabase PostgreSQL - URL корректный")
        return url
    
    # Если URL начинается с https://, заменяем на postgresql://
    if url.startswith('https://'):
        # Извлекаем хост и путь
        parts = url.replace('https://', '').split('/')
        host = parts[0]
        
        # Для Supabase нужен специальный формат
        if 'supabase.co' in host:
            try:
                # Пытаемся найти ID проекта
                project_id = host.split('.')[0]
                # Формируем правильный URL для PostgreSQL с паролем по умолчанию
                # Это примерный формат, его нужно уточнить для конкретной инсталляции
                postgresql_url = f"postgresql://postgres:postgres@db.{project_id}.supabase.co:5432/postgres"
                logger.info(f"URL Supabase преобразован в PostgreSQL формат: {postgresql_url[:20]}...")
                return postgresql_url
            except Exception as e:
                logger.error(f"Ошибка при преобразовании URL Supabase: {e}")
                # Простое преобразование как резервный вариант
                postgresql_url = url.replace('https://', 'postgresql://')
                logger.info(f"URL базы данных преобразован из https:// в postgresql:// формат (резервный вариант): {postgresql_url[:20]}...")
                return postgresql_url
        else:
            # Для других случаев просто заменяем протокол
            postgresql_url = url.replace('https://', 'postgresql://')
            logger.info(f"URL базы данных преобразован из https:// в postgresql:// формат: {postgresql_url[:20]}...")
            return postgresql_url
    
    # Если URL начинается с http://, тоже заменяем на postgresql://
    if url.startswith('http://'):
        postgresql_url = url.replace('http://', 'postgresql://')
        logger.info(f"URL базы данных преобразован из http:// в postgresql:// формат: {postgresql_url[:20]}...")
        return postgresql_url
    
    # Если URL уже имеет правильный формат postgresql://
    if url.startswith('postgresql://') or url.startswith('postgres://'):
        logger.info(f"URL базы данных уже в правильном формате: {url[:20]}...")
        return url
    
    # В других случаях возвращаем URL без изменений, но с предупреждением
    logger.warning(f"URL базы данных имеет неизвестный формат. Начало URL: {url[:10]}...")
    return url

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    logger.info(f"Получено обновление от Telegram: {data}")

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN") # Используем TELEGRAM_BOT_TOKEN

    if "callback_query" in data:
        callback_query = data["callback_query"]
        callback_data = callback_query.get("data")
        user_id = callback_query.get("from", {}).get("id")
        chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
        message_id = callback_query.get("message", {}).get("message_id")
        
        logger.info(f"Получен callback_query с data: {callback_data}, user_id: {user_id}, chat_id: {chat_id}")
        
        # Отвечаем на callback_query, чтобы убрать "часики" на кнопке
        if telegram_bot_token: # Проверяем telegram_bot_token
            answer_callback_url = f"https://api.telegram.org/bot{telegram_bot_token}/answerCallbackQuery"
            async with httpx.AsyncClient() as client:
                try:
                    await client.post(answer_callback_url, json={"callback_query_id": callback_query["id"]})
                except Exception as e_ans:
                    logger.error(f"Ошибка при отправке answerCallbackQuery: {e_ans}")
        else:
            logger.error("TELEGRAM_BOT_TOKEN не найден, не могу отправить answerCallbackQuery.")
        
        # Обработка callback для проверки подписки на канал
        if callback_data == "check_subscription_callback":
            logger.info(f"Пользователь {user_id} запросил проверку подписки на канал")
            
            # Используем функцию из сервиса для проверки подписки
            is_subscribed = await check_channel_subscription(user_id)
            
            if is_subscribed:
                # Пользователь подписан - отправляем уведомление об успешной подписке
                await send_telegram_message(
                    chat_id=chat_id, 
                    text="✅ Подписка подтверждена! Теперь у вас есть доступ к приложению."
                )
                
                # Изменяем сообщение, убирая кнопку "Проверить подписку"
                if message_id and telegram_bot_token: # Проверяем telegram_bot_token
                    target_channel_username = os.getenv("TARGET_CHANNEL_USERNAME")
                    channel_link = "наш канал"
                    
                    if target_channel_username:
                        if target_channel_username.startswith("@"):
                            channel_link = f"https://t.me/{target_channel_username[1:]}"
                        elif not target_channel_username.startswith("-100"): 
                            channel_link = f"https://t.me/{target_channel_username}"
                    
                    # Создаем кнопку только для перехода к каналу
                    reply_markup = {
                        "inline_keyboard": [[{"text": "Канал", "url": channel_link}]]
                    }
                    
                    edit_markup_url = f"https://api.telegram.org/bot{telegram_bot_token}/editMessageReplyMarkup"
                    async with httpx.AsyncClient() as client:
                        try:
                            await client.post(
                                edit_markup_url, 
                                json={
                                    "chat_id": chat_id,
                                    "message_id": message_id,
                                    "reply_markup": reply_markup
                                }
                            )
                        except Exception as e_edit:
                            logger.error(f"Ошибка при редактировании сообщения: {e_edit}")
            else:
                # Пользователь все еще не подписан
                await send_telegram_message(
                    chat_id=chat_id, 
                    text="❌ Подписка не обнаружена. Пожалуйста, подпишитесь на канал и попробуйте снова."
                )
            
            # Возвращаем ответ на webhook
            return {"ok": True, "action": "check_subscription_processed"}
    # ... (остальная часть кода)
    # ... (остальная часть кода)
    return {"status": "ok"}

# Выделим отправку сообщений в отдельную функцию для переиспользования
async def send_telegram_message(chat_id, text, parse_mode="HTML"):
    """Отправляет сообщение через Telegram API"""
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        logger.error("Отсутствует TELEGRAM_BOT_TOKEN при отправке сообщения")
        return False
        
    telegram_api_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(telegram_api_url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            })
            if response.status_code == 200:
                logger.info(f"Сообщение успешно отправлено пользователю {chat_id}")
                return True
            else:
                logger.error(f"Ошибка при отправке сообщения: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Исключение при отправке сообщения в Telegram: {e}")
            return False

# Добавляем прямой эндпоинт для проверки и обновления статуса подписки
@app.get("/manual-check-premium/{user_id}")
async def manual_check_premium(user_id: int, request: Request, force_update: bool = False):
    """
    Ручная проверка премиум-статуса и обновление кэша.
    Параметр force_update=true позволяет принудительно обновить кэш для пользователя.
    """
    try:
        db_url = os.getenv("SUPABASE_URL") or os.getenv("DATABASE_URL") or os.getenv("RENDER_DATABASE_URL")
        if not db_url:
            logger.error("Отсутствуют SUPABASE_URL, DATABASE_URL и RENDER_DATABASE_URL при ручной проверке премиума")
            return {"success": False, "error": "Отсутствуют SUPABASE_URL, DATABASE_URL и RENDER_DATABASE_URL в переменных окружения"}
            
        # Нормализуем URL базы данных
        db_url = normalize_db_url(db_url)
            
        # Подключаемся к БД
        conn = await asyncpg.connect(db_url)
        try:
            # Проверяем наличие активной подписки
            query = """
            SELECT COUNT(*) 
            FROM user_subscription 
            WHERE user_id = $1 
              AND is_active = TRUE 
              AND end_date > NOW()
            """
            count = await conn.fetchval(query, user_id)
            has_premium = count > 0
            
            # Получаем детали подписки
            subscription_details = {}
            if has_premium:
                details_query = """
                SELECT 
                    end_date,
                    payment_id,
                    created_at,
                    updated_at
                FROM user_subscription 
                WHERE user_id = $1 
                  AND is_active = TRUE
                ORDER BY end_date DESC 
                LIMIT 1
                """
                record = await conn.fetchrow(details_query, user_id)
                if record:
                    subscription_details = {
                        "end_date": record["end_date"].strftime('%Y-%m-%d %H:%M:%S'),
                        "payment_id": record["payment_id"],
                        "created_at": record["created_at"].strftime('%Y-%m-%d %H:%M:%S'),
                        "updated_at": record["updated_at"].strftime('%Y-%m-%d %H:%M:%S')
                    }
            
            # Если force_update = true, принудительно обновляем статус во всех кэшах
            if force_update and has_premium:
                # Здесь можно добавить логику обновления кэша или других механизмов
                # В этом примере мы просто логируем событие
                logger.info(f"Принудительное обновление премиум-статуса для пользователя {user_id}")
            
            return {
                "success": True, 
                "user_id": user_id,
                "has_premium": has_premium,
                "subscription_details": subscription_details
            }
            
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Ошибка при ручной проверке премиум-статуса: {e}")
        return {"success": False, "error": str(e)}

# --- Настройка обслуживания статических файлов ---
import os
from fastapi.staticfiles import StaticFiles

# Путь к папке со статическими файлами
static_folder = os.path.join(os.path.dirname(__file__), "static")

# ФЛАГ для монтирования статики в конце файла
SHOULD_MOUNT_STATIC = os.path.exists(static_folder)
# НОВЫЙ ФЛАГ, указывающий, что мы уже настроили маршруты SPA
SPA_ROUTES_CONFIGURED = False

if SHOULD_MOUNT_STATIC:
    logger.info(f"Статические файлы будут обслуживаться из папки: {static_folder} (монтирование в конце файла)")
else:
    logger.warning(f"Папка статических файлов не найдена: {static_folder}")
    logger.warning("Статические файлы не будут обслуживаться. Только API endpoints доступны.")

class AnalyzeRequest(BaseModel):
    username: str

class AnalysisResult(BaseModel):
    themes: List[str]
    styles: List[str]
    analyzed_posts_sample: List[str]
    best_posting_time: str # Пока строка
    analyzed_posts_count: int
    
# Добавляем пропущенное определение класса AnalyzeResponse
class AnalyzeResponse(BaseModel):
    themes: List[str]
    styles: List[str]
    analyzed_posts_sample: List[str] 
    best_posting_time: str
    analyzed_posts_count: int
    message: Optional[str] = None
    error: Optional[str] = None
    
# --- ДОБАВЛЯЕМ ОПРЕДЕЛЕНИЕ МОДЕЛИ PlanGenerationRequest ---
class PlanGenerationRequest(BaseModel):
    themes: List[str]
    styles: List[str]
    period_days: int = Field(7, gt=0, le=30) # По умолчанию 7 дней, с ограничениями
    channel_name: str # Добавляем обязательное имя канала

# Модель для одного элемента плана (для структурированного ответа)
class PlanItem(BaseModel):
    day: int # День от начала периода (1, 2, ...)
    topic_idea: str # Предложенная тема/идея поста
    format_style: str # Предложенный формат/стиль

# --- НОВЫЕ МОДЕЛИ для детализации поста --- 
class GeneratePostDetailsRequest(BaseModel):
    topic_idea: str = Field(..., description="Идея поста из плана")
    format_style: str = Field(..., description="Формат/стиль поста из плана")
    keywords: Optional[List[str]] = Field(None, description="(Опционально) Ключевые слова для поиска изображений и уточнения текста") 
    post_samples: Optional[List[str]] = Field(None, description="Примеры постов канала для имитации стиля")

# --- ОБЩИЙ ТИП для найденного изображения --- 
class FoundImage(BaseModel):
    id: str
    source: str # Источник (unsplash, pexels, openverse)
    preview_url: str # URL миниатюры
    regular_url: str # URL основного изображения
    description: Optional[str] = None
    author_name: Optional[str] = None
    author_url: Optional[str] = None

# --- Определение PostImage ПЕРЕД его использованием --- 
class PostImage(BaseModel):
    url: str
    id: Optional[str] = None
    preview_url: Optional[str] = None
    alt: Optional[str] = None
    author: Optional[str] = None # Соответствует author_name в БД
    author_url: Optional[str] = None
    source: Optional[str] = None

# --- Модель ответа для детализации поста --- 
class PostDetailsResponse(BaseModel):
    generated_text: str = Field(..., description="Сгенерированный текст поста")
    found_images: List[FoundImage] = Field([], description="Список найденных изображений из разных источников") 
    message: str = Field("", description="Дополнительное сообщение")
    channel_name: Optional[str] = Field(None, description="Имя канала, к которому относится пост")
    # Теперь PostImage определен выше
    selected_image_data: Optional[PostImage] = Field(None, description="Данные выбранного изображения")

# --- Модель для СОЗДАНИЯ/ОБНОВЛЕНИЯ поста --- 
class PostData(BaseModel):
    target_date: str = Field(..., description="Дата поста YYYY-MM-DD")
    topic_idea: str
    format_style: str
    final_text: str
    image_url: Optional[str] = Field(None, description="URL изображения (опционально)") # Оставляем для старых версий? Можно удалить позже.
    images_ids: Optional[List[str]] = Field(None, description="Список ID изображений (устарело)") # Помечаем как устаревшее
    channel_name: Optional[str] = Field(None, description="Имя канала, к которому относится пост")
    # PostImage определен выше
    selected_image_data: Optional[PostImage] = Field(None, description="Данные выбранного изображения")

# --- Модель для сохраненного поста (для ответа GET /posts) --- 
class SavedPostResponse(PostData):
    id: str 
    # Убираем дублирующие поля из PostData
    # created_at: str 
    # updated_at: str
    # image_url: Optional[str] = Field(None, description="URL изображения (опционально)")
    # images_ids: Optional[List[str]] = Field(None, description="Список ID изображений")
    # channel_name: Optional[str] = Field(None, description="Имя канала, к которому относится пост")
    # Добавляем поля, специфичные для ответа
    created_at: str = Field(..., description="Время создания поста")
    updated_at: str = Field(..., description="Время последнего обновления поста")

# --- Функция для получения постов Telegram через HTTP парсинг ---
async def get_telegram_posts_via_http(username: str) -> List[str]:
    """Получение постов канала Telegram через HTTP парсинг."""
    try:
        url = f"https://t.me/s/{username}"
        logger.info(f"Запрос HTTP парсинга для канала @{username}: {url}")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            
        if response.status_code != 200:
            logger.warning(f"HTTP статус-код для @{username}: {response.status_code}")
            return []
            
        # Используем BeautifulSoup для парсинга HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем блоки с сообщениями
        message_blocks = soup.select('div.tgme_widget_message_bubble')
        
        if not message_blocks:
            logger.warning(f"Не найдены блоки сообщений для @{username}")
            return []
            
        # Извлекаем текст сообщений
        posts = []
        for block in message_blocks:
            text_block = block.select_one('div.tgme_widget_message_text')
            if text_block and text_block.text.strip():
                posts.append(text_block.text.strip())
        
        logger.info(f"Найдено {len(posts)} постов через HTTP парсинг для @{username}")
        return posts
        
    except Exception as e:
        logger.error(f"Ошибка при HTTP парсинге канала @{username}: {e}")
        raise

# --- Функция для получения примеров постов ---
def get_sample_posts(channel_name: str) -> List[str]:
    """Возвращает пример постов для демонстрации в случае, если не удалось получить реальные посты."""
    # Базовые примеры постов
    generic_posts = [
        "Добрый день, уважаемые подписчики! Сегодня мы обсудим важную тему, которая касается каждого.",
        "Представляем вам новый обзор актуальных событий. Оставляйте свои комментарии и делитесь мнением.",
        "Интересный факт: знаете ли вы, что статистика показывает, что 90% людей...",
        "В этом посте мы разберем самые популярные вопросы от наших подписчиков.",
        "Подводим итоги недели: что важного произошло и что нас ждет впереди."
    ]
    
    # Можно добавить специфичные примеры для разных каналов
    tech_posts = [
        "Новый iPhone уже в продаже. Первые впечатления и обзор характеристик.",
        "Обзор последних изменений в Android. Что нас ждет в новой версии?",
        "ИИ и его влияние на современное программирование: полезные инструменты для разработчиков.",
        "Какой язык программирования выбрать в 2024 году? Обзор популярных технологий.",
        "Новые инструменты для веб-разработки, которые стоит попробовать каждому."
    ]
    
    business_posts = [
        "5 стратегий, которые помогут вашему бизнесу выйти на новый уровень.",
        "Как правильно инвестировать в 2024 году? Советы экспертов.",
        "Тайм-менеджмент для руководителя: как все успевать и не выгорать.",
        "Анализ рынка: главные тренды и прогнозы на ближайшее будущее.",
        "История успеха: как небольшой стартап превратился в миллионный бизнес."
    ]
    
    # Выбираем подходящий набор примеров в зависимости от имени канала
    channel_lower = channel_name.lower()
    if any(keyword in channel_lower for keyword in ["tech", "code", "programming", "dev", "it"]):
        return tech_posts
    elif any(keyword in channel_lower for keyword in ["business", "finance", "money", "startup"]):
        return business_posts
    else:
        return generic_posts

# --- Функция для сохранения результатов анализа в базу данных ---
async def save_suggested_idea(idea_data: Dict[str, Any]) -> str:
    """Сохраняет предложенную идею в базу данных."""
    try:
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            return "Ошибка: Клиент Supabase не инициализирован"
        
        # Подготавливаем данные в соответствии со структурой таблицы suggested_ideas
        idea_to_save = {
            "id": str(uuid.uuid4()),  # Генерируем UUID
            "channel_name": idea_data.get("channel_name", ""),
            "user_id": idea_data.get("user_id"),
            "topic_idea": idea_data.get("topic_idea", ""),
            "format_style": idea_data.get("format_style", ""),
            "relative_day": idea_data.get("day", 0),
            "is_detailed": False  # Изначально идея не детализирована
        }
        
        # Сохранение в Supabase
        result = supabase.table("suggested_ideas").insert(idea_to_save).execute()
        
        # Проверка результата
        if hasattr(result, 'data') and len(result.data) > 0:
            logger.info(f"Успешно сохранена идея для канала {idea_data.get('channel_name')}")
            return "success"
        else:
            logger.error(f"Ошибка при сохранении идеи: {result}")
            return "error"
            
    except Exception as e:
        logger.error(f"Ошибка при сохранении идеи: {e}")
        return f"Ошибка: {str(e)}"

# --- Функция для анализа контента с помощью DeepSeek ---
async def analyze_content_with_deepseek(texts: List[str], api_key: str) -> Dict[str, List[str]]:
    """Анализ контента с использованием модели DeepSeek через OpenRouter API."""
    
    # Проверяем наличие API ключа
    if not api_key:
        logger.warning("Анализ контента с DeepSeek невозможен: отсутствует OPENROUTER_API_KEY")
        return {
            "themes": ["Тема 1", "Тема 2", "Тема 3", "Тема 4", "Тема 5"],
            "styles": ["Формат 1", "Формат 2", "Формат 3", "Формат 4", "Формат 5"]
        }
    
    # Если нет текстов или API ключа, возвращаем пустой результат
    if not texts or not api_key:
        logger.error("Отсутствуют тексты или API ключ для анализа")
        return {"themes": [], "styles": []}
    
    # Объединяем тексты для анализа
    combined_text = "\n\n".join([f"Пост {i+1}: {text}" for i, text in enumerate(texts)])
    logger.info(f"Подготовлено {len(texts)} текстов для анализа через DeepSeek")
    
    # --- ИЗМЕНЕНИЕ: Уточненные промпты для анализа --- 
    system_prompt = """Ты - эксперт по анализу контента Telegram-каналов. 
Твоя задача - глубоко проанализировать предоставленные посты и выявить САМЫЕ ХАРАКТЕРНЫЕ, ДОМИНИРУЮЩИЕ темы и стили/форматы, отражающие СУТЬ и УНИКАЛЬНОСТЬ канала. 
Избегай слишком общих формулировок, если они не являются ключевыми. Сосредоточься на качестве, а не на количестве.

Выдай результат СТРОГО в формате JSON с двумя ключами: "themes" и "styles". Каждый ключ должен содержать массив из 3-5 наиболее РЕЛЕВАНТНЫХ строк."""
    
    user_prompt = f"""Проанализируй СТРОГО следующие посты из Telegram-канала:
{combined_text}

Определи 3-5 САМЫХ ХАРАКТЕРНЫХ тем и 3-5 САМЫХ РАСПРОСТРАНЕННЫХ стилей/форматов подачи контента, которые наилучшим образом отражают специфику ИМЕННО ЭТОГО канала. 
Основывайся ТОЛЬКО на предоставленных текстах. 

Представь результат ТОЛЬКО в виде JSON объекта с ключами "themes" и "styles". Никакого другого текста."""
    # --- КОНЕЦ ИЗМЕНЕНИЯ --- 
    
    # Делаем запрос к API
    analysis_result = {"themes": [], "styles": []}
    
    try:
        # Инициализируем клиент
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        
        # Запрашиваем ответ от API
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free", # <--- ИЗМЕНЕНО НА НОВУЮ БЕСПЛАТНУЮ МОДЕЛЬ
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=600,
            timeout=60,
            extra_headers={
                "HTTP-Referer": "https://content-manager.onrender.com",
                "X-Title": "Smart Content Assistant"
            }
        )
        
        # Получаем текст ответа
        analysis_text = response.choices[0].message.content.strip()
        logger.info(f"Получен ответ от DeepSeek: {analysis_text[:100]}...")
        
        # Извлекаем JSON из ответа
        json_match = re.search(r'(\{.*\})', analysis_text, re.DOTALL)
        if json_match:
            analysis_text = json_match.group(1)
        
        # Парсим JSON
        analysis_json = json.loads(analysis_text)
        
        # --- ИЗМЕНЕНИЕ: Обработка ключей themes и styles/style --- 
        themes = analysis_json.get("themes", [])
        # Пытаемся получить стили по ключу "styles" или "style"
        styles = analysis_json.get("styles", analysis_json.get("style", [])) 
        
        if isinstance(themes, list) and isinstance(styles, list):
            analysis_result = {"themes": themes, "styles": styles}
            logger.info(f"Успешно извлечены темы ({len(themes)}) и стили ({len(styles)}) из JSON.")
        else:
            logger.warning(f"Некорректный тип данных для тем или стилей в JSON: {analysis_json}")
            # Оставляем analysis_result пустым или сбрасываем в дефолтное значение
            analysis_result = {"themes": [], "styles": []}
        # --- КОНЕЦ ИЗМЕНЕНИЯ --- 
    
    except json.JSONDecodeError as e:
        # Если не удалось распарсить JSON, используем регулярные выражения
        logger.error(f"Ошибка парсинга JSON: {e}, текст: {analysis_text}")
        
        themes_match = re.findall(r'"themes":\s*\[(.*?)\]', analysis_text, re.DOTALL)
        if themes_match:
            theme_items = re.findall(r'"([^"]+)"', themes_match[0])
            analysis_result["themes"] = theme_items
        
        styles_match = re.findall(r'"styles":\s*\[(.*?)\]', analysis_text, re.DOTALL)
        if styles_match:
            style_items = re.findall(r'"([^"]+)"', styles_match[0])
            analysis_result["styles"] = style_items
    
    except Exception as e:
        # Обрабатываем любые другие ошибки
        logger.error(f"Ошибка при анализе контента через DeepSeek: {e}")
    
    return analysis_result

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_channel(request: Request, req: AnalyzeRequest):
    """Анализ канала Telegram на основе запроса."""
    # Получение telegram_user_id из заголовков
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    # Валидация user_id
    if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
        logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
        return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})
        logger.info(f"Анализ для пользователя Telegram ID: {telegram_user_id}")
    
    # Проверка лимита анализа каналов
    # Удаленный импорт: from services.supabase_subscription_service import SupabaseSubscriptionService
    subscription_service = SupabaseSubscriptionService(supabase)
    can_analyze = await subscription_service.can_analyze_channel(int(telegram_user_id))
    if not can_analyze:
        # Здесь можно отправить уведомление в чат бота или вернуть специальное сообщение
        return JSONResponse(status_code=403, content={"error": "Достигнут лимит анализа каналов для бесплатной подписки. Оформите подписку для снятия ограничений."})
    
    # Обработка имени пользователя
    username = req.username.replace("@", "").strip()
    logger.info(f"Получен запрос на анализ канала @{username}")
    
    posts = []
    errors_list = []
    error_message = None
    
    # --- НАЧАЛО: ПОПЫТКА ПОЛУЧЕНИЯ ЧЕРЕЗ HTTP (ПЕРВЫЙ ПРИОРИТЕТ) ---
    try:
        logger.info(f"Пытаемся получить посты канала @{username} через HTTP парсинг")
        http_posts = await get_telegram_posts_via_http(username)
        
        if http_posts and len(http_posts) > 0:
            posts = [{"text": post} for post in http_posts]
            logger.info(f"Успешно получено {len(posts)} постов через HTTP парсинг")
        else:
            logger.warning(f"HTTP парсинг не вернул постов для канала @{username}, пробуем Telethon")
            errors_list.append("HTTP: Не получены посты, пробуем Telethon")
    except Exception as http_error:
        logger.error(f"Ошибка при HTTP парсинге для канала @{username}: {http_error}")
        errors_list.append(f"HTTP: {str(http_error)}")
        logger.info("Переключаемся на метод Telethon")
    
    # --- НАЧАЛО: ПОПЫТКА ПОЛУЧЕНИЯ ЧЕРЕЗ TELETHON (ВТОРОЙ ПРИОРИТЕТ) ---
    # Только если HTTP метод не дал результатов
    if not posts:
        try:
            logger.info(f"Пытаемся получить посты канала @{username} через Telethon")
            telethon_posts, telethon_error = get_telegram_posts(username)
            
            if telethon_error:
                logger.warning(f"Ошибка Telethon для канала @{username}: {telethon_error}")
                errors_list.append(f"Telethon: {telethon_error}")
            else:
                # Если Telethon успешно получил посты
                posts = telethon_posts
                logger.info(f"Успешно получено {len(posts)} постов через Telethon")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при получении постов канала @{username} через Telethon: {e}")
            errors_list.append(f"Ошибка Telethon: {str(e)}")
    
    # --- НАЧАЛО: ИСПОЛЬЗУЕМ ПРИМЕРЫ КАК ПОСЛЕДНИЙ ВАРИАНТ ---
    # Если не удалось получить посты ни через HTTP, ни через Telethon
    sample_data_used = False
    if not posts:
        logger.warning(f"Используем примеры постов для канала {username}")
        sample_posts = get_sample_posts(username)
        posts = [{"text": post} for post in sample_posts]
        error_message = "Не удалось получить реальные посты. Используются примеры для демонстрации."
        errors_list.append(error_message)
        sample_data_used = True
        logger.info(f"Используем примеры постов для канала {username}")
    
    # Ограничиваем анализ первыми 20 постами
    posts = posts[:20]
    logger.info(f"Анализируем {len(posts)} постов")
    
    # Анализ контента
    themes = []
    styles = []
    sample_posts = []
    
    try:
        # Подготовка списка текстов для анализа
        texts = [post.get("text", "") for post in posts if post.get("text")]
        
        # Анализ через deepseek
        analysis_result = await analyze_content_with_deepseek(texts, OPENROUTER_API_KEY)
        
        # Извлекаем результаты из возвращаемого словаря
        themes = analysis_result.get("themes", [])
        styles = analysis_result.get("styles", [])
        
        # Сохранение результата анализа в базе данных (если есть telegram_user_id)
        if telegram_user_id and supabase:
            try:
                # Перед сохранением результатов анализа вызываем функцию исправления схемы
                try:
                    logger.info("Вызов функции fix_schema перед сохранением результатов анализа")
                    schema_fix_result = await fix_schema()
                    logger.info(f"Результат исправления схемы: {schema_fix_result}")
                except Exception as schema_error:
                    logger.warning(f"Ошибка при исправлении схемы: {schema_error}")
                
                # Проверяем, существует ли уже запись для этого пользователя и канала
                analysis_check = supabase.table("channel_analysis").select("id").eq("user_id", telegram_user_id).eq("channel_name", username).execute()
                
                # Получение текущей даты-времени в ISO формате для updated_at
                current_datetime = datetime.now().isoformat()
                
                # Создаем словарь с данными анализа
                analysis_data = {
                    "user_id": int(telegram_user_id),  # Убедимся, что user_id - целое число
                    "channel_name": username,
                    "themes": themes,
                    "styles": styles,
                    "analyzed_posts_count": len(posts),
                    "sample_posts": sample_posts[:5] if len(sample_posts) > 5 else sample_posts,
                    "best_posting_time": "18:00 - 20:00 МСК",  # Временная заглушка
                    "is_sample_data": sample_data_used,
                    "updated_at": current_datetime
                }
                
                # Попробуем прямой SQL запрос для вставки/обновления данных, если обычный метод не сработает
                try:
                    # Если запись существует, обновляем ее, иначе создаем новую
                    if hasattr(analysis_check, 'data') and len(analysis_check.data) > 0:
                        # Обновляем существующую запись
                        result = supabase.table("channel_analysis").update(analysis_data).eq("user_id", telegram_user_id).eq("channel_name", username).execute()
                        logger.info(f"Обновлен результат анализа для канала @{username} пользователя {telegram_user_id}")
                    else:
                        # Создаем новую запись
                        result = supabase.table("channel_analysis").insert(analysis_data).execute()
                        logger.info(f"Сохранен новый результат анализа для канала @{username} пользователя {telegram_user_id}")
                except Exception as api_error:
                    logger.warning(f"Ошибка при сохранении через API: {api_error}. Пробуем прямой SQL запрос.")
                    
                    # Получаем URL и ключ Supabase
                    supabase_url = os.getenv('SUPABASE_URL')
                    supabase_key = os.getenv('SUPABASE_ANON_KEY')
                    
                    if supabase_url and supabase_key:
                        # Прямой запрос через SQL
                        url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json"
                        headers = {
                            "apikey": supabase_key,
                            "Authorization": f"Bearer {supabase_key}",
                            "Content-Type": "application/json"
                        }
                        
                        # Сериализуем JSON данные для SQL запроса
                        themes_json = json.dumps(themes)
                        styles_json = json.dumps(styles)
                        sample_posts_json = json.dumps(sample_posts[:5] if len(sample_posts) > 5 else sample_posts)
                        
                        # SQL запрос для вставки/обновления
                        sql_query = f"""
                        INSERT INTO channel_analysis 
                        (user_id, channel_name, themes, styles, analyzed_posts_count, sample_posts, best_posting_time, is_sample_data, updated_at)
                        VALUES 
                        ({telegram_user_id}, '{username}', '{themes_json}'::jsonb, '{styles_json}'::jsonb, {len(posts)}, 
                         '{sample_posts_json}'::jsonb, '18:00 - 20:00 МСК', {sample_data_used}, '{current_datetime}')
                        ON CONFLICT (user_id, channel_name) 
                        DO UPDATE SET 
                        themes = '{themes_json}'::jsonb,
                        styles = '{styles_json}'::jsonb,
                        analyzed_posts_count = {len(posts)},
                        sample_posts = '{sample_posts_json}'::jsonb,
                        best_posting_time = '18:00 - 20:00 МСК',
                        is_sample_data = {sample_data_used},
                        updated_at = '{current_datetime}';
                        """
                        
                        response = requests.post(url, json={"query": sql_query}, headers=headers)
                        
                        if response.status_code in [200, 204]:
                            logger.info(f"Результат анализа для канала @{username} сохранен через прямой SQL запрос")
                        else:
                            logger.error(f"Ошибка при выполнении прямого SQL запроса: {response.status_code} - {response.text}")
                
            except Exception as db_error:
                logger.error(f"Ошибка при сохранении результатов анализа в БД: {db_error}")
                errors_list.append(f"Ошибка БД: {str(db_error)}")
        
        # Подготовка образцов постов для ответа
        sample_texts = [post.get("text", "") for post in posts[:5] if post.get("text")]
        sample_posts = sample_texts
        
    except Exception as e:
        logger.error(f"Ошибка при анализе контента: {e}")
        # Если произошла ошибка при анализе, возвращаем ошибку 500
        raise HTTPException(status_code=500, detail=f"Ошибка при анализе контента: {str(e)}")
    
    # Временная заглушка для лучшего времени постинга
    best_posting_time = "18:00 - 20:00 МСК"
    
    # После успешного анализа:
    has_subscription = await subscription_service.has_active_subscription(int(telegram_user_id))
    if not has_subscription:
        await subscription_service.increment_analysis_usage(int(telegram_user_id))
    
    return AnalyzeResponse(
        themes=themes,
        styles=styles,
        analyzed_posts_sample=sample_posts,
        best_posting_time=best_posting_time,
        analyzed_posts_count=len(posts),
        message=error_message
    )
                
    except Exception as e:
        logger.error(f"Ошибка при генерации плана: {e}\\n{traceback.format_exc()}") # Добавляем traceback
        return AnalyzeResponse(
            message=f"Ошибка при генерации плана: {str(e)}",
            themes=[],
            styles=[],
            analyzed_posts_sample=[],
            analyzed_posts_count=0,
            error=str(e)
    )

# --- Маршрут для получения сохраненного анализа канала ---
@app.get("/channel-analysis", response_model=Dict[str, Any])
async def get_channel_analysis(request: Request, channel_name: str):
    """Получение сохраненного анализа канала."""
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
            logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
            return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})
        
        if not supabase:
            return {"error": "База данных недоступна"}
        
        # Запрос данных из базы
        result = supabase.table("channel_analysis").select("*").eq("user_id", telegram_user_id).eq("channel_name", channel_name).execute()
        
        # Проверка результата
        if not hasattr(result, 'data') or len(result.data) == 0:
            return {"error": f"Анализ для канала @{channel_name} не найден"}
        
        # Возвращаем данные
        return result.data[0]
        
    except Exception as e:
        logger.error(f"Ошибка при получении анализа канала: {e}")
        return {"error": str(e)}

# --- Маршрут для получения списка всех проанализированных каналов ---
@app.get("/analyzed-channels", response_model=List[Dict[str, Any]])
async def get_analyzed_channels(request: Request):
    """Получение списка всех проанализированных каналов пользователя."""
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
            logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
            return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})
        
        if not supabase:
            return []
        
        # Запрос данных из базы
        result = supabase.table("channel_analysis").select("channel_name,updated_at").eq("user_id", telegram_user_id).order("updated_at", desc=True).execute()
        
        # Проверка результата
        if not hasattr(result, 'data'):
            return []
        
        # Возвращаем данные
        return result.data
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка проанализированных каналов: {e}")
        return []

# --- Модель для ответа от /ideas ---
class SuggestedIdeasResponse(BaseModel):
    ideas: List[Dict[str, Any]] = []
    message: Optional[str] = None

# --- Маршрут для получения ранее сохраненных результатов анализа ---
@app.get("/ideas", response_model=SuggestedIdeasResponse)
async def get_saved_ideas(request: Request, channel_name: Optional[str] = None):
    """Получение ранее сохраненных результатов анализа."""
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос идей без идентификации пользователя Telegram")
            return SuggestedIdeasResponse(
                message="Для доступа к идеям необходимо авторизоваться через Telegram",
                ideas=[]
            )
        
        # Преобразуем ID пользователя в число
        try:
            telegram_user_id = int(telegram_user_id)
        except (ValueError, TypeError):
            logger.error(f"Некорректный ID пользователя в заголовке: {telegram_user_id}")
            return SuggestedIdeasResponse(
                message="Некорректный ID пользователя",
                ideas=[]
            )
        
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            return SuggestedIdeasResponse(
                message="Ошибка: не удалось подключиться к базе данных",
                ideas=[]
            )
        
        # Строим запрос к базе данных
        query = supabase.table("suggested_ideas").select("*").eq("user_id", telegram_user_id)
        
        # Если указано имя канала, фильтруем по нему
        if channel_name:
            query = query.eq("channel_name", channel_name)
            
        # Выполняем запрос
        result = query.order("created_at", desc=True).execute()
        
        # Обрабатываем результат
        if not hasattr(result, 'data'):
            logger.error(f"Ошибка при получении идей из БД: {result}")
            return SuggestedIdeasResponse(
                message="Не удалось получить сохраненные идеи",
                ideas=[]
            )
            
        # === ИЗМЕНЕНИЕ: Корректное формирование ответа ===
        ideas = []
        for item in result.data:
            # Просто берем нужные поля напрямую из ответа БД
            idea = {
                "id": item.get("id"),
                "channel_name": item.get("channel_name"),
                "topic_idea": item.get("topic_idea"),  # Берем напрямую
                "format_style": item.get("format_style"),  # Берем напрямую
                "relative_day": item.get("relative_day"),
                "is_detailed": item.get("is_detailed"),
                "created_at": item.get("created_at")
                # Убрана ненужная обработка themes_json/styles_json
            }
            # Добавляем только если есть тема
            if idea["topic_idea"]:
                ideas.append(idea)
            else:
                logger.warning(f"Пропущена идея без topic_idea: ID={idea.get('id', 'N/A')}")  # Добавил .get для безопасности
        # === КОНЕЦ ИЗМЕНЕНИЯ ===
                
        logger.info(f"Получено {len(ideas)} идей для пользователя {telegram_user_id}")
        return SuggestedIdeasResponse(ideas=ideas)
        
    except Exception as e:
        logger.error(f"Ошибка при получении идей: {e}")
        return SuggestedIdeasResponse(
            message=f"Ошибка при получении идей: {str(e)}",
            ideas=[]
        )

# --- Модель ответа для генерации плана ---
class PlanGenerationResponse(BaseModel):
    plan: List[PlanItem] = []
    message: Optional[str] = None

# Функция для очистки текста от маркеров форматирования
def clean_text_formatting(text):
    """Очищает текст от форматирования маркдауна, эмодзи, буллетов и лишних символов."""
    import re
    if not text:
        return ""
    # Удаляем заголовки типа "### **День 1**", "### **1 день**", "### **ДЕНЬ 1**" и другие вариации
    text = re.sub(r'#{1,6}\s*\*?\*?(?:[Дд]ень|ДЕНЬ)?\s*\d+\s*(?:[Дд]ень|ДЕНЬ)?\*?\*?', '', text)
    # Удаляем числа и слово "день" в начале строки (без символов #)
    text = re.sub(r'^(?:\*?\*?(?:[Дд]ень|ДЕНЬ)?\s*\d+\s*(?:[Дд]ень|ДЕНЬ)?\*?\*?)', '', text)
    # Удаляем символы маркдауна, кавычки, буллеты, эмодзи и спецсимволы
    text = re.sub(r'[\*\_\#\-\•\»\“\”\"\'\`\|\[\]\{\}\(\)\^\~\=\+\<\>\u2022\u25CF\u25A0\u25B6\u25C6\u2605\uFE0F\u200D\u23F3\u23F0\u231A\u231B\u23F1\u23F2\u23F3\u23F4\u23F5\u23F6\u23F7\u23F8\u23F9\u23FA\u23FB\u23FC\u23FD\u23FE\u23FF]', '', text)
    # Удаляем emoji (базово)
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]', '', text)
    # Удаляем буллеты и точки в начале строки
    text = re.sub(r'^[\s\u2022\u25CF\u25A0\u25B6\u25C6\-]+', '', text, flags=re.MULTILINE)
    # Очищаем начальные и конечные пробелы
    text = text.strip()
    # Делаем первую букву заглавной, если строка не пустая
    if text and len(text) > 0:
        text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
    return text

# --- Маршрут для генерации плана публикаций ---
@app.post("/generate-plan", response_model=PlanGenerationResponse)
async def generate_content_plan(request: Request, req: PlanGenerationRequest):
    """Генерация и сохранение плана контента на основе тем и стилей."""
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
            logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
            return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})
            
        themes = req.themes
        styles = req.styles
        period_days = req.period_days
        channel_name = req.channel_name
        
        if not themes or not styles:
            logger.warning(f"Запрос с пустыми темами или стилями: themes={themes}, styles={styles}")
            return PlanGenerationResponse(
                message="Необходимо указать темы и стили для генерации плана",
                plan=[]
            )
            
        # Проверяем наличие API ключа
        if not OPENROUTER_API_KEY:
            logger.warning("Генерация плана невозможна: отсутствует OPENROUTER_API_KEY")
            # Генерируем простой план без использования API
            plan_items = []
            for day in range(1, period_days + 1):
                random_theme = random.choice(themes)
                random_style = random.choice(styles)
                plan_items.append(PlanItem(
                    day=day,
                    topic_idea=f"Пост о {random_theme}",
                    format_style=random_style
                ))
            logger.info(f"Создан базовый план из {len(plan_items)} идей (без использования API)")
            return PlanGenerationResponse(
                plan=plan_items,
                message="План сгенерирован с базовыми идеями (API недоступен)"
            )
            
        # --- ИЗМЕНЕНИЕ НАЧАЛО: Уточненные промпты --> ЕЩЕ БОЛЕЕ СТРОГИЙ ПРОМПТ ---
        system_prompt = f"""Ты - опытный контент-маркетолог. Твоя задача - сгенерировать план публикаций для Telegram-канала на {period_days} дней.
Используй предоставленные темы и стили.

Темы: {', '.join(themes)}
Стили (используй ТОЛЬКО их): {', '.join(styles)}

Для КАЖДОГО дня из {period_days} дней предложи ТОЛЬКО ОДНУ идею поста (конкретный заголовок/концепцию) и выбери ТОЛЬКО ОДИН стиль из списка выше.

СТРОГО СЛЕДУЙ ФОРМАТУ ВЫВОДА:
Каждая строка должна содержать только день, идею и стиль, разделенные ДВУМЯ двоеточиями (::).
НЕ ДОБАВЛЯЙ НИКАКИХ ЗАГОЛОВКОВ, НОМЕРОВ ВЕРСИЙ, СПИСКОВ ФИЧ, КОММЕНТАРИЕВ ИЛИ ЛЮБОГО ДРУГОГО ЛИШНЕГО ТЕКСТА.
Только строки плана.

Пример НУЖНОГО формата:
День 1:: Запуск нового продукта X:: Анонс
День 2:: Советы по использованию Y:: Лайфхак
День 3:: Интервью с экспертом Z:: Интервью

Формат КАЖДОЙ строки: День <номер_дня>:: <Идея поста>:: <Стиль из списка>"""

        user_prompt = f"""Сгенерируй план контента для Telegram-канала \"{channel_name}\" на {period_days} дней.
Темы: {', '.join(themes)}
Стили (используй ТОЛЬКО их): {', '.join(styles)}

Выдай ровно {period_days} строк СТРОГО в формате:
День <номер_дня>:: <Идея поста>:: <Стиль из списка>

Не включай ничего, кроме этих строк."""
        # --- ИЗМЕНЕНИЕ КОНЕЦ ---

        # Настройка клиента OpenAI для использования OpenRouter
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        
        # Запрос к API
        logger.info(f"Отправка запроса на генерацию плана контента для канала @{channel_name} с уточненным промптом")
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free", # <--- ИЗМЕНЕНО НА НОВУЮ БЕСПЛАТНУЮ МОДЕЛЬ
            messages=[
                # {"role": "system", "content": system_prompt}, # Системный промпт может конфликтовать с некоторыми моделями, тестируем без него или с ним
                {"role": "user", "content": user_prompt} # Помещаем все инструкции в user_prompt
            ],
            temperature=0.7, # Немного снижаем температуру для строгости формата
            max_tokens=150 * period_days, # Примерно 150 токенов на идею
            timeout=120,
            extra_headers={
                "HTTP-Referer": "https://content-manager.onrender.com",
                "X-Title": "Smart Content Assistant"
            }
        )
        
        # === НАЧАЛО ИЗМЕНЕНИЯ: Проверка ответа API ===
        plan_text = ""
        if response and response.choices and len(response.choices) > 0 and response.choices[0].message and response.choices[0].message.content:
            plan_text = response.choices[0].message.content.strip()
            logger.info(f"Получен ответ с планом публикаций (первые 100 символов): {plan_text[:100]}...")
        else:
            # Логируем полный ответ, если структура неожиданная
            logger.error(f"Некорректный или пустой ответ от OpenRouter API при генерации плана. Status: {response.response.status_code if hasattr(response, 'response') else 'N/A'}")
            try:
                # Попробуем залогировать тело ответа, если оно есть
                raw_response_content = await response.response.text() if hasattr(response, 'response') and hasattr(response.response, 'text') else str(response)
                logger.error(f"Полный ответ API (или его представление): {raw_response_content}")
            except Exception as log_err:
                logger.error(f"Не удалось залогировать тело ответа API: {log_err}")
                
            # Возвращаем пустой план с сообщением об ошибке
            return PlanGenerationResponse(
                plan=[],
                message="Ошибка: API не вернул ожидаемый результат для генерации плана."
            )
        # === КОНЕЦ ИЗМЕНЕНИЯ ===
        
        plan_items = []
        lines = plan_text.split('\n')

        # --- ИЗМЕНЕНИЕ НАЧАЛО: Улучшенный парсинг с новым разделителем ---
        expected_style_set = set(s.lower() for s in styles) # Для быстрой проверки
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            parts = line.split('::')
            if len(parts) == 3:
                # === ИСПРАВЛЕНО: Выровнен отступ для try ===
                try:
                    day_part = parts[0].lower().replace('день', '').strip()
                    day = int(day_part)
                    topic_idea = clean_text_formatting(parts[1].strip())
                    format_style = clean_text_formatting(parts[2].strip())

                    # Проверяем, входит ли стиль в запрошенный список (без учета регистра)
                    if format_style.lower() not in expected_style_set:
                        logger.warning(f"Стиль '{format_style}' из ответа LLM не найден в запрошенных стилях. Выбираем случайный.")
                        format_style = random.choice(styles) if styles else "Без указания стиля"

                    if topic_idea: # Пропускаем, если тема пустая
                        plan_items.append(PlanItem(
                            day=day,
                            topic_idea=topic_idea,
                            format_style=format_style
                        ))
                    else:
                        logger.warning(f"Пропущена строка плана из-за пустой темы после очистки: {line}")
                # === ИСПРАВЛЕНО: Выровнен отступ для except ===
                except ValueError:
                    logger.warning(f"Не удалось извлечь номер дня из строки плана: {line}")
                except Exception as parse_err:
                    logger.warning(f"Ошибка парсинга строки плана '{line}': {parse_err}")
            # === ИСПРАВЛЕНО: Выровнен отступ для else ===
            else:
                logger.warning(f"Строка плана не соответствует формату 'День X:: Тема:: Стиль': {line}")
        # --- ИЗМЕНЕНИЕ КОНЕЦ ---

        # ... (остальная логика обработки plan_items: сортировка, дополнение, проверка пустого плана) ...
        # Если и сейчас нет идей, генерируем вручную
        if not plan_items:
            logger.warning("Не удалось извлечь идеи из ответа LLM или все строки были некорректными, генерируем базовый план.")
            for day in range(1, period_days + 1):
                random_theme = random.choice(themes) if themes else "Общая тема"
                random_style = random.choice(styles) if styles else "Общий стиль"
                # === ИЗМЕНЕНИЕ: Убираем 'Пост о' ===
                fallback_topic = f"{random_theme} ({random_style})"
                plan_items.append(PlanItem(
                    day=day,
                    topic_idea=fallback_topic, # <--- Используем новую строку
                    format_style=random_style
                ))
        
        # Сортируем по дням
        plan_items.sort(key=lambda x: x.day)
        
        # Обрезаем до запрошенного количества дней (на случай, если LLM выдал больше)
        plan_items = plan_items[:period_days]
        
        # Если план получился короче запрошенного периода, дополняем (возможно, из-за ошибок парсинга)
        if len(plan_items) < period_days:
            existing_days = {item.day for item in plan_items}
            needed_days = period_days - len(plan_items)
            logger.warning(f"План короче запрошенного ({len(plan_items)}/{period_days}), дополняем {needed_days} идеями.")
            start_day = max(existing_days) + 1 if existing_days else 1
            for i in range(needed_days):
                current_day = start_day + i
                if current_day not in existing_days:
                    random_theme = random.choice(themes) if themes else "Дополнительная тема"
                    random_style = random.choice(styles) if styles else "Дополнительный стиль"
                    # === ИЗМЕНЕНИЕ: Убираем 'Пост о' и '(Дополнено)' ===
                    fallback_topic = f"{random_theme} ({random_style})"
                    plan_items.append(PlanItem(
                        day=current_day,
                        topic_idea=fallback_topic, # <--- Используем новую строку
                        format_style=random_style
                    ))
        
            # Сортируем по дням еще раз после возможного дополнения
            plan_items.sort(key=lambda x: x.day)
        
        logger.info(f"Сгенерирован и обработан план из {len(plan_items)} идей для канала @{channel_name}")
        return PlanGenerationResponse(plan=plan_items)
                
    except Exception as e:
        logger.error(f"Ошибка при генерации плана: {e}\\n{traceback.format_exc()}") # Добавляем traceback
        return PlanGenerationResponse(
            message=f"Ошибка при генерации плана: {str(e)}",
            plan=[]
        )

# --- Настройка обработки корневого маршрута для обслуживания статических файлов ---
@app.get("/")
async def root():
    """Обслуживание корневого маршрута - возвращает index.html"""
    if SHOULD_MOUNT_STATIC:
        return FileResponse(os.path.join(static_folder, "index.html"))
    else:
        return {"message": "API работает, но статические файлы не настроены. Обратитесь к API напрямую."}

# --- ДОБАВЛЯЕМ API ЭНДПОИНТЫ ДЛЯ РАБОТЫ С ПОСТАМИ ---
@app.get("/posts", response_model=List[SavedPostResponse])
async def get_posts(request: Request, channel_name: Optional[str] = None):
    """Получение сохраненных постов."""
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос постов без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для доступа к постам необходимо авторизоваться через Telegram")
        
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        
        # Строим запрос к базе данных
        query = supabase.table("saved_posts").select("*").eq("user_id", telegram_user_id)
        
        # Если указано имя канала, фильтруем по нему
        if channel_name:
            query = query.eq("channel_name", channel_name)
            
        # Выполняем запрос
        result = query.order("target_date", desc=True).execute()
        
        # Проверка результата
        if not hasattr(result, 'data'):
            logger.error(f"Ошибка при получении постов из БД: {result}")
            return []
            
        # === ИЗМЕНЕНИЕ: Запрос для получения связанных изображений ===
        # Строим запрос к базе данных, запрашивая связанные данные из saved_images
        # Обратите внимание: имя таблицы saved_images используется как имя связи
        query = supabase.table("saved_posts").select(
            "*, saved_images(*)" # <--- Запрашиваем все поля поста и все поля связанного изображения
        ).eq("user_id", int(telegram_user_id))
        # === КОНЕЦ ИЗМЕНЕНИЯ ===
        
        # Если указано имя канала, фильтруем по нему
        if channel_name:
            query = query.eq("channel_name", channel_name)
            
        # Выполняем запрос
        result = query.order("target_date", desc=True).execute()
        
        # Проверка результата
        if not hasattr(result, 'data'):
            logger.error(f"Ошибка при получении постов из БД: {result}")
            return []
            
        # === ИЗМЕНЕНИЕ: Обработка ответа для включения данных изображения ===
        posts_with_images = []
        for post_data in result.data:
            # Создаем объект SavedPostResponse из основных данных поста
            response_item = SavedPostResponse(**post_data)
            
            # Проверяем, есть ли связанные данные изображения и они не пустые
            image_relation_data = post_data.get("saved_images")
            
            # === ИЗМЕНЕНО: Логирование на уровне INFO ===
            logger.info(f"Обработка поста ID: {response_item.id}. Связанные данные изображения: {image_relation_data}")
            # === КОНЕЦ ИЗМЕНЕНИЯ ===
            
            if image_relation_data and isinstance(image_relation_data, dict):
                # Создаем объект PostImage из данных saved_images
                # Убедимся, что ключи соответствуют модели PostImage
                try:
                    # --- ИЗМЕНЕНИЕ: Приоритет alt_description, затем alt ---
                    alt_text = image_relation_data.get("alt_description") or image_relation_data.get("alt")
                    # --- КОНЕЦ ИЗМЕНЕНИЯ ---
                    response_item.selected_image_data = PostImage(
                        id=image_relation_data.get("id"),
                        url=image_relation_data.get("url"),
                        preview_url=image_relation_data.get("preview_url"),
                        alt=alt_text, # <--- Используем подготовленный alt_text
                        author=image_relation_data.get("author"), # В saved_images это 'author'
                        author_url=image_relation_data.get("author_url"),
                        source=image_relation_data.get("source")
                    )
                    # === ИЗМЕНЕНО: Логирование на уровне INFO ===
                    logger.info(f"Успешно создано selected_image_data для поста {response_item.id} с изображением ID: {response_item.selected_image_data.id}")
                    # === КОНЕЦ ИЗМЕНЕНИЯ ===
                except Exception as mapping_error:
                     logger.error(f"Ошибка при создании PostImage для поста {response_item.id}: {mapping_error}")
                     logger.error(f"Данные изображения: {image_relation_data}")
                     response_item.selected_image_data = None # Очищаем при ошибке
            else:
                # Если ключ 'saved_images' отсутствует или пуст, selected_image_data остается None
                response_item.selected_image_data = None
                # Логируем, если ожидали изображение (т.е. saved_image_id не None), но его нет
                if post_data.get("saved_image_id"):
                    logger.warning(f"Для поста {post_data['id']} есть saved_image_id, но связанные данные изображения не были получены или пусты. Связанные данные: {image_relation_data}")


            posts_with_images.append(response_item)
            
        return posts_with_images
        # === КОНЕЦ ИЗМЕНЕНИЯ ===
        
    except Exception as e:
        logger.error(f"Ошибка при получении постов: {e}")
        # === ДОБАВЛЕНО: Перевыброс HTTPException для корректного ответа ===
        raise HTTPException(status_code=500, detail=str(e))
        # === КОНЕЦ ДОБАВЛЕНИЯ ===

@app.post("/posts", response_model=SavedPostResponse)
async def create_post(request: Request, post_data: PostData):
    """Создание нового поста."""
    try:
        # === ДОБАВЛЕНО: Принудительное обновление схемы перед операцией ===
        try:
            logger.info("Вызов fix_schema перед созданием поста...")
            fix_result = await fix_schema()
            if not fix_result.get("success"):
                logger.warning(f"Не удалось обновить/проверить схему перед созданием поста: {fix_result}")
                # Можно решить, прерывать ли операцию или нет. Пока продолжаем.
            else:
                logger.info("Проверка/обновление схемы перед созданием поста завершена успешно.")
        except Exception as pre_save_fix_err:
            logger.error(f"Ошибка при вызове fix_schema перед созданием поста: {pre_save_fix_err}", exc_info=True)
            # Продолжаем, но логируем ошибку
        # === КОНЕЦ ДОБАВЛЕНИЯ ===

        # === ДОБАВЛЕНО: Пауза после обновления схемы ===
        logger.info("Небольшая пауза после fix_schema, чтобы дать PostgREST время...")
        await asyncio.sleep(0.7) # Пауза 0.7 секунды
        # === КОНЕЦ ДОБАВЛЕНИЯ ===

        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос создания поста без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для создания поста необходимо авторизоваться через Telegram")
        
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        
        # Извлекаем данные изображения отдельно
        selected_image = post_data.selected_image_data
        
        # Создаем словарь с основными данными поста для сохранения
        post_to_save = post_data.dict(exclude={"selected_image_data"}) # Исключаем объект изображения
        post_to_save["user_id"] = int(telegram_user_id)
        post_to_save["id"] = str(uuid.uuid4()) # Генерируем ID для нового поста
        
        # === ДОБАВЛЕНО: Обработка target_date ===
        if not post_to_save.get("target_date"):
            logger.warning(f"Получена пустая target_date для нового поста {post_to_save['id']}, устанавливаем в NULL.")
            post_to_save["target_date"] = None
        else:
            # Дополнительно можно добавить валидацию формата YYYY-MM-DD, если нужно
            try:
                datetime.strptime(post_to_save["target_date"], '%Y-%m-%d')
            except ValueError:
                logger.error(f"Некорректный формат target_date: {post_to_save['target_date']} для поста {post_to_save['id']}. Устанавливаем в NULL.")
                post_to_save["target_date"] = None
        # === КОНЕЦ ДОБАВЛЕНИЯ ===
        
        # --- НАЧАЛО: Обработка выбранного изображения --- 
        saved_image_id = None
        if selected_image:
            try:
                # --- УДАЛЕНО: Проверка наличия колонки external_id --- 

                # Проверяем, существует ли изображение с таким URL (более надежно)
                image_check = None
                if selected_image.url:
                    image_check_result = supabase.table("saved_images").select("id").eq("url", selected_image.url).limit(1).execute()
                    if hasattr(image_check_result, 'data') and len(image_check_result.data) > 0:
                        image_check = image_check_result.data[0]
                # --- КОНЕЦ ПРОВЕРКИ ПО URL ---

                if image_check:
                    # Изображение уже существует, используем его ID (UUID)
                    saved_image_id = image_check["id"]
                    logger.info(f"Используем существующее изображение {saved_image_id} (URL: {selected_image.url}) для поста")
                else:
                    # Изображение не найдено, сохраняем новое
                    # ГЕНЕРИРУЕМ НОВЫЙ UUID для нашей БД
                    new_internal_id = str(uuid.uuid4()) 
                    # --- УДАЛЕНО: Логика с external_id --- 
                    
                    image_data_to_save = {
                        "id": new_internal_id, # Используем наш UUID
                        "url": selected_image.url,
                        "preview_url": selected_image.preview_url or selected_image.url,
                        "alt": selected_image.alt or "",
                        "author": selected_image.author or "", # Соответствует 'author' в PostImage
                        "author_url": selected_image.author_url or "",
                        "source": selected_image.source or "frontend_selection",
                        "user_id": int(telegram_user_id),
                        # --- УДАЛЕНО: external_id ---
                    }
                    
                    image_result = supabase.table("saved_images").insert(image_data_to_save).execute()
                    if hasattr(image_result, 'data') and len(image_result.data) > 0:
                        saved_image_id = new_internal_id # Используем наш ID для связи
                        logger.info(f"Сохранено новое изображение {saved_image_id} для поста")
                    else:
                        logger.error(f"Ошибка при сохранении нового изображения: {image_result}")
                        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении нового изображения: {getattr(image_result, 'error', 'Unknown error')}")
            except Exception as img_err:
                logger.error(f"Ошибка при обработке/сохранении изображения: {img_err}")
                raise HTTPException(status_code=500, detail=f"Ошибка при обработке/сохранении изображения: {str(img_err)}")
        # --- КОНЕЦ: Обработка выбранного изображения --- 

        # Удаляем старые поля из данных для сохранения поста
        post_to_save.pop('image_url', None)
        post_to_save.pop('images_ids', None)
        
        # === ИЗМЕНЕНИЕ НАЧАЛО ===
        # Добавляем ID сохраненного изображения в данные поста
        post_to_save["saved_image_id"] = saved_image_id
        # === ИЗМЕНЕНИЕ КОНЕЦ ===
        
        # === ИЗМЕНЕНИЕ НАЧАЛО: Логирование данных перед сохранением ===
        logger.info(f"Подготовлены данные для сохранения в saved_posts: {post_to_save}")
        # === КОНЕЦ ДОБАВЛЕНИЯ ===

        # === ИЗМЕНЕНО: Убран механизм ретрая ===
        try:
            logger.info(f"Выполняем insert в saved_posts для ID {post_to_save['id']}...")
            # === ИСПРАВЛЕНО: Выровнен отступ ===
            result = supabase.table("saved_posts").insert(post_to_save).execute()
            logger.info(f"Insert выполнен. Status: {result.status_code if hasattr(result, 'status_code') else 'N/A'}")
        except APIError as e:
            logger.error(f"Ошибка APIError при insert в saved_posts: {e}")
            # Перехватываем и логируем, чтобы увидеть детали перед 500 ошибкой
            raise HTTPException(status_code=500, detail=f"Ошибка БД при создании поста: {e.message}")
        except Exception as general_e:
            logger.error(f"Непредвиденная ошибка при insert в saved_posts: {general_e}")
            raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка БД при создании поста: {str(general_e)}")
        
        # === ИЗМЕНЕНО: Убран лишний отступ ===
        # Проверка результата
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.error(f"Ошибка при сохранении поста {post_to_save['id']}: Ответ Supabase пуст или не содержит данных.")
            last_error_details = f"Status: {result.status_code if hasattr(result, 'status_code') else 'N/A'}"
            raise HTTPException(status_code=500, detail=f"Не удалось сохранить пост. {last_error_details}")
        # === КОНЕЦ ИЗМЕНЕНИЯ ===

        created_post = result.data[0]
        post_id = created_post["id"]
        
        logger.info(f"Пользователь {telegram_user_id} создал пост: {post_data.topic_idea}")
        
        # Возвращаем данные созданного поста, обогащенные данными изображения
        response_data = SavedPostResponse(**created_post)
        if saved_image_id and selected_image: # Если было выбрано и сохранено/найдено изображение
             response_data.selected_image_data = selected_image # Возвращаем исходные данные изображения
        elif saved_image_id: # Если изображение было найдено, но не передано (маловероятно, но на всякий случай)
             # Пытаемся получить данные изображения из БД
             img_data_res = supabase.table("saved_images").select("id, url, preview_url, alt, author, author_url, source").eq("id", saved_image_id).maybe_single().execute()
             if img_data_res.data:
                  response_data.selected_image_data = PostImage(**img_data_res.data)

        return response_data
        
    except HTTPException as http_err:
        # Перехватываем HTTP исключения, чтобы не попасть в общий Exception
        raise http_err
    except Exception as e:
        logger.error(f"Ошибка при создании поста: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера при создании поста: {str(e)}")

@app.put("/posts/{post_id}", response_model=SavedPostResponse)
async def update_post(post_id: str, request: Request, post_data: PostData):
    """Обновление существующего поста."""
    try:
        # === ДОБАВЛЕНО: Принудительное обновление схемы перед операцией ===
        try:
            logger.info(f"Вызов fix_schema перед обновлением поста {post_id}...")
            fix_result = await fix_schema()
            if not fix_result.get("success"):
                logger.warning(f"Не удалось обновить/проверить схему перед обновлением поста {post_id}: {fix_result}")
            else:
                logger.info(f"Проверка/обновление схемы перед обновлением поста {post_id} завершена успешно.")
        except Exception as pre_update_fix_err:
            logger.error(f"Ошибка при вызове fix_schema перед обновлением поста {post_id}: {pre_update_fix_err}", exc_info=True)
        # === КОНЕЦ ДОБАВЛЕНИЯ ===

        # === ДОБАВЛЕНО: Пауза после обновления схемы ===
        logger.info(f"Небольшая пауза после fix_schema для поста {post_id}, чтобы дать PostgREST время...")
        await asyncio.sleep(0.7) # Пауза 0.7 секунды
        # === КОНЕЦ ДОБАВЛЕНИЯ ===

        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос обновления поста без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для обновления поста необходимо авторизоваться через Telegram")
        
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        
        # Проверяем, что пост принадлежит пользователю
        post_check = supabase.table("saved_posts").select("id").eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
        if not hasattr(post_check, 'data') or len(post_check.data) == 0:
            logger.warning(f"Попытка обновить чужой или несуществующий пост: {post_id}")
            raise HTTPException(status_code=404, detail="Пост не найден или нет прав на его редактирование")
        
        # === ИЗМЕНЕНИЕ ЛОГИКИ ОБРАБОТКИ ИЗОБРАЖЕНИЯ ===
        # Используем getattr для безопасного доступа, на случай если поле отсутствует в запросе
        selected_image = getattr(post_data, 'selected_image_data', None)
        # Флаг, указывающий, было ли поле selected_image_data *явно* передано в запросе
        image_field_provided_in_request = hasattr(post_data, 'selected_image_data')

        # Переменная для хранения ID изображения, которое нужно сохранить в посте
        # Изначально None, изменится только если изображение предоставлено
        image_id_to_set_in_post = None
        image_processed = False # Флаг, что мы обработали данные изображения из запроса

        if image_field_provided_in_request:
            image_processed = True # Отмечаем, что данные изображения были в запросе
            if selected_image: # Если изображение передано и оно не None/пустое
                try:
                    # Проверяем, существует ли изображение с таким URL
                    image_check = None
                    if selected_image.url:
                        image_check_result = supabase.table("saved_images").select("id").eq("url", selected_image.url).limit(1).execute()
                        if hasattr(image_check_result, 'data') and len(image_check_result.data) > 0:
                            image_check = image_check_result.data[0]

                    if image_check:
                        image_id_to_set_in_post = image_check["id"]
                        logger.info(f"Используем существующее изображение {image_id_to_set_in_post} для обновления поста {post_id}")
                    else:
                        # Сохраняем новое изображение
                        new_internal_id = str(uuid.uuid4())
                        image_data_to_save = {
                            "id": new_internal_id,
                            "url": selected_image.url,
                            "preview_url": selected_image.preview_url or selected_image.url,
                            "alt": selected_image.alt or "",
                            "author": selected_image.author or "",
                            "author_url": selected_image.author_url or "",
                            "source": selected_image.source or "frontend_selection",
                            "user_id": int(telegram_user_id),
                        }
                        image_result = supabase.table("saved_images").insert(image_data_to_save).execute()
                        if hasattr(image_result, 'data') and len(image_result.data) > 0:
                            image_id_to_set_in_post = new_internal_id
                            logger.info(f"Сохранено новое изображение {image_id_to_set_in_post} для обновления поста {post_id}")
                        else:
                            logger.error(f"Ошибка при сохранении нового изображения при обновлении поста: {image_result}")
                            raise HTTPException(status_code=500, detail=f"Ошибка при сохранении нового изображения: {getattr(image_result, 'error', 'Unknown error')}")
                except Exception as img_err:
                    logger.error(f"Ошибка при обработке/сохранении изображения при обновлении поста: {img_err}")
                    raise HTTPException(status_code=500, detail=f"Ошибка при обработке/сохранении изображения: {str(img_err)}")
            else: # Если selected_image_data передан как null или пустой объект
                image_id_to_set_in_post = None # Явно указываем, что связь нужно удалить
                logger.info(f"В запросе на обновление поста {post_id} передано пустое изображение (None/null). Связь будет очищена.")
        # Если image_field_provided_in_request == False, то image_processed остается False,
        # и мы НЕ будем обновлять поле saved_image_id в post_to_update далее.

        # Создаем словарь с основными данными поста для обновления
        # Исключаем selected_image_data, т.к. его не нужно писать в saved_posts
        post_to_update = post_data.dict(exclude={"selected_image_data", "image_url", "images_ids"})
        post_to_update["updated_at"] = datetime.now().isoformat()

        # Обработка target_date (остается как было)
        if "target_date" in post_to_update and not post_to_update.get("target_date"):
            logger.warning(f"Получена пустая target_date при обновлении поста {post_id}, устанавливаем в NULL.")
            post_to_update["target_date"] = None
        elif post_to_update.get("target_date"):
            try:
                datetime.strptime(post_to_update["target_date"], '%Y-%m-%d')
            except ValueError:
                logger.error(f"Некорректный формат target_date: {post_to_update['target_date']} при обновлении поста {post_id}. Устанавливаем в NULL.")
                post_to_update["target_date"] = None

        # Обновляем saved_image_id ТОЛЬКО если поле selected_image_data было явно передано в запросе
        if image_processed:
            # Обновляем поле saved_image_id значением, полученным при обработке изображения
            # Если было передано пустое изображение, image_id_to_set_in_post будет None, и связь очистится
            post_to_update["saved_image_id"] = image_id_to_set_in_post
            logger.info(f"Поле saved_image_id для поста {post_id} будет обновлено на: {image_id_to_set_in_post}")
        else:
            # Если поле selected_image_data НЕ БЫЛО передано в запросе,
            # НЕ трогаем поле saved_image_id в post_to_update.
            # Убедимся, что его точно нет в словаре для обновления, чтобы не затереть существующее значение в БД.
            post_to_update.pop("saved_image_id", None)
            logger.info(f"Поле selected_image_data не предоставлено в запросе на обновление поста {post_id}. Поле saved_image_id не будет изменено.")

        # Логирование данных перед сохранением
        logger.info(f"Подготовлены данные для обновления в saved_posts: {post_to_update}")

        # Выполнение UPDATE запроса
        try:
            logger.info(f"Выполняем update в saved_posts для ID {post_id}...")
            result = supabase.table("saved_posts").update(post_to_update).eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
            logger.info(f"Update выполнен. Status: {result.status_code if hasattr(result, 'status_code') else 'N/A'}")
        except APIError as e:
            logger.error(f"Ошибка APIError при update в saved_posts для ID {post_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка БД при обновлении поста: {e.message}")
        except Exception as general_e:
            logger.error(f"Непредвиденная ошибка при update в saved_posts для ID {post_id}: {general_e}")
            raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка БД при обновлении поста: {str(general_e)}")
        
        # Проверка результата
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.error(f"Ошибка при обновлении поста {post_id}: Ответ Supabase пуст или не содержит данных.")
            last_error_details = f"Status: {result.status_code if hasattr(result, 'status_code') else 'N/A'}"
            raise HTTPException(status_code=500, detail=f"Не удалось обновить пост. {last_error_details}")

        updated_post = result.data[0]
        logger.info(f"Пользователь {telegram_user_id} обновил пост: {post_id}")

        # Возвращаем данные обновленного поста, обогащенные АКТУАЛЬНЫМИ данными изображения
        response_data = SavedPostResponse(**updated_post)
        # Получаем ID изображения из обновленного поста (updated_post),
        # так как оно могло измениться или остаться прежним
        final_image_id = updated_post.get("saved_image_id")

        if final_image_id:
            # Если ID есть, пытаемся получить данные изображения из БД
            img_data_res = supabase.table("saved_images").select("id, url, preview_url, alt, author, author_url, source").eq("id", final_image_id).maybe_single().execute()
            if img_data_res.data:
                 try: # Добавляем try-except для маппинга
                     alt_text = img_data_res.data.get("alt_description") or img_data_res.data.get("alt")
                     response_data.selected_image_data = PostImage(
                          id=img_data_res.data.get("id"),
                          url=img_data_res.data.get("url"),
                          preview_url=img_data_res.data.get("preview_url"),
                          alt=alt_text,
                          author=img_data_res.data.get("author"),
                          author_url=img_data_res.data.get("author_url"),
                          source=img_data_res.data.get("source")
                     )
                 except Exception as mapping_err:
                     logger.error(f"Ошибка при маппинге данных изображения из БД для обновленного поста {post_id}: {mapping_err}")
                     response_data.selected_image_data = None
            else:
                 logger.warning(f"Не удалось получить данные изображения {final_image_id} из БД для ответа на обновление поста {post_id}")
                 response_data.selected_image_data = None
        else:
            # Если final_image_id отсутствует в обновленном посте, selected_image_data остается None
            response_data.selected_image_data = None

        return response_data

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"Ошибка при обновлении поста {post_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера при обновлении поста: {str(e)}")

@app.delete("/posts/{post_id}")
async def delete_post(post_id: str, request: Request):
    """Удаление поста."""
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос удаления поста без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для удаления поста необходимо авторизоваться через Telegram")
        
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        
        # Проверяем, что пост принадлежит пользователю
        post_check = supabase.table("saved_posts").select("id").eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
        if not hasattr(post_check, 'data') or len(post_check.data) == 0:
            logger.warning(f"Попытка удалить чужой или несуществующий пост: {post_id}")
            raise HTTPException(status_code=404, detail="Пост не найден или нет прав на его удаление")
        
        # --- ДОБАВЛЕНО: Удаление связей перед удалением поста --- 
        try:
            delete_links_res = supabase.table("post_images").delete().eq("post_id", post_id).execute()
            logger.info(f"Удалено {len(delete_links_res.data) if hasattr(delete_links_res, 'data') else 0} связей для удаляемого поста {post_id}")
        except Exception as del_link_err:
            logger.error(f"Ошибка при удалении связей post_images для поста {post_id} перед удалением поста: {del_link_err}")
            # Продолжаем удаление поста, но логируем ошибку
        # --- КОНЕЦ ДОБАВЛЕНИЯ ---
        
        # Удаление из Supabase
        result = supabase.table("saved_posts").delete().eq("id", post_id).execute()
        
        # Проверка результата
        if not hasattr(result, 'data'):
            logger.error(f"Ошибка при удалении поста: {result}")
            raise HTTPException(status_code=500, detail="Ошибка при удалении поста")
            
        logger.info(f"Пользователь {telegram_user_id} удалил пост {post_id}")
        return {"message": "Пост успешно удален"}
        
    except HTTPException as http_err:
        # Перехватываем HTTP исключения
        raise http_err
    except Exception as e:
        logger.error(f"Ошибка при удалении поста: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера при удалении поста: {str(e)}")

# --- Настраиваем обработку всех путей SPA для обслуживания статических файлов (в конце файла) ---
@app.get("/{rest_of_path:path}")
async def serve_spa(rest_of_path: str):
    """Обслуживает все запросы к путям SPA, возвращая index.html"""
    # Проверяем, есть ли запрошенный файл
    if SHOULD_MOUNT_STATIC:
        file_path = os.path.join(static_folder, rest_of_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # Если файл не найден, возвращаем index.html для поддержки SPA-роутинга
        return FileResponse(os.path.join(static_folder, "index.html"))
    else:
        return {"message": "API работает, но статические файлы не настроены. Обратитесь к API напрямую."}

# --- Функция для генерации ключевых слов для поиска изображений ---
async def generate_image_keywords(text: str, topic: str, format_style: str) -> List[str]:
    """Генерация ключевых слов для поиска изображений с помощью ИИ."""
    try:
        # Если нет API-ключа, вернем список с тематикой поста
        if not OPENROUTER_API_KEY:
            words = re.findall(r'\b[а-яА-Яa-zA-Z]{4,}\b', text.lower())
            stop_words = ["и", "в", "на", "с", "по", "для", "а", "но", "что", "как", "так", "это"]
            filtered_words = [w for w in words if w not in stop_words]
            
            # Если есть тема и формат, добавляем их
            result = []
            if topic:
                result.append(topic)
            if format_style:
                result.append(format_style)
                
            # Добавляем несколько наиболее часто встречающихся слов
            word_counts = Counter(filtered_words)
            common_words = [word for word, _ in word_counts.most_common(3)]
            result.extend(common_words)
            
            # Добавляем контекстные слова для разнообразия результатов
            context_words = ["business", "abstract", "professional", "technology", "creative", "modern"]
            result.extend(random.sample(context_words, 2))
            
            return result
        
        # Инициализируем клиент OpenAI через OpenRouter
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        
        # Создаем промпт для генерации ключевых слов
        system_prompt = """Твоя задача - сгенерировать 2-3 эффективных ключевых слова для поиска изображений.
        Ключевые слова должны точно отражать тематику текста и быть универсальными для поиска стоковых изображений.
        Выбирай короткие конкретные существительные на английском языке, даже если текст на русском.
        Формат ответа: список ключевых слов через запятую."""
        
        user_prompt = f"""Текст поста: {text[:300]}...

Тематика поста: {topic}
Формат поста: {format_style}

Выдай 2-3 лучших ключевых слова на английском языке для поиска подходящих изображений. Только ключевые слова, без объяснений."""
        
        # Запрос к API
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free", # <--- ИЗМЕНЕНО НА НОВУЮ БЕСПЛАТНУЮ МОДЕЛЬ
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=100,
            timeout=15,
            extra_headers={
                "HTTP-Referer": "https://content-manager.onrender.com",
                "X-Title": "Smart Content Assistant"
            }
        )
        
        # Получаем и обрабатываем ответ
        keywords_text = response.choices[0].message.content.strip()
        keywords_list = re.split(r'[,;\n]', keywords_text)
        keywords = [k.strip() for k in keywords_list if k.strip()]
        
        # Если не удалось получить ключевые слова, используем запасной вариант
        if not keywords:
            logger.warning("Не удалось получить ключевые слова от API, используем запасной вариант")
            return [topic, format_style] + random.sample(["business", "abstract", "professional"], 2)
        
        logger.info(f"Сгенерированы ключевые слова для поиска изображений: {keywords}")
        return keywords
        
    except Exception as e:
        logger.error(f"Ошибка при генерации ключевых слов для поиска изображений: {e}")
        # В случае ошибки возвращаем базовые ключевые слова
        return [topic, format_style, "concept", "idea"]

# --- Функция для поиска изображений в Unsplash ---
async def search_unsplash_images(query: str, count: int = 5, topic: str = "", format_style: str = "", post_text: str = "") -> List[FoundImage]:
    """Поиск изображений в Unsplash API с улучшенным выбором ключевых слов."""
    # Проверяем наличие ключа
    if not UNSPLASH_ACCESS_KEY:
        logger.warning(f"Поиск изображений в Unsplash невозможен: отсутствует UNSPLASH_ACCESS_KEY")
        # Возвращаем заглушки с изображениями-заполнителями
        placeholder_images = []
        for i in range(min(count, 5)):  # Ограничиваем до 5 заглушек
            placeholder_images.append(FoundImage(
                id=f"placeholder_{i}",
                source="unsplash",
                preview_url=f"https://via.placeholder.com/150x100?text=Image+{i+1}",
                regular_url=f"https://via.placeholder.com/800x600?text=Unsplash+API+key+required",
                description=f"Placeholder image {i+1}",
                author_name="Demo",
                author_url="https://unsplash.com"
            ))
        return placeholder_images
    
    try:
        # Используем ИИ для генерации лучших ключевых слов
        keywords = []
        if post_text:
            keywords = await generate_image_keywords(post_text, topic, format_style)
        
        # Если не удалось сгенерировать ключевые слова или их мало, добавляем исходный запрос
        if not keywords or len(keywords) < 2:
            if query:
                keywords.append(query)
            
            # Добавляем тему и формат, если они есть
            if topic and topic not in keywords:
                keywords.append(topic)
            if format_style and format_style not in keywords:
                keywords.append(format_style)
                
            # Если все еще мало ключевых слов, добавляем контекстные
            if len(keywords) < 3:
                context_words = ["business", "abstract", "professional", "technology"]
                keywords.extend(random.sample(context_words, min(2, len(context_words))))
        
        logger.info(f"Итоговые ключевые слова для поиска: {keywords}")
        
        unsplash_api_url = f"https://api.unsplash.com/search/photos"
        per_page = min(count * 3, 30) 
        headers = {
            "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}",
            "Accept-Version": "v1"
        }
        
        all_photos = []
        async with httpx.AsyncClient(timeout=15.0) as client: # Увеличим таймаут
            for keyword in keywords[:3]:
                try:
                    logger.info(f"Поиск изображений в Unsplash по запросу: {keyword}")
                    response = await client.get(
                        unsplash_api_url,
                        headers=headers,
                        params={"query": keyword, "per_page": per_page}
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Ошибка при запросе к Unsplash API: {response.status_code} {response.text}")
                        continue
                    
                    results = response.json()
                    if 'results' in results and results['results']:
                        all_photos.extend(results['results'])
                    else:
                        logger.warning(f"Нет результатов по запросу '{keyword}'")
                         
                except httpx.ReadTimeout:
                    logger.warning(f"Таймаут при поиске изображений по ключевому слову '{keyword}'")
                    continue
                except Exception as e:
                    logger.error(f"Ошибка при выполнении запроса к Unsplash по ключевому слову '{keyword}': {e}")
                    continue
        
        if not all_photos:
            logger.warning(f"Не найдено изображений по всем ключевым словам")
            return []
            
        random.shuffle(all_photos)
        selected_photos = all_photos[:count] # Берем нужное количество *после* перемешивания
        
        images = []
        for photo in selected_photos:
            # Просто формируем объекты FoundImage без сохранения в БД
            images.append(FoundImage(
                id=photo['id'],
                source="unsplash",
                preview_url=photo['urls']['small'],
                regular_url=photo['urls']['regular'],
                description=photo.get('description') or photo.get('alt_description') or query,
                author_name=photo['user']['name'],
                author_url=photo['user']['links']['html']
            ))
        
        logger.info(f"Найдено и отобрано {len(images)} изображений из {len(all_photos)} в Unsplash для предложения")
        return images
    except Exception as e:
        logger.error(f"Ошибка при поиске изображений в Unsplash: {e}")
        return []

# --- Endpoint для генерации деталей поста ---
@app.post("/generate-post-details", response_model=PostDetailsResponse)
async def generate_post_details(request: Request, req: GeneratePostDetailsRequest):
    """Генерация детального поста на основе идеи, с текстом и релевантными изображениями."""
    # Удаленный импорт: from services.supabase_subscription_service import SupabaseSubscriptionService
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    subscription_service = SupabaseSubscriptionService(supabase)
    if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
        logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
        return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})
    can_generate_post = await subscription_service.can_generate_post(int(telegram_user_id))
    logger.info(f"Проверка лимита генерации постов для пользователя {telegram_user_id}: {can_generate_post}")
    if not can_generate_post:
        usage = await subscription_service.get_user_usage(int(telegram_user_id))
        reset_at = usage.get("reset_at")
        return JSONResponse(status_code=403, content={"error": f"Достигнут лимит в 2 генерации постов для бесплатной подписки. Следующая попытка будет доступна после: {reset_at}. Лимиты обновляются каждые 3 дня. Оформите подписку для снятия ограничений."})
    await subscription_service.increment_post_usage(int(telegram_user_id))
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
    # Валидация user_id
    if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
        logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
        return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})
    logger.info(f"Анализ для пользователя Telegram ID: {telegram_user_id}")

    # Проверка лимита анализа каналов
    # Удаленный импорт: from services.supabase_subscription_service import SupabaseSubscriptionService
    subscription_service = SupabaseSubscriptionService(supabase)
    can_analyze = await subscription_service.can_analyze_channel(int(telegram_user_id))
    if not can_analyze:
        # Здесь можно отправить уведомление в чат бота или вернуть специальное сообщение
        return JSONResponse(status_code=403, content={"error": "Достигнут лимит анализа каналов для бесплатной подписки. Оформите подписку для снятия ограничений."})

    # Обработка имени пользователя
    username = req.username.replace("@", "").strip()
    logger.info(f"Получен запрос на анализ канала @{username}")
    
    posts = []
    errors_list = []
    error_message = None
    
    # --- НАЧАЛО: ПОПЫТКА ПОЛУЧЕНИЯ ЧЕРЕЗ HTTP (ПЕРВЫЙ ПРИОРИТЕТ) ---
    try:
        logger.info(f"Пытаемся получить посты канала @{username} через HTTP парсинг")
        http_posts = await get_telegram_posts_via_http(username)
        
        if http_posts and len(http_posts) > 0:
            posts = [{"text": post} for post in http_posts]
            logger.info(f"Успешно получено {len(posts)} постов через HTTP парсинг")
        else:
            logger.warning(f"HTTP парсинг не вернул постов для канала @{username}, пробуем Telethon")
            errors_list.append("HTTP: Не получены посты, пробуем Telethon")
    except Exception as http_error:
        logger.error(f"Ошибка при HTTP парсинге для канала @{username}: {http_error}")
        errors_list.append(f"HTTP: {str(http_error)}")
        logger.info("Переключаемся на метод Telethon")
    
    # --- НАЧАЛО: ПОПЫТКА ПОЛУЧЕНИЯ ЧЕРЕЗ TELETHON (ВТОРОЙ ПРИОРИТЕТ) ---
    # Только если HTTP метод не дал результатов
    if not posts:
        try:
            logger.info(f"Пытаемся получить посты канала @{username} через Telethon")
            telethon_posts, telethon_error = get_telegram_posts(username)
            
            if telethon_error:
                logger.warning(f"Ошибка Telethon для канала @{username}: {telethon_error}")
                errors_list.append(f"Telethon: {telethon_error}")
            else:
                # Если Telethon успешно получил посты
                posts = telethon_posts
                logger.info(f"Успешно получено {len(posts)} постов через Telethon")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при получении постов канала @{username} через Telethon: {e}")
            errors_list.append(f"Ошибка Telethon: {str(e)}")
    
    # --- НАЧАЛО: ИСПОЛЬЗУЕМ ПРИМЕРЫ КАК ПОСЛЕДНИЙ ВАРИАНТ ---
    # Если не удалось получить посты ни через HTTP, ни через Telethon
    sample_data_used = False
    if not posts:
        logger.warning(f"Используем примеры постов для канала {username}")
        sample_posts = get_sample_posts(username)
        posts = [{"text": post} for post in sample_posts]
        error_message = "Не удалось получить реальные посты. Используются примеры для демонстрации."
        errors_list.append(error_message)
        sample_data_used = True
        logger.info(f"Используем примеры постов для канала {username}")
    
    # Ограничиваем анализ первыми 20 постами
    posts = posts[:20]
    logger.info(f"Анализируем {len(posts)} постов")
    
    # Анализ контента
    themes = []
    styles = []
    sample_posts = []
    
    try:
        # Подготовка списка текстов для анализа
        texts = [post.get("text", "") for post in posts if post.get("text")]
        
        # Анализ через deepseek
        analysis_result = await analyze_content_with_deepseek(texts, OPENROUTER_API_KEY)
        
        # Извлекаем результаты из возвращаемого словаря
        themes = analysis_result.get("themes", [])
        styles = analysis_result.get("styles", [])
        
        # Сохранение результата анализа в базе данных (если есть telegram_user_id)
        if telegram_user_id and supabase:
            try:
                # Перед сохранением результатов анализа вызываем функцию исправления схемы
                try:
                    logger.info("Вызов функции fix_schema перед сохранением результатов анализа")
                    schema_fix_result = await fix_schema()
                    logger.info(f"Результат исправления схемы: {schema_fix_result}")
                except Exception as schema_error:
                    logger.warning(f"Ошибка при исправлении схемы: {schema_error}")
                
                # Проверяем, существует ли уже запись для этого пользователя и канала
                analysis_check = supabase.table("channel_analysis").select("id").eq("user_id", telegram_user_id).eq("channel_name", username).execute()
                
                # Получение текущей даты-времени в ISO формате для updated_at
                current_datetime = datetime.now().isoformat()
                
                # Создаем словарь с данными анализа
                analysis_data = {
                    "user_id": int(telegram_user_id),  # Убедимся, что user_id - целое число
                    "channel_name": username,
                    "themes": themes,
                    "styles": styles,
                    "analyzed_posts_count": len(posts),
                    "sample_posts": sample_posts[:5] if len(sample_posts) > 5 else sample_posts,
                    "best_posting_time": "18:00 - 20:00 МСК",  # Временная заглушка
                    "is_sample_data": sample_data_used,
                    "updated_at": current_datetime
                }
                
                # Попробуем прямой SQL запрос для вставки/обновления данных, если обычный метод не сработает
                try:
                    # Если запись существует, обновляем ее, иначе создаем новую
                    if hasattr(analysis_check, 'data') and len(analysis_check.data) > 0:
                        # Обновляем существующую запись
                        result = supabase.table("channel_analysis").update(analysis_data).eq("user_id", telegram_user_id).eq("channel_name", username).execute()
                        logger.info(f"Обновлен результат анализа для канала @{username} пользователя {telegram_user_id}")
                    else:
                        # Создаем новую запись
                        result = supabase.table("channel_analysis").insert(analysis_data).execute()
                        logger.info(f"Сохранен новый результат анализа для канала @{username} пользователя {telegram_user_id}")
                except Exception as api_error:
                    logger.warning(f"Ошибка при сохранении через API: {api_error}. Пробуем прямой SQL запрос.")
                    
                    # Получаем URL и ключ Supabase
                    supabase_url = os.getenv('SUPABASE_URL')
                    supabase_key = os.getenv('SUPABASE_ANON_KEY')
                    
                    if supabase_url and supabase_key:
                        # Прямой запрос через SQL
                        url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json"
                        headers = {
                            "apikey": supabase_key,
                            "Authorization": f"Bearer {supabase_key}",
                            "Content-Type": "application/json"
                        }
                        
                        # Сериализуем JSON данные для SQL запроса
                        themes_json = json.dumps(themes)
                        styles_json = json.dumps(styles)
                        sample_posts_json = json.dumps(sample_posts[:5] if len(sample_posts) > 5 else sample_posts)
                        
                        # SQL запрос для вставки/обновления
                        sql_query = f"""
                        INSERT INTO channel_analysis 
                        (user_id, channel_name, themes, styles, analyzed_posts_count, sample_posts, best_posting_time, is_sample_data, updated_at)
                        VALUES 
                        ({telegram_user_id}, '{username}', '{themes_json}'::jsonb, '{styles_json}'::jsonb, {len(posts)}, 
                         '{sample_posts_json}'::jsonb, '18:00 - 20:00 МСК', {sample_data_used}, '{current_datetime}')
                        ON CONFLICT (user_id, channel_name) 
                        DO UPDATE SET 
                        themes = '{themes_json}'::jsonb,
                        styles = '{styles_json}'::jsonb,
                        analyzed_posts_count = {len(posts)},
                        sample_posts = '{sample_posts_json}'::jsonb,
                        best_posting_time = '18:00 - 20:00 МСК',
                        is_sample_data = {sample_data_used},
                        updated_at = '{current_datetime}';
                        """
                        
                        response = requests.post(url, json={"query": sql_query}, headers=headers)
                        
                        if response.status_code in [200, 204]:
                            logger.info(f"Результат анализа для канала @{username} сохранен через прямой SQL запрос")
                        else:
                            logger.error(f"Ошибка при выполнении прямого SQL запроса: {response.status_code} - {response.text}")
                
            except Exception as db_error:
                logger.error(f"Ошибка при сохранении результатов анализа в БД: {db_error}")
                errors_list.append(f"Ошибка БД: {str(db_error)}")
        
        # Подготовка образцов постов для ответа
        sample_texts = [post.get("text", "") for post in posts[:5] if post.get("text")]
        sample_posts = sample_texts
        
    except Exception as e:
        logger.error(f"Ошибка при анализе контента: {e}")
        # Если произошла ошибка при анализе, возвращаем ошибку 500
        raise HTTPException(status_code=500, detail=f"Ошибка при анализе контента: {str(e)}")
    
    # Временная заглушка для лучшего времени постинга
    best_posting_time = "18:00 - 20:00 МСК"
    
    # После успешного анализа:
    has_subscription = await subscription_service.has_active_subscription(int(telegram_user_id))
    if not has_subscription:
        await subscription_service.increment_analysis_usage(int(telegram_user_id))
    
    return AnalyzeResponse(
        themes=themes,
        styles=styles,
        analyzed_posts_sample=sample_posts,
        best_posting_time=best_posting_time,
        analyzed_posts_count=len(posts),
        message=error_message
    )
                
    except Exception as e:
        logger.error(f"Ошибка при генерации плана: {e}\\n{traceback.format_exc()}") # Добавляем traceback
        return AnalyzeResponse(
            message=f"Ошибка при генерации плана: {str(e)}",
            themes=[],
            styles=[],
            analyzed_posts_sample=[],
            analyzed_posts_count=0,
            error=str(e)
        )

# --- Функция для исправления форматирования в существующих идеях ---
async def fix_existing_ideas_formatting():
    """Исправляет форматирование в существующих идеях."""
    if not supabase:
        logger.error("Невозможно исправить форматирование: клиент Supabase не инициализирован")
        return
    
    try:
        # Получение всех идей
        result = supabase.table("suggested_ideas").select("id,topic_idea,format_style").execute()
        
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.info("Нет идей для исправления форматирования")
            return
        
        fixed_count = 0
        for idea in result.data:
            original_topic = idea.get("topic_idea", "")
            original_format = idea.get("format_style", "")
            
            # Очищаем форматирование
            cleaned_topic = clean_text_formatting(original_topic)
            cleaned_format = clean_text_formatting(original_format)
            
            # Если текст изменился, обновляем запись
            if cleaned_topic != original_topic or cleaned_format != original_format:
                supabase.table("suggested_ideas").update({
                    "topic_idea": cleaned_topic,
                    "format_style": cleaned_format
                }).eq("id", idea["id"]).execute()
                fixed_count += 1
        
        logger.info(f"Исправлено форматирование в {fixed_count} идеях")
    except Exception as e:
        logger.error(f"Ошибка при исправлении форматирования: {e}")

# --- Запуск исправления форматирования при старте сервера ---
@app.on_event("startup")
async def startup_event():
    """Запуск обслуживающих процессов при старте приложения."""
    logger.info("Запуск обслуживающих процессов...")
    
    # Проверяем и логируем наличие переменных окружения (замаскированные для безопасности)
    supabase_url = os.getenv("SUPABASE_URL")
    database_url = os.getenv("DATABASE_URL")
    render_database_url = os.getenv("RENDER_DATABASE_URL")
    
    # Логируем доступные переменные окружения (замаскированные)
    if supabase_url:
        masked_url = supabase_url[:10] + "..." + supabase_url[-5:] if len(supabase_url) > 15 else "***"
        logger.info(f"Найдена переменная SUPABASE_URL: {masked_url}")
    if database_url:
        masked_url = database_url[:10] + "..." + database_url[-5:] if len(database_url) > 15 else "***" 
        logger.info(f"Найдена переменная DATABASE_URL: {masked_url}")
    if render_database_url:
        masked_url = render_database_url[:10] + "..." + render_database_url[-5:] if len(render_database_url) > 15 else "***"
        logger.info(f"Найдена переменная RENDER_DATABASE_URL: {masked_url}")
    
    # Проверяем наличие переменных окружения
    db_url = supabase_url or database_url or render_database_url
    if not db_url:
        logger.error("Отсутствуют переменные окружения SUPABASE_URL, DATABASE_URL и RENDER_DATABASE_URL!")
        # Продолжаем работу приложения с предупреждением
    else:
        # Проверяем формат URL и логируем его
        if db_url.startswith('https://'):
            logger.info(f"URL базы данных имеет формат https:// - будет преобразован в postgresql://")
        elif db_url.startswith('postgresql://') or db_url.startswith('postgres://'):
            logger.info(f"URL базы данных имеет правильный формат postgresql://")
        else:
            logger.warning(f"URL базы данных имеет неизвестный формат! Начало: {db_url[:10]}...")
    
    # Проверка и добавление недостающих столбцов (оставляем существующую логику)
    if supabase:
        if not await check_db_tables():
            logger.error("Ошибка при проверке таблиц в базе данных!")
            # Продолжаем работу приложения даже при ошибке
        else:
            logger.info("Проверка таблиц базы данных завершена успешно.")
    else:
        logger.warning("Клиент Supabase не инициализирован, проверка таблиц пропущена.")
    
    # Исправление форматирования в JSON полях
    # await fix_formatting_in_json_fields() # Отключаем временно, если не нужно
    
    logger.info("Обслуживающие процессы запущены успешно")

    # --- ДОБАВЛЕНО: Вызов fix_schema при старте --- 
    try:
        fix_result = await fix_schema()
        logger.info(f"Результат проверки/исправления схемы при старте: {fix_result}")
        if not fix_result.get("success"):
            logger.error("Ошибка при проверке/исправлении схемы БД при запуске!")
            # Решите, следует ли прерывать запуск или нет.
            # Пока продолжаем работу.
    except Exception as schema_fix_error:
        logger.error(f"Исключение при вызове fix_schema во время старта: {schema_fix_error}", exc_info=True)
    # --- КОНЕЦ ДОБАВЛЕНИЯ ---

# --- Функция для исправления форматирования в существующих постах ---
async def fix_existing_posts_formatting():
    """Исправляет форматирование в существующих постах."""
    if not supabase:
        logger.error("Невозможно исправить форматирование постов: клиент Supabase не инициализирован")
        return
    
    try:
        # Получение всех постов
        result = supabase.table("saved_posts").select("id,topic_idea,format_style,final_text").execute()
        
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.info("Нет постов для исправления форматирования")
            return
        
        fixed_count = 0
        for post in result.data:
            original_topic = post.get("topic_idea", "")
            original_format = post.get("format_style", "")
            original_text = post.get("final_text", "")
            
            # Очищаем форматирование
            cleaned_topic = clean_text_formatting(original_topic)
            cleaned_format = clean_text_formatting(original_format)
            cleaned_text = clean_text_formatting(original_text)
            
            # Если текст изменился, обновляем запись
            if (cleaned_topic != original_topic or 
                cleaned_format != original_format or 
                cleaned_text != original_text):
                supabase.table("saved_posts").update({
                    "topic_idea": cleaned_topic,
                    "format_style": cleaned_format,
                    "final_text": cleaned_text
                }).eq("id", post["id"]).execute()
                fixed_count += 1
        
        logger.info(f"Исправлено форматирование в {fixed_count} постах")
    except Exception as e:
        logger.error(f"Ошибка при исправлении форматирования постов: {e}")

# --- Эндпоинт для сохранения изображения ---
@app.post("/save-image", response_model=Dict[str, Any])
async def save_image(request: Request, image_data: Dict[str, Any]):
    """Сохранение информации об изображении в базу данных."""
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
            logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
            return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})
        
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        
        # Добавляем идентификатор пользователя к данным изображения
        image_data["user_id"] = int(telegram_user_id)
        
        # Проверяем наличие обязательных полей
        if not image_data.get("url"):
            raise HTTPException(status_code=400, detail="URL изображения обязателен")
        
        # Если не передан id, генерируем его
        if not image_data.get("id"):
            image_data["id"] = f"img_{str(uuid.uuid4())}"
        
        # Если не передан preview_url, используем основной URL
        if not image_data.get("preview_url"):
            image_data["preview_url"] = image_data["url"]
        
        # Добавляем timestamp
        image_data["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Проверяем, существует ли уже такое изображение
        image_check = supabase.table("saved_images").select("id").eq("url", image_data["url"]).execute()
        
        if hasattr(image_check, 'data') and len(image_check.data) > 0:
            # Изображение уже существует, возвращаем его id
            return {"id": image_check.data[0]["id"], "status": "exists"}
        
        # Сохраняем информацию об изображении
        result = supabase.table("saved_images").insert(image_data).execute()
        
        # Проверка результата
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.error(f"Ошибка при сохранении изображения: {result}")
            raise HTTPException(status_code=500, detail="Ошибка при сохранении изображения")
        
        logger.info(f"Пользователь {telegram_user_id} сохранил изображение {image_data.get('id')}")
        return result.data[0]
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении изображения: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Эндпоинт для получения всех изображений пользователя ---
@app.get("/images", response_model=List[Dict[str, Any]])
async def get_user_images(request: Request, limit: int = 20):
    """Получение всех сохраненных изображений пользователя."""
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос получения изображений пользователя без идентификации")
            raise HTTPException(status_code=401, detail="Для получения изображений необходимо авторизоваться через Telegram")
        
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        
        # Получаем все изображения пользователя
        result = supabase.table("saved_images").select("*").eq("user_id", int(telegram_user_id)).limit(limit).execute()
        
        # Если в результате есть данные, возвращаем их
        if hasattr(result, 'data'):
            logger.info(f"Получено {len(result.data)} изображений для пользователя {telegram_user_id}")
            return result.data
        
        return []
        
    except Exception as e:
        logger.error(f"Ошибка при получении изображений пользователя: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- НОВЫЙ ЭНДПОИНТ: Получение одного изображения по ID --- 
@app.get("/images/{image_id}", response_model=Dict[str, Any])
async def get_image_by_id(request: Request, image_id: str):
    """Получение данных одного сохраненного изображения по его ID."""
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос получения изображения по ID без идентификации")
            raise HTTPException(status_code=401, detail="Для получения изображения необходимо авторизоваться")
        
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        
        # Получаем изображение по ID, проверяя принадлежность пользователю
        result = supabase.table("saved_images").select("*").eq("id", image_id).eq("user_id", int(telegram_user_id)).maybe_single().execute()
        
        # Если изображение найдено, возвращаем его
        if result.data:
            logger.info(f"Получено изображение {image_id} для пользователя {telegram_user_id}")
            return result.data
        else:
            logger.warning(f"Изображение {image_id} не найдено или не принадлежит пользователю {telegram_user_id}")
            raise HTTPException(status_code=404, detail="Изображение не найдено или доступ запрещен")
            
    except Exception as e:
        logger.error(f"Ошибка при получении изображения по ID {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Эндпоинт для получения изображений поста ---
@app.get("/post-images/{post_id}", response_model=List[Dict[str, Any]])
async def get_post_images(request: Request, post_id: str):
    """Получение изображений, связанных с постом."""
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос получения изображений поста без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для получения изображений поста необходимо авторизоваться через Telegram")
        
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        
        # Проверяем существование поста и принадлежность пользователю
        post_check = supabase.table("saved_posts").select("id").eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
        
        if not hasattr(post_check, 'data') or len(post_check.data) == 0:
            logger.warning(f"Попытка получить изображения чужого или несуществующего поста {post_id}")
            raise HTTPException(status_code=404, detail="Пост не найден или вы не имеете к нему доступа")
        
        # Получаем изображения поста через таблицу связей
        result = supabase.table("post_images").select("saved_images(*)").eq("post_id", post_id).execute()
        
        # Если в результате есть данные и они имеют нужную структуру, извлекаем изображения
        images = []
        if hasattr(result, 'data') and len(result.data) > 0:
            for item in result.data:
                if "saved_images" in item and item["saved_images"]:
                    images.append(item["saved_images"])
        
        # Если изображений не найдено, проверяем, есть ли прямая ссылка в данных поста
        if not images:
            post_data = supabase.table("saved_posts").select("image_url").eq("id", post_id).execute()
            if hasattr(post_data, 'data') and len(post_data.data) > 0 and post_data.data[0].get("image_url"):
                images.append({
                    "id": f"direct_img_{post_id}",
                    "url": post_data.data[0]["image_url"],
                    "preview_url": post_data.data[0]["image_url"],
                    "alt": "Изображение поста",
                    "source": "direct"
                })
        
        return images
        
    except Exception as e:
        logger.error(f"Ошибка при получении изображений поста: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Эндпоинт для проксирования изображений через наш сервер ---
@app.get("/image-proxy/{image_id}")
async def proxy_image(request: Request, image_id: str, size: Optional[str] = None):
    """
    Проксирует изображение через наш сервер, скрывая исходный URL.
    
    Args:
        image_id: ID изображения в базе данных
        size: размер изображения (small, medium, large)
    """
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос проксирования изображения без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для доступа к изображению необходимо авторизоваться через Telegram")
        
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        
        # Получаем данные об изображении из базы
        image_data = supabase.table("saved_images").select("*").eq("id", image_id).execute()
        
        if not hasattr(image_data, 'data') or len(image_data.data) == 0:
            logger.warning(f"Изображение с ID {image_id} не найдено")
            raise HTTPException(status_code=404, detail="Изображение не найдено")
        
        image = image_data.data[0]
        
        # Получаем URL изображения
        image_url = image.get("url")
        if not image_url:
            logger.error(f"Для изображения {image_id} не указан URL")
            raise HTTPException(status_code=500, detail="Данные изображения повреждены")
        
        # Выполняем запрос к внешнему сервису для получения изображения
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    logger.error(f"Ошибка при получении изображения {image_id} по URL {image_url}: {response.status}")
                    raise HTTPException(status_code=response.status, detail="Не удалось получить изображение")
                
                # Определяем тип контента
                content_type = response.headers.get("Content-Type", "image/jpeg")
                
                # Получаем содержимое изображения
                image_content = await response.read()
                
                # Возвращаем изображение как ответ
                return Response(content=image_content, media_type=content_type)
    
    except Exception as e:
        logger.error(f"Ошибка при проксировании изображения: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Эндпоинт для получения всех изображений пользователя ---
@app.get("/user-images", response_model=List[Dict[str, Any]])
async def get_user_images_legacy(request: Request, limit: int = 20):
    """
    Получение всех изображений пользователя (устаревший эндпоинт).
    Переадресует на новый эндпоинт /images.
    """
    return await get_user_images(request, limit)

@app.post("/save-suggested-idea", response_model=Dict[str, Any])
async def save_suggested_idea(idea_data: Dict[str, Any], request: Request):
    telegram_user_id = request.headers.get("x-telegram-user-id")
    if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
        logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
        return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})
    if not supabase:
        logging.error("Supabase client not initialized")
        raise HTTPException(status_code=500, detail="Database not initialized")
    subscription_service = SupabaseSubscriptionService(supabase)
    can_generate = await subscription_service.can_generate_idea(int(telegram_user_id))
    if not can_generate:
        return JSONResponse(status_code=403, content={"error": "Достигнут лимит генерации идей для бесплатной подписки. Оформите подписку для снятия ограничений."})
    await subscription_service.increment_idea_usage(int(telegram_user_id))
    try:
        # Очищаем форматирование текста перед сохранением
        if "topic_idea" in idea_data:
            idea_data["topic_idea"] = clean_text_formatting(idea_data["topic_idea"])
        
        # Генерируем уникальный ID для идеи
        idea_id = f"idea_{int(time.time())}_{random.randint(1000, 9999)}"
        idea_data["id"] = idea_id
        idea_data["user_id"] = int(telegram_user_id)
        idea_data["created_at"] = datetime.now().isoformat()
        
        # Сохраняем идею в базе данных
        result = supabase.table("suggested_ideas").insert(idea_data).execute()
        
        if hasattr(result, 'data') and result.data:
            logging.info(f"Saved idea with ID {idea_id}")
            return {"id": idea_id, "message": "Idea saved successfully"}
        else:
            logging.error(f"Failed to save idea: {result}")
            raise HTTPException(status_code=500, detail="Failed to save idea")
    except Exception as e:
        logging.error(f"Error saving idea: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

async def check_db_tables():
    """Проверка и создание необходимых таблиц в базе данных."""
    try:
        # Получаем URL базы данных
        db_url = os.getenv("SUPABASE_URL") or os.getenv("DATABASE_URL")
        if not db_url:
            logger.error("Отсутствуют SUPABASE_URL и DATABASE_URL в переменных окружения при проверке таблиц БД")
            return False
        
        # Проверяем есть ли клиент Supabase
        if not supabase:
            logger.error("Клиент Supabase не инициализирован для проверки таблиц")
            return False
            
        # Для проверки просто запрашиваем одну строку из таблицы, чтобы убедиться, что соединение работает
        try:
        result = supabase.table("suggested_ideas").select("id").limit(1).execute()
        logger.info("Таблица suggested_ideas существует и доступна.")
        except Exception as e:
            logger.error(f"Ошибка при проверке соединения с Supabase: {e}")
            return False
        
        # Автоматическое добавление недостающих столбцов
        try:
            move_temp_files.add_missing_columns()
            logger.info("Проверка и добавление недостающих столбцов выполнены.")
            
            # Явное добавление столбца updated_at в таблицу channel_analysis и обновление кэша схемы
            try:
                # Получение URL и ключа Supabase
                supabase_url = os.getenv('SUPABASE_URL') or os.getenv('DATABASE_URL')
                supabase_key = os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_ANON_KEY')
                
                if supabase_url and supabase_key:
                    # Прямой запрос через API
                    url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json"
                    headers = {
                        "apikey": supabase_key,
                        "Authorization": f"Bearer {supabase_key}",
                        "Content-Type": "application/json"
                    }
                    
                    # SQL-команда для добавления столбца и обновления кэша
                    sql_query = """
                    ALTER TABLE channel_analysis 
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
                    
                    NOTIFY pgrst, 'reload schema';
                    """
                    
                    response = requests.post(url, json={"query": sql_query}, headers=headers)
                    
                    if response.status_code in [200, 204]:
                        logger.info("Столбец updated_at успешно добавлен и кэш схемы обновлен")
                    else:
                        logger.warning(f"Ошибка при добавлении столбца updated_at: {response.status_code} - {response.text}")
            except Exception as column_e:
                logger.warning(f"Ошибка при явном добавлении столбца updated_at: {str(column_e)}")
            
        except Exception as e:
            logger.warning(f"Ошибка при добавлении недостающих столбцов: {str(e)}")
            
        return True
    except Exception as e:
        logger.error(f"Ошибка при проверке таблиц базы данных: {e}")
        return False

async def fix_formatting_in_json_fields():
    """Исправление форматирования в JSON полях."""
    try:
        # Исправляем форматирование в существующих идеях
        await fix_existing_ideas_formatting()
        
        # Исправляем форматирование в существующих постах
        await fix_existing_posts_formatting()
    except Exception as e:
        logger.error(f"Ошибка при исправлении форматирования: {str(e)}")
        # Продолжаем работу приложения даже при ошибке

@app.get("/fix-schema")
async def fix_schema():
    """Исправление схемы базы данных: добавление недостающих колонок и обновление кэша схемы."""
    logger.info("Запуск исправления схемы БД...")
    results = {
        "success": False,
        "message": "Не инициализирован",
        "response_code": 500,
        "operations": []
    }
    try:
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            results["message"] = "Ошибка: не удалось подключиться к базе данных"
            return results

        # Список команд для выполнения
        sql_commands = [
            # Добавление preview_url в saved_images
            {
                "name": "add_preview_url_to_saved_images",
                "query": "ALTER TABLE saved_images ADD COLUMN IF NOT EXISTS preview_url TEXT;"
            },
            # Добавление updated_at в channel_analysis
            {
                "name": "add_updated_at_to_channel_analysis",
                "query": "ALTER TABLE channel_analysis ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"
            },
            # Добавление external_id в saved_images
            {
                "name": "add_external_id_to_saved_images",
                "query": "ALTER TABLE saved_images ADD COLUMN IF NOT EXISTS external_id TEXT;"
            },
            # Добавление saved_image_id в saved_posts
            {
                "name": "add_saved_image_id_to_saved_posts",
                "query": "ALTER TABLE saved_posts ADD COLUMN IF NOT EXISTS saved_image_id UUID REFERENCES saved_images(id) ON DELETE SET NULL;"
            }
        ]

        all_commands_successful = True
        saved_image_id_column_verified = False # Флаг для проверки колонки

        for command in sql_commands:
            logger.info(f"Выполнение команды SQL: {command['name']}")
            result = await _execute_sql_direct(command['query'])
            status_code = result.get("status_code")
            op_result = {
                "name": command['name'],
                "status_code": status_code,
                "error": result.get("error")
            }
            results["operations"] .append(op_result)

            if status_code not in [200, 204]:
                logger.warning(f"Ошибка при выполнении {command['name']}: {status_code} - {result.get('error')}")
                all_commands_successful = False
            else:
                logger.info(f"Команда {command['name']} выполнена успешно (или колонка уже существовала).")

            # === ДОБАВЛЕНО: Проверка существования колонки saved_image_id ===
            if command['name'] == 'add_saved_image_id_to_saved_posts' and status_code in [200, 204]:
                logger.info("Проверка фактического наличия колонки 'saved_image_id' в 'saved_posts'...")
                verification_query = "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'saved_posts' AND column_name = 'saved_image_id'" # УБРАНА ТОЧКА С ЗАПЯТОЙ
                verify_result = await _execute_sql_direct(verification_query)
                verify_status = verify_result.get("status_code")
                op_result_verify = {
                    "name": "verify_saved_image_id_column",
                    "status_code": verify_status,
                    "data": verify_result.get("data"),
                    "error": verify_result.get("error")
                }
                results["operations"].append(op_result_verify)

                # === НАЧАЛО ИЗМЕНЕНИЯ: Более надежная проверка ===
                column_found = False
                verification_data = verify_result.get("data")
                if verify_status == 200 and isinstance(verification_data, list) and len(verification_data) > 0:
                    first_item = verification_data[0]
                    if isinstance(first_item, dict) and first_item.get("column_name") == "saved_image_id":
                        column_found = True
                
                if column_found:
                    logger.info("ПРОВЕРКА УСПЕШНА (новая логика): Колонка 'saved_image_id' найдена в 'saved_posts'.")
                    saved_image_id_column_verified = True
                else:
                    # Этот блок теперь должен выполняться только если колонка ДЕЙСТВИТЕЛЬНО не найдена или произошла ошибка запроса
                    logger.error("ПРОВЕРКА НЕУДАЧНА (новая логика): Колонка 'saved_image_id' НЕ найдена в 'saved_posts' или ошибка в данных.")
                    logger.error(f"Результат проверки (для отладки): status={verify_status}, data={verification_data}, error={verify_result.get('error')}")
                    # Мы все еще должны считать это ошибкой, если колонка должна быть
                    all_commands_successful = False 
                # === КОНЕЦ ИЗМЕНЕНИЯ ===
        else: # Этот else относится к if command['name'] == 'add_saved_image_id_to_saved_posts' ...
             # Он будет выполнен, если команда добавления колонки НЕ УДАЛАСЬ (status_code != 200/204)
             # Или если это была не команда добавления saved_image_id
             pass # Ничего не делаем здесь, ошибка уже залогирована выше

            # === КОНЕЦ ДОБАВЛЕНИЯ === # Это комментарий из оригинального кода, не имеет отношения к моим изменениям

        # --- End of loop ---

        # Принудительно обновляем кэш схемы ПОСЛЕ всех изменений
        logger.info("Принудительное обновление кэша схемы PostgREST...")
        # === ИЗМЕНЕНИЕ: Усиленное обновление кэша ===
        notify_successful = True
        for i in range(3): # Попробуем несколько раз с задержкой
            refresh_result = await _execute_sql_direct("NOTIFY pgrst, 'reload schema';")
            status_code = refresh_result.get("status_code")
            results["operations"] .append({
                 "name": f"notify_pgrst_attempt_{i+1}",
                 "status_code": status_code,
                 "error": refresh_result.get("error")
            })
            if status_code not in [200, 204]:
                 logger.warning(f"Попытка {i+1} обновления кэша не удалась: {status_code} - {refresh_result.get('error')}")
                 notify_successful = False
            else:
                 logger.info(f"Попытка {i+1} обновления кэша успешна.")
                 notify_successful = True # Достаточно одной успешной попытки
                 break # Выходим из цикла, если успешно
            await asyncio.sleep(0.5) # Небольшая пауза между попытками
        # === КОНЕЦ ИЗМЕНЕНИЯ ===

        if all_commands_successful and saved_image_id_column_verified and notify_successful:
            results["success"] = True
            results["message"] = "Схема проверена/исправлена, колонка 'saved_image_id' подтверждена, кэш обновлен."
            results["response_code"] = 200
            logger.info("Исправление схемы, проверка колонки и обновление кэша завершено успешно.")
        elif not saved_image_id_column_verified:
             results["success"] = False
             results["message"] = "Ошибка: не удалось добавить/подтвердить колонку 'saved_image_id' в таблице 'saved_posts'."
             results["response_code"] = 500
             logger.error(f"Ошибка при проверке/добавлении колонки saved_image_id. Детали: {results['operations']}")
        else:
            results["success"] = False
            results["message"] = "Во время исправления схемы или обновления кэша возникли ошибки."
            results["response_code"] = 500
            logger.error(f"Ошибки во время исправления схемы или обновления кэша. Детали: {results['operations']}")

        return results

    except Exception as e:
        logger.error(f"Критическая ошибка при исправлении схемы БД: {e}", exc_info=True)
        results["success"] = False
        results["message"] = f"Ошибка при исправлении схемы: {e}"
        results["response_code"] = 500
        return results

@app.get("/check-schema")
async def check_schema():
    """Проверка структуры таблицы channel_analysis и содержимого кэша схемы."""
    try:
        # Получение URL и ключа Supabase
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            return {"success": False, "message": "Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY"}
        
        # Прямой запрос через API
        url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
        
        # SQL запрос для проверки структуры таблицы
        table_structure_query = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'channel_analysis'
        AND table_schema = 'public'
        ORDER BY ordinal_position;
        """
        
        # SQL запрос для проверки кэша схемы
        cache_query = """
        SELECT pg_notify('pgrst', 'reload schema');
        SELECT 'Cache reloaded' as status;
        """
        
        # Выполнение запроса для получения структуры таблицы
        table_response = requests.post(url, json={"query": table_structure_query}, headers=headers)
        
        # Выполнение запроса для обновления кэша схемы
        cache_response = requests.post(url, json={"query": cache_query}, headers=headers)
        
        # Проверка наличия колонки updated_at
        updated_at_exists = False
        columns = []
        if table_response.status_code == 200:
            try:
                table_data = table_response.json()
                columns = table_data
                for column in table_data:
                    if column.get('column_name') == 'updated_at':
                        updated_at_exists = True
                        break
            except Exception as parse_error:
                logger.error(f"Ошибка при разборе ответа: {parse_error}")
        
        # Если колонки updated_at нет, добавляем ее
        if not updated_at_exists:
            add_column_query = """
            ALTER TABLE channel_analysis 
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
            
            NOTIFY pgrst, 'reload schema';
            """
            add_column_response = requests.post(url, json={"query": add_column_query}, headers=headers)
            
            # Повторная проверка структуры после добавления колонки
            table_response2 = requests.post(url, json={"query": table_structure_query}, headers=headers)
            if table_response2.status_code == 200:
                try:
                    columns = table_response2.json()
                    for column in columns:
                        if column.get('column_name') == 'updated_at':
                            updated_at_exists = True
                            break
                except Exception:
                    pass
        
        return {
            "success": True,
            "table_structure": columns,
            "updated_at_exists": updated_at_exists,
            "cache_response": {
                "status_code": cache_response.status_code,
                "response": cache_response.json() if cache_response.status_code == 200 else None
            }
        }
            
    except Exception as e:
        logger.error(f"Исключение при проверке схемы: {str(e)}")
        return {"success": False, "message": f"Ошибка: {str(e)}"}

@app.get("/recreate-schema")
async def recreate_schema():
    """Пересоздание таблицы channel_analysis с нужной структурой."""
    try:
        # Получение URL и ключа Supabase
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            return {"success": False, "message": "Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY"}
        
        # Прямой запрос через API
        url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
        
        # SQL запрос для создания резервной копии данных
        backup_query = """
        CREATE TEMPORARY TABLE temp_channel_analysis AS
        SELECT * FROM channel_analysis;
        SELECT COUNT(*) AS backup_rows FROM temp_channel_analysis;
        """
        
        # SQL запрос для удаления и пересоздания таблицы с нужной структурой
        recreate_query = """
        DROP TABLE IF EXISTS channel_analysis;
        
        CREATE TABLE channel_analysis (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id BIGINT NOT NULL,
            channel_name TEXT NOT NULL,
            themes JSONB DEFAULT '[]'::jsonb,
            styles JSONB DEFAULT '[]'::jsonb,
            sample_posts JSONB DEFAULT '[]'::jsonb,
            best_posting_time TEXT,
            analyzed_posts_count INTEGER DEFAULT 0,
            is_sample_data BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(user_id, channel_name)
        );
        
        CREATE INDEX idx_channel_analysis_user_id ON channel_analysis(user_id);
        CREATE INDEX idx_channel_analysis_channel_name ON channel_analysis(channel_name);
        CREATE INDEX idx_channel_analysis_updated_at ON channel_analysis(updated_at);
        
        NOTIFY pgrst, 'reload schema';
        SELECT 'Table recreated' AS status;
        """
        
        # SQL запрос для восстановления данных из резервной копии
        restore_query = """
        INSERT INTO channel_analysis (
            id, user_id, channel_name, themes, styles, sample_posts, 
            best_posting_time, analyzed_posts_count, is_sample_data, created_at
        )
        SELECT 
            id, user_id, channel_name, themes, styles, sample_posts, 
            best_posting_time, analyzed_posts_count, is_sample_data, created_at
        FROM temp_channel_analysis
        ON CONFLICT (user_id, channel_name) DO NOTHING;
        
        SELECT COUNT(*) AS restored_rows FROM channel_analysis;
        DROP TABLE IF EXISTS temp_channel_analysis;
        """
        
        # Выполнение запроса для создания резервной копии данных
        backup_response = requests.post(url, json={"query": backup_query}, headers=headers)
        backup_success = backup_response.status_code == 200
        backup_data = backup_response.json() if backup_success else None
        
        # Выполнение запроса для пересоздания таблицы
        recreate_response = requests.post(url, json={"query": recreate_query}, headers=headers)
        recreate_success = recreate_response.status_code == 200
        
        # Если создание резервной копии успешно, пытаемся восстановить данные
        restore_data = None
        restore_success = False
        if backup_success:
            restore_response = requests.post(url, json={"query": restore_query}, headers=headers)
            restore_success = restore_response.status_code == 200
            restore_data = restore_response.json() if restore_success else None
        
        # Финальное обновление кэша схемы
        cache_query = """
        NOTIFY pgrst, 'reload schema';
        SELECT pg_sleep(1);
        NOTIFY pgrst, 'reload schema';
        SELECT 'Cache reloaded twice' as status;
        """
        cache_response = requests.post(url, json={"query": cache_query}, headers=headers)
        
        return {
            "success": recreate_success,
            "backup": {
                "success": backup_success,
                "data": backup_data
            },
            "recreate": {
                "success": recreate_success,
                "data": recreate_response.json() if recreate_success else None
            },
            "restore": {
                "success": restore_success,
                "data": restore_data
            },
            "cache_reload": {
                "success": cache_response.status_code == 200,
                "data": cache_response.json() if cache_response.status_code == 200 else None
            }
        }
            
    except Exception as e:
        logger.error(f"Исключение при пересоздании схемы: {str(e)}")
        return {"success": False, "message": f"Ошибка: {str(e)}"}

# --- НОВЫЙ ЭНДПОИНТ для сохранения НЕСКОЛЬКИХ идей --- 
class SaveIdeasRequest(BaseModel):
    ideas: List[Dict[str, Any]]
    channel_name: Optional[str] = None # Можно передать имя канала один раз

@app.post("/save-suggested-ideas", response_model=Dict[str, Any])
async def save_suggested_ideas_batch(payload: SaveIdeasRequest, request: Request):
    telegram_user_id = request.headers.get("x-telegram-user-id")
    if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
        logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
        return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})
    if not supabase:
        logging.error("Supabase client not initialized")
        raise HTTPException(status_code=500, detail="Database not initialized")
    subscription_service = SupabaseSubscriptionService(supabase)
    can_generate = await subscription_service.can_generate_idea(int(telegram_user_id))
    if not can_generate:
        return JSONResponse(status_code=403, content={"error": "Достигнут лимит генерации идей для бесплатной подписки. Оформите подписку для снятия ограничений."})
    await subscription_service.increment_idea_usage(int(telegram_user_id))
    try:
    saved_count = 0
    errors = []
    saved_ids = []

    ideas_to_save = payload.ideas
    channel_name = payload.channel_name
    logger.info(f"Получен запрос на сохранение {len(ideas_to_save)} идей для канала {channel_name}")

    # --- НАЧАЛО: Удаление старых идей для этого канала перед сохранением новых --- 
    if channel_name:
        try:
            delete_result = supabase.table("suggested_ideas")\
                .delete()\
                .eq("user_id", int(telegram_user_id))\
                .eq("channel_name", channel_name)\
                .execute()
                logger.info(f"Удалено {len(delete_result.data) if hasattr(delete_result, 'data') else 0} старых идей для канала {channel_name}")
        except Exception as del_err:
            logger.error(f"Ошибка при удалении старых идей для канала {channel_name}: {del_err}")
            # Не прерываем выполнение, но логируем ошибку
            errors.append(f"Ошибка удаления старых идей: {str(del_err)}")
    # --- КОНЕЦ: Удаление старых идей --- 

    # --- ДОБАВЛЕНО: Вызов fix_schema перед вставкой --- 
    try:
        logger.info("Вызов fix_schema непосредственно перед сохранением идей...")
        fix_result = await fix_schema()
        if not fix_result.get("success"):
            logger.warning(f"Не удалось обновить/проверить схему перед сохранением идей: {fix_result}")
            # Не прерываем, но логируем. Ошибка, скорее всего, повторится при вставке.
            errors.append("Предупреждение: не удалось проверить/обновить схему перед сохранением.")
        else:
            logger.info("Проверка/обновление схемы перед сохранением идей завершена успешно.")
    except Exception as pre_save_fix_err:
        logger.error(f"Ошибка при вызове fix_schema перед сохранением идей: {pre_save_fix_err}", exc_info=True)
        errors.append(f"Ошибка проверки схемы перед сохранением: {str(pre_save_fix_err)}")
    # --- КОНЕЦ ДОБАВЛЕНИЯ ---

    records_to_insert = []
    for idea_data in ideas_to_save:
        try:
            # Очищаем форматирование текста перед сохранением
            topic_idea = clean_text_formatting(idea_data.get("topic_idea", ""))
            format_style = clean_text_formatting(idea_data.get("format_style", ""))

            if not topic_idea: # Пропускаем идеи без темы
                continue

            # Генерируем уникальный ID для идеи (используем UUID)
            idea_id = str(uuid.uuid4())
            record = {
                "id": idea_id,
                "user_id": int(telegram_user_id),
                "channel_name": idea_data.get("channel_name") or channel_name, # Используем из идеи или общий
                "topic_idea": topic_idea,
                "format_style": format_style,
                "relative_day": idea_data.get("day"),
                "created_at": datetime.now().isoformat(),
                "is_detailed": idea_data.get("is_detailed", False),
            }
            records_to_insert.append(record)
            saved_ids.append(idea_id)
        except Exception as e:
            errors.append(f"Ошибка подготовки идеи {idea_data.get('topic_idea')}: {str(e)}")
            logger.error(f"Ошибка подготовки идеи {idea_data.get('topic_idea')}: {str(e)}")

    if not records_to_insert:
        logger.warning("Нет идей для сохранения после обработки.")
        return {"message": "Нет корректных идей для сохранения.", "saved_count": 0, "errors": errors}

    try:
        # Сохраняем все подготовленные записи одним запросом
        result = supabase.table("suggested_ideas").insert(records_to_insert).execute()

        if hasattr(result, 'data') and result.data:
            saved_count = len(result.data)
            logger.info(f"Успешно сохранено {saved_count} идей батчем.")
            return {"message": f"Успешно сохранено {saved_count} идей.", "saved_count": saved_count, "saved_ids": saved_ids, "errors": errors}
        else:
            error_detail = getattr(result, 'error', 'Unknown error')
            logger.error(f"Ошибка при батч-сохранении идей: {error_detail}")
            errors.append(f"Ошибка при батч-сохранении: {error_detail}")
            # Пытаемся сохранить по одной, если батч не удался
            logger.warning("Попытка сохранить идеи по одной...")
            saved_count_single = 0
            saved_ids_single = []
            for record in records_to_insert:
                 try:
                     single_result = supabase.table("suggested_ideas").insert(record).execute()
                     if hasattr(single_result, 'data') and single_result.data:
                         saved_count_single += 1
                         saved_ids_single.append(record['id'])
                     else:
                         single_error = getattr(single_result, 'error', 'Unknown error')
                         errors.append(f"Ошибка сохранения идеи {record.get('topic_idea')}: {single_error}")
                         logger.error(f"Ошибка сохранения идеи {record.get('topic_idea')}: {single_error}")
                 except Exception as single_e:
                     errors.append(f"Исключение при сохранении идеи {record.get('topic_idea')}: {str(single_e)}")
                     logger.error(f"Исключение при сохранении идеи {record.get('topic_idea')}: {str(single_e)}")
                     
            logger.info(f"Сохранено {saved_count_single} идей по одной.")
            return {
                 "message": f"Сохранено {saved_count_single} идей (остальные с ошибкой).", 
                 "saved_count": saved_count_single, 
                 "saved_ids": saved_ids_single, 
                 "errors": errors
            }

    except Exception as e:
        logger.error(f"Исключение при батч-сохранении идей: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Исключение при батч-сохранении: {str(e)}")

        return {"message": f"Успешно сохранено {saved_count} идей.", "saved_count": saved_count, "saved_ids": saved_ids, "errors": errors}
    except Exception as e:
        logger.error(f"Ошибка при сохранении идей: {str(e)}")
        return {"message": "Не удалось сохранить идеи.", "saved_count": 0, "errors": [str(e)]}

# --- Создаем папку для загрузок, если ее нет ---
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads") # Используем относительный путь внутри backend
os.makedirs(UPLOADS_DIR, exist_ok=True)
logger.info(f"Папка для загруженных изображений: {os.path.abspath(UPLOADS_DIR)}")

# --- НОВЫЙ ЭНДПОИНТ ДЛЯ ЗАГРУЗКИ ИЗОБРАЖЕНИЙ ---
@app.post("/upload-image")
async def upload_image(request: Request, file: UploadFile = File(...)):
    """Загружает файл изображения в Supabase Storage."""
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
        logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
        return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})

    # Преобразуем ID пользователя в целое число
    try:
        telegram_user_id = int(telegram_user_id)
    except (ValueError, TypeError):
        logger.error(f"Некорректный ID пользователя в заголовке: {telegram_user_id}")
        raise HTTPException(status_code=400, detail="Некорректный формат ID пользователя")

    if not supabase:
        logger.error("Клиент Supabase не инициализирован")
        raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")

    try:
        # Проверка типа файла
        content_type = file.content_type
        if not content_type or not content_type.startswith("image/"):
             logger.warning(f"Попытка загрузить не изображение: {file.filename}, тип: {content_type}")
             raise HTTPException(status_code=400, detail="Допускаются только файлы изображений (JPEG, PNG, GIF, WEBP)")

        # Генерируем уникальное имя файла/путь в бакете, сохраняя расширение
        _, ext = os.path.splitext(file.filename)
        allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        if ext.lower() not in allowed_extensions:
             logger.warning(f"Попытка загрузить файл с недопустимым расширением: {file.filename}")
             raise HTTPException(status_code=400, detail=f"Недопустимое расширение файла. Разрешены: {', '.join(allowed_extensions)}")

        # Формируем путь внутри бакета (например, public/<uuid>.<ext>)
        # 'public/' - необязательная папка внутри бакета для удобства организации
        storage_path = f"public/{uuid.uuid4()}{ext.lower()}"
        bucket_name = "post-images" # Имя бакета в Supabase Storage

        # Читаем содержимое файла
        file_content = await file.read()
        # Сбрасываем указатель файла, если он понадобится снова (хотя здесь не нужен)
        await file.seek(0)

        logger.info(f"Попытка загрузки файла в Supabase Storage: бакет='{bucket_name}', путь='{storage_path}', тип='{content_type}'")

        # Загружаем файл в Supabase Storage
        # Используем file_options для установки content-type
        upload_response = supabase.storage.from_(bucket_name).upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": content_type, "cache-control": "3600"} # Устанавливаем тип и кэширование
        )

        # Supabase Python client v1 не возвращает полезных данных при успехе, проверяем на исключения
        # В v2 (если используется) ответ будет другим. Пока ориентируемся на отсутствие ошибок.
        logger.info(f"Файл успешно загружен в Supabase Storage (ответ API: {upload_response}). Путь: {storage_path}")

        # Получаем публичный URL для загруженного файла
        public_url_response = supabase.storage.from_(bucket_name).get_public_url(storage_path)

        if not public_url_response:
             logger.error(f"Не удалось получить публичный URL для файла: {storage_path}")
             raise HTTPException(status_code=500, detail="Не удалось получить URL для загруженного файла.")

        public_url = public_url_response # В v1 get_public_url возвращает строку URL

        logger.info(f"Пользователь {telegram_user_id} успешно загрузил изображение: {storage_path}, URL: {public_url}")

        # Возвращаем ТОЛЬКО публичный URL
        return {"url": public_url}

    except HTTPException as http_err:
        raise http_err
    except APIError as storage_api_err:
        logger.error(f"Ошибка API Supabase Storage при загрузке файла: {storage_api_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка хранилища при загрузке: {storage_api_err.message}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при загрузке файла в Supabase Storage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось обработать загрузку файла: {str(e)}")
    finally:
        # Важно закрыть файл в любом случае
        if file and hasattr(file, 'close') and callable(file.close):
            await file.close()

# --- Настройка обслуживания статических файлов (SPA) ---
# Убедимся, что этот код идет ПОСЛЕ монтирования /uploads
# Путь к папке сборки фронтенда (предполагаем, что она на два уровня выше и в папке frontend/dist)
static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

# ФЛАГ для монтирования статики в конце файла
SHOULD_MOUNT_STATIC = os.path.exists(static_folder) and os.path.isdir(static_folder)

if SHOULD_MOUNT_STATIC:
    logger.info(f"Статические файлы SPA будут обслуживаться из папки: {static_folder}")
    try: # ИСПРАВЛЕНО: Добавлен блок try...except
        app.mount("/", StaticFiles(directory=static_folder, html=True), name="static-spa") # ИСПРАВЛЕНО: Убраны лишние `\`
        logger.info(f"Статические файлы SPA успешно смонтированы в корневом пути '/'")

        # Явно добавим обработчик для корневого пути, если StaticFiles не справляется
        @app.get("/") # ИСПРАВЛЕНО: Убраны лишние `\`
        async def serve_index():
            index_path = os.path.join(static_folder, "index.html")
            if os.path.exists(index_path):
                 return FileResponse(index_path)
            else:
                 logger.error(f"Файл index.html не найден в {static_folder}")
                 raise HTTPException(status_code=404, detail="Index file not found")

        # Обработчик для всех остальных путей SPA (если StaticFiles(html=True) недостаточно)
        # Этот обработчик ПЕРЕХВАТИТ все, что не было перехвачено ранее (/api, /uploads, etc.)
        @app.get("/{rest_of_path:path}") # ИСПРАВЛЕНО: Убраны лишние `\`
        async def serve_spa_catch_all(request: Request, rest_of_path: str):
            # Исключаем API пути, чтобы избежать конфликтов (на всякий случай)
            # Проверяем, не начинается ли путь с /api/, /docs, /openapi.json или /uploads/
            if rest_of_path.startswith("api/") or \
               rest_of_path.startswith("docs") or \
               rest_of_path.startswith("openapi.json") or \
               rest_of_path.startswith("uploads/"):
                 # Этот код не должен выполняться, т.к. роуты API/docs/uploads определены выше, но для надежности
                 # Логируем попытку доступа к API через SPA catch-all
                 logger.debug(f"Запрос к '{rest_of_path}' перехвачен SPA catch-all, но проигнорирован (API/Docs/Uploads).")
                 # Важно вернуть 404, чтобы FastAPI мог найти правильный обработчик, если он есть
                 raise HTTPException(status_code=404, detail="Not Found (SPA Catch-all exclusion)")


            index_path = os.path.join(static_folder, "index.html")
            if os.path.exists(index_path):
                # Логируем возврат index.html для SPA пути
                logger.debug(f"Возвращаем index.html для SPA пути: '{rest_of_path}'")
                return FileResponse(index_path)
            else:
                logger.error(f"Файл index.html не найден в {static_folder} для пути {rest_of_path}")
                raise HTTPException(status_code=404, detail="Index file not found")

        logger.info("Обработчики для SPA настроены.")

    except RuntimeError as mount_error: # ИСПРАВЛЕНО: Добавлен блок except
        logger.error(f"Ошибка при монтировании статических файлов SPA: {mount_error}. Возможно, имя 'static-spa' уже используется или путь '/' занят.")
    except Exception as e: # ИСПРАВЛЕНО: Добавлен блок except
        logger.error(f"Непредвиденная ошибка при монтировании статических файлов SPA: {e}")
else:
    logger.warning(f"Папка статических файлов SPA не найдена: {static_folder}")
    logger.warning("Обслуживание SPA фронтенда не настроено. Только API endpoints доступны.")

# --- Запуск сервера (обычно в конце файла) ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Запуск сервера на порту {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True) # reload=True для разработки

# Добавляем прямой эндпоинт для проверки и обновления статуса подписки из клиента
@app.get("/direct_premium_check", status_code=200)
async def direct_premium_check(request: Request, user_id: Optional[str] = None):
    """
    Прямая проверка премиум-статуса для клиента.
    Принимает user_id в параметре запроса или берет его из заголовка x-telegram-user-id.
    """
    # Добавляем заголовки CORS чтобы API работало корректно
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Content-Type": "application/json"
    }
    
    try:
        effective_user_id = user_id
        
        # Если user_id не предоставлен в параметрах, проверяем заголовки
        if not effective_user_id:
            effective_user_id = request.headers.get("x-telegram-user-id")
            
        # Если все равно нет ID, пробуем получить из данных запроса
        if not effective_user_id and hasattr(request, "state"):
            effective_user_id = request.state.get("user_id")
        
        # Логируем информацию о запросе
        logger.info(f"Прямая проверка премиум-статуса для user_id: {effective_user_id}")
            
        # Проверка на валидность ID
        if not effective_user_id or effective_user_id == '123456789' or not effective_user_id.isdigit():
            logger.error(f"Некорректный или отсутствующий Telegram ID для премиум-проверки: {effective_user_id}")
            return JSONResponse(
                content={
                    "has_premium": False,
                    "user_id": None,
                    "error": "Ошибка авторизации: не удалось получить корректный Telegram ID",
                    "message": "Для проверки премиум-статуса необходим корректный Telegram ID. Откройте приложение внутри Telegram."
                },
                headers=headers
            )
            
        # Проверяем премиум-статус через REST API
        try:
            # Проверяем, инициализирован ли Supabase клиент
            if not supabase:
                logger.error("Supabase клиент не инициализирован")
                return JSONResponse(
                    content={
                        "has_premium": False,
                        "user_id": effective_user_id,
                        "error": "Supabase client not initialized"
                    },
                    headers=headers
                )
            
            # Запрашиваем активные подписки для пользователя через REST API
            subscription_query = supabase.table("user_subscription").select("*").eq("user_id", effective_user_id).eq("is_active", True).execute()
            
            logger.info(f"Результат запроса подписки через REST API: data={subscription_query.data if hasattr(subscription_query, 'data') else None} count={len(subscription_query.data) if hasattr(subscription_query, 'data') else 0}")
            
            has_premium = False
            subscription_end_date = None
            
            # Проверяем результаты запроса
            if hasattr(subscription_query, 'data') and subscription_query.data:
                from datetime import datetime, timezone
                
                # Проверяем подписки на активность и срок
                # Создаем datetime с UTC timezone
                current_date = datetime.now(timezone.utc)
                logger.info(f"Текущая дата с timezone: {current_date.isoformat()}")
                active_subscriptions = []
                
                for subscription in subscription_query.data:
                    end_date = subscription.get("end_date")
                    if end_date:
                        try:
                            # Преобразуем дату из строки в объект datetime c timezone
                            if isinstance(end_date, str):
                                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                            
                            # Если дата окончания в будущем, добавляем в активные
                            logger.info(f"Сравнение дат: end_date={end_date.isoformat()}, current_date={current_date.isoformat()}")
                            if end_date > current_date:
                                active_subscriptions.append(subscription)
                                logger.info(f"Подписка активна: end_date позже текущей даты")
                            else:
                                logger.info(f"Подписка неактивна: end_date раньше текущей даты")
                        except Exception as e:
                            logger.error(f"Ошибка при обработке даты подписки {end_date}: {e}")
                
                # Если есть активные подписки, устанавливаем has_premium = True
                if active_subscriptions:
                    has_premium = True
                    # Берем самую позднюю дату окончания
                    latest_subscription = max(active_subscriptions, key=lambda x: x.get("end_date"))
                    end_date = latest_subscription.get("end_date")
                    if isinstance(end_date, str):
                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    subscription_end_date = end_date.strftime('%Y-%m-%d %H:%M:%S')
            
            logger.info(f"Результат проверки подписки для {effective_user_id}: has_premium={has_premium}, end_date={subscription_end_date}")
            
            # Получаем лимиты использования в зависимости от статуса
            analysis_count = 9999 if has_premium else 3  # Для премиум - неограниченно, для бесплатного - 3
            post_generation_count = 9999 if has_premium else 1  # Для премиум - неограниченно, для бесплатного - 1
            
            # Формируем ответ
            response_data = {
                "has_premium": has_premium,
                "user_id": effective_user_id,
                "error": None,
                "analysis_count": analysis_count,
                "post_generation_count": post_generation_count
            }
            
            # Добавляем дату окончания подписки, если есть
            if subscription_end_date:
                response_data["subscription_end_date"] = subscription_end_date
            
            return JSONResponse(content=response_data, headers=headers)
            
        except Exception as e:
            logger.error(f"Ошибка при прямой проверке премиум-статуса через REST API: {e}")
            
            # Альтернативный способ с использованием httpx
            try:
                supabase_url = os.getenv("SUPABASE_URL")
                supabase_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
                
                if not supabase_url or not supabase_key:
                    raise ValueError("Отсутствуют SUPABASE_URL или SUPABASE_KEY")
                
                # Формируем запрос к REST API Supabase
                httpx_headers = {
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json"
                }
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{supabase_url}/rest/v1/user_subscription",
                        headers=httpx_headers,
                        params={
                            "select": "*",
                            "user_id": f"eq.{effective_user_id}",
                            "is_active": "eq.true"
                        }
                    )
                    
                    if response.status_code == 200:
                        subscriptions = response.json()
                        logger.info(f"Получены подписки через httpx: {subscriptions}")
                        
                        # Проверяем подписки на активность и срок
                        from datetime import datetime, timezone
                        # Создаем datetime с UTC timezone
                        current_date = datetime.now(timezone.utc)
                        logger.info(f"Текущая дата с timezone (httpx): {current_date.isoformat()}")
                        active_subscriptions = []
                        
                        for subscription in subscriptions:
                            end_date = subscription.get("end_date")
                            if end_date:
                                try:
                                    # Преобразуем дату из строки в объект datetime c timezone
                                    if isinstance(end_date, str):
                                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                    
                                    # Если дата окончания в будущем, добавляем в активные
                                    logger.info(f"Сравнение дат (httpx): end_date={end_date.isoformat()}, current_date={current_date.isoformat()}")
                                    if end_date > current_date:
                                        active_subscriptions.append(subscription)
                                        logger.info(f"Подписка активна (httpx): end_date позже текущей даты")
                                    else:
                                        logger.info(f"Подписка неактивна (httpx): end_date раньше текущей даты")
                                except Exception as e:
                                    logger.error(f"Ошибка при обработке даты подписки {end_date}: {e}")
                        
                        # Если есть активные подписки, устанавливаем has_premium = True
                        has_premium = bool(active_subscriptions)
                        subscription_end_date = None
                        
                        if active_subscriptions:
                            # Берем самую позднюю дату окончания
                            latest_subscription = max(active_subscriptions, key=lambda x: x.get("end_date"))
                            end_date = latest_subscription.get("end_date")
                            if isinstance(end_date, str):
                                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                            subscription_end_date = end_date.strftime('%Y-%m-%d %H:%M:%S')
                        
                        logger.info(f"Результат проверки подписки через httpx для {effective_user_id}: has_premium={has_premium}, end_date={subscription_end_date}")
                        
                        # Получаем лимиты использования
                        analysis_count = 9999 if has_premium else 3
                        post_generation_count = 9999 if has_premium else 1
                        
                        # Формируем ответ
                        response_data = {
                            "has_premium": has_premium,
                            "user_id": effective_user_id,
                            "error": None,
                            "analysis_count": analysis_count,
                            "post_generation_count": post_generation_count
                        }
                        
                        # Добавляем дату окончания подписки, если есть
                        if subscription_end_date:
                            response_data["subscription_end_date"] = subscription_end_date
                        
                        return JSONResponse(content=response_data, headers=headers)
                    else:
                        logger.error(f"Ошибка при запросе к Supabase REST API: {response.status_code} - {response.text}")
                        return JSONResponse(
                            content={
                                "has_premium": False,
                                "user_id": effective_user_id,
                                "error": f"HTTP Error: {response.status_code}"
                            },
                            headers=headers
                        )
            
            except Exception as httpx_error:
                logger.error(f"Ошибка при проверке премиум-статуса через httpx: {httpx_error}")
                return JSONResponse(
                    content={
                        "has_premium": False,
                        "user_id": effective_user_id,
                        "error": str(httpx_error)
                    },
                    headers=headers
                )
    
    except Exception as e:
        logger.error(f"Ошибка при прямой проверке премиум-статуса: {e}")
        return JSONResponse(
            content={
                "has_premium": False,
                "user_id": effective_user_id if 'effective_user_id' in locals() else None,
                "error": str(e)
            },
            headers=headers
        )

# Добавляем эндпоинт для API v2 для проверки премиум-статуса
@app.get("/api-v2/premium/check", status_code=200)
async def premium_check_v2(request: Request, user_id: Optional[str] = None):
    """API v2 для проверки премиум-статуса."""
    return await direct_premium_check(request, user_id)

# Добавляем raw API эндпоинт для обхода SPA роутера
@app.get("/raw-api-data/xyz123/premium-data/{user_id}", status_code=200)
async def raw_premium_data(user_id: str, request: Request):
    """
    Специальный нестандартный URL для получения премиум-статуса в обход SPA роутера.
    """
    return await direct_premium_check(request, user_id)

# Добавляем эндпоинт для проверки статуса подписки (для совместимости с клиентским кодом)
@app.get("/subscription/status", status_code=200)
async def subscription_status(request: Request, user_id: Optional[str] = None):
    """
    Проверка статуса подписки.
    Поддерживается для совместимости с клиентским кодом.
    Дублирует функциональность direct_premium_check.
    """
    logger.info(f"Запрос /subscription/status для user_id: {user_id}")
    result = await direct_premium_check(request, user_id)
    
    # Преобразуем формат ответа для совместимости с интерфейсом клиента
    if isinstance(result, JSONResponse):
        data = result.body
        if isinstance(data, bytes):
            import json
            try:
                data = json.loads(data.decode('utf-8'))
            except:
                data = {}
    else:
        data = result
    
    return JSONResponse(
        content={
            "has_subscription": data.get("has_premium", False),
            "analysis_count": data.get("analysis_count", 3),
            "post_generation_count": data.get("post_generation_count", 1),
            "subscription_end_date": data.get("subscription_end_date")
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Content-Type": "application/json"
        }
    )

# Добавляем новый эндпоинт для прямого доступа к базе данных для проверки премиум, как это делает бот
@app.get("/bot-style-premium-check/{user_id}", status_code=200)
async def bot_style_premium_check(user_id: str, request: Request):
    """
    Прямая проверка премиум-статуса через базу данных, используя тот же метод, который использует бот.
    Этот эндпоинт игнорирует кэширование и промежуточные слои, работая напрямую с базой данных.
    """
    try:
        logger.info(f"[BOT-STYLE] Запрос премиум-статуса для пользователя: {user_id}")
        
        # Проверка на валидность ID
        if not user_id or user_id == '123456789' or not user_id.isdigit():
            logger.error(f"Некорректный Telegram ID для bot-style-premium-check: {user_id}")
            return JSONResponse(
                status_code=401, 
                content={
                    "success": False, 
                    "error": "Ошибка авторизации: не удалось получить корректный Telegram ID."
                }
            )
        
        # Проверяем, что user_id предоставлен и преобразуем его в int
        try:
            user_id_int = int(user_id)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "ID пользователя должен быть числом"}
            )
        
        # Проверяем, что у нас есть доступ к базе данных
        db_url = os.getenv("SUPABASE_URL") or os.getenv("DATABASE_URL") or os.getenv("RENDER_DATABASE_URL")
        if not db_url:
            logger.error("[BOT-STYLE] Отсутствуют SUPABASE_URL, DATABASE_URL и RENDER_DATABASE_URL")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Отсутствуют настройки подключения к базе данных"}
            )
            
        # Нормализуем URL базы данных
        db_url = normalize_db_url(db_url)
        
        # Подключаемся напрямую к базе данных (так же, как это делает бот)
        conn = await asyncpg.connect(db_url)
        try:
            # Проверяем наличие активной подписки
            query = """
            SELECT
                id,
                user_id,
                start_date,
                end_date,
                is_active,
                payment_id,
                created_at,
                updated_at
            FROM user_subscription 
            WHERE user_id = $1 
              AND is_active = TRUE 
              AND end_date > NOW()
            ORDER BY end_date DESC
            LIMIT 1
            """
            
            subscription = await conn.fetchrow(query, user_id_int)
            
            # Проверяем результат
            if subscription:
                # Подписка существует и активна
                has_premium = True
                subscription_end_date = subscription["end_date"].strftime('%Y-%m-%d %H:%M:%S') if subscription["end_date"] else None
                
                # Форматируем subscription в словарь
                subscription_data = {
                    "id": subscription["id"],
                    "user_id": subscription["user_id"],
                    "start_date": subscription["start_date"].strftime('%Y-%m-%d %H:%M:%S') if subscription["start_date"] else None,
                    "end_date": subscription_end_date,
                    "is_active": subscription["is_active"],
                    "payment_id": subscription["payment_id"],
                    "created_at": subscription["created_at"].strftime('%Y-%m-%d %H:%M:%S') if subscription["created_at"] else None,
                    "updated_at": subscription["updated_at"].strftime('%Y-%m-%d %H:%M:%S') if subscription["updated_at"] else None
                }
            else:
                # Подписка не существует или не активна
                has_premium = False
                subscription_data = None
                subscription_end_date = None
            
            # Получаем лимиты в зависимости от статуса подписки
            analysis_count = 9999 if has_premium else 3
            post_generation_count = 9999 if has_premium else 1
            
            # Формируем ответ
            response = {
                "success": True,
                "user_id": user_id_int,
                "has_premium": has_premium,
                "analysis_count": analysis_count,
                "post_generation_count": post_generation_count,
                "subscription": subscription_data
            }
            
            # Добавляем дату окончания подписки если есть
            if subscription_end_date:
                response["subscription_end_date"] = subscription_end_date
            
            # Возвращаем ответ с заголовками CORS
            return JSONResponse(
                content=response,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                    "Content-Type": "application/json"
                }
            )
            
        finally:
            # Закрываем соединение с базой данных
            await conn.close()
        
    except Exception as e:
        logger.error(f"[BOT-STYLE] Ошибка при проверке премиум-статуса: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/user/init-usage", response_model=Dict[str, Any])
async def init_user_usage(request: Request):
    """Инициализирует запись лимитов для пользователя, если её нет."""
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
        logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
        return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})
    # Удаленный импорт: from services.supabase_subscription_service import SupabaseSubscriptionService
    subscription_service = SupabaseSubscriptionService(supabase)
    usage = await subscription_service.get_user_usage(int(telegram_user_id))
    return usage

# Примерная структура данных, которые может отправлять Telegram Web App
# Важно: Реальная структура может отличаться, нужно смотреть документацию Telegram
class WebAppInitData(BaseModel):
    user_id: int
    chat_id: int
    # Могут быть и другие поля, например, auth_date, hash и т.д.

# Эндпоинт для проверки доступа к приложению
@app.post("/api/check-app-access")
async def check_app_access(request: Request):
    """
    Проверяет, подписан ли пользователь на канал.
    Вызывается из Telegram Mini App при его инициализации.
    Ожидает X-Telegram-User-Id и X-Telegram-Chat-Id в заголовках.
    """
    try:
        telegram_user_id_str = request.headers.get("X-Telegram-User-Id")
        telegram_chat_id_str = request.headers.get("X-Telegram-Chat-Id")
        
        # Также поддерживаем получение данных из тела запроса для мобильных клиентов
        if not telegram_user_id_str or not telegram_chat_id_str:
            try:
                data = await request.json()
                if not telegram_user_id_str and "user_id" in data:
                    telegram_user_id_str = str(data["user_id"])
                if not telegram_chat_id_str and "chat_id" in data:
                    telegram_chat_id_str = str(data["chat_id"])
            except Exception:
                # Если не удалось прочитать JSON, просто продолжаем с имеющимися данными
                pass

        if not telegram_user_id_str or not telegram_chat_id_str:
            logger.warning("Отсутствуют X-Telegram-User-Id или X-Telegram-Chat-Id в заголовках для /api/check-app-access")
            return {"access_granted": False, "error": "missing_telegram_ids"}

        try:
            user_id = int(telegram_user_id_str)
            chat_id = int(telegram_chat_id_str) # chat_id где запущен WebApp (обычно это ID пользователя для приватного чата с ботом)
        except ValueError:
            logger.error(f"Некорректный формат User-Id или Chat-Id: {telegram_user_id_str}, {telegram_chat_id_str}")
            return {"access_granted": False, "error": "invalid_telegram_ids_format"}

        logger.info(f"Запрос на проверку доступа к приложению от user_id: {user_id}, chat_id: {chat_id}")
        
        # Используем функцию из сервиса telegram_channel_service для проверки подписки
        is_subscribed = await check_channel_subscription(user_id)
        
        if not is_subscribed:
            logger.info(f"Пользователь {user_id} не подписан на канал. Отправляем уведомление.")
            # Отправляем сообщение с инструкциями и кнопками
            await handle_subscription_check_request(user_id, chat_id)
            return {"access_granted": False, "reason": "not_subscribed"}
        
        logger.info(f"Пользователь {user_id} подписан на канал. Доступ разрешен.")
        return {"access_granted": True}

    except Exception as e:
        logger.error(f"Ошибка в /api/check-app-access: {e}", exc_info=True)
        # В случае неожиданной ошибки, безопаснее отказать в доступе
        return {"access_granted": False, "error": "server_error"}

