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
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

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
)

# --- Подключение статических файлов ---
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Контекстные переменные для состояния приложения
unsplash_auth = None
unsplash_api = None

@app.post("/generate-invoice", response_model=Dict[str, Any])
async def generate_invoice(request: Request):
    """Генерирует инвойс для платежа через Telegram."""
    try:
        data = await request.json()
        logger.info(f"Получен запрос на создание инвойса: {data}")
        
        # Получаем обязательные параметры
        user_id = data.get("user_id")
        if not user_id:
            logger.error("Отсутствует user_id в запросе")
            return {"ok": False, "error": "Необходимо указать user_id"}
        
        # Опционально получаем другие параметры
        description = data.get("description", "Премиум подписка")
        amount = data.get("amount", 339)  # Сумма по умолчанию в рублях
        
        # Получаем токен бота для API запроса
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not telegram_token:
            logger.error("Отсутствует TELEGRAM_BOT_TOKEN при создании инвойса")
            return {"ok": False, "error": "Отсутствует токен бота"}
        
        # Подготовка платежных данных
        invoice_payload = f"premium_subscription_{user_id}_{int(time.time())}"
        payment_data = {
            "chat_id": user_id,
            "title": "Премиум подписка",
            "description": description,
            "payload": invoice_payload,
            "provider_token": os.getenv("TELEGRAM_PAYMENT_TOKEN"),
            "currency": "RUB",
            "prices": [{"label": "Подписка", "amount": int(amount * 100)}]  # в копейках
        }
        
        # Отправляем запрос к API Telegram
        telegram_api_url = f"https://api.telegram.org/bot{telegram_token}/sendInvoice"
        async with httpx.AsyncClient() as client:
            response = await client.post(telegram_api_url, json=payment_data)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Инвойс успешно создан: {result}")
                return {"ok": True, "result": result}
            else:
                logger.error(f"Ошибка при создании инвойса: {response.status_code} - {response.text}")
                return {"ok": False, "error": f"Ошибка API Telegram: {response.text}"}
    
    except Exception as e:
        logger.error(f"Ошибка при генерации инвойса: {e}")
        return {"ok": False, "error": str(e)}

@app.post("/send-stars-invoice", response_model=Dict[str, Any])
async def send_stars_invoice(request: Request):
    """Отправляет инвойс для покупки звезд через Telegram."""
    try:
        data = await request.json()
        logger.info(f"Получен запрос на создание инвойса для звезд: {data}")
        
        # Получаем обязательные параметры
        user_id = data.get("user_id")
        if not user_id:
            logger.error("Отсутствует user_id в запросе")
            return {"ok": False, "error": "Необходимо указать user_id"}
        
        # Получаем количество звезд и вычисляем цену
        stars_amount = data.get("stars_amount", 10)  # По умолчанию 10 звезд
        price_per_star = 19  # Базовая цена за одну звезду
        
        # Скидки при покупке большего количества
        if stars_amount >= 100:
            price_per_star = 12  # -37% от базовой цены
        elif stars_amount >= 50:
            price_per_star = 15  # -21% от базовой цены
        elif stars_amount >= 20:
            price_per_star = 17  # -11% от базовой цены
        
        total_amount = stars_amount * price_per_star
        
        # Описание для инвойса
        stars_word = "звезд"  # По умолчанию для 5+ звезд
        if stars_amount % 10 == 1 and stars_amount % 100 != 11:
            stars_word = "звезда"
        elif 2 <= stars_amount % 10 <= 4 and (stars_amount % 100 < 10 or stars_amount % 100 >= 20):
            stars_word = "звезды"
        
        description = f"{stars_amount} {stars_word} для генерации постов"
        
        # Получаем токен бота для API запроса
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not telegram_token:
            logger.error("Отсутствует TELEGRAM_BOT_TOKEN при создании инвойса для звезд")
            return {"ok": False, "error": "Отсутствует токен бота"}
        
        # Подготовка платежных данных
        invoice_payload = f"stars_purchase_{user_id}_{stars_amount}_{int(time.time())}"
        payment_data = {
            "chat_id": user_id,
            "title": f"Покупка {stars_amount} {stars_word}",
            "description": description,
            "payload": invoice_payload,
            "provider_token": os.getenv("TELEGRAM_PAYMENT_TOKEN"),
            "currency": "RUB",
            "prices": [{"label": f"{stars_amount} {stars_word}", "amount": int(total_amount * 100)}]  # в копейках
        }
        
        # Отправляем запрос к API Telegram
        telegram_api_url = f"https://api.telegram.org/bot{telegram_token}/sendInvoice"
        async with httpx.AsyncClient() as client:
            response = await client.post(telegram_api_url, json=payment_data)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Инвойс для звезд успешно создан: {result}")
                return {"ok": True, "result": result, "stars_amount": stars_amount, "total_amount": total_amount}
            else:
                logger.error(f"Ошибка при создании инвойса для звезд: {response.status_code} - {response.text}")
                return {"ok": False, "error": f"Ошибка API Telegram: {response.text}"}
    
    except Exception as e:
        logger.error(f"Ошибка при генерации инвойса для звезд: {e}")
        return {"ok": False, "error": str(e)}

