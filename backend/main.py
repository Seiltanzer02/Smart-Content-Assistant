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
from dateutil.relativedelta import relativedelta

# FastAPI компоненты
from fastapi import FastAPI, Request, File, UploadFile, HTTPException, Query, Path, Response, Header, Depends, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

# Telethon
from telethon import TelegramClient
from telethon.errors import ChannelInvalidError, ChannelPrivateError, UsernameNotOccupiedError
from dotenv import load_dotenv

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
from backend.telegram_utils import get_telegram_posts_via_telethon, get_telegram_posts_via_http, get_sample_posts
import backend.move_temp_files
from datetime import datetime, timedelta
import traceback

# Unsplash
from unsplash import Api as UnsplashApi
from unsplash import Auth as UnsplashAuth

# DeepSeek
from openai import AsyncOpenAI, OpenAIError

# PostgreSQL
import asyncpg

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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Добавляем ключ для резервного API
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL") 
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") 

# --- Константы (включая имя сессии Telegram) --- 
SESSION_NAME = "telegram_session" # <-- Определяем имя файла сессии
IMAGE_SEARCH_COUNT = 15 # Сколько изображений запрашивать у Unsplash
IMAGE_RESULTS_COUNT = 5 # Сколько изображений показывать пользователю

# --- Валидация переменных окружения без аварийного завершения --- 
missing_keys = []
if not OPENROUTER_API_KEY:
    logger.warning("Ключ OPENROUTER_API_KEY не найден! Функции анализа контента будут недоступны.")
    missing_keys.append("OPENROUTER_API_KEY")

# Для OPENAI_API_KEY предупреждение, но не добавление в missing_keys, так как это запасной вариант
if not OPENAI_API_KEY:
    logger.warning("Ключ OPENAI_API_KEY не найден! Запасной вариант API будет недоступен.")

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

# --- Подключение роутеров ---
from backend.routes import user_limits, analysis, ideas, posts, user_settings, images
# Импортируем новый роутер для проверки подписки на канал
from backend.services.telegram_subscription_check import info_router as telegram_channel_info_router

app.include_router(user_limits.router)
app.include_router(analysis.router)
app.include_router(ideas.router)
app.include_router(posts.router)
app.include_router(user_settings.router, prefix="/api/user", tags=["User Settings"])
app.include_router(images.router, prefix="/api", tags=["Images"])
# Добавляем новый роутер для проверки подписки на канал
app.include_router(telegram_channel_info_router, prefix="", tags=["Telegram Channel Info"])
# --- Конец подключения роутеров ---

