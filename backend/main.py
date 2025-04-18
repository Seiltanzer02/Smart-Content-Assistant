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
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import time # Добавляем модуль time для работы с временем
import requests
from bs4 import BeautifulSoup
import telethon
import aiohttp
from telegram_utils import get_telegram_posts, get_mock_telegram_posts
import move_temp_files
from datetime import datetime

# --- ДОБАВЛЯЕМ ИМПОРТЫ для Unsplash --- 
# from pyunsplash import PyUnsplash # <-- УДАЛЯЕМ НЕПРАВИЛЬНЫЙ ИМПОРТ
from unsplash import Api as UnsplashApi # <-- ИМПОРТИРУЕМ ИЗ ПРАВИЛЬНОГО МОДУЛЯ
from unsplash import Auth as UnsplashAuth # <-- ИМПОРТИРУЕМ ИЗ ПРАВИЛЬНОГО МОДУЛЯ
# ---------------------------------------

# --- ПЕРЕМЕЩАЕМ Логгирование В НАЧАЛО --- 
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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

# --- Модель ответа для детализации поста --- 
class PostDetailsResponse(BaseModel):
    generated_text: str = Field(..., description="Сгенерированный текст поста")
    # Используем новый общий тип
    found_images: List[FoundImage] = Field([], description="Список найденных изображений из разных источников") 
    message: str = Field("", description="Дополнительное сообщение")

# --- Модель для СОЗДАНИЯ/ОБНОВЛЕНИЯ поста --- 
class PostData(BaseModel):
    target_date: str = Field(..., description="Дата поста YYYY-MM-DD")
    topic_idea: str
    format_style: str
    final_text: str
    # Сделаем image_url опциональным
    image_url: Optional[str] = Field(None, description="URL изображения (опционально)")
    # Добавляем поле для массива изображений
    images_ids: Optional[List[str]] = Field(None, description="Список ID изображений")
    # Добавляем поле канала
    channel_name: Optional[str] = Field(None, description="Имя канала, к которому относится пост")