@app.post("/generate-stars-invoice-link", response_model=Dict[str, Any])
async def generate_stars_invoice_link(request: Request):
    """Генерирует ссылку на оплату звезд через Telegram бота."""
    try:
        data = await request.json()
        logger.info(f"Получен запрос на создание ссылки для оплаты звезд: {data}")
        
        # Получаем обязательные параметры
        user_id = data.get("user_id")
        if not user_id:
            logger.error("Отсутствует user_id в запросе")
            return {"ok": False, "error": "Необходимо указать user_id"}
        
        # Получаем количество звезд и вычисляем цену
        stars_amount = data.get("stars_amount", 10)  # По умолчанию 10 звезд
        
        # Формируем deeplink к боту с командой для покупки звезд
        bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "SmartContentHelperBot")
        
        # Создаем команду для бота, которая запустит процесс покупки
        command = f"buy_stars_{stars_amount}"
        
        # Формируем URL для открытия бота с нужной командой
        telegram_link = f"https://t.me/{bot_username}?start={command}"
        
        return {
            "ok": True, 
            "link": telegram_link,
            "stars_amount": stars_amount
        }
    
    except Exception as e:
        logger.error(f"Ошибка при генерации ссылки для покупки звезд: {e}")
        return {"ok": False, "error": str(e)}