# --- ВАЖНО: API-эндпоинты для проверки подписки ПЕРЕД SPA-маршрутами ---
@app.get("/bot-style-premium-check/{user_id}", status_code=200)
async def bot_style_premium_check(user_id: str, request: Request):
    """
    Проверка премиум-статуса через Supabase REST API (без прямого подключения к PostgreSQL).
    """
    import os
    import httpx
    from datetime import datetime, timezone
    from fastapi.responses import JSONResponse

    logger.info(f"[BOT-STYLE] Запрос премиум-статуса для пользователя: {user_id}")
    if not user_id:
        return JSONResponse(status_code=400, content={"success": False, "error": "ID пользователя не указан"})
    try:
        user_id_int = int(user_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"success": False, "error": "ID пользователя должен быть числом"})

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    if not supabase_url or not supabase_key:
        logger.error("[BOT-STYLE] Не заданы SUPABASE_URL или SUPABASE_ANON_KEY")
        return JSONResponse(status_code=500, content={"success": False, "error": "Не заданы SUPABASE_URL или SUPABASE_ANON_KEY"})

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}"
    }
    params = {
        "select": "*",
        "user_id": f"eq.{user_id_int}",
        "is_active": "eq.true"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{supabase_url}/rest/v1/user_subscription", headers=headers, params=params)
        if resp.status_code != 200:
            logger.error(f"[BOT-STYLE] Ошибка Supabase REST: {resp.status_code} - {resp.text}")
            return JSONResponse(status_code=500, content={"success": False, "error": f"Supabase REST error: {resp.status_code}"})
        data = resp.json()
        subscription = None
        has_premium = False
        subscription_end_date = None
        if data and isinstance(data, list) and len(data) > 0:
            # Берём самую свежую подписку
            sub = sorted(data, key=lambda x: x.get("end_date", ""), reverse=True)[0]
            # Проверяем дату окончания
            end_date = sub.get("end_date")
            is_active = sub.get("is_active", False)
            if end_date and is_active:
                try:
                    # Преобразуем дату в datetime
                    dt_end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                    if dt_end > datetime.now(timezone.utc):
                        has_premium = True
                        subscription_end_date = dt_end.strftime('%Y-%m-%d %H:%M:%S')
                        subscription = sub
                except Exception as dt_err:
                    logger.warning(f"[BOT-STYLE] Не удалось разобрать дату окончания: {dt_err}")
        analysis_count = 9999 if has_premium else 3
        post_generation_count = 9999 if has_premium else 1
        response = {
            "success": True,
            "user_id": user_id_int,
            "has_premium": has_premium,
            "analysis_count": analysis_count,
            "post_generation_count": post_generation_count,
            "subscription": subscription
        }
        if subscription_end_date:
            response["subscription_end_date"] = subscription_end_date
        return JSONResponse(
            content=response,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Content-Type": "application/json"
            }
        )
    except Exception as e:
        logger.error(f"[BOT-STYLE] Ошибка при проверке премиум-статуса через Supabase REST: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

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
        amount = 70 # <--- УСТАНОВЛЕНО В 70 Stars
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

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    """Вебхук для обработки обновлений от бота Telegram."""
    try:
        data = await request.json()
        logger.info(f"Получен вебхук от Telegram: {data}")

        # 1. Обработка pre_checkout_query
        pre_checkout_query = data.get("pre_checkout_query")
        if pre_checkout_query:
            query_id = pre_checkout_query.get("id")
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            logger.info(f"[telegram_webhook] pre_checkout_query: query_id={query_id}")
            if not bot_token:
                logger.error("[telegram_webhook] Нет TELEGRAM_BOT_TOKEN")
                return {"ok": False, "error": "TELEGRAM_BOT_TOKEN не задан"}
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/answerPreCheckoutQuery",
                    json={"pre_checkout_query_id": query_id, "ok": True}
                )
                logger.info(f"[telegram_webhook] Ответ на pre_checkout_query: {resp.text}")
            return {"ok": True, "pre_checkout_query": True}

        # 2. Обработка успешной оплаты
        message = data.get("message", {})
        successful_payment = message.get("successful_payment")
        if successful_payment:
            user_id_raw = message.get("from", {}).get("id")
            try:
                user_id = int(user_id_raw)
                logger.info(f'[telegram_webhook] user_id приведён к int: {user_id} ({type(user_id)})')
            except Exception as e:
                logger.error(f'[telegram_webhook] Не удалось привести user_id к int: {user_id_raw}, ошибка: {e}')
                return {"ok": False, "error": "Некорректный user_id"}
            payment_id = successful_payment.get("telegram_payment_charge_id")
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            now = datetime.utcnow()
            start_date = now
            end_date = now + relativedelta(months=1)
            logger.info(f'[telegram_webhook] Успешная оплата: user_id={user_id} ({type(user_id)}), payment_id={payment_id}, start_date={start_date}, end_date={end_date}')
            try:
                # Проверяем, есть ли уже подписка
                existing = supabase.table("user_subscription").select("id").eq("user_id", user_id).execute()
                if existing and hasattr(existing, "data") and existing.data and len(existing.data) > 0:
                    # Обновляем
                    supabase.table("user_subscription").update({
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "payment_id": payment_id,
                        "is_active": True,
                        "updated_at": now.isoformat()
                    }).eq("user_id", user_id).execute()
                else:
                    # Создаём новую
                    supabase.table("user_subscription").insert({
                        "user_id": user_id,
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "payment_id": payment_id,
                        "is_active": True,
                        "created_at": now.isoformat(),
                        "updated_at": now.isoformat()
                    }).execute()
                logger.info(f'[telegram_webhook] Подписка успешно активирована для user_id={user_id}')
            except Exception as e:
                logger.error(f'[telegram_webhook] Ошибка при активации подписки: {e}', exc_info=True)
            return {"ok": True, "successful_payment": True}

        # --- Дальнейшая обработка сообщений (оставляю существующую логику) ---
        # Получаем сообщение, если оно есть
        message = data.get('message')
        if not message:
            return {"ok": True}
        
        # Получаем ID пользователя и текст сообщения
        user_id = message.get('from', {}).get('id')
        text = message.get('text', '')
        
        # Дополнительное логирование
        logger.info(f"Обрабатываем сообщение от пользователя {user_id}: {text}")
        
        # Если это команда /start с параметром check_premium или команда /check_premium
        if text.startswith('/start check_premium') or text == '/check_premium':
            logger.info(f"Получена команда проверки премиума от пользователя {user_id}")
            
            # Проверяем премиум-статус пользователя через REST API вместо прямого подключения к БД
            try:
                # Проверяем, инициализирован ли Supabase клиент
                if not supabase:
                    logger.error("Supabase клиент не инициализирован")
                    await send_telegram_message(user_id, "Ошибка сервера: не удалось подключиться к базе данных. Пожалуйста, сообщите администратору.")
                    return {"ok": True, "error": "Supabase client not initialized"}
                
                # Запрашиваем активные подписки для пользователя через REST API
                try:
                    subscription_query = supabase.table("user_subscription").select("*").eq("user_id", user_id).eq("is_active", True).execute()
                    logger.info(f"Результат запроса подписки через REST API: {subscription_query}")
                    has_premium = False
                    end_date_str = 'неизвестно'
                    # Проверяем результаты запроса
                    if hasattr(subscription_query, 'data') and subscription_query.data:
                        from datetime import datetime, timezone
                        current_date = datetime.now(timezone.utc)
                        active_subscriptions = []
                        for subscription in subscription_query.data:
                            end_date = subscription.get("end_date")
                            if end_date:
                                try:
                                    if isinstance(end_date, str):
                                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                    if end_date > current_date:
                                        active_subscriptions.append(subscription)
                                except Exception as e:
                                    logger.error(f"Ошибка при обработке даты подписки {end_date}: {e}")
                        if active_subscriptions:
                            has_premium = True
                            latest_subscription = max(active_subscriptions, key=lambda x: x.get("end_date"))
                            end_date = latest_subscription.get("end_date")
                            if isinstance(end_date, str):
                                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                            end_date_str = end_date.strftime('%d.%m.%Y %H:%M')
                    logger.info(f"Результат проверки подписки для {user_id}: has_premium={has_premium}, end_date={end_date_str}")
                    if has_premium:
                        reply_text = f"✅ У вас активирован ПРЕМИУМ доступ!\nДействует до: {end_date_str}\nОбновите страницу приложения, чтобы увидеть изменения."
                    else:
                        reply_text = "❌ У вас нет активной ПРЕМИУМ подписки.\nДля получения премиум-доступа оформите подписку в приложении."
                    await send_telegram_message(user_id, reply_text)
                    return {"ok": True, "has_premium": has_premium}
                except Exception as api_error:
                    logger.error(f"Ошибка при проверке премиум-статуса через REST API: {api_error}")
                    try:
                        supabase_url = os.getenv("SUPABASE_URL")
                        supabase_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
                        if not supabase_url or not supabase_key:
                            raise ValueError("Отсутствуют SUPABASE_URL или SUPABASE_KEY")
                        headers = {
                            "apikey": supabase_key,
                            "Authorization": f"Bearer {supabase_key}",
                            "Content-Type": "application/json"
                        }
                        async with httpx.AsyncClient() as client:
                            response = await client.get(
                                f"{supabase_url}/rest/v1/user_subscription",
                                headers=headers,
                                params={
                                    "select": "*",
                                    "user_id": f"eq.{user_id}",
                                    "is_active": "eq.true"
                                }
                            )
                            if response.status_code == 200:
                                subscriptions = response.json()
                                from datetime import datetime, timezone
                                current_date = datetime.now(timezone.utc)
                                active_subscriptions = []
                                for subscription in subscriptions:
                                    end_date = subscription.get("end_date")
                                    if end_date:
                                        try:
                                            if isinstance(end_date, str):
                                                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                            if end_date > current_date:
                                                active_subscriptions.append(subscription)
                                        except Exception as e:
                                            logger.error(f"Ошибка при обработке даты подписки {end_date}: {e}")
                                has_premium = bool(active_subscriptions)
                                end_date_str = 'неизвестно'
                                if active_subscriptions:
                                    latest_subscription = max(active_subscriptions, key=lambda x: x.get("end_date"))
                                    end_date = latest_subscription.get("end_date")
                                    if isinstance(end_date, str):
                                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                    end_date_str = end_date.strftime('%d.%m.%Y %H:%M')
                                logger.info(f"Результат проверки подписки через httpx для {user_id}: has_premium={has_premium}, end_date={end_date_str}")
                                if has_premium:
                                    reply_text = f"✅ У вас активирован ПРЕМИУМ доступ!\nДействует до: {end_date_str}\nОбновите страницу приложения, чтобы увидеть изменения."
                                else:
                                    reply_text = "❌ У вас нет активной ПРЕМИУМ подписки.\nДля получения премиум-доступа оформите подписку в приложении."
                                await send_telegram_message(user_id, reply_text)
                                return {"ok": True, "has_premium": has_premium}
                            else:
                                logger.error(f"Ошибка при запросе к Supabase REST API: {response.status_code} - {response.text}")
                                raise Exception(f"HTTP Error: {response.status_code}")
                    except Exception as httpx_error:
                        logger.error(f"Ошибка при проверке премиум-статуса через httpx: {httpx_error}")
                        await send_telegram_message(user_id, "Ошибка подключения к базе данных. Пожалуйста, попробуйте позже.")
                        return {"ok": False, "error": str(httpx_error)}
            except Exception as e:
                logger.error(f"Ошибка при проверке премиум-статуса: {e}")
                await send_telegram_message(user_id, f"Произошла ошибка при проверке статуса подписки. Пожалуйста, попробуйте позже.")
                return {"ok": False, "error": str(e)}
        # Если это просто команда /start
        elif text.startswith('/start'):
            logger.info(f"Получена команда /start от пользователя {user_id}")
            welcome_message = (
                "Привет! Я твой верный помощник в мире Telegram-каналов! 🤖✍️\n\n" +
                "Забудь о муках выбора тем и поиске идей — я проанализирую твой канал " +
                "(или любой другой!) и предложу свежие темы и стили публикаций. ✨\n\n" +
                "А еще я помогу тебе превратить идею в готовый пост с текстом и даже подберу классные картинки! 🖼️\n\n" +
                "Навигация простая: \n" +
                "📊 <b>Анализ</b>: Узнай все о контенте канала.\n" +
                "💡 <b>Идеи</b>: Получи порцию вдохновения для новых постов.\n" +
                "📅 <b>Календарь</b>: Планируй публикации наперед.\n" +
                "📜 <b>Посты</b>: Редактируй и управляй созданными постами.\n" +
                "⭐️ <b>Подписка</b>: Открой все безлимитные возможности.\n\n" +
                "Готов творить? Выбери канал для анализа или переходи к идеям! 👇"
            )
            await send_telegram_message(user_id, welcome_message)
            return {"ok": True}
        
        # ... остальная обработка вебхуков ...
        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука Telegram: {e}")
        return {"ok": False, "error": str(e)}

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
# (перенесена в backend/telegram_utils.py)

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_channel(request: Request, req: AnalyzeRequest):
    """Анализ канала Telegram на основе запроса."""
    # Получение telegram_user_id из заголовков
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if telegram_user_id:
        logger.info(f"Анализ для пользователя Telegram ID: {telegram_user_id}")
        # Проверка лимита анализа каналов
        from backend.services.supabase_subscription_service import SupabaseSubscriptionService
        subscription_service = SupabaseSubscriptionService(supabase)
        can_analyze = await subscription_service.can_analyze_channel(int(telegram_user_id))
        if not can_analyze:
            raise HTTPException(status_code=403, detail="Достигнут лимит анализа каналов для бесплатной подписки. Оформите подписку для снятия ограничений.")
    
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
            telethon_posts, telethon_error = await get_telegram_posts_via_telethon(username)
            
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
                
                # Увеличиваем счетчик анализа для пользователя
                try:
                    has_subscription = await subscription_service.has_active_subscription(int(telegram_user_id))
                    if not has_subscription:
                        logger.info(f"Увеличиваем счетчик анализа для пользователя {telegram_user_id}")
                        await subscription_service.increment_analysis_usage(int(telegram_user_id))
                        logger.info(f"Счетчик анализа успешно увеличен для пользователя {telegram_user_id}")
                except Exception as counter_error:
                    logger.error(f"Ошибка при увеличении счетчика анализа: {counter_error}")
                    # Продолжаем работу, даже если не удалось увеличить счетчик
                
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
    
    return AnalyzeResponse(
        themes=themes,
        styles=styles,
        analyzed_posts_sample=sample_posts,
        best_posting_time=best_posting_time,
        analyzed_posts_count=len(posts),
        message=error_message
    )
    # После успешного анализа (до return AnalyzeResponse)
    if telegram_user_id:
        await subscription_service.increment_analysis_usage(int(telegram_user_id))