# --- Модель для сохраненного поста (для ответа GET /posts) --- 
class SavedPostResponse(PostData):
    id: str 
    created_at: str 
    updated_at: str
    image_url: Optional[str] = Field(None, description="URL изображения (опционально)")
    images_ids: Optional[List[str]] = Field(None, description="Список ID изображений")
    channel_name: Optional[str] = Field(None, description="Имя канала, к которому относится пост")

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
    
    # Подготавливаем промпты
    system_prompt = """Ты - аналитик контента для Telegram-каналов. 
    Определи основные темы и форматы контента канала. 
    Выдай в JSON формате с полями "themes" и "styles", где каждое содержит массив строк."""
    
    user_prompt = f"""Проанализируй следующие посты и определи основные темы и форматы:
{combined_text}
Выдели 5-7 основных тем и 5-7 форматов подачи. Только JSON формат."""
    
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
            model="deepseek/deepseek-chat",
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
        
        # Проверяем структуру JSON
        if "themes" in analysis_json and "styles" in analysis_json:
            analysis_result = analysis_json
        else:
            logger.warning(f"Некорректная структура JSON: {analysis_json}")
    
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
    if telegram_user_id:
        logger.info(f"Анализ для пользователя Telegram ID: {telegram_user_id}")
    
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
        
        # Извлечение результатов анализа
        if isinstance(analysis_result, dict):
            themes = analysis_result.get("themes", [])
            styles = analysis_result.get("styles", [])
        elif isinstance(analysis_result, tuple) and len(analysis_result) >= 2:
            themes, styles = analysis_result[0], analysis_result[1]
        else:
            logger.warning(f"Неожиданный формат результата анализа: {type(analysis_result)}")
            themes = []
            styles = []
        
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
    
    return AnalyzeResponse(
        themes=themes,
        styles=styles,
        analyzed_posts_sample=sample_posts,
        best_posting_time=best_posting_time,
        analyzed_posts_count=len(posts),
        message=error_message
    )

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
            
        # Преобразуем данные
        ideas = []
        for item in result.data:
            try:
                # Пробуем распарсить JSON-строки
                themes = json.loads(item.get("themes_json", "[]")) if "themes_json" in item else []
                styles = json.loads(item.get("styles_json", "[]")) if "styles_json" in item else []
                
                # Создаем словарь с данными
                idea = {
                    "id": item.get("id"),
                    "channel_name": item.get("channel_name"),
                    "themes": themes,
                    "styles": styles,
                    "created_at": item.get("created_at")
                }
                ideas.append(idea)
            except Exception as e:
                logger.error(f"Ошибка при обработке идеи {item.get('id')}: {e}")
                
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
            
        # Формируем системный промпт
        system_prompt = """Ты - опытный контент-маркетолог и эксперт по планированию публикаций. 
Твоя задача - сгенерировать план публикаций для Telegram-канала на основе указанных тем и стилей/форматов.

Для каждого дня периода предложи идею поста, которая сочетает одну из указанных тем с одним из указанных стилей/форматов.
План должен быть разнообразным - старайся использовать разные комбинации тем и стилей.

Каждая идея должна включать:
1. День периода (число от 1 до заданного количества дней)
2. Конкретную идею поста по выбранной теме (в формате понятного заголовка/концепции, не абстрактно)
3. Формат/стиль поста (из списка указанных стилей)

ОЧЕНЬ ВАЖНО:
- НЕ ИСПОЛЬЗУЙ markdown-форматирование (**, ##, *, _) в идеях и названиях форматов
- НЕ НАЧИНАЙ названия идей с "День X:" или подобных конструкций
- Идеи должны быть короткими заголовками, а не длинными текстами
- Используй простые понятные формулировки без специальных символов

Ответ должен быть в формате: план публикаций из нескольких идей постов."""

        # Формируем запрос к пользователю
        user_prompt = f"""Сгенерируй план контента для Telegram-канала "@{channel_name}" на {period_days} дней.

Темы канала:
{", ".join(themes)}

Стили/форматы постов:
{", ".join(styles)}

Создай план из {period_days} публикаций (по одной на каждый день), используя указанные темы и стили. 
Для каждого поста укажи день, конкретную идею (не общую тему, а конкретный заголовок или концепцию поста) и стиль/формат.

ВАЖНО: Не используй никакого markdown-форматирования в тексте идей и форматов. Названия идей должны быть чистыми текстовыми строками без *, **, #, ##, ### и т.д."""

        # Настройка клиента OpenAI для использования OpenRouter
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        
        # Запрос к API
        logger.info(f"Отправка запроса на генерацию плана контента для канала @{channel_name}")
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,  # Более высокая температура для разнообразия
            max_tokens=2000,
            timeout=120,
            extra_headers={
                "HTTP-Referer": "https://content-manager.onrender.com",
                "X-Title": "Smart Content Assistant"
            }
        )
        
        # Извлечение ответа
        plan_text = response.choices[0].message.content.strip()
        logger.info(f"Получен ответ с планом публикаций: {plan_text[:100]}...")
        
        # Анализ ответа для извлечения плана
        plan_items = []
        
        # Пробуем извлечь идеи из текста
        # Паттерн: число (день), затем тема и стиль
        lines = plan_text.split('\n')
        current_day = None
        current_topic = ""
        current_style = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Пробуем найти упоминание дня
            day_match = re.search(r'(?:день|день)\s*(\d+)[:\.]', line.lower())
            if day_match:
                # Если у нас есть текущий день, сохраняем предыдущую идею
                if current_day is not None and current_topic:
                    plan_items.append(PlanItem(
                        day=current_day,
                        topic_idea=clean_text_formatting(current_topic.strip()),
                        format_style=clean_text_formatting(current_style.strip()) if current_style else "Без указания стиля"
                    ))
                
                # Начинаем новую идею
                current_day = int(day_match.group(1))
                # Извлекаем тему из оставшейся части строки
                rest_of_line = line[day_match.end():].strip(' -:.')
                if rest_of_line:
                    current_topic = rest_of_line
                    current_style = ""
            elif "стиль:" in line.lower() or "формат:" in line.lower():
                # Извлекаем стиль
                style_parts = re.split(r'(?:стиль|формат)[:\s]+', line, flags=re.IGNORECASE, maxsplit=1)
                if len(style_parts) > 1:
                    current_style = style_parts[1].strip()
            elif current_day is not None:
                # Если нет явного указания на день или стиль, добавляем текст к текущей теме
                if not current_topic:
                    current_topic = line
                elif not current_style and ("стиль" in line.lower() or "формат" in line.lower()):
                    current_style = line
                else:
                    current_topic += " " + line
        
        # Добавляем последнюю идею, если она есть
        if current_day is not None and current_topic:
            plan_items.append(PlanItem(
                day=current_day,
                topic_idea=clean_text_formatting(current_topic.strip()),
                format_style=clean_text_formatting(current_style.strip()) if current_style else "Без указания стиля"
            ))
            
        # Если не удалось извлечь идеи через регулярные выражения, используем более простой подход
        if not plan_items:
            day_counter = 1
            for line in lines:
                line = line.strip()
                if not line or len(line) < 10:  # Игнорируем короткие строки
                    continue
                
                # Проверяем, не заголовок ли это
                if re.match(r'^(план|идеи|публикации|контент|posts|список).*$', line.lower()):
                    continue
                
                # Пытаемся найти стиль в строке
                style_match = re.search(r'(?:стиль|формат)[:\s]+(.*?)$', line, re.IGNORECASE)
                if style_match:
                    format_style = cleanup_idea_title(style_match.group(1).strip())
                    topic_idea = cleanup_idea_title(line[:style_match.start()].strip())
                else:
                    # Если явно не указан стиль, берем случайный из списка
                    format_style = random.choice(styles)
                    topic_idea = cleanup_idea_title(line)
                
                plan_items.append(PlanItem(
                    day=day_counter,
                    topic_idea=topic_idea,
                    format_style=format_style
                ))
                day_counter += 1
                
                # Ограничиваем количество дней
                if day_counter > period_days:
                        break
                    
        # Если и сейчас нет идей, генерируем вручную
        if not plan_items:
            for day in range(1, period_days + 1):
                random_theme = random.choice(themes)
                random_style = random.choice(styles)
                plan_items.append(PlanItem(
                    day=day,
                    topic_idea=f"Пост о {random_theme}",
                    format_style=random_style
                ))
                
        # Сортируем по дням
        plan_items.sort(key=lambda x: x.day)
        
        # Обрезаем до запрошенного количества дней
        plan_items = plan_items[:period_days]
        
        # Если план получился короче запрошенного периода, дополняем
        if len(plan_items) < period_days:
            existing_days = set(item.day for item in plan_items)
            for day in range(1, period_days + 1):
                if day not in existing_days:
                    random_theme = random.choice(themes)
                    random_style = random.choice(styles)
                    plan_items.append(PlanItem(
                        day=day,
                        topic_idea=f"Пост о {random_theme}",
                        format_style=random_style
                    ))
        
        # Сортируем по дням еще раз
        plan_items.sort(key=lambda x: x.day)
        
        logger.info(f"Сгенерирован план из {len(plan_items)} идей для канала @{channel_name}")
        return PlanGenerationResponse(plan=plan_items)
                
    except Exception as e:
        logger.error(f"Ошибка при генерации плана: {e}")
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
            
        return result.data
        
    except Exception as e:
        logger.error(f"Ошибка при получении постов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/posts", response_model=SavedPostResponse)
