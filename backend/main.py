from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request, Form, Depends, Body
import uvicorn
import os
from pydantic import BaseModel, Field, Json
from fastapi import HTTPException
import logging
import asyncio  # Для асинхронных операций и sleep
from fastapi.middleware.cors import CORSMiddleware
from telethon import TelegramClient
from telethon.errors import ChannelInvalidError, ChannelPrivateError, UsernameNotOccupiedError
from dotenv import load_dotenv
import httpx # Для асинхронных HTTP запросов
from collections import Counter
import re # Для очистки текста
from openai import AsyncOpenAI, OpenAIError # Добавляем OpenAI
import json # Для парсинга потенциального JSON ответа
from typing import List, Optional, Dict, Any, Tuple, Union
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Message
import random # <--- Добавляем импорт random
from supabase import create_client, Client, AClient # <--- Импортируем create_client, Client, AClient
from postgrest.exceptions import APIError # <--- ИМПОРТИРУЕМ ИЗ POSTGREST
from telethon.sessions import StringSession # Если используем строку сессии
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PhoneNumberInvalidError, AuthKeyError, ApiIdInvalidError
import uuid # Для генерации уникальных имен файлов
import mimetypes # Для определения типа файла
from telethon.errors import RPCError
import getpass # Для получения пароля
from fastapi.responses import FileResponse, Response # Добавляем Response
from fastapi.staticfiles import StaticFiles
import time # Добавляем модуль time для работы с временем
import requests
from bs4 import BeautifulSoup
import telethon
import aiohttp
from telegram_utils import get_telegram_posts, get_mock_telegram_posts
import move_temp_files
from datetime import datetime, timedelta
import traceback
# Убираем неиспользуемые импорты psycopg2
# import psycopg2 # Добавляем импорт для прямого подключения (если нужно)
# from psycopg2 import sql # Для безопасной вставки имен таблиц/колонок
import shutil # Добавляем импорт shutil

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
            supabase.table("suggested_ideas").select("id").limit(1).execute()
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
    """Генерирует invoice_link для оплаты Stars через Telegram Bot API createInvoiceLink."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        amount = data.get("amount", 1)  # По умолчанию 1 Star, если не указано иное
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id обязателен")
        
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN не задан в окружении")
        
        url = f"https://api.telegram.org/bot{bot_token}/createInvoiceLink"
        
        # Используем amount из запроса или значение по умолчанию
        payment_amount = int(amount)
        
        payload = {
            "title": "Подписка Premium",
            "description": "Подписка Premium на 1 месяц",
            "payload": f"stars_invoice_{user_id}_{int(time.time())}",
            "provider_token": "",
            "currency": "XTR",
            "prices": [{"label": "XTR", "amount": payment_amount}],
            "photo_url": "https://smart-content-assistant.onrender.com/static/premium_sub.jpg"
        }
        
        logger.info(f"Создание инвойса для пользователя {user_id} на сумму {payment_amount} Stars")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            tg_data = response.json()
            if not tg_data.get("ok"):
                logger.error(f"Ошибка Telegram API createInvoiceLink: {tg_data}")
                return {"success": False, "error": tg_data}
            
            invoice_link = tg_data["result"]
            
        logger.info(f"Создан инвойс для пользователя {user_id}: {invoice_link}")
        return {"success": True, "invoice_link": invoice_link}
        
    except Exception as e:
        logger.error(f"Ошибка при генерации Stars invoice link: {e}")
        return {"success": False, "error": str(e)}

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Обработка webhook-запросов от Telegram, включая платежи и ответ на pre_checkout_query."""
    try:
        data = await request.json()
        logger.info(f"Получен webhook от Telegram: {data.get('update_id')}")
        
        # 1. Обработка pre_checkout_query
        pre_checkout_query = data.get("pre_checkout_query")
        if pre_checkout_query:
            query_id = pre_checkout_query.get("id")
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            
            if not bot_token:
                logger.error("TELEGRAM_BOT_TOKEN не задан")
                return {"ok": False, "error": "TELEGRAM_BOT_TOKEN не задан"}
            
            # Автоматически одобряем pre_checkout_query
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/answerPreCheckoutQuery",
                    json={"pre_checkout_query_id": query_id, "ok": True}
                )
                logger.info(f"Ответ на pre_checkout_query {query_id}: {resp.status_code}")
            
            return {"ok": True, "pre_checkout_query": True}
        
        # 2. Обработка успешной оплаты
        message = data.get("message", {})
        successful_payment = message.get("successful_payment")
        
        if successful_payment:
            user_id = message.get("from", {}).get("id")
            payment_id = successful_payment.get("telegram_payment_charge_id")
            
            if not user_id:
                logger.error("Не удалось получить user_id из успешного платежа")
                return {"ok": False, "error": "Не удалось получить user_id"}
            
            logger.info(f"Обработка успешного платежа для пользователя {user_id}, payment_id: {payment_id}")
            
            now = datetime.utcnow()
            start_date = now
            # Продолжительность подписки - 30 дней
            end_date = now + timedelta(days=30)
            
            for attempt in range(3):  # Максимум 3 попытки
                try:
                    # Проверяем, есть ли уже подписка
                    existing = supabase.table("user_subscription").select("*").eq("user_id", user_id).execute()
                    
                    if existing.data and len(existing.data) > 0:
                        # Обновляем подписку
                        update_result = supabase.table("user_subscription").update({
                            "is_active": True,
                            "start_date": start_date.isoformat(),
                            "end_date": end_date.isoformat(),
                            "payment_id": payment_id,
                            "updated_at": now.isoformat()
                        }).eq("user_id", user_id).execute()
                        
                        logger.info(f"Обновлена подписка для пользователя {user_id} до {end_date.isoformat()}")
                    else:
                        # Создаём новую подписку
                        insert_result = supabase.table("user_subscription").insert({
                            "user_id": user_id,
                            "is_active": True,
                            "start_date": start_date.isoformat(),
                            "end_date": end_date.isoformat(),
                            "payment_id": payment_id,
                            "created_at": now.isoformat(),
                            "updated_at": now.isoformat()
                        }).execute()
                        
                        logger.info(f"Создана новая подписка для пользователя {user_id} до {end_date.isoformat()}")
                    
                    # Если успешно, выходим из цикла повторных попыток
                    break
                    
                except Exception as e:
                    logger.error(f"Ошибка при активации подписки (попытка {attempt+1}/3): {e}")
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
        
    except HTTPException as http_ex:
        # Пробрасываем HTTP исключения дальше
        raise http_ex
    except Exception as e:
        logger.error(f"Ошибка при генерации деталей поста: {e}", exc_info=True)
        # Если произошла общая ошибка, возвращаем ошибку 500
        raise HTTPException(status_code=500, detail=f"Ошибка при генерации поста: {str(e)}")

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
    """Проверка наличия необходимых таблиц в базе данных."""
    try:
        # Проверка наличия таблицы suggested_ideas
        result = supabase.table("suggested_ideas").select("id").limit(1).execute()
        logger.info("Таблица suggested_ideas существует и доступна.")
        
        # Автоматическое добавление недостающих столбцов
        try:
            move_temp_files.add_missing_columns()
            logger.info("Проверка и добавление недостающих столбцов выполнены.")
            
            # Явное добавление столбца updated_at в таблицу channel_analysis и обновление кэша схемы
            try:
                # Получение URL и ключа Supabase
                supabase_url = os.getenv('SUPABASE_URL')
                supabase_key = os.getenv('SUPABASE_ANON_KEY')
                
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
        logger.error(f"Ошибка при проверке таблиц: {str(e)}")
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