# --- Маршрут для получения сохраненного анализа канала ---
@app.get("/channel-analysis", response_model=Dict[str, Any])
async def get_channel_analysis(request: Request, channel_name: str):
    """Получение сохраненного анализа канала."""
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            return {"error": "Для получения анализа необходимо авторизоваться через Telegram"}
        
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
        if not telegram_user_id:
            return []
        
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
    limit_reached: Optional[bool] = False
    reset_at: Optional[str] = None
    subscription_required: Optional[bool] = False

# Функция для очистки текста от маркеров форматирования
def clean_text_formatting(text):
    """Очищает текст от форматирования маркдауна и прочего."""
    if not text:
        return ""
    
    # Удаляем заголовки типа "### **День 1**", "### **1 день**", "### **ДЕНЬ 1**" и другие вариации
    text = re.sub(r'#{1,6}\s*\*?\*?(?:[Дд]ень|ДЕНЬ)?\s*\d+\s*(?:[Дд]ень|ДЕНЬ)?\*?\*?', '', text)
    
    # Удаляем числа и слово "день" в начале строки (без символов #)
    text = re.sub(r'^(?:\*?\*?(?:[Дд]ень|ДЕНЬ)?\s*\d+\s*(?:[Дд]ень|ДЕНЬ)?\*?\*?)', '', text)
    
    # Удаляем символы маркдауна
    text = re.sub(r'\*\*|\*|__|_|#{1,6}', '', text)
    
    # Очищаем начальные и конечные пробелы
    text = text.strip()
    
    # Делаем первую букву заглавной, если строка не пустая
    if text and len(text) > 0:
        text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
    
    return text

def parse_plan_response(plan_text, styles, period_days):
    import re
    plan_items = []
    expected_style_set = set(s.lower() for s in styles)
    # 1. Попытка распарсить как JSON
    try:
        plan_text_clean = plan_text.strip()
        if plan_text_clean.startswith('```json'):
            plan_text_clean = plan_text_clean[7:]
        if plan_text_clean.endswith('```'):
            plan_text_clean = plan_text_clean[:-3]
        plan_text_clean = plan_text_clean.strip()
        plan_json = json.loads(plan_text_clean)
        if isinstance(plan_json, dict):
            plan_json = [plan_json]
        for item in plan_json:
            day = int(item.get("day", 0))
            topic_idea = clean_text_formatting(item.get("topic_idea", ""))
            format_style = clean_text_formatting(item.get("format_style", ""))
            # Фильтрация плейсхолдеров
            if not topic_idea or re.search(r"\[.*\]", topic_idea):
                continue
            if format_style.lower() not in expected_style_set:
                format_style = random.choice(styles)
            plan_items.append(PlanItem(day=day, topic_idea=topic_idea, format_style=format_style))
        if plan_items:
            return plan_items
    except Exception as e:
        logger.info(f"Ответ не является валидным JSON: {e}")
    # 2. Парсинг по строкам с разделителем ::
    lines = plan_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split('::')
        if len(parts) == 3:
            try:
                day_part = parts[0].lower().replace('день', '').strip()
                day = int(day_part)
                topic_idea = clean_text_formatting(parts[1].strip())
                format_style = clean_text_formatting(parts[2].strip())
                if not topic_idea or re.search(r"\[.*\]", topic_idea):
                    continue
                if format_style.lower() not in expected_style_set:
                    format_style = random.choice(styles)
                plan_items.append(PlanItem(day=day, topic_idea=topic_idea, format_style=format_style))
            except Exception as parse_err:
                logger.warning(f"Ошибка парсинга строки плана '{line}': {parse_err}")
        else:
            logger.warning(f"Строка плана не соответствует формату 'День X:: Тема:: Стиль': {line}")
    return plan_items