async def create_post(request: Request, post_data: PostData):
    """Создание нового поста."""
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос создания поста без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для создания поста необходимо авторизоваться через Telegram")
        
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        
        # Создаем словарь с данными для сохранения
        post_to_save = post_data.dict()
        post_to_save["user_id"] = int(telegram_user_id)
        
        # Создаем новую запись или обновляем существующую
        if "id" not in post_to_save or not post_to_save["id"]:
            post_to_save["id"] = str(uuid.uuid4())
        
        # Обработка изображений: проверяем, переданы ли ID изображений
        images_ids = post_to_save.get("images_ids", [])
        
        # Если передано только одно изображение через image_url, а images_ids пустой, 
        # добавляем его в базу и сохраняем ID
        if post_to_save.get("image_url") and not images_ids:
            try:
                image_data = {
                    "id": f"post_img_{str(uuid.uuid4())}",
                    "url": post_to_save["image_url"],
                    "preview_url": post_to_save["image_url"],
                    "alt": "Изображение поста",
                    "source": "post",
                    "user_id": int(telegram_user_id),
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                image_result = supabase.table("saved_images").insert(image_data).execute()
                if hasattr(image_result, 'data') and len(image_result.data) > 0:
                    images_ids = [image_data["id"]]
                    post_to_save["images_ids"] = images_ids
            except Exception as img_err:
                logger.error(f"Ошибка при сохранении изображения из URL: {img_err}")
        
        # Сохранение в Supabase
        result = supabase.table("saved_posts").insert(post_to_save).execute()
        
        # Проверка результата
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.error(f"Ошибка при сохранении поста: {result}")
            raise HTTPException(status_code=500, detail="Ошибка при сохранении поста")
            
        post_id = result.data[0]["id"]
        
        # Если есть изображения, сохраняем связи в таблице post_images
        if images_ids and len(images_ids) > 0:
            try:
                for img_id in images_ids:
                    # Проверяем существование изображения
                    image_check = supabase.table("saved_images").select("id").eq("id", img_id).execute()
                    if hasattr(image_check, 'data') and len(image_check.data) > 0:
                        # Связываем пост с изображением
                        post_image_data = {
                            "post_id": post_id,
                            "image_id": img_id,
                            "user_id": int(telegram_user_id)
                        }
                        
                        supabase.table("post_images").insert(post_image_data).execute()
            except Exception as rel_err:
                logger.warning(f"Ошибка при создании связей с изображениями: {rel_err}")
                # Не прерываем обработку, т.к. сам пост уже сохранен
            
        logger.info(f"Пользователь {telegram_user_id} создал пост: {post_data.topic_idea}")
        return result.data[0]
        
    except Exception as e:
        logger.error(f"Ошибка при создании поста: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/posts/{post_id}", response_model=SavedPostResponse)
async def update_post(post_id: str, request: Request, post_data: PostData):
    """Обновление существующего поста."""
    try:
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
        
        # Создаем словарь с данными для обновления
        post_to_update = post_data.dict()
        
        # Обновление в Supabase
        result = supabase.table("saved_posts").update(post_to_update).eq("id", post_id).execute()
        
        # Проверка результата
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.error(f"Ошибка при обновлении поста: {result}")
            raise HTTPException(status_code=500, detail="Ошибка при обновлении поста")
            
        logger.info(f"Пользователь {telegram_user_id} обновил пост {post_id}")
        return result.data[0]
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении поста: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        
        # Удаление из Supabase
        result = supabase.table("saved_posts").delete().eq("id", post_id).execute()
        
        # Проверка результата
        if not hasattr(result, 'data'):
            logger.error(f"Ошибка при удалении поста: {result}")
            raise HTTPException(status_code=500, detail="Ошибка при удалении поста")
            
        logger.info(f"Пользователь {telegram_user_id} удалил пост {post_id}")
        return {"message": "Пост успешно удален"}
        
    except Exception as e:
        logger.error(f"Ошибка при удалении поста: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
            model="deepseek/deepseek-chat",
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
        
        # Использование прямого API запроса вместо клиента
        unsplash_api_url = f"https://api.unsplash.com/search/photos"
        
        # Увеличим количество запрашиваемых изображений для большего разнообразия
        per_page = min(count * 3, 30)  # Запрашиваем в 3 раза больше, но не больше 30
        
        headers = {
            "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}",
            "Accept-Version": "v1"
        }
        
        # Выполняем запросы по каждому ключевому слову
        all_photos = []
        
        for keyword in keywords[:3]:  # Ограничиваем до 3 запросов
            try:
                logger.info(f"Поиск изображений в Unsplash по запросу: {keyword}")
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        unsplash_api_url,
                        headers=headers,
                        params={"query": keyword, "per_page": per_page}
                    )
                    
                if response.status_code != 200:
                    logger.error(f"Ошибка при запросе к Unsplash API: {response.status_code} {response.text}")
                    continue
                    
                # Парсим результаты
                results = response.json()
                if 'results' not in results or not results['results']:
                    logger.warning(f"Нет результатов по запросу '{keyword}'")
                    continue
                    
                # Добавляем найденные фото в общий список
                all_photos.extend(results['results'])
                
                # Сохраняем изображения в базе данных, если она доступна
                if supabase:
                    for photo in results['results']:
                        try:
                            # Проверяем, существует ли уже это изображение в базе
                            image_check = supabase.table("saved_images").select("id").eq("url", photo['urls']['regular']).execute()
                            
                            if not hasattr(image_check, 'data') or len(image_check.data) == 0:
                                # Если изображения нет, сохраняем его
                                image_data = {
                                    "id": photo['id'],
                                    "url": photo['urls']['regular'],
                                    "preview_url": photo['urls']['small'],
                                    "alt": photo.get('description') or photo.get('alt_description') or keyword,
                                    "author": photo['user']['name'],
                                    "author_url": photo['user']['links']['html'],
                                    "source": "unsplash",
                                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                                }
                                
                                supabase.table("saved_images").insert(image_data).execute()
                                logger.debug(f"Сохранено изображение {photo['id']} в базе данных")
                        except Exception as db_error:
                            logger.error(f"Ошибка при сохранении изображения в БД: {db_error}")
                
            except Exception as e:
                logger.error(f"Ошибка при выполнении запроса к Unsplash по ключевому слову '{keyword}': {e}")
                continue
        
        # Если не нашли фото, возвращаем пустой список
        if not all_photos:
            logger.warning(f"Не найдено изображений по всем ключевым словам")
            return []
            
        # Перемешиваем результаты для разнообразия
        random.shuffle(all_photos)
        
        # Берем только нужное количество
        selected_photos = all_photos[:count]
        
        # Формируем результат
        images = []
        for photo in selected_photos:
            images.append(FoundImage(
                id=photo['id'],
                source="unsplash",
                preview_url=photo['urls']['small'],
                regular_url=photo['urls']['regular'],
                description=photo.get('description') or photo.get('alt_description') or query,
                author_name=photo['user']['name'],
                author_url=photo['user']['links']['html']
            ))
        
        logger.info(f"Найдено и отобрано {len(images)} изображений из {len(all_photos)} в Unsplash")
        return images
    except Exception as e:
        logger.error(f"Ошибка при поиске изображений в Unsplash: {e}")
        return []

# --- Endpoint для генерации деталей поста ---
@app.post("/generate-post-details", response_model=PostDetailsResponse)
async def generate_post_details(request: Request, req: GeneratePostDetailsRequest):
    """Генерация деталей поста: текст и изображения."""
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос генерации деталей поста без идентификации пользователя Telegram")
            return PostDetailsResponse(
                generated_text="Для генерации деталей поста необходимо авторизоваться через Telegram",
                found_images=[],
                message="Ошибка авторизации"
            )
            
        topic_idea = req.topic_idea
        format_style = req.format_style
        keywords = req.keywords or []
        post_samples = req.post_samples or []
        
        # Извлекаем имя канала из параметров, если есть
        channel_name = request.query_params.get("channel_name", "Unknown")
        
        # Если нет ключа API для OpenRouter, используем заглушку
        if not OPENROUTER_API_KEY:
            logger.warning("Генерация текста поста невозможна: отсутствует OPENROUTER_API_KEY")
            
            # Генерируем заглушечный текст
            generated_text = f"""Пример текста для поста на тему "{topic_idea}" в стиле "{format_style}".
            
Это заглушка, так как отсутствует API ключ для генерации текста. 
В реальном приложении здесь будет сгенерированный ИИ контент на основе темы и стиля.

#контент #демо #пример"""
            
            # Поиск изображений по ключевым словам или теме
            images = await search_unsplash_images(
                query="",
                count=IMAGE_SEARCH_COUNT,
                topic=topic_idea,
                format_style=format_style,
                post_text=generated_text
            )
            
            return PostDetailsResponse(
                generated_text=generated_text,
                found_images=images[:IMAGE_RESULTS_COUNT],  # Ограничиваем количество
                message="Текст и изображения сгенерированы в демо-режиме (API ключи недоступны)"
            )
            
        # Формируем системный промпт
        system_prompt = """Ты - опытный копирайтер, специализирующийся на создании контента для социальных сетей.
Твоя задача - написать текст поста для Telegram-канала на основе предоставленной идеи, стиля и примеров постов.

Пост должен быть:
1. Содержательным и интересным
2. Соответствовать указанной теме/идее
3. Выдержан в указанном стиле/формате
4. Включать хештеги, если уместно
5. Иметь длину, подходящую для Telegram (рекомендуется 500-1500 символов)

ВАЖНО:
- НЕ ИСПОЛЬЗУЙ маркеры форматирования (**жирный**, *курсив*, ##заголовки)
- Текст должен быть готов к публикации БЕЗ дополнительного редактирования
- Используй только обычный текст и эмодзи
- Не используй маркдаун или другие специальные форматы

Анализируй примеры постов, чтобы понять тональность и стиль канала. Не копируй примеры напрямую, а используй их как ориентир."""

        # Формируем запрос к пользователю
        user_prompt = f"""Напиши текст поста для Telegram-канала "@{channel_name}" на тему/идею:
"{topic_idea}"

Стиль/формат поста:
"{format_style}"

Примеры постов из этого канала для анализа стиля:
{' '.join([f'Пример {i+1}: "{sample[:100]}..."' for i, sample in enumerate(post_samples[:3])])}"

Ключевые слова и фразы для включения в текст (опционально):
{', '.join(keywords) if keywords else 'Нет конкретных ключевых слов, ориентируйся на тему'}

НАПОМИНАНИЕ: Текст должен быть готов к прямой публикации. НЕ используй маркеры форматирования (**, ##, --). Используй обычный текст."""

        # Настройка клиента OpenAI для использования OpenRouter
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        
        # Запрос к API для генерации текста
        logger.info(f"Отправка запроса на генерацию текста поста на тему '{topic_idea}'")
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,  # Средняя креативность
            max_tokens=1500,
            timeout=60,
            extra_headers={
                "HTTP-Referer": "https://content-manager.onrender.com",
                "X-Title": "Smart Content Assistant"
            }
        )
        
        # Извлечение сгенерированного текста
        generated_text = response.choices[0].message.content.strip()
        logger.info(f"Получен текст поста длиной {len(generated_text)} символов")
        
        # Очистка текста от возможных маркеров форматирования
        cleaned_text = generated_text
        # Удаляем маркеры жирного текста
        cleaned_text = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned_text)
        # Удаляем маркеры курсива
        cleaned_text = re.sub(r'\*(.*?)\*', r'\1', cleaned_text)
        # Удаляем маркеры заголовков
        cleaned_text = re.sub(r'#{1,6}\s+(.*?)(?:\n|$)', r'\1\n', cleaned_text)
        # Удаляем другие возможные маркеры
        cleaned_text = re.sub(r'__(.*?)__', r'\1', cleaned_text)
        cleaned_text = re.sub(r'~~(.*?)~~', r'\1', cleaned_text)
        cleaned_text = re.sub(r'\+\+(.*?)\+\+', r'\1', cleaned_text)
        
        logger.info(f"Текст очищен от маркеров форматирования")
        
        # Используем ИИ для поиска оптимальных ключевых слов для изображений
        # Запускаем поиск изображений с улучшенными параметрами
        images = await search_unsplash_images(
            query="",  # Пустой запрос, т.к. используем ключевые слова из ИИ
            count=IMAGE_SEARCH_COUNT,
            topic=topic_idea,
            format_style=format_style,
            post_text=cleaned_text
        )
        
        return PostDetailsResponse(
            generated_text=cleaned_text,
            found_images=images[:IMAGE_RESULTS_COUNT],
            message="Текст и изображения успешно сгенерированы"
        )
    except Exception as e:
        logger.error(f"Ошибка при генерации деталей поста: {e}")
        return PostDetailsResponse(
            generated_text=f"Произошла ошибка при генерации текста: {str(e)}",
            found_images=[],  # Пустой список при ошибке
            message=f"Ошибка: {str(e)}"
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
    
    # Проверка и добавление недостающих столбцов
    if not await check_db_tables():
        logger.error("Ошибка при проверке таблиц в базе данных!")
        # Продолжаем работу приложения даже при ошибке
    
    # Исправление форматирования в JSON полях
    await fix_formatting_in_json_fields()
    
    logger.info("Обслуживающие процессы запущены успешно")

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
    """Исправление схемы базы данных - добавление недостающего столбца updated_at и обновление кэша схемы."""
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
        
        # SQL-команда для добавления столбца и обновления кэша
        sql_query = """
        -- Добавление столбца updated_at в таблицу channel_analysis
        ALTER TABLE channel_analysis 
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        
        -- Обновление схемы кэша для таблиц
        NOTIFY pgrst, 'reload schema';
        """
        
        response = requests.post(url, json={"query": sql_query}, headers=headers)
        
        if response.status_code in [200, 204]:
            logger.info("Столбец updated_at успешно добавлен и кэш схемы обновлен")
            
            # Дополнительно выполним запрос для обновления кэша через второй метод
            refresh_query = "SELECT pg_notify('pgrst', 'reload schema');"
            refresh_response = requests.post(url, json={"query": refresh_query}, headers=headers)
            
            return {
                "success": True, 
                "message": "Схема обновлена, колонка updated_at добавлена и кэш обновлен", 
                "response_code": response.status_code,
                "refresh_response_code": refresh_response.status_code if 'refresh_response' in locals() else None
            }
        else:
            logger.warning(f"Ошибка при добавлении столбца updated_at: {response.status_code} - {response.text}")
            return {
                "success": False, 
                "message": f"Ошибка при добавлении столбца updated_at: {response.status_code}", 
                "response_text": response.text
            }
            
    except Exception as e:
        logger.error(f"Исключение при исправлении схемы: {str(e)}")
        return {"success": False, "message": f"Ошибка: {str(e)}"}

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