async def check_db_tables():
    """Проверка наличия необходимых таблиц в базе данных."""
    try:
        # Проверка наличия таблицы suggested_ideas
        result = supabase.table("suggested_ideas").select("id").limit(1).execute()
        logger.info("Таблица suggested_ideas существует и доступна.")
        
        # Автоматическое добавление недостающих столбцов
        try:
            move_temp_files.add_missing_columns()
            logger.info("Проверка и добавление недостающих столбцов выполнены.")
            
            # Явное добавление столбца updated_at в таблицу channel_analysis и обновление кэша схемы
            try:
                # Получение URL и ключа Supabase
                supabase_url = os.getenv('SUPABASE_URL')
                supabase_key = os.getenv('SUPABASE_ANON_KEY')
                
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
        logger.error(f"Ошибка при проверке таблиц: {str(e)}")
        return False

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

@app.get("/subscription/status")
async def get_subscription_status(request: Request):
    user_id = request.query_params.get("user_id")
    telegram_user_id = request.headers.get("X-Telegram-User-Id") or user_id
    
    logger.info(f'Запрос /subscription/status для user_id: {user_id}, X-Telegram-User-Id: {telegram_user_id}')
    
    if not telegram_user_id:
        logger.error("Отсутствует user_id в запросе статуса подписки")
        return {"has_subscription": False, "analysis_count": 0, "post_generation_count": 0, "error": "user_id обязателен"}
    
    try:
        # Преобразуем ID пользователя в число (если возможно)
        try:
            telegram_user_id = int(telegram_user_id)
        except (ValueError, TypeError):
            logger.warning(f"Некорректный ID пользователя при проверке статуса: {telegram_user_id}")
        
        # Получаем данные о подписке, сортированные по дате окончания (сначала самые новые)
        res = supabase.table("user_subscription").select("*").eq("user_id", telegram_user_id).order("end_date", desc=True).execute()
        logger.info(f'Результат запроса к user_subscription: {res.data}')
        
        # Проверяем наличие данных
        subscription = None
        has_subscription = False
        subscription_end_date = None
        
        if res.data and len(res.data) > 0:
            subscription = res.data[0]  # Берем самую новую подписку
            
            # Получаем дату окончания подписки и статус активности
            subscription_end_date = subscription.get("end_date")
            is_active_flag = subscription.get("is_active", False)
            
            now = datetime.now()
            is_expired = False
            
            # Проверяем не истек ли срок подписки
            try:
                if subscription_end_date:
                    if 'Z' in subscription_end_date:
                        end_date_dt = datetime.fromisoformat(subscription_end_date.replace('Z', '+00:00'))
                    else:
                        end_date_dt = datetime.fromisoformat(subscription_end_date)
                    
                    is_expired = end_date_dt <= now
                    logger.info(f"Проверка срока: end_date={end_date_dt}, now={now}, is_expired={is_expired}")
            except Exception as date_error:
                logger.error(f"Ошибка при парсинге даты окончания подписки: {date_error}")
                is_expired = True  # При ошибке парсинга считаем подписку истекшей
            
            # Подписка активна, если флаг is_active=True И срок не истек
            has_subscription = is_active_flag and not is_expired
            
            logger.info(f"Статус подписки для пользователя {telegram_user_id}: has_subscription={has_subscription}, is_active={is_active_flag}, is_expired={is_expired}")
        
        # Получаем статистику использования
        usage_res = supabase.table("user_usage_stats").select("*").eq("user_id", telegram_user_id).execute()
        
        analysis_count = 0
        post_generation_count = 0
        
        if usage_res.data and len(usage_res.data) > 0:
            usage = usage_res.data[0]
            analysis_count = usage.get("analysis_count", 0)
            post_generation_count = usage.get("post_generation_count", 0)
        
        # Формируем ответ
        response = {
            "has_subscription": has_subscription,
            "analysis_count": analysis_count,
            "post_generation_count": post_generation_count
        }
        
        if subscription_end_date:
            response["subscription_end_date"] = subscription_end_date
            
        if subscription and "is_active" in subscription:
            response["is_active_flag"] = subscription["is_active"]
        
        logger.info(f"Отправляем ответ о статусе подписки: {response}")
        return response
        
    except Exception as e:
        logger.error(f"Ошибка при получении статуса подписки: {str(e)}", exc_info=True)
        return {"has_subscription": False, "analysis_count": 0, "post_generation_count": 0, "error": str(e)}