# --- Маршрут для генерации плана публикаций ---
@app.post("/generate-plan", response_model=PlanGenerationResponse)
async def generate_content_plan(request: Request, req: PlanGenerationRequest):
    """Генерация и сохранение плана контента на основе тем и стилей."""
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос генерации плана без идентификации пользователя Telegram")
            return PlanGenerationResponse(
                message="Для генерации плана необходимо авторизоваться через Telegram",
                plan=[]
            )
            
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

        user_prompt = f"""Сгенерируй план контента для Telegram-канала \"{channel_name}\" на {period_days} дней.\nТемы: {', '.join(themes)}\nСтили (используй ТОЛЬКО их): {', '.join(styles)}\n\nВыдай ровно {period_days} строк СТРОГО в формате:\nДень <номер_дня>:: <Идея поста>:: <Стиль из списка>\n\nНе включай ничего, кроме этих строк.\nСТРОГО ЗАПРЕЩЕНО использовать любые квадратные скобки [], фигурные скобки {{}} , плейсхолдеры, шаблоны, слова 'ссылка', 'памятка', 'контакт', 'email', 'телефон', 'номер', 'название', 'детали', 'уточнить', 'см. ниже', 'см. выше', 'подробнее', 'заполнить', 'указать', 'добавить', 'оставить', 'вставить', 'пример', 'шаблон', 'placeholder', 'link', 'reference', 'details', 'to be filled', 'to be added', 'to be specified', 'see below', 'see above', 'fill in', 'insert', 'add', 'TBD', 'TBA', 'N/A', '---', '***', '???', '!!!', '[]', '{{}}', '()' и любые подобные конструкции.\nВыдай только полностью готовый, финальный, осмысленный текст для каждой идеи без мест для ручного заполнения, без ссылок, без памяток, без контактов, без email, без телефона, без любых заготовок. Только чистый, законченный текст для публикации."""
        # --- ИЗМЕНЕНИЕ КОНЕЦ ---

        # Настройка клиента OpenAI для использования OpenRouter
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        
        # Запрос к API
        logger.info(f"Отправка запроса на генерацию плана контента для канала @{channel_name} с уточненным промптом")
        response = await client.chat.completions.create(
            model="google/gemini-2.5-flash-preview", # <--- ИЗМЕНЕНО НА НОВУЮ БЕСПЛАТНУЮ МОДЕЛЬ
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
        
        plan_items = parse_plan_response(plan_text, styles, period_days)
        # Если не удалось — fallback
        if not plan_items:
            logger.warning("Не удалось извлечь идеи из ответа LLM или все строки были некорректными, генерируем базовый план.")
            for day in range(1, period_days + 1):
                random_theme = random.choice(themes) if themes else "Общая тема"
                random_style = random.choice(styles) if styles else "Общий стиль"
                fallback_topic = f"{random_theme} ({random_style})"
                plan_items.append(PlanItem(
                    day=day,
                    topic_idea=fallback_topic,
                    format_style=random_style
                ))
        # ... сортировка, обрезка, дополнение ...
        plan_items.sort(key=lambda x: x.day)
        plan_items = plan_items[:period_days]
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
                    fallback_topic = f"{random_theme} ({random_style})"
                    plan_items.append(PlanItem(
                        day=current_day,
                        topic_idea=fallback_topic,
                        format_style=random_style
                    ))
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
                logger.info(f"Обработка выбранного изображения: {selected_image.dict() if hasattr(selected_image, 'dict') else selected_image}")
                
                # Проверяем, является ли изображение внешним (с Unsplash или другого источника)
                is_external_image = selected_image.source in ["unsplash", "pexels", "openverse"]
                
                if is_external_image:
                    logger.info(f"Обнаружено внешнее изображение с источником {selected_image.source}")
                    try:
                        # Используем новую функцию для скачивания и сохранения внешнего изображения
                        external_image_result = await download_and_save_external_image(
                            selected_image, 
                            int(telegram_user_id)
                        )
                        saved_image_id = external_image_result["id"]
                        
                        # Обновляем данные об изображении, чтобы они указывали на локальную копию
                        if external_image_result.get("is_new", False) and external_image_result.get("url"):
                            selected_image.url = external_image_result["url"]
                            if external_image_result.get("preview_url"):
                                selected_image.preview_url = external_image_result["preview_url"]
                            selected_image.source = f"{selected_image.source}_saved"
                        
                        logger.info(f"Внешнее изображение успешно обработано, saved_image_id: {saved_image_id}")
                    except Exception as ext_img_err:
                        logger.error(f"Ошибка при обработке внешнего изображения: {ext_img_err}")
                        raise HTTPException(status_code=500, detail=f"Не удалось обработать внешнее изображение: {str(ext_img_err)}")
                else:
                    # Это локальное изображение или загруженное пользователем
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
                    # Проверяем, является ли изображение внешним (с Unsplash или другого источника)
                    is_external_image = selected_image.source in ["unsplash", "pexels", "openverse"]
                    
                    if is_external_image:
                        logger.info(f"Обнаружено внешнее изображение с источником {selected_image.source} при обновлении поста {post_id}")
                        try:
                            # Используем функцию для скачивания и сохранения внешнего изображения
                            external_image_result = await download_and_save_external_image(
                                selected_image, 
                                int(telegram_user_id)
                            )
                            image_id_to_set_in_post = external_image_result["id"]
                            
                            # Обновляем данные об изображении, чтобы они указывали на локальную копию
                            if external_image_result.get("is_new", False) and external_image_result.get("url"):
                                selected_image.url = external_image_result["url"]
                                if external_image_result.get("preview_url"):
                                    selected_image.preview_url = external_image_result["preview_url"]
                                selected_image.source = f"{selected_image.source}_saved"
                            
                            logger.info(f"Внешнее изображение успешно обработано при обновлении поста {post_id}, saved_image_id: {image_id_to_set_in_post}")
                        except Exception as ext_img_err:
                            logger.error(f"Ошибка при обработке внешнего изображения при обновлении поста {post_id}: {ext_img_err}")
                            raise HTTPException(status_code=500, detail=f"Не удалось обработать внешнее изображение: {str(ext_img_err)}")
                    else:
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
        return {"success": True, "message": "Пост успешно удален"}
        
    except HTTPException as http_err:
        # Перехватываем HTTP исключения
        raise http_err
    except Exception as e:
        logger.error(f"Ошибка при удалении поста: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера при удалении поста: {str(e)}")

# --- Настраиваем обработку всех путей SPA для обслуживания статических файлов (в конце файла) ---
# @app.get("/{rest_of_path:path}")
# async def serve_spa(request: Request, rest_of_path: str):
#     """Обслуживает все запросы к путям SPA, возвращая index.html"""
#     # Проверяем, не является ли запрос к API или другим специальным маршрутам
#     if rest_of_path.startswith(("api/", "api-v2/", "docs", "openapi.json", "uploads/", "assets/")):
#         # Возвращаем JSONResponse с 404 для API путей
#         return JSONResponse(content={"error": "Not found (main SPA)"}, status_code=404)
#     
#     # Проверяем, есть ли запрошенный файл
#     if SHOULD_MOUNT_STATIC:
#         file_path = os.path.join(static_folder, rest_of_path)
#         if os.path.exists(file_path) and os.path.isfile(file_path):
#             # Определяем content_type на основе расширения файла
#             return FileResponse(file_path)
#         
#         # Если файл не найден, возвращаем index.html для поддержки SPA-роутинга
#         index_path = os.path.join(static_folder, "index.html")
#         if os.path.exists(index_path):
#             return FileResponse(index_path, media_type="text/html")
#         else:
#             return JSONResponse(content={"error": "Frontend not found"}, status_code=404)
#     else:
#         return JSONResponse(content={"message": "API работает, но статические файлы не настроены. Обратитесь к API напрямую."}, status_code=404)

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
            model="google/gemini-2.5-flash-preview", # <--- ИЗМЕНЕНО НА НОВУЮ БЕСПЛАТНУЮ МОДЕЛЬ
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
    # === ИЗМЕНЕНО: Инициализация found_images в начале ===
    found_images = [] 
    channel_name = req.channel_name if hasattr(req, 'channel_name') else ""
    api_error_message = None # Добавляем переменную для хранения ошибки API
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if telegram_user_id:
            # Проверка лимита генерации идей
            from backend.services.supabase_subscription_service import SupabaseSubscriptionService
            subscription_service = SupabaseSubscriptionService(supabase)
            can_generate = await subscription_service.can_generate_post(int(telegram_user_id))
            if not can_generate:
                usage = await subscription_service.get_user_usage(int(telegram_user_id))
                reset_at = usage.get("reset_at")
                raise HTTPException(status_code=403, detail=f"Достигнут лимит в 2 генерации постов для бесплатной подписки. Следующая попытка будет доступна после: {reset_at}. Лимиты обновляются каждые 3 дня. Оформите подписку для снятия ограничений.")
        if not telegram_user_id:
            logger.warning("Запрос генерации поста без идентификации пользователя Telegram")
            # Используем HTTPException для корректного ответа
            raise HTTPException(
                status_code=401, 
                detail="Для генерации постов необходимо авторизоваться через Telegram"
            )
            
        topic_idea = req.topic_idea
        format_style = req.format_style
        # channel_name уже определен выше
        
        # Проверка наличия API ключа
        if not OPENROUTER_API_KEY:
            logger.warning("Генерация деталей поста невозможна: отсутствует OPENROUTER_API_KEY")
            raise HTTPException(
                status_code=503, # Service Unavailable
                detail="API для генерации текста недоступен"
            )
            
        # Проверка наличия имени канала для получения примеров постов
        post_samples = []
        if channel_name:
            try:
                # Пытаемся получить примеры постов из имеющегося анализа канала
                channel_data = await get_channel_analysis(request, channel_name)
                if channel_data and "analyzed_posts_sample" in channel_data:
                    post_samples = channel_data["analyzed_posts_sample"]
                    logger.info(f"Получено {len(post_samples)} примеров постов для канала @{channel_name}")
            except Exception as e:
                logger.warning(f"Не удалось получить примеры постов для канала @{channel_name}: {e}")
                # Продолжаем без примеров
                pass
                
        # Формируем системный промпт
        system_prompt = """Ты - опытный контент-маркетолог для Telegram-каналов.
Твоя задача - сгенерировать текст поста на основе идеи и формата, который будет готов к публикации.

Пост должен быть:
1. Хорошо структурированным и легко читаемым
2. Соответствовать указанной теме/идее
3. Соответствовать указанному формату/стилю
4. Иметь правильное форматирование для Telegram (если нужно - с эмодзи, абзацами, списками)

Не используй хэштеги, если это не является частью формата.
Сделай пост уникальным и интересным, учитывая специфику Telegram-аудитории.
Используй примеры постов канала, если они предоставлены, чтобы сохранить стиль."""

        # Формируем запрос пользователя
        user_prompt = f"""Создай пост для Telegram-канала "@{channel_name}" на тему:
"{topic_idea}"

Формат поста: {format_style}

Напиши полный текст поста, который будет готов к публикации.
СТРОГО ЗАПРЕЩЕНО использовать любые квадратные скобки [], фигурные скобки {{}}, плейсхолдеры, шаблоны, слова 'ссылка', 'контакт', 'email', 'телефон', 'название', 'дата', 'пример', 'шаблон', 'placeholder', 'link', 'reference', 'details', 'to be filled', 'to be added', 'fill in', 'insert', 'указать', 'оставить', 'заполнить', 'см. ниже', 'см. выше', 'подробнее', 'N/A' и любые другие вставки. В ответе должен быть только готовый текст поста без вставок и шаблонов, только готовый для публикации текст.\n"""

        # Если есть примеры постов канала, добавляем их
        if post_samples:
            sample_text = "\n\n".join(post_samples[:3])  # Берем до 3 примеров, чтобы не превышать токены
            user_prompt += f"""
            
Вот несколько примеров постов из этого канала для сохранения стиля:

{sample_text}
"""

        # Настройка клиента OpenAI для использования OpenRouter
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        
        # === ИЗМЕНЕНО: Добавлена обработка ошибок API ===
        post_text = ""
        try:
            # Запрос к API
            logger.info(f"Отправка запроса на генерацию поста по идее: {topic_idea}")
            response = await client.chat.completions.create(
                model="google/gemini-2.5-flash-preview", # <--- ИЗМЕНЕНО НА НОВУЮ БЕСПЛАТНУЮ МОДЕЛЬ
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=850, # === ИЗМЕНЕНО: Уменьшен лимит токенов с 1000 до 850 ===
                timeout=60,
                extra_headers={
                    "HTTP-Referer": "https://content-manager.onrender.com",
                    "X-Title": "Smart Content Assistant"
                }
            )
            
            # Проверка ответа и извлечение текста
            if response and response.choices and len(response.choices) > 0 and response.choices[0].message and response.choices[0].message.content:
                post_text = response.choices[0].message.content.strip()
                logger.info(f"Получен текст поста ({len(post_text)} символов)")
            # === ДОБАВЛЕНО: Явная проверка на ошибку в ответе ===
            elif response and hasattr(response, 'error') and response.error:
                err_details = response.error
                # Пытаемся получить сообщение об ошибке
                api_error_message = getattr(err_details, 'message', str(err_details)) 
                logger.error(f"OpenRouter API вернул ошибку: {api_error_message}")
                post_text = "[Текст не сгенерирован из-за ошибки API]"
            # === КОНЕЦ ДОБАВЛЕНИЯ ===
            else:
                # Общий случай некорректного ответа
                api_error_message = "API вернул некорректный или пустой ответ"
                logger.error(f"Некорректный или пустой ответ от OpenRouter API. Ответ: {response}")
                post_text = "[Текст не сгенерирован из-за ошибки API]"
                
        except Exception as api_error:
            # Ловим ошибки HTTP запроса или другие исключения
            api_error_message = f"Ошибка соединения с API: {str(api_error)}"
            logger.error(f"Ошибка при запросе к OpenRouter API: {api_error}", exc_info=True)
            post_text = "[Текст не сгенерирован из-за ошибки API]"
        # === КОНЕЦ ИЗМЕНЕНИЯ ===

        # Генерируем ключевые слова для поиска изображений на основе темы и текста
        image_keywords = await generate_image_keywords(post_text, topic_idea, format_style)
        logger.info(f"Сгенерированы ключевые слова для поиска изображений: {image_keywords}")
        
        # Поиск изображений по ключевым словам
        # found_images инициализирован в начале
        for keyword in image_keywords[:3]:  # Ограничиваем до 3 ключевых слов для поиска
            try:
                # Получаем не более 5 изображений
                image_count = min(5 - len(found_images), 3)
                if image_count <= 0:
                    break
                    
                images = await search_unsplash_images(
                    keyword, 
                    count=image_count,
                    topic=topic_idea,
                    format_style=format_style,
                    post_text=post_text
                )
                
                # Добавляем только уникальные изображения
                existing_ids = {img.id for img in found_images}
                unique_images = [img for img in images if img.id not in existing_ids]
                found_images.extend(unique_images)
                
                # Ограничиваем до 5 изображений всего
                if len(found_images) >= 5:
                    found_images = found_images[:5]
                    break
                    
                logger.info(f"Найдено {len(unique_images)} уникальных изображений по ключевому слову '{keyword}'")
            except Exception as e:
                logger.error(f"Ошибка при поиске изображений для ключевого слова '{keyword}': {e}")
                continue
        
        # Если изображения не найдены, повторяем поиск с общей идеей
        if not found_images:
            try:
                found_images = await search_unsplash_images(
                    topic_idea, 
                    count=5,
                    topic=topic_idea,
                    format_style=format_style
                )
                logger.info(f"Найдено {len(found_images)} изображений по основной теме")
            except Exception as e:
                logger.error(f"Ошибка при поиске изображений по основной теме: {e}")
                found_images = []
        
        # Просто возвращаем найденные изображения без сохранения
        logger.info(f"Подготовлено {len(found_images)} предложенных изображений")
        
        # === ИЗМЕНЕНО: Передача сообщения об ошибке в ответе ===
        response_message = f"Сгенерирован пост с {len(found_images[:IMAGE_RESULTS_COUNT])} предложенными изображениями"
        if api_error_message:
            # Если была ошибка API, добавляем ее в сообщение ответа
            response_message = f"Ошибка генерации текста: {api_error_message}. Изображений найдено: {len(found_images[:IMAGE_RESULTS_COUNT])}"
        
        return PostDetailsResponse(
            generated_text=post_text, # Будет пустым или '[...]' при ошибке
            found_images=found_images[:IMAGE_RESULTS_COUNT],
            message=response_message, # <--- Сообщение включает ошибку API
            channel_name=channel_name,
            selected_image_data=PostImage(
                url=found_images[0].regular_url if found_images else "",
                id=found_images[0].id if found_images else None,
                preview_url=found_images[0].preview_url if found_images else "",
                alt=found_images[0].description if found_images else "",
                author=found_images[0].author_name if found_images else "",
                author_url=found_images[0].author_url if found_images else ""
            ) if found_images else None
        )
        # После успешной генерации (до return PostDetailsResponse)
        if telegram_user_id:
            await subscription_service.increment_post_usage(int(telegram_user_id))
        # === КОНЕЦ ИЗМЕНЕНИЯ ===
                
    except HTTPException as http_err:
        # Перехватываем HTTPException, чтобы они не попадали в общий Exception
        raise http_err
    except Exception as e:
        logger.error(f"Ошибка при генерации деталей поста: {e}")
        traceback.print_exc() # Печатаем traceback для диагностики
        # === ИЗМЕНЕНО: Используем HTTPException для ответа ===
        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка сервера при генерации деталей поста: {str(e)}"
        )
        # === КОНЕЦ ИЗМЕНЕНИЯ ===

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
        if not telegram_user_id:
            logger.warning("Запрос сохранения изображения без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для сохранения изображения необходимо авторизоваться через Telegram")
        
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
    if not telegram_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not supabase:
        logging.error("Supabase client not initialized")
        raise HTTPException(status_code=500, detail="Database not initialized")
    
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
            backend.move_temp_files.add_missing_columns()
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
    """Сохраняет список предложенных идей в базу данных."""
    telegram_user_id = request.headers.get("x-telegram-user-id")
    if not telegram_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Преобразуем ID пользователя в целое число
    try:
        telegram_user_id = int(telegram_user_id)
    except (ValueError, TypeError):
        logger.error(f"Некорректный ID пользователя в заголовке: {telegram_user_id}")
        raise HTTPException(status_code=400, detail="Некорректный формат ID пользователя")

    if not supabase:
        logger.error("Supabase client not initialized")
        raise HTTPException(status_code=500, detail="Database not initialized")

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
            logger.info(f"Удалено {len(delete_result.data)} старых идей для канала {channel_name}")
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

