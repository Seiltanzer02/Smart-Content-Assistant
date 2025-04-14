from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request, Form, Depends
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
from telegram_utils import get_telegram_posts_via_telethon

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

# --- Инициализация Supabase клиента, только если есть ключи --- 
supabase = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info("Клиент Supabase успешно инициализирован.")
    except Exception as e:
        logger.error(f"Ошибка инициализации клиента Supabase: {e}")
else:
    logger.warning("Клиент Supabase не инициализирован из-за отсутствия ключей.")
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
    # Добавляем поле канала
    channel_name: Optional[str] = Field(None, description="Имя канала, к которому относится пост")

# --- Модель для сохраненного поста (для ответа GET /posts) --- 
class SavedPostResponse(PostData): # Наследуем от PostData
    id: str 
    created_at: str 
    updated_at: str
    # Переопределяем для ясности, хотя наследование сработало бы
    image_url: Optional[str] = Field(None, description="URL изображения (опционально)")
    # Добавляем поле канала
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
        
        # Проверяем структуру таблицы, возможно столбец называется иначе или имеет другой формат
        idea_to_save = {
            "channel_name": idea_data.get("channel_name", ""),
            "user_id": idea_data.get("user_id"),
            "themes_json": json.dumps(idea_data.get("themes", [])),
            "styles_json": json.dumps(idea_data.get("styles", []))
            # Используем themes_json и styles_json вместо themes и styles
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
        
        # Сохранение результата анализа в базу данных (если есть telegram_user_id)
        if telegram_user_id:
            try:
                # Создаем словарь с данными для предложения
                idea_data = {
                    "channel_name": username,
                    "themes": themes,
                    "styles": styles,
                    "user_id": telegram_user_id
                }
                # Вызываем функцию сохранения, передавая словарь напрямую или создавая объект, если требуется
                await save_suggested_idea(idea_data)
                logger.info(f"Результаты анализа сохранены для пользователя {telegram_user_id}, канал @{username}")
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
    
    # Временный заглушка для лучшего времени постинга
    best_posting_time = "18:00 - 20:00 МСК"
    
    return AnalyzeResponse(
        themes=themes,
        styles=styles,
        analyzed_posts_sample=sample_posts,
        best_posting_time=best_posting_time,
        analyzed_posts_count=len(posts),
        message=error_message
    )

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

Ответ должен быть в формате: план публикаций из нескольких идей постов."""

        # Формируем запрос к пользователю
        user_prompt = f"""Сгенерируй план контента для Telegram-канала "@{channel_name}" на {period_days} дней.

Темы канала:
{", ".join(themes)}

Стили/форматы постов:
{", ".join(styles)}

Создай план из {period_days} публикаций (по одной на каждый день), используя указанные темы и стили. 
Для каждого поста укажи день, конкретную идею (не общую тему, а конкретный заголовок или концепцию поста) и стиль/формат."""

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
                        topic_idea=current_topic.strip(),
                        format_style=current_style.strip() if current_style else "Без указания стиля"
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
                topic_idea=current_topic.strip(),
                format_style=current_style.strip() if current_style else "Без указания стиля"
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
                    format_style = style_match.group(1).strip()
                    topic_idea = line[:style_match.start()].strip()
                else:
                    # Если явно не указан стиль, берем случайный из списка
                    format_style = random.choice(styles)
                    topic_idea = line
                
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
        post_to_save["user_id"] = telegram_user_id
        
        # Сохранение в Supabase
        result = supabase.table("saved_posts").insert(post_to_save).execute()
        
        # Проверка результата
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.error(f"Ошибка при сохранении поста: {result}")
            raise HTTPException(status_code=500, detail="Ошибка при сохранении поста")
            
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
        post_check = supabase.table("saved_posts").select("id").eq("id", post_id).eq("user_id", telegram_user_id).execute()
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
        post_check = supabase.table("saved_posts").select("id").eq("id", post_id).eq("user_id", telegram_user_id).execute()
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

# --- Функция для поиска изображений в Unsplash ---
async def search_unsplash_images(query: str, count: int = 5) -> List[FoundImage]:
    """Поиск изображений в Unsplash API."""
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
        # Инициализация клиента для работы с Unsplash API
        auth = UnsplashAuth(client_id=UNSPLASH_ACCESS_KEY)
        api = UnsplashApi(auth)
        
        # Поиск изображений
        logger.info(f"Поиск изображений в Unsplash по запросу: {query}")
        search_results = api.search.photos(query, per_page=count)
        
        # Формирование результата
        images = []
        for photo in search_results['results']:
            images.append(FoundImage(
                id=photo['id'],
                source="unsplash",
                preview_url=photo['urls']['small'],
                regular_url=photo['urls']['regular'],
                description=photo.get('description') or photo.get('alt_description') or query,
                author_name=photo['user']['name'],
                author_url=photo['user']['links']['html']
            ))
        
        logger.info(f"Найдено {len(images)} изображений в Unsplash по запросу '{query}'")
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
            search_query = " ".join(keywords) if keywords else topic_idea
            images = await search_unsplash_images(search_query, IMAGE_SEARCH_COUNT)
            
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

Анализируй примеры постов, чтобы понять тональность и стиль канала. Не копируй примеры напрямую, а используй их как ориентир."""

        # Формируем запрос к пользователю
        user_prompt = f"""Напиши текст поста для Telegram-канала "@{channel_name}" на тему/идею:
"{topic_idea}"

Стиль/формат поста:
"{format_style}"

Примеры постов из этого канала для анализа стиля:
{' '.join([f'Пример {i+1}: "{sample[:100]}..."' for i, sample in enumerate(post_samples[:3])])}"

Ключевые слова и фразы для включения в текст (опционально):
{', '.join(keywords) if keywords else 'Нет конкретных ключевых слов, ориентируйся на тему'}"""

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
        
        # Поиск изображений по ключевым словам или теме
        search_query = " ".join(keywords[:2]) if keywords else topic_idea
        images = await search_unsplash_images(search_query, IMAGE_SEARCH_COUNT)
        
        return PostDetailsResponse(
            generated_text=generated_text,
            found_images=images[:IMAGE_RESULTS_COUNT],  # Ограничиваем количество
            message="Текст и изображения успешно сгенерированы"
        )
    except Exception as e:
        logger.error(f"Ошибка при генерации деталей поста: {e}")
        return PostDetailsResponse(
            generated_text=f"Произошла ошибка при генерации текста: {str(e)}",
            found_images=[],  # Пустой список при ошибке
            message=f"Ошибка: {str(e)}"
        )

# Монтирование статических файлов для обслуживания из /static
if SHOULD_MOUNT_STATIC and not SPA_ROUTES_CONFIGURED:
    app.mount("/assets", StaticFiles(directory=os.path.join(static_folder, "assets")), name="assets")
    logger.info(f"Статические файлы смонтированы по пути /assets из {os.path.join(static_folder, 'assets')}")
    SPA_ROUTES_CONFIGURED = True 