def normalize_db_url(url: str) -> str:
    """Нормализует URL базы данных, преобразуя его в стандартный формат
    для случаев, когда URL содержит нестандартные части, такие как параметры ssl или pool_timeout."""
    # Если URL пустой, вернем пустую строку
    if not url:
        return ""
    
    # Если URL уже в правильном формате (postgresql://user:pass@host:port/database), вернем его как есть
    if url.startswith("postgresql://"):
        # Отсекаем параметры запроса, если они есть
        base_url = url.split("?")[0]
        return base_url
    
    # Если URL в формате postgres://, преобразуем в postgresql://
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    
    # Если URL в каком-то другом формате, просто возвращаем его
    return url

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Вебхук для обработки обновлений от бота Telegram."""
    try:
        # Получаем данные запроса
        data = await request.json()
        logger.info(f"Получен вебхук от Telegram: {data}")

        # Проверяем наличие pre_checkout_query
        if "pre_checkout_query" in data:
            pre_checkout_query = data["pre_checkout_query"]
            query_id = pre_checkout_query.get("id")
            
            if not query_id:
                logger.error("Получен pre_checkout_query без ID")
                return {"ok": False, "error": "Invalid pre_checkout_query format"}
                
            # Получаем токен бота для API запроса
            telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
            if not telegram_token:
                logger.error("Отсутствует TELEGRAM_BOT_TOKEN при обработке pre_checkout_query")
                return {"ok": False, "error": "Отсутствует токен бота"}
                
            # Подтверждаем платеж
            telegram_api_url = f"https://api.telegram.org/bot{telegram_token}/answerPreCheckoutQuery"
            async with httpx.AsyncClient() as client:
                response = await client.post(telegram_api_url, json={
                    "pre_checkout_query_id": query_id,
                    "ok": True
                })
                
                if response.status_code == 200:
                    logger.info(f"Успешно подтвержден pre_checkout_query: {query_id}")
                    return {"ok": True}
                else:
                    logger.error(f"Ошибка при подтверждении pre_checkout_query: {response.status_code} - {response.text}")
                    return {"ok": False, "error": f"Failed to answer pre_checkout_query: {response.text}"}
        
        # Проверяем, есть ли сообщение
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
                        
                        # Проверяем подписки на активность и срок
                        # ИСПРАВЛЕНО: Создаем datetime с UTC timezone
                        current_date = datetime.now(timezone.utc)
                        active_subscriptions = []
                        
                        for subscription in subscription_query.data:
                            end_date = subscription.get("end_date")
                            if end_date:
                                try:
                                    # Преобразуем дату из строки в объект datetime
                                    if isinstance(end_date, str):
                                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                    
                                    # Если дата окончания в будущем, добавляем в активные
                                    if end_date > current_date:
                                        active_subscriptions.append(subscription)
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
                            end_date_str = end_date.strftime('%d.%m.%Y %H:%M')
                    
                    logger.info(f"Результат проверки подписки для {user_id}: has_premium={has_premium}, end_date={end_date_str}")
                    
                    # Формируем текст ответа
                    if has_premium:
                        reply_text = f"✅ У вас активирован ПРЕМИУМ доступ!\nДействует до: {end_date_str}\nОбновите страницу приложения, чтобы увидеть изменения."
                    else:
                        reply_text = "❌ У вас нет активной ПРЕМИУМ подписки.\nДля получения премиум-доступа оформите подписку в приложении."
                    
                    # Отправляем ответ пользователю
                    await send_telegram_message(user_id, reply_text)
                    
                    return {"ok": True, "has_premium": has_premium}
                    
                except Exception as api_error:
                    logger.error(f"Ошибка при проверке премиум-статуса через REST API: {api_error}")
                    # Попробуем альтернативный способ проверки, используя REST API напрямую через httpx
                    try:
                        supabase_url = os.getenv("SUPABASE_URL")
                        supabase_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
                        
                        if not supabase_url or not supabase_key:
                            raise ValueError("Отсутствуют SUPABASE_URL или SUPABASE_KEY")
                        
                        # Формируем запрос к REST API Supabase
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
                                
                                # Проверяем подписки на активность и срок
                                from datetime import datetime, timezone
                                # ИСПРАВЛЕНО: Создаем datetime с UTC timezone
                                current_date = datetime.now(timezone.utc)
                                active_subscriptions = []
                                
                                for subscription in subscriptions:
                                    end_date = subscription.get("end_date")
                                    if end_date:
                                        try:
                                            # Преобразуем дату из строки в объект datetime
                                            if isinstance(end_date, str):
                                                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                            
                                            # Если дата окончания в будущем, добавляем в активные
                                            if end_date > current_date:
                                                active_subscriptions.append(subscription)
                                        except Exception as e:
                                            logger.error(f"Ошибка при обработке даты подписки {end_date}: {e}")
                                
                                # Если есть активные подписки, устанавливаем has_premium = True
                                has_premium = bool(active_subscriptions)
                                end_date_str = 'неизвестно'
                                
                                if active_subscriptions:
                                    # Берем самую позднюю дату окончания
                                    latest_subscription = max(active_subscriptions, key=lambda x: x.get("end_date"))
                                    end_date = latest_subscription.get("end_date")
                                    if isinstance(end_date, str):
                                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                    end_date_str = end_date.strftime('%d.%m.%Y %H:%M')
                                
                                logger.info(f"Результат проверки подписки через httpx для {user_id}: has_premium={has_premium}, end_date={end_date_str}")
                                
                                # Формируем текст ответа
                                if has_premium:
                                    reply_text = f"✅ У вас активирован ПРЕМИУМ доступ!\nДействует до: {end_date_str}\nОбновите страницу приложения, чтобы увидеть изменения."
                                else:
                                    reply_text = "❌ У вас нет активной ПРЕМИУМ подписки.\nДля получения премиум-доступа оформите подписку в приложении."
                                
                                # Отправляем ответ пользователю
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
                return True
            else:
                logger.error(f"Ошибка при отправке сообщения в Telegram: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения в Telegram: {e}")
            return False