# --- Создаем папку для загрузок, если ее нет ---
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads") # Используем относительный путь внутри backend
os.makedirs(UPLOADS_DIR, exist_ok=True)
logger.info(f"Папка для загруженных изображений: {os.path.abspath(UPLOADS_DIR)}")

# --- НОВЫЙ ЭНДПОИНТ ДЛЯ ЗАГРУЗКИ ИЗОБРАЖЕНИЙ ---
@app.post("/upload-image")
async def upload_image(request: Request, file: UploadFile = File(...)):
    """Загружает файл изображения в Supabase Storage."""
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id:
        logger.warning("Запрос загрузки изображения без идентификации пользователя Telegram")
        raise HTTPException(status_code=401, detail="Для загрузки изображения необходимо авторизоваться через Telegram")

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

# Старый код настройки SPA - закомментирован и перенесен в конец файла
# # --- Настройка обслуживания статических файлов (SPA) ---
# # Убедимся, что этот код идет ПОСЛЕ монтирования /uploads
# # Путь к папке сборки фронтенда (предполагаем, что она на два уровня выше и в папке frontend/dist)
# static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
# 
# # ФЛАГ для монтирования статики в конце файла
# SHOULD_MOUNT_STATIC = os.path.exists(static_folder) and os.path.isdir(static_folder)
# 
# if SHOULD_MOUNT_STATIC:
#     logger.info(f"Статические файлы SPA будут обслуживаться из папки: {static_folder}")
#     try: # ИСПРАВЛЕНО: Добавлен блок try...except
#         app.mount("/", StaticFiles(directory=static_folder, html=True), name="static-spa") # ИСПРАВЛЕНО: Убраны лишние `\`
#         logger.info(f"Статические файлы SPA успешно смонтированы в корневом пути '/'")
# 
#         # Явно добавим обработчик для корневого пути, если StaticFiles не справляется
#         @app.get("/") # ИСПРАВЛЕНО: Убраны лишние `\`
#         async def serve_index():
#             index_path = os.path.join(static_folder, "index.html")
#             if os.path.exists(index_path):
#                  return FileResponse(index_path, media_type="text/html")
#             else:
#                  logger.error(f"Файл index.html не найден в {static_folder}")
#                  return JSONResponse(content={"error": "Frontend not found"}, status_code=404)
# 
#         # Обработчик для всех остальных путей SPA (если StaticFiles(html=True) недостаточно)
#         # Этот обработчик ПЕРЕХВАТИТ все, что не было перехвачено ранее (/api, /uploads, etc.)
#         @app.get("/{rest_of_path:path}") # ИСПРАВЛЕНО: Убраны лишние `\`
#         async def serve_spa_catch_all(request: Request, rest_of_path: str):
#             # Попытка обслужить статический актив из /assets/
#             if rest_of_path.startswith("assets/"):
#                 file_path = os.path.join(static_folder, rest_of_path)
#                 if os.path.exists(file_path) and os.path.isfile(file_path):
#                     return FileResponse(file_path) # FastAPI/Starlette угадает media_type
#                 else:
#                     # Если файл в /assets/ не найден, это ошибка 404 для конкретного ресурса
#                     logger.error(f"Статический актив не найден: {file_path}")
#                     return JSONResponse(content={"error": "Asset not found"}, status_code=404)
# 
#             # Исключаем API пути, чтобы SPA не перехватывал их.
#             # Эти пути должны обрабатываться своими собственными декораторами.
#             # Если запрос дошел сюда и это API путь, значит, соответствующий эндпоинт не найден.
#             if rest_of_path.startswith(("api/", "api-v2/", "docs", "openapi.json", "uploads/")):
#                 logger.debug(f"Запрос к API-подобному пути '{rest_of_path}' не был обработан специализированным роутером и возвращает 404 из SPA catch-all.")
#                 return JSONResponse(content={"error": f"API endpoint '{rest_of_path}' not found"}, status_code=404)
# 
#             # Если это не API и не известный статический актив (не в /assets/), 
#             # то это должен быть путь SPA, возвращаем index.html для клиентского роутинга.
#             index_path = os.path.join(static_folder, "index.html")
#             if os.path.exists(index_path):
#                 return FileResponse(index_path, media_type="text/html")
#             
#             # Крайний случай: index.html не найден (проблема конфигурации сервера)
#             logger.error(f"Файл index.html не найден в {static_folder} для SPA пути {rest_of_path}")
#             return JSONResponse(content={"error": "Frontend index.html not found"}, status_code=500)
# 
#         logger.info("Обработчики для SPA настроены.")
# 
#     except RuntimeError as mount_error: # ИСПРАВЛЕНО: Добавлен блок except
#         logger.error(f"Ошибка при монтировании статических файлов SPA: {mount_error}. Возможно, имя 'static-spa' уже используется или путь '/' занят.")
#     except Exception as e: # ИСПРАВЛЕНО: Добавлен блок except
#         logger.error(f"Непредвиденная ошибка при монтировании статических файлов SPA: {e}")
# else:
#     logger.warning(f"Папка статических файлов SPA не найдена: {static_folder}")
#     logger.warning("Обслуживание SPA фронтенда не настроено. Только API endpoints доступны.")

# --- Запуск сервера (обычно в конце файла) ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Запуск сервера на порту {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True) # reload=True для разработки

# Добавляем эндпоинт для API v2 для проверки премиум-статуса
@app.get("/api-v2/premium/check", status_code=200)
async def premium_check_v2(request: Request, user_id: Optional[str] = None):
    """Альтернативный эндпоинт для проверки премиум-статуса (API v2)"""
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

@app.get("/subscription/status")
async def get_subscription_status(request: Request):
    user_id = request.query_params.get("user_id")
    logger.info(f'Запрос /subscription/status для user_id: {user_id}')
    if not user_id:
        return {"error": "user_id обязателен"}
    try:
        result = supabase.table("user_subscription").select("*").eq("user_id", int(user_id)).maybe_single().execute()
        logger.info(f'Результат запроса к user_subscription: {result.data}')
        if result.data:
            sub = result.data
            now = datetime.now(timezone.utc)
            
            # Правильно обрабатываем дату окончания подписки
            end_date_str = sub.get("end_date")
            if end_date_str and sub.get("is_active", False):
                # Стандартизируем формат даты
                if 'Z' in end_date_str:
                    end_date_str = end_date_str.replace('Z', '+00:00')
                
                # Используем fromisoformat для парсинга ISO 8601 формата
                end_date = datetime.fromisoformat(end_date_str)
                
                # Проверяем наличие информации о часовом поясе
                if end_date.tzinfo is None:
                    logger.info(f"Дата сброса не содержит информации о часовом поясе, добавляем UTC: {end_date_str}")
                    end_date = end_date.replace(tzinfo=timezone.utc)
                
                is_active = sub.get("is_active", False) and end_date > now
            else:
                is_active = False
                
            response_data = {
                "has_subscription": is_active,
                "is_active": is_active,
                "subscription_end_date": sub.get("end_date")
            }
            logger.info(f'Возвращаем статус для user_id {user_id}: {response_data}')
            return response_data
        else:
            response_data = {
                "has_subscription": False,
                "is_active": False,
                "subscription_end_date": None
            }
            logger.info(f'Подписка не найдена для user_id {user_id}, возвращаем: {response_data}')
            return response_data
    except Exception as e:
        logger.error(f'Ошибка в /subscription/status для user_id {user_id}: {e}', exc_info=True)
        return {"error": str(e)}

# ... existing code ...
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# Добавляем прямой эндпоинт для проверки и обновления статуса подписки из клиента
@app.get("/direct_premium_check", status_code=200)
async def direct_premium_check(request: Request, user_id: Optional[str] = None):
    """
    Прямая проверка премиум-статуса для клиента.
    Использует прямое подключение к базе данных через asyncpg как в Telegram боте.
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
            
        if not effective_user_id:
            return JSONResponse(
                content={
                    "has_premium": False,
                    "user_id": None,
                    "error": "ID пользователя не предоставлен",
                    "message": "Не удалось определить ID пользователя"
                },
                headers=headers
            )
        
        # Парсим user_id в int
        try:
            user_id_int = int(effective_user_id)
        except ValueError:
            return JSONResponse(
                content={
                    "has_premium": False,
                    "user_id": effective_user_id,
                    "error": "ID пользователя должен быть числом"
                },
                headers=headers
            )
        
        # Проверяем, что у нас есть доступ к базе данных
        db_url = os.getenv("SUPABASE_URL") or os.getenv("DATABASE_URL") or os.getenv("RENDER_DATABASE_URL")
        if not db_url:
            logger.error("Отсутствуют SUPABASE_URL, DATABASE_URL и RENDER_DATABASE_URL")
            return JSONResponse(
                content={
                    "has_premium": False,
                    "user_id": effective_user_id,
                    "error": "Отсутствуют настройки подключения к базе данных"
                },
                headers=headers
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
                from datetime import datetime
                end_date_obj = subscription["end_date"]
                subscription_end_date = end_date_obj.strftime('%Y-%m-%d %H:%M:%S')
                end_date_formatted = end_date_obj.strftime('%d.%m.%Y %H:%M')
                
                logger.info(f"Найдена активная подписка для пользователя {user_id_int}. Действует до: {end_date_formatted}")
            else:
                # Подписка не существует или не активна
                has_premium = False
                subscription_end_date = None
                logger.info(f"Активная подписка для пользователя {user_id_int} не найдена")
            
            # Получаем лимиты в зависимости от статуса подписки
            analysis_count = 9999 if has_premium else 3
            post_generation_count = 9999 if has_premium else 1
            
            # Формируем ответ
            response_data = {
                "has_premium": has_premium,
                "user_id": user_id_int,
                "error": None,
                "analysis_count": analysis_count,
                "post_generation_count": post_generation_count
            }
            
            # Добавляем дату окончания подписки, если есть
            if subscription_end_date:
                response_data["subscription_end_date"] = subscription_end_date
            
            return JSONResponse(content=response_data, headers=headers)
            
        finally:
            # Закрываем соединение с базой данных
            await conn.close()
    
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

# --- Вспомогательная функция для скачивания и сохранения внешних изображений ---
async def download_and_save_external_image(image_data: PostImage, user_id: int) -> Dict[str, Any]:
    """
    Скачивает изображение с внешнего URL и сохраняет его в Supabase Storage.
    Возвращает информацию о сохраненном изображении, включая ID в базе данных.
    
    Args:
        image_data: Данные изображения, включая URL и метаданные
        user_id: ID пользователя, который сохраняет изображение
        
    Returns:
        Dict с информацией о сохраненном изображении, включая ID
    """
    if not image_data or not image_data.url:
        logger.error("Попытка скачать изображение с пустым URL")
        raise ValueError("URL изображения не может быть пустым")
    
    logger.info(f"Скачивание внешнего изображения с URL: {image_data.url}, источник: {image_data.source}")
    
    try:
        # Проверяем, существует ли уже это изображение в базе данных
        image_check_result = supabase.table("saved_images").select("id").eq("url", image_data.url).limit(1).execute()
        if hasattr(image_check_result, 'data') and len(image_check_result.data) > 0:
            # Изображение уже существует в базе данных
            saved_image_id = image_check_result.data[0]["id"]
            logger.info(f"Изображение с URL {image_data.url} уже существует в базе данных с ID {saved_image_id}")
            return {"id": saved_image_id, "is_new": False}
        
        # Скачиваем изображение
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Начинаем скачивание изображения с URL: {image_data.url}")
            response = await client.get(image_data.url)
            response.raise_for_status()  # Проверяем успешность запроса
            
            # Получаем расширение файла из URL или из Content-Type
            file_ext = None
            content_type = response.headers.get("Content-Type", "").lower()
            
            if "image/jpeg" in content_type or "image/jpg" in content_type:
                file_ext = "jpg"
            elif "image/png" in content_type:
                file_ext = "png"
            elif "image/webp" in content_type:
                file_ext = "webp"
            elif "image/gif" in content_type:
                file_ext = "gif"
            else:
                # Пытаемся получить расширение из URL
                url_path = image_data.url.split("?")[0].lower()
                if url_path.endswith(".jpg") or url_path.endswith(".jpeg"):
                    file_ext = "jpg"
                elif url_path.endswith(".png"):
                    file_ext = "png"
                elif url_path.endswith(".webp"):
                    file_ext = "webp"
                elif url_path.endswith(".gif"):
                    file_ext = "gif"
                else:
                    # Если не удалось определить расширение, используем jpg по умолчанию
                    file_ext = "jpg"
            
            # Создаем уникальное имя файла
            new_internal_id = str(uuid.uuid4())
            filename = f"{new_internal_id}.{file_ext}"
            storage_path = f"external/{filename}"
            
            logger.info(f"Скачано изображение, размер: {len(response.content)} байт, тип: {content_type}")
            
            # Сохраняем изображение в Supabase Storage
            storage_result = supabase.storage.from_("post-images").upload(
                storage_path,
                response.content,
                file_options={"content-type": content_type}
            )
            
            # Получаем публичный URL для сохраненного изображения
            public_url = supabase.storage.from_("post-images").get_public_url(storage_path)
            logger.info(f"Изображение сохранено в Storage, публичный URL: {public_url}")
            
            # Сохраняем информацию об изображении в базу данных
            image_data_to_save = {
                "id": new_internal_id,
                "url": public_url,  # Используем URL из нашего хранилища
                "preview_url": image_data.preview_url or public_url,
                "alt": image_data.alt or "",
                "author": image_data.author or "",
                "author_url": image_data.author_url or "",
                "source": f"{image_data.source}_saved" if image_data.source else "external_saved",
                "user_id": user_id,
                "external_url": image_data.url  # Сохраняем оригинальный URL
            }
            
            image_result = supabase.table("saved_images").insert(image_data_to_save).execute()
            if not hasattr(image_result, 'data') or len(image_result.data) == 0:
                logger.error(f"Ошибка при сохранении информации об изображении в БД: {image_result}")
                raise Exception("Не удалось сохранить информацию об изображении в базе данных")
            
            logger.info(f"Информация об изображении сохранена в БД с ID: {new_internal_id}")
            return {
                "id": new_internal_id,
                "is_new": True,
                "url": public_url,
                "preview_url": image_data.preview_url or public_url,
                "alt": image_data.alt or "",
                "author": image_data.author or "",
                "author_url": image_data.author_url or "",
                "source": f"{image_data.source}_saved" if image_data.source else "external_saved"
            }
    
    except httpx.RequestError as e:
        logger.error(f"Ошибка при скачивании изображения: {e}")
        raise Exception(f"Не удалось скачать изображение: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        raise Exception(f"Ошибка при обработке внешнего изображения: {str(e)}")

# === ДОБАВЛЯЕМ МОДЕЛИ PYDANTIC ДЛЯ USER_SETTINGS ===
class UserSettingsBase(BaseModel):
    channelName: Optional[str] = None
    selectedChannels: List[str] = Field(default_factory=list)
    allChannels: List[str] = Field(default_factory=list)

class UserSettingsCreate(UserSettingsBase):
    pass

class UserSettingsResponse(UserSettingsBase):
    id: uuid.UUID
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # For Pydantic v2, replaces orm_mode
# === КОНЕЦ МОДЕЛЕЙ USER_SETTINGS ===

# ... existing code ...
# Placeholder for get_telegram_user_id_from_request dependency
# This should ideally be a shared dependency that extracts user_id from headers
async def get_telegram_user_id_from_request(request: Request) -> int:
    telegram_user_id_str = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id_str:
        logger.warning("Запрос без X-Telegram-User-Id заголовка")
        raise HTTPException(status_code=401, detail="X-Telegram-User-Id header missing")
    try:
        user_id = int(telegram_user_id_str)
        return user_id
    except ValueError:
        logger.warning(f"Некорректный X-Telegram-User-Id: {telegram_user_id_str}")
        raise HTTPException(status_code=400, detail="Invalid X-Telegram-User-Id format")

# ... existing code ...
# (Найдите подходящее место для добавления новых эндпоинтов, например, сгруппировав их с другими API относящимися к пользователю)

# === API ЭНДПОИНТЫ ДЛЯ USER_SETTINGS ===

@app.get("/api/user/settings", response_model=Optional[UserSettingsResponse])
async def get_user_settings(
    request: Request,
    user_id: int = Depends(get_telegram_user_id_from_request)
):
    """
    Получение пользовательских настроек.
    """
    if not supabase:
        logger.error("Supabase клиент не инициализирован при получении настроек пользователя")
        raise HTTPException(status_code=503, detail="База данных недоступна")

    try:
        response = await asyncio.to_thread(
            supabase.table("user_settings")
            .select("*")
            .eq("user_id", user_id)
            .maybe_single()
            .execute
        )
        if response.data:
            return UserSettingsResponse(**response.data)
        return None # Возвращаем None если настроек нет, фронтенд обработает
    except APIError as e:
        logger.error(f"Supabase APIError при получении настроек пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {e.message}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при получении настроек пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@app.put("/api/user/settings", response_model=UserSettingsResponse)
async def update_user_settings(
    settings_data: UserSettingsCreate,
    request: Request,
    user_id: int = Depends(get_telegram_user_id_from_request)
):
    """
    Обновление или создание пользовательских настроек.
    """
    if not supabase:
        logger.error("Supabase клиент не инициализирован при обновлении настроек пользователя")
        raise HTTPException(status_code=503, detail="База данных недоступна")

    now = datetime.now(timezone.utc)
    
    # Преобразуем Pydantic модель в словарь для Supabase
    # Для Pydantic v1: .dict(), для v2: .model_dump()
    # Будем использовать .dict(exclude_unset=True) чтобы не перезаписывать поля пустыми значениями, если они не переданы
    # Однако, для selectedChannels и allChannels, если придет пустой список, он должен сохраниться.
    # Поэтому лучше использовать .dict() без exclude_unset для этих полей, или обеспечить их передачу.
    # Модель UserSettingsCreate имеет default_factory, так что поля всегда будут.
    data_to_save = settings_data.model_dump() if hasattr(settings_data, 'model_dump') else settings_data.dict()
    data_to_save["user_id"] = user_id
    data_to_save["updated_at"] = now

    try:
        # Проверяем, существуют ли настройки для этого пользователя
        existing_settings_response = await asyncio.to_thread(
            supabase.table("user_settings")
            .select("id") # Достаточно одного поля для проверки существования
            .eq("user_id", user_id)
            .maybe_single()
            .execute
        )

        if existing_settings_response.data:
            # Обновляем существующие настройки
            response = await asyncio.to_thread(
                supabase.table("user_settings")
                .update(data_to_save)
                .eq("user_id", user_id)
                .execute
            )
        else:
            # Создаем новые настройки
            data_to_save["created_at"] = now
            # data_to_save["id"] = uuid.uuid4() # PK генерируется базой данных по умолчанию
            response = await asyncio.to_thread(
                supabase.table("user_settings")
                .insert(data_to_save)
                .execute
            )
        
        if response.data:
            # Возвращаем первую запись из результата (должна быть одна)
            return UserSettingsResponse(**response.data[0])
        else:
            logger.error(f"Ошибка при сохранении настроек пользователя {user_id}: ответ Supabase не содержит данных. Response: {response}")
            raise HTTPException(status_code=500, detail="Не удалось сохранить настройки пользователя")

    except APIError as e:
        logger.error(f"Supabase APIError при сохранении настроек пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {e.message}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при сохранении настроек пользователя {user_id}: {e}")
        # Добавляем traceback для лучшей диагностики
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

# === КОНЕЦ API ЭНДПОИНТОВ USER_SETTINGS ===

# ... existing code ...
# Убедитесь, что эти эндпоинты добавлены до любых "catch-all" маршрутов, если они есть.
# Например, до @app.get("/{rest_of_path:path}")
# ... existing code ...

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_API_URL = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}' if TELEGRAM_BOT_TOKEN else None

@app.post('/api/send-image-to-chat')
async def send_image_to_chat(request: Request):
    try:
        data = await request.json()
        image_url = data.get('imageUrl')
        alt = data.get('alt', '')
        telegram_user_id = request.headers.get('x-telegram-user-id')
        if not telegram_user_id:
            raise HTTPException(status_code=401, detail='Не передан идентификатор пользователя Telegram')
        if not TELEGRAM_BOT_TOKEN:
            raise HTTPException(status_code=500, detail='TELEGRAM_BOT_TOKEN не задан в окружении')
        if not image_url:
            raise HTTPException(status_code=400, detail='Не передан URL изображения')
        # Отправляем изображение через Telegram Bot API
        payload = {
            'chat_id': telegram_user_id,
            'photo': image_url
        }
        resp = requests.post(f'{TELEGRAM_API_URL}/sendPhoto', data=payload)
        if resp.status_code == 200:
            return JSONResponse({'success': True})
        else:
            return JSONResponse({'success': False, 'error': resp.text}, status_code=500)
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

from backend.services.telegram_subscription_check import info_router as telegram_channel_info_router
app.include_router(telegram_channel_info_router, prefix="", tags=["Telegram Channel Info"])

from backend.services.telegram_subscription_check import check_user_channel_subscription

@app.get("/api-v2/channel-subscription/check", status_code=200)
async def channel_subscription_check_v2(request: Request, user_id: Optional[str] = None):
    """
    Проверка подписки на канал (аналогично премиум-подписке).
    user_id можно передать как query или через X-Telegram-User-Id.
    """
    effective_user_id = user_id or request.headers.get("x-telegram-user-id")
    if not effective_user_id:
        return {"has_channel_subscription": False, "user_id": None, "error": "ID пользователя не предоставлен"}
    try:
        user_id_int = int(effective_user_id)
    except ValueError:
        return {"has_channel_subscription": False, "user_id": effective_user_id, "error": "ID пользователя должен быть числом"}
    try:
        is_subscribed, error_msg = await check_user_channel_subscription(user_id_int)
        return {"has_channel_subscription": is_subscribed, "user_id": user_id_int, "error": error_msg}
    except Exception as e:
        return {"has_channel_subscription": False, "user_id": user_id_int, "error": str(e)}


# --- Настройка обслуживания статических файлов (SPA) ---
# Убедимся, что этот код идет ПОСЛЕ всех API маршрутов
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
                 return FileResponse(index_path, media_type="text/html")
            else:
                 logger.error(f"Файл index.html не найден в {static_folder}")
                 return JSONResponse(content={"error": "Frontend not found"}, status_code=404)

        # Обработчик для всех остальных путей SPA (если StaticFiles(html=True) недостаточно)
        # Этот обработчик ПЕРЕХВАТИТ все, что не было перехвачено ранее (/api, /uploads, etc.)
        @app.get("/{rest_of_path:path}") # ИСПРАВЛЕНО: Убраны лишние `\`
        async def serve_spa_catch_all(request: Request, rest_of_path: str):
            # Попытка обслужить статический актив из /assets/
            if rest_of_path.startswith("assets/"):
                file_path = os.path.join(static_folder, rest_of_path)
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    return FileResponse(file_path) # FastAPI/Starlette угадает media_type
                else:
                    # Если файл в /assets/ не найден, это ошибка 404 для конкретного ресурса
                    logger.error(f"Статический актив не найден: {file_path}")
                    return JSONResponse(content={"error": "Asset not found"}, status_code=404)

            # Исключаем API пути, чтобы SPA не перехватывал их.
            # Эти пути должны обрабатываться своими собственными декораторами.
            # Если запрос дошел сюда и это API путь, значит, соответствующий эндпоинт не найден.
            if rest_of_path.startswith(("api/", "api-v2/", "docs", "openapi.json", "uploads/")):
                logger.debug(f"Запрос к API-подобному пути '{rest_of_path}' не был обработан специализированным роутером и возвращает 404 из SPA catch-all.")
                return JSONResponse(content={"error": f"API endpoint '{rest_of_path}' not found"}, status_code=404)

            # Если это не API и не известный статический актив (не в /assets/), 
            # то это должен быть путь SPA, возвращаем index.html для клиентского роутинга.
            index_path = os.path.join(static_folder, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path, media_type="text/html")
            
            # Крайний случай: index.html не найден (проблема конфигурации сервера)
            logger.error(f"Файл index.html не найден в {static_folder} для SPA пути {rest_of_path}")
            return JSONResponse(content={"error": "Frontend index.html not found"}, status_code=500)

        logger.info("Обработчики для SPA настроены.")

    except RuntimeError as mount_error: # ИСПРАВЛЕНО: Добавлен блок except
        logger.error(f"Ошибка при монтировании статических файлов SPA: {mount_error}. Возможно, имя 'static-spa' уже используется или путь '/' занят.")
    except Exception as e: # ИСПРАВЛЕНО: Добавлен блок except
        logger.error(f"Непредвиденная ошибка при монтировании статических файлов SPA: {e}")
else:
    logger.warning(f"Папка статических файлов SPA не найдена: {static_folder}")
    logger.warning("Обслуживание SPA фронтенда не настроено. Только API endpoints доступны.")

