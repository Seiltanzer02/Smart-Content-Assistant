from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request, Form, Depends
import uvicorn
import os
from pydantic import BaseModel, Field, Json
from fastapi import HTTPException
import logging
import asyncio
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

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
# СНОВА используем os.getenv для Supabase, проблема была в .env файле
SUPABASE_URL = os.getenv("SUPABASE_URL") 
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") 

# --- Константы (включая имя сессии Telegram) --- 
SESSION_NAME = "telegram_session" # <-- Определяем имя файла сессии
IMAGE_SEARCH_COUNT = 15 # Сколько изображений запрашивать у Unsplash
IMAGE_RESULTS_COUNT = 5 # Сколько изображений показывать пользователю

# --- Теперь проверки ключей --- 
if not OPENROUTER_API_KEY:
    logger.error("Ключ OPENROUTER_API_KEY не найден в .env файле!")
    exit(1)
if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
    logger.error("TELEGRAM_API_ID или TELEGRAM_API_HASH не найдены в .env файле!")
    exit(1)
if not UNSPLASH_ACCESS_KEY:
    logger.warning("Ключ UNSPLASH_ACCESS_KEY не найден в .env файле! Поиск Unsplash будет недоступен.")
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    logger.error("SUPABASE_URL или SUPABASE_ANON_KEY не найдены в .env файле!")
    exit(1)

# --- Инициализация Supabase клиента --- 
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    logger.info("Клиент Supabase успешно инициализирован.")
except Exception as e:
    logger.error(f"Ошибка инициализации клиента Supabase: {e}")
    supabase = None # Устанавливаем в None, чтобы потом проверять
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

# --- Модели для ПРЕДЛОЖЕННЫХ ИДЕЙ ---
class SuggestedIdeaBase(BaseModel):
    topic_idea: str
    format_style: str
    relative_day: Optional[int] = None

class SuggestedIdeaCreate(SuggestedIdeaBase):
    # Пока совпадает с Base, но можно добавить поля специфичные для создания
    pass

class SuggestedIdeaResponse(BaseModel):
    id: str # UUID будет строкой
    relative_day: int
    topic_idea: str
    format_style: str
    is_detailed: bool = False
    created_at: str # Timestamp будет строкой
    channel_name: Optional[str] = None # Добавляем опциональное имя канала

# Добавим модель для ответа на загрузку изображения
class UploadResponse(BaseModel):
    image_url: str

# --- ВОССТАНАВЛИВАЕМ Модель для запроса ДЕТАЛИЗАЦИИ поста --- 
class DetailRequest(BaseModel):
    topic_idea: str
    format_style: str

# --- Вспомогательные функции --- 

# --- ДОБАВЛЯЕМ ОБРАТНО ФУНКЦИЮ АНАЛИЗА КОНТЕНТА --- 
async def analyze_content_with_deepseek(text_list: list[str], api_key: str) -> tuple[list[str], list[str], list[str]]:
    """Анализирует тексты постов для определения тем, стилей и возвращает примеры."""
    # Возвращает кортеж: (список_тем, список_стилей, список_примеров_постов)
    if not api_key:
        logger.warning("OPENROUTER_API_KEY не найден. Анализ контента пропускается.")
        return [], [], []
    if not text_list:
        logger.info("Нет текстов для анализа контента.")
        return [], [], []

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )
    
    # Ограничим количество текста для анализа и для примеров
    posts_for_analysis_count = 10 # Сколько постов анализируем
    posts_for_examples_count = 3  # Сколько примеров вернем
    texts_to_analyze = text_list[:posts_for_analysis_count]
    # Берем первые N постов ИЗ ТЕХ, что анализировали, в качестве примеров
    post_samples_to_return = texts_to_analyze[:posts_for_examples_count] 
    
    combined_text = "\n--- НОВЫЙ ПОСТ ---\n".join(texts_to_analyze)
    max_length = 15000 
    if len(combined_text) > max_length:
        combined_text = combined_text[:max_length] + "... (текст обрезан)"
        
    prompt = (
        f"Проанализируй следующие тексты постов из Telegram-канала, разделенные '--- НОВЫЙ ПОСТ ---'.\n"
        f"1. Определи 5-7 основных тем или ключевых концепций, обсуждаемых в этих постах.\n"
        f"2. Определи 2-3 типичных формата или стиля подачи материала (например: 'Список советов', 'Новость/Анонс', 'Личный опыт/История', 'Вопрос-Ответ', 'Инструкция', 'Юмор/Мем').\n"
        f"Ответ дай СТРОГО в формате JSON:\n"
        '{{"themes": ["Тема 1", ...], "styles": ["Стиль 1", ...]}}\n'
        f"Без какого-либо другого текста до или после JSON.\n\n"
        f"Тексты постов:\n{combined_text}"
    )

    themes = []
    styles = []
    try:
        logger.info(f"Отправка запроса на анализ контента к OpenRouter (модель: deepseek/deepseek-chat)...")
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5, 
            max_tokens=500, 
            response_format={ "type": "json_object" } 
        )
        raw_response_content = response.choices[0].message.content.strip()
        logger.info(f"Получен ответ от OpenRouter/DeepSeek: {raw_response_content}")
        try:
            parsed_json = json.loads(raw_response_content)
            themes = parsed_json.get("themes", [])
            styles = parsed_json.get("styles", [])
            if not isinstance(themes, list) or not isinstance(styles, list):
                 logger.error("Ответ от LLM имеет неверную структуру JSON (themes/styles не списки).")
                 themes, styles = [], [] 
            else:
                 # Очистка на всякий случай
                 themes = [str(t).strip() for t in themes if str(t).strip()]
                 styles = [str(s).strip() for s in styles if str(s).strip()]
        except json.JSONDecodeError:
            logger.error("Не удалось распарсить JSON из ответа LLM.")
        if not themes and not styles:
             logger.warning("Не удалось извлечь темы и стили из ответа OpenRouter/DeepSeek.")
    except OpenAIError as e:
        logger.error(f"Ошибка OpenRouter API при анализе контента: {e}")
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при анализе контента через OpenRouter/DeepSeek: {e}")

    # Возвращаем также примеры постов
    return themes, styles, post_samples_to_return

# --- ВОССТАНАВЛИВАЕМ ФУНКЦИЮ ПАРСИНГА ПЛАНА --- 
def parse_plan_to_ideas(raw_plan: str) -> List[Dict]:
    """Парсит сырой текст плана в список словарей для сохранения в БД."""
    ideas = []
    # Улучшенный регекс для извлечения дня, стиля и темы
    pattern = re.compile(r"^ДЕНЬ\s+(\d+):\s+\[([\w\s/]+)\]\s+(.+)$", re.MULTILINE | re.IGNORECASE)
    matches = pattern.findall(raw_plan)
    
    if not matches:
        # Попробуем без квадратных скобок для стиля
        pattern_no_brackets = re.compile(r"^ДЕНЬ\s+(\d+):\s+([\w\s/]+?)\s+-\s+(.+)$", re.MULTILINE | re.IGNORECASE)
        matches = pattern_no_brackets.findall(raw_plan)
        if not matches:
             # Совсем простой вариант (день: тема)
             pattern_simple = re.compile(r"^ДЕНЬ\s+(\d+):\s+(.+)$", re.MULTILINE | re.IGNORECASE)
             matches_simple = pattern_simple.findall(raw_plan)
             if not matches_simple:
                logger.warning(f"Не найдено совпадений в плане для парсинга: {raw_plan}")
                return []
             # Обработка простого случая (без стиля)
             for day, topic in matches_simple:
                try:
                    ideas.append({
                        "relative_day": int(day),
                        "format_style": "Не указан", # Стиль по умолчанию
                        "topic_idea": topic.strip(),
                        "is_detailed": False
                    })
                except ValueError:
                    logger.warning(f"Не удалось распарсить день {day} в простом формате")
             return ideas

    # Обработка стандартного или формата без скобок
    for match in matches:
        day, style, topic = match # Ожидаем 3 группы
        try:
            ideas.append({
                "relative_day": int(day),
                "format_style": style.strip(),
                "topic_idea": topic.strip(),
                "is_detailed": False
            })
        except ValueError:
            logger.warning(f"Не удалось распарсить день {day}")
            continue
            
    logger.info(f"Распарсено идей: {len(ideas)}")
    return ideas
# --- КОНЕЦ ФУНКЦИИ ПАРСИНГА --- 

# --- Эндпоинты FastAPI --- 
@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI приложение запущено.")
    
    # Проверка доступности классов ошибок Telethon
    logger.info("Проверка импортов Telethon...")
    try:
        # Проверяем, что все импортированные классы ошибок Telethon доступны
        error_classes = [
            SessionPasswordNeededError,
            FloodWaitError, 
            PhoneNumberInvalidError,
            AuthKeyError,
            ApiIdInvalidError,
            RPCError
        ]
        logger.info(f"Проверка импортов Telethon успешна: {len(error_classes)} классов ошибок доступны")
    except ImportError as e:
        logger.error(f"Ошибка импорта классов Telethon: {e}")
    except Exception as e:
        logger.error(f"Ошибка при проверке импортов Telethon: {e}")
    
    # Вывод информации о конфигурации
    logger.info(f"Конфигурация Telegram: API_ID={'Настроен' if TELEGRAM_API_ID else 'Не настроен'}, API_HASH={'Настроен' if TELEGRAM_API_HASH else 'Не настроен'}, SESSION_NAME={'Настроен' if SESSION_NAME else 'Не настроен'}")
    logger.info(f"Конфигурация OpenRouter: API_KEY={'Настроен' if OPENROUTER_API_KEY else 'Не настроен'}")
    logger.info(f"Конфигурация Supabase: URL={'Настроен' if SUPABASE_URL else 'Не настроен'}, KEY={'Настроен' if SUPABASE_ANON_KEY else 'Не настроен'}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("FastAPI приложение остановлено.")

@app.get("/")
async def read_root():
    """Корневой маршрут, возвращает JSON, если запрос от API, или index.html для браузера"""
    # Логируем вызов корневого маршрута
    logger.info("Запрос к корневому пути '/'")
    
    # Если папка статических файлов существует и запрос, вероятно, из браузера
    if SHOULD_MOUNT_STATIC and os.path.exists(os.path.join(static_folder, "index.html")):
        logger.info("Отдаем index.html из статических файлов")
        return FileResponse(os.path.join(static_folder, "index.html"))
    
    # Иначе возвращаем JSON с информацией об API
    return {"message": "Smart Content Assistant Backend API"}

# Определяем модель ответа для /analyze, чтобы включить примеры
class AnalyzeResponse(BaseModel):
    message: str
    themes: List[str]
    styles: List[str]
    analyzed_posts_sample: List[str]
    best_posting_time: str
    analyzed_posts_count: int

# --- Функция для работы с Telegram --- 
async def get_telegram_posts_via_telethon(username: str, limit: int = 20) -> tuple[List[str], Optional[str]]:
    """Подключается к Telegram, получает посты и отключается."""
    posts_text = []
    error_message = None

    if not (TELEGRAM_API_ID and TELEGRAM_API_HASH and SESSION_NAME):
        return [], "Конфигурация Telegram (API_ID, API_HASH, SESSION_NAME) не найдена."

    client = None # Инициализируем как None
    try:
        api_id_int = int(TELEGRAM_API_ID)
        
        # Проверяем существование файла сессии и его целостность
        session_file = f"{SESSION_NAME}.session"
        if os.path.exists(session_file):
            logger.info(f"Найден файл сессии Telegram: {session_file}")
            try:
                # Попытка использовать существующий файл сессии
                client = TelegramClient(SESSION_NAME, api_id_int, TELEGRAM_API_HASH)
            except Exception as e:
                logger.error(f"Ошибка при использовании существующего файла сессии: {e}")
                # Пробуем создать новый файл сессии с временным именем
                new_session_name = f"{SESSION_NAME}_new_{int(time.time())}"
                logger.info(f"Создание новой сессии Telegram с именем: {new_session_name}")
                client = TelegramClient(new_session_name, api_id_int, TELEGRAM_API_HASH)
        else:
            logger.warning(f"Файл сессии {session_file} не найден, создаем новый")
            client = TelegramClient(SESSION_NAME, api_id_int, TELEGRAM_API_HASH)
            
        logger.info(f"Попытка подключения к Telegram (сессия: {client.session.filename})...")
        
        # Проверяем, есть ли бот-токен в переменных окружения
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        
        if bot_token:
            # Используем бот-токен для авторизации вместо интерактивного ввода
            logger.info("Используем бот-токен для авторизации в Telegram")
            try:
                await client.start(bot_token=bot_token)
                logger.info("Авторизация с использованием бот-токена успешна")
            except Exception as e:
                logger.error(f"Ошибка при авторизации с бот-токеном: {e}")
                # Вместо попытки создать гостевую сессию, используем примеры постов
                error_message = "Невозможно авторизоваться в Telegram. Используем примеры постов."
                return get_sample_posts(username), error_message
        else:
            # Без бот-токена сразу используем примеры постов
            logger.warning("Бот-токен не найден, невозможно авторизоваться в Telegram")
            error_message = "Бот-токен не настроен. Используем примеры постов."
            return get_sample_posts(username), error_message
            
        # Проверка авторизации
        try:
            is_authorized = await client.is_user_authorized()
            if is_authorized:
                logger.info("Авторизация в Telegram успешна.")
            else:
                logger.warning("Не авторизован в Telegram. Используем примеры постов.")
                return get_sample_posts(username), "Не авторизован в Telegram."
        except Exception as e:
            logger.error(f"Ошибка при проверке авторизации: {e}")
            return get_sample_posts(username), f"Ошибка при проверке авторизации: {e}"
        
        # Попытка получения информации о канале
        logger.info(f"Получение информации о канале @{username}...")
        try:
            # Пробуем получить сущность канала
            channel = await client.get_entity(username)
            logger.info(f"Канал @{username} найден. Получение последних {limit} постов...")
            
            # Получаем сообщения из канала
            messages = await client.get_messages(channel, limit=limit)
            for message in messages:
                if isinstance(message, Message) and message.text: # Берем только сообщения с текстом
                    posts_text.append(message.text)
            logger.info(f"Получено {len(posts_text)} текстовых постов.")
            
            # Если не нашли текстовых постов, выполняем резервную стратегию
            if not posts_text:
                logger.warning(f"Текстовые посты не найдены в канале @{username}. Возвращаем заглушки.")
                # Возвращаем заглушки для анализа (примеры постов)
                return get_sample_posts(username), None
                
        except ValueError as e:
            # Обработка ошибки, если username не является валидным entity
            error_message = f"Не удалось найти канал или пользователя @{username}: {e}"
            logger.error(error_message)
            # Возвращаем заглушки для анализа (примеры постов)
            return get_sample_posts(username), None
        except Exception as e:
            # Другие возможные ошибки Telethon при получении entity или сообщений
            error_message = f"Ошибка при работе с каналом @{username}: {type(e).__name__}: {e}"
            logger.exception(error_message)
            # Возвращаем заглушки для анализа (примеры постов)
            return get_sample_posts(username), None

    except SessionPasswordNeededError:
         error_message = "Требуется пароль двухфакторной аутентификации Telegram."
         logger.error(error_message)
    except PhoneNumberInvalidError:
        error_message = "Введен неверный номер телефона для Telegram."
        logger.error(error_message)
    except FloodWaitError as e:
        error_message = f"Telegram попросил подождать {e.seconds} секунд (флуд-контроль). Попробуйте позже."
        logger.error(error_message)
    except AuthKeyError:
        error_message = "Проблема с ключом авторизации Telegram. Возможно, устаревшая сессия."
        logger.error(error_message)
    except ApiIdInvalidError:
        error_message = "Недействительный API ID для Telegram. Проверьте настройки TELEGRAM_API_ID."
        logger.error(error_message)
    except RPCError as e:
        error_message = f"Ошибка удаленного вызова процедур Telegram: {str(e)}"
        logger.error(error_message)
    except Exception as e:
        error_message = f"Ошибка при подключении/авторизации в Telegram: {type(e).__name__}: {e}"
        logger.exception(error_message)
    finally:
        # Отключаемся в любом случае, если клиент был создан и подключен
        if client and client.is_connected():
            try:
                await client.disconnect()
                logger.info("Отключено от Telegram.")
            except Exception as e:
                 logger.error(f"Ошибка при отключении от Telegram: {e}", exc_info=True)
            
    return posts_text, error_message

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_channel(request: Request, analyze_request: AnalyzeRequest):
    # Получаем Telegram User ID из заголовка
    user_id = None
    try:
        user_id = request.headers.get("x-telegram-user-id")
        if user_id:
            logger.info(f"Запрос на анализ канала от пользователя: {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при получении User ID: {e}")
    
    # Продолжаем с анализом канала
    username = analyze_request.username.lstrip('@')
    logger.info(f"Получен запрос на анализ канала: @{username}")

    posts = []
    error_messages = []

    # --- СТРАТЕГИЯ 1: Получение постов через Telethon (как было раньше) ---
    try:
        logger.info(f"Попытка получить посты через Telethon для канала @{username}")
        telethon_posts, telethon_error = await get_telegram_posts_via_telethon(username)
        
        if telethon_posts:
            logger.info(f"Успешно получено {len(telethon_posts)} постов через Telethon")
            posts = telethon_posts
            error_message = None
        elif telethon_error:
            error_messages.append(f"Ошибка Telethon: {telethon_error}")
            logger.warning(f"Не удалось получить посты через Telethon: {telethon_error}")
    except Exception as e:
        error_message = f"Непредвиденная ошибка Telethon: {str(e)}"
        error_messages.append(error_message)
        logger.error(f"Непредвиденная ошибка при получении постов через Telethon: {error_message}")
    
    # --- СТРАТЕГИЯ 2: Если Telethon не сработал, пробуем через HTTP парсинг ---
    if not posts:
        try:
            logger.info(f"Попытка получить посты через HTTP парсинг для канала @{username}")
            http_posts = await get_telegram_posts_via_http(username)
            
            if http_posts and len(http_posts) > 0:
                logger.info(f"Успешно получено {len(http_posts)} постов через HTTP парсинг")
                posts = http_posts
            else:
                logger.warning(f"Не удалось получить посты через HTTP парсинг (пустой результат)")
                error_messages.append("HTTP парсинг вернул пустой результат")
        except Exception as e:
            error_message = f"Ошибка HTTP парсинга: {str(e)}"
            error_messages.append(error_message)
            logger.error(f"Ошибка при получении постов через HTTP парсинг: {error_message}")
    
    # --- СТРАТЕГИЯ 3: Если оба метода не сработали, используем примеры постов ---
    if not posts:
        logger.warning(f"Не удалось получить посты ни через Telethon, ни через HTTP. Используем примеры.")
        posts = get_sample_posts(username)
        error_messages.append("Использованы примеры постов, так как не удалось получить реальные данные")
    
    # Проверяем, есть ли посты после всех попыток
    if len(posts) == 0:
        # Если совсем нет постов (что маловероятно, т.к. у нас есть заглушки), возвращаем ошибку
        detail = "Не удалось получить посты для анализа: " + "; ".join(error_messages)
        raise HTTPException(status_code=404, detail=detail)
    
    # --- АНАЛИЗ КОНТЕНТА ---
    logger.info(f"Анализ {len(posts)} постов канала @{username}...")
    
    try:
        themes, styles, post_samples = await analyze_content_with_deepseek(posts, OPENROUTER_API_KEY)
        
        # Если не получили темы/стили из API, добавим примеры для демонстрации
        if not themes:
            logger.warning("Не получены темы от API анализа. Используем заглушки.")
            themes = ["Информационные технологии", "Образование", "Саморазвитие", "Бизнес", "Маркетинг"]
        
        if not styles:
            logger.warning("Не получены стили от API анализа. Используем заглушки.")
            styles = ["Новость/Анонс", "Список советов", "Инструкция"]
        
        logger.info(f"Анализ канала @{username} завершен успешно")
    except Exception as e:
        logger.error(f"Ошибка при анализе контента: {str(e)}")
        # Используем заглушки в случае ошибки
        themes = ["Информационные технологии", "Образование", "Саморазвитие", "Бизнес", "Маркетинг"]
        styles = ["Новость/Анонс", "Список советов", "Инструкция"]
        post_samples = posts[:3] if len(posts) >= 3 else posts
    
    # Временная заглушка для лучшего времени публикации
    best_posting_time = "18:00 - 20:00 МСК"
    
    # Формируем сообщение на основе способа получения постов
    using_samples = len(error_messages) > 0 and "примеры" in error_messages[-1]
    message = f"Анализ для канала @{username} завершен." + (" (использованы примеры постов)" if using_samples else "")
    
    return AnalyzeResponse(
        message=message,
        themes=themes, 
        styles=styles,
        analyzed_posts_sample=post_samples if post_samples else posts[:min(3, len(posts))],
        best_posting_time=best_posting_time,
        analyzed_posts_count=len(posts) 
    )

@app.post("/generate-plan", response_model=List[SuggestedIdeaResponse])
async def generate_plan(request: Request, plan_request: PlanGenerationRequest):
    """Генерирует и СОХРАНЯЕТ в БД список идей для постов для КОНКРЕТНОГО канала."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Сервис базы данных недоступен.")

    # Получаем Telegram User ID из заголовка
    user_id = None
    if "x-telegram-user-id" in request.headers:
        try:
            user_id = int(request.headers["x-telegram-user-id"])
        except ValueError:
            logger.warning(f"Некорректный Telegram User ID в заголовке: {request.headers.get('x-telegram-user-id')}")

    # --- ИНИЦИАЛИЗАЦИЯ КЛИЕНТА ВНУТРИ ФУНКЦИИ --- 
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="Ключ OPENROUTER_API_KEY не настроен.")
    
    # Создаем клиент OpenRouter/OpenAI здесь
    client = AsyncOpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1" 
    )
    # --------------------------------------------

    current_channel = plan_request.channel_name # Получаем имя канала из запроса
    user_info = f", пользователь: {user_id}" if user_id else ""
    logger.info(f"Запрос генерации плана на {plan_request.period_days} дней для канала '{current_channel}'{user_info}...")

    prompt = f"""Создай контент-план на {plan_request.period_days} дней для Telegram-канала.
Основные темы: {', '.join(plan_request.themes)}
Предпочтительные стили/форматы: {', '.join(plan_request.styles)}

Для каждого дня предложи ОДНУ идею поста в формате:
ДЕНЬ <N>: [<СТИЛЬ/ФОРМАТ>] <ТЕМА_ПОСТА>

Пример:
ДЕНЬ 1: [Личный опыт/История] Как я начал заниматься трейдингом
ДЕНЬ 2: [Анализ/Инструкция] Основы технического анализа для новичков
...
ДЕНЬ {plan_request.period_days}: [<СТИЛЬ/ФОРМАТ>] <ТЕМА_ПОСТА>

ВАЖНО: Выведи только строки "ДЕНЬ N: ...", без вступлений и заключений.
"""

    logger.info(f"Запрос генерации плана на {plan_request.period_days} дней...")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Используем локально созданный 'client'
            completion = await client.chat.completions.create(
                model="deepseek/deepseek-chat", # Используем модель для генерации идей
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500
            )
            raw_plan = completion.choices[0].message.content
            logger.info(f"Сырой план получен: \n{raw_plan}")
            
            if not raw_plan:
                 raise ValueError("API вернуло пустой план.")

            ideas_to_save_raw = parse_plan_to_ideas(raw_plan) # Функция парсинга
            
            if not ideas_to_save_raw:
                 logger.warning("Не удалось распарсить идеи из ответа API. Попытка {attempt + 1}")
                 if attempt == max_retries - 1:
                      raise ValueError("Не удалось извлечь идеи из ответа API после нескольких попыток.")
                 await asyncio.sleep(1) # Небольшая задержка перед повторной попыткой
                 continue # Переходим к следующей попытке

            # Добавляем channel_name и user_id к каждой идее перед сохранением
            ideas_to_save = [
                {**idea, "channel_name": current_channel, "user_id": user_id} for idea in ideas_to_save_raw
            ]

            # --- Удаление старых идей ТОЛЬКО для этого канала и пользователя --- 
            try:
                delete_query = supabase.table('suggested_ideas').delete().eq('channel_name', current_channel)
                
                # Если есть Telegram User ID, также ограничиваем удаление идеями этого пользователя
                if user_id:
                    delete_query = delete_query.eq('user_id', user_id)
                    logger.info(f"Удаление старых предложенных идей для канала '{current_channel}' и пользователя {user_id}...")
                else:
                    logger.info(f"Удаление старых предложенных идей для канала '{current_channel}'...")
                
                delete_response = delete_query.execute()
                
                api_error = getattr(delete_response, 'error', None)
                if api_error:
                     logger.error(f"Ошибка при удалении старых идей для канала '{current_channel}': {api_error.message}")
                else:
                     deleted_count = len(getattr(delete_response, 'data', []))
                     logger.info(f"Старые идеи успешно удалены (или их не было). Строк: {deleted_count}")
            except Exception as e:
                 logger.exception(f"Непредвиденная ошибка при удалении старых идей: {e}")
                 # Не прерываем выполнение, пробуем добавить новые
            # --- Конец удаления --- 

            # Сохранение новых идей (уже с channel_name и user_id)
            try:
                insert_response = supabase.table('suggested_ideas').insert(ideas_to_save).execute()
                if not insert_response.data:
                    error_detail = getattr(getattr(insert_response, 'error', None), 'message', "Неизвестная ошибка сохранения идей")
                    logger.error(f"Supabase insert идей вернул пустые данные. Ошибка: {error_detail}")
                    raise HTTPException(status_code=500, detail=f"Не удалось сохранить идеи: {error_detail}")
                
                # Возвращаем сохраненные данные с ID и created_at
                saved_ideas_data = insert_response.data
                # Преобразуем в модель ответа (Pydantic сам обработает Optional поля)
                response_models = [SuggestedIdeaResponse(**idea) for idea in saved_ideas_data]
                logger.info(f"Успешно сохранено {len(response_models)} идей для канала '{current_channel}'{user_info}.")
                return response_models # Успех, выходим из цикла
                
            except APIError as e:
                 logger.error(f"Ошибка API Supabase при сохранении идей: {e.message}", exc_info=True)
                 raise HTTPException(status_code=getattr(e, 'status_code', 500), detail=f"Ошибка базы данных при сохранении идей: {e.message}")
            except Exception as e:
                 logger.exception(f"Непредвиденная ошибка при сохранении идей: {e}")
                 raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера при сохранении идей: {str(e)}")

        except OpenAIError as e:
            logger.error(f"Ошибка OpenAI API при генерации плана (Попытка {attempt + 1}): {e}", exc_info=True)
            # Обработка специфичных ошибок API (rate limit, auth, etc.)
            if isinstance(e, RateLimitError):
                 raise HTTPException(status_code=429, detail="Превышен лимит запросов к API генерации.")
            if isinstance(e, AuthenticationError):
                 raise HTTPException(status_code=401, detail="Ошибка аутентификации с API генерации.")
            # Другие ошибки OpenAI
            if attempt == max_retries - 1:
                 raise HTTPException(status_code=503, detail=f"Ошибка API генерации: {e}")
        except ValueError as e:
             logger.error(f"Ошибка значения при генерации плана (Попытка {attempt + 1}): {e}", exc_info=True)
             if attempt == max_retries - 1:
                  raise HTTPException(status_code=500, detail=f"Ошибка обработки данных: {e}")
        except Exception as e:
            logger.exception(f"Непредвиденная ошибка при генерации плана (Попытка {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                 raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера при генерации плана: {str(e)}")
        
        # Если дошли сюда, значит была ошибка, ждем и пробуем снова
        await asyncio.sleep(2 ** attempt) # Экспоненциальная задержка (1, 2, 4 сек)

    # Если вышли из цикла без return, значит все попытки не удались
    raise HTTPException(status_code=500, detail="Не удалось сгенерировать план после нескольких попыток.")

# --- ВОССТАНАВЛИВАЕМ ЭНДПОИНТ GET /posts --- 
@app.get("/posts", response_model=List[SavedPostResponse])
async def get_saved_posts(request: Request, channel_name: Optional[str] = Query(None, description="Фильтр по имени канала")):
    """Получает список всех сохраненных постов из базы данных Supabase с опциональной фильтрацией по каналу."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Сервис базы данных недоступен.")
    
    # Получаем Telegram User ID из заголовка
    user_id = None
    if "x-telegram-user-id" in request.headers:
        try:
            user_id = int(request.headers["x-telegram-user-id"])
        except ValueError:
            logger.warning(f"Некорректный Telegram User ID в заголовке: {request.headers.get('x-telegram-user-id')}")
            # Не возвращаем ошибку, просто продолжаем без фильтрации (для обратной совместимости)
    
    user_filter_info = f", для пользователя: {user_id}" if user_id else ""
    logger.info(f"Запрос списка сохраненных постов{' для канала: ' + channel_name if channel_name else ''}{user_filter_info}...")
    
    try:
        # Базовый запрос
        query = supabase.table('saved_posts').select("*")
        
        # Добавляем фильтры
        if channel_name:
            query = query.eq('channel_name', channel_name)
        
        # Если есть Telegram User ID, фильтруем по нему
        if user_id:
            query = query.eq('user_id', user_id)
            
        # Сортировка и выполнение
        response = query.order('target_date', desc=False).execute()
        
        if hasattr(response, 'data') and isinstance(response.data, list):
            logger.info(f"Ответ Supabase (select): {len(response.data)} постов{' для канала ' + channel_name if channel_name else ''}{user_filter_info}.")
            return [SavedPostResponse(**post) for post in response.data]
        else:
             logger.warning(f"Не получены данные или некорректный формат ответа от Supabase (select posts): {response}")
             return []
             
    except APIError as e:
        logger.error(f"Ошибка API Supabase при получении постов: {e.message} (Code: {e.code})", exc_info=True)
        raise HTTPException(status_code=getattr(e, 'status_code', 500), detail=f"Ошибка базы данных: {e.message}")
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при получении постов: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

# --- ВОССТАНАВЛИВАЕМ CRUD для постов --- 
@app.post("/posts", response_model=SavedPostResponse, status_code=201)
async def create_saved_post(request: Request, post_data: PostData):
    """Создает новую запись поста в базе данных."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Сервис базы данных недоступен.")
    
    # Получаем Telegram User ID из заголовка
    user_id = None
    if "x-telegram-user-id" in request.headers:
        try:
            user_id = int(request.headers["x-telegram-user-id"])
        except ValueError:
            logger.warning(f"Некорректный Telegram User ID в заголовке: {request.headers.get('x-telegram-user-id')}")
    
    channel_info = f", Канал='{post_data.channel_name}'" if post_data.channel_name else ""
    user_info = f", User ID={user_id}" if user_id else ""
    logger.info(f"Запрос на создание поста: Дата={post_data.target_date}, Тема='{post_data.topic_idea}'{channel_info}{user_info}")
    
    # Преобразуем Pydantic модель в словарь
    data_to_insert = post_data.model_dump() 
    
    # Добавляем Telegram User ID в данные, если он доступен
    if user_id:
        data_to_insert["user_id"] = user_id
    
    try:
        response = supabase.table('saved_posts').insert(data_to_insert).execute()
        
        if not response.data:
            error_detail = getattr(getattr(response, 'error', None), 'message', "Неизвестная ошибка сохранения поста")
            logger.error(f"Supabase insert поста вернул пустые данные. Ошибка: {error_detail}")
            raise HTTPException(status_code=500, detail=f"Не удалось сохранить пост: {error_detail}")

        created_post_data = response.data[0]
        logger.info(f"Пост успешно создан с ID: {created_post_data.get('id')}")
        return SavedPostResponse(**created_post_data)

    except APIError as e:
        logger.error(f"Ошибка API Supabase при создании поста: {e.message}", exc_info=True)
        raise HTTPException(status_code=getattr(e, 'status_code', 500), detail=f"Ошибка базы данных при создании поста: {e.message}")
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при создании поста: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@app.put("/posts/{post_id}", response_model=SavedPostResponse)
async def update_saved_post(request: Request, post_id: str, post_data: PostData):
    """Обновляет существующий пост по его ID."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Сервис базы данных недоступен.")
    
    # Получаем Telegram User ID из заголовка
    user_id = None
    if "x-telegram-user-id" in request.headers:
        try:
            user_id = int(request.headers["x-telegram-user-id"])
        except ValueError:
            logger.warning(f"Некорректный Telegram User ID в заголовке: {request.headers.get('x-telegram-user-id')}")
    
    logger.info(f"Запрос на обновление поста ID: {post_id}")
    
    # Преобразуем Pydantic модель в словарь
    data_to_update = post_data.model_dump() 
    
    # Если есть Telegram User ID, добавляем его в данные для обновления
    if user_id:
        data_to_update["user_id"] = user_id

    try:
        # Базовый запрос
        query = supabase.table('saved_posts').update(data_to_update).eq('id', post_id)
        
        # Если есть Telegram User ID, также проверяем, что обновляемый пост принадлежит пользователю
        if user_id:
            query = query.eq('user_id', user_id)
            
        response = query.execute()
        
        if not response.data:
            # Проверяем, была ли ошибка или просто пост не найден
            error_detail = getattr(getattr(response, 'error', None), 'message', None)
            if error_detail:
                 logger.error(f"Ошибка API Supabase при обновлении поста {post_id}: {error_detail}")
                 raise HTTPException(status_code=500, detail=f"Ошибка базы данных при обновлении: {error_detail}")
            else:
                 # Ошибки нет, но данных тоже нет - значит пост не найден или не принадлежит пользователю
                 logger.warning(f"Пост с ID {post_id} не найден для обновления или не принадлежит пользователю {user_id}.")
                 raise HTTPException(status_code=404, detail=f"Пост с ID {post_id} не найден или у вас нет прав на его редактирование.")

        updated_post_data = response.data[0]
        logger.info(f"Пост с ID {post_id} успешно обновлен.")
        return SavedPostResponse(**updated_post_data)

    except APIError as e:
        logger.error(f"Ошибка API Supabase при обновлении поста {post_id}: {e.message}", exc_info=True)
        raise HTTPException(status_code=getattr(e, 'status_code', 500), detail=f"Ошибка базы данных при обновлении: {e.message}")
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при обновлении поста {post_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера при обновлении: {str(e)}")

@app.delete("/posts/{post_id}", status_code=204)
async def delete_saved_post(request: Request, post_id: str):
    """Удаляет пост по его ID."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Сервис базы данных недоступен.")
    
    # Получаем Telegram User ID из заголовка
    user_id = None
    if "x-telegram-user-id" in request.headers:
        try:
            user_id = int(request.headers["x-telegram-user-id"])
        except ValueError:
            logger.warning(f"Некорректный Telegram User ID в заголовке: {request.headers.get('x-telegram-user-id')}")
    
    logger.info(f"Запрос на удаление поста ID: {post_id}" + (f" от пользователя {user_id}" if user_id else ""))
    
    try:
        # Базовый запрос
        query = supabase.table('saved_posts').delete()
        
        # Добавляем фильтры
        query = query.eq('id', post_id)
        
        # Если есть Telegram User ID, также проверяем, что удаляемый пост принадлежит пользователю
        if user_id:
            query = query.eq('user_id', user_id)
            
        response = query.execute()

        # Проверяем, была ли ошибка
        error_detail = getattr(getattr(response, 'error', None), 'message', None)
        if error_detail:
            logger.error(f"Ошибка API Supabase при удалении поста {post_id}: {error_detail}")
            raise HTTPException(status_code=500, detail=f"Ошибка базы данных при удалении: {error_detail}")
            
        # Проверяем, был ли пост реально удален (data будет не пустой, если что-то удалили)
        if not response.data:
             if user_id:
                  logger.warning(f"Пост с ID {post_id} не найден для удаления (или уже удален) или не принадлежит пользователю {user_id}.")
             else:
                  logger.warning(f"Пост с ID {post_id} не найден для удаления (или уже удален).")
        else:
             logger.info(f"Пост с ID {post_id} успешно удален.")
             
        # В любом случае возвращаем 204 No Content, если не было ошибки API
        return # FastAPI автоматически вернет 204 статус

    except APIError as e:
        logger.error(f"Ошибка API Supabase при удалении поста {post_id}: {e.message}", exc_info=True)
        raise HTTPException(status_code=getattr(e, 'status_code', 500), detail=f"Ошибка базы данных при удалении: {e.message}")
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при удалении поста {post_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера при удалении: {str(e)}")
# --- КОНЕЦ CRUD для постов --- 

# --- Эндпоинт GET /ideas ---
@app.get("/ideas", response_model=List[SuggestedIdeaResponse])
async def get_suggested_ideas(request: Request, channel_name: Optional[str] = Query(None, description="Filter ideas by channel name")):
    """Получает список предложенных идей, опционально фильтруя по имени канала."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Сервис базы данных недоступен.")

    # Получаем Telegram User ID из заголовка
    user_id = None
    if "x-telegram-user-id" in request.headers:
        try:
            user_id = int(request.headers["x-telegram-user-id"])
        except ValueError:
            logger.warning(f"Некорректный Telegram User ID в заголовке: {request.headers.get('x-telegram-user-id')}")
    
    user_filter_info = f", для пользователя: {user_id}" if user_id else ""
    logger.info(f"Запрос списка предложенных идей (канал: {channel_name or 'все'}){user_filter_info}")
    
    try:
        query = supabase.table('suggested_ideas').select("*").order('relative_day', desc=False)
        
        # Применяем фильтры
        if channel_name:
            # Фильтруем по имени канала, если оно передано
            query = query.eq('channel_name', channel_name)
        
        # Если есть Telegram User ID, фильтруем по нему
        if user_id:
            query = query.eq('user_id', user_id)

        response = query.execute()

        if hasattr(response, 'data') and isinstance(response.data, list):
            logger.info(f"Получено {len(response.data)} идей для канала '{channel_name or 'все'}'{user_filter_info}.")
            # Преобразуем в модель ответа
            return [SuggestedIdeaResponse(**idea) for idea in response.data]
        else:
            logger.warning(f"Не получены данные или некорректный формат ответа от Supabase (select ideas): {response}")
            return [] # Возвращаем пустой список, а не None

    except APIError as e:
        logger.error(f"Ошибка API Supabase при получении идей: {e.message}", exc_info=True)
        raise HTTPException(status_code=getattr(e, 'status_code', 500), detail=f"Ошибка базы данных: {e.message}")
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при получении идей: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

# --- Эндпоинт POST /upload-image ---
@app.post("/upload-image", response_model=UploadResponse, status_code=201)
async def upload_image(file: UploadFile = File(...)):
    """Загружает изображение в Supabase Storage."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Сервис базы данных недоступен.")
        
    logger.info(f"Запрос на загрузку файла: {file.filename}")
    
    # Проверка размера файла (например, 5MB)
    max_size = 5 * 1024 * 1024 
    size = await file.read() # Читаем файл для получения размера
    await file.seek(0) # Возвращаем указатель в начало файла!
    if len(size) > max_size:
        raise HTTPException(status_code=413, detail="Файл слишком большой. Максимальный размер: 5MB.")
        
    # Определение MIME типа
    mime_type, _ = mimetypes.guess_type(file.filename)
    if not mime_type or not mime_type.startswith('image/'):
         raise HTTPException(status_code=400, detail="Неподдерживаемый тип файла. Пожалуйста, загрузите изображение.")

    # Генерируем уникальное имя файла
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"uploads/{uuid.uuid4()}{file_extension}"
    # --- ИСПРАВЛЯЕМ ИМЯ БАКЕТА --- 
    bucket_name = "post-images" # <--- ИСПОЛЬЗУЕМ ДЕФИС
    # -----------------------------

    try:
        logger.info(f"Загрузка файла '{file.filename}' в Supabase Storage: '{bucket_name}/{unique_filename}' с типом {mime_type}...")
        file_content = await file.read()
        
        response = supabase.storage.from_(bucket_name).upload(
            path=unique_filename,
            file=file_content, 
            file_options={"content-type": mime_type, "upsert": "false"}
        )
        
        public_url_response = supabase.storage.from_(bucket_name).get_public_url(unique_filename)
        
        if not public_url_response or isinstance(public_url_response, dict) and public_url_response.get('error'): # Уточняем проверку ошибки URL
             logger.error(f"Файл загружен, но не удалось получить public URL: {public_url_response}")
             raise HTTPException(status_code=500, detail="Файл загружен, но не удалось получить публичный URL.")

        logger.info(f"Файл успешно загружен. Public URL: {public_url_response}")
        return UploadResponse(image_url=public_url_response)

    except APIError as e:
        # Обработка ошибок Supabase Storage (например, бакет не найден, RLS)
        logger.error(f"Ошибка API Supabase Storage при загрузке файла: {getattr(e, 'message', str(e))} (Code: {getattr(e, 'code', 'N/A')}, Status: {getattr(e, 'status_code', 'N/A')})", exc_info=False) # Убираем exc_info для APIError, так как сообщение часто самодостаточно
        error_detail = f"Ошибка хранилища: {getattr(e, 'message', 'Неизвестная ошибка API')}"
        status_code = getattr(e, 'status_code', 500)
        # Конкретизируем сообщение об ошибке для 'Bucket not found'
        if isinstance(getattr(e, 'message', {}), dict) and e.message.get("error") == "Bucket not found":
            error_detail = f"Хранилище (bucket) с именем '{bucket_name}' не найдено в Supabase. Убедитесь, что оно создано."
            status_code = 404 # Явно ставим 404
        elif 'policy' in str(getattr(e, 'message', '')).lower():
             error_detail = "Ошибка прав доступа при загрузке изображения. Проверьте политики RLS для бакета."
             status_code = 403 # Явно ставим 403
        raise HTTPException(status_code=status_code, detail=error_detail)
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при загрузке файла: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера при загрузке файла: {str(e)}")

# --- ЭНДПОИНТ: Детализация поста --- 
@app.post("/generate-post-details", response_model=PostDetailsResponse)
async def generate_post_details(request: Request, detail_request: DetailRequest, channel_name: Optional[str] = Query(None, description="Имя канала для контекста")):
    """Генерирует текст поста, ключевые слова и ищет релевантные изображения на Unsplash."""
    
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="Ключ OpenRouter API не настроен.")
    
    # Получаем Telegram User ID из заголовка
    user_id = None
    if "x-telegram-user-id" in request.headers:
        try:
            user_id = int(request.headers["x-telegram-user-id"])
        except ValueError:
            logger.warning(f"Некорректный Telegram User ID в заголовке: {request.headers.get('x-telegram-user-id')}")
    
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY
    )
    
    topic = detail_request.topic_idea
    style = detail_request.format_style
    channel_info = f", Канал='{channel_name}'" if channel_name else ""
    user_info = f", User ID={user_id}" if user_id else ""
    logger.info(f"Запрос генерации деталей поста: Тема='{topic}', Стиль='{style}'{channel_info}{user_info}")

    generated_text = ""
    keywords = []
    found_images: List[FoundImage] = []
    message = ""
    category = "general"  # Категория по умолчанию
    
    # --- ШАГ 0: Генерация ключевых слов (асинхронно) --- 
    async def generate_keywords():
        nonlocal keywords, category
        # Запрос с определением тематики и генерацией более универсальных ключевых слов
        keyword_prompt = f"""На основе темы поста '{topic}' и стиля '{style}', сначала определи основную ТЕМАТИКУ поста (например: finance, business, travel, tech, lifestyle, health, education, art, politics), а затем предложи 2 специфических ключевых слова на английском языке для поиска подходящих изображений. 

Если определена тематика ФИНАНСЫ или БИЗНЕС, то используй специфические термины: "stock market" (а не просто "market"), "financial chart", "trading desk", "investment", "business finance".

Если определена тематика ПУТЕШЕСТВИЯ, используй термины: "travel destination", "landscape", "architecture", "cityscape", "nature view".

Если определена тематика ТЕХНОЛОГИИ, используй термины: "technology", "computer", "digital", "gadget", "startup office".

Для любой другой тематики выбирай максимально конкретные термины, подходящие этой тематике.

Ответ дай в формате:
ТЕМАТИКА: [название тематики]
KEYWORDS: [ключевое слово 1], [ключевое слово 2]"""

        try:
            logger.info("Отправка запроса на генерацию ключевых слов...")
            response = await client.chat.completions.create(
                model="deepseek/deepseek-chat", 
                messages=[{"role": "user", "content": keyword_prompt}],
                temperature=0.6,
                max_tokens=100
            )
            raw_keywords = response.choices[0].message.content.strip()
            logger.info(f"Получены сырые ключевые слова: {raw_keywords}")
            
            # Извлекаем тематику и ключевые слова из ответа
            category = "general"  # По умолчанию
            category_match = re.search(r"ТЕМАТИКА:\s*(\w+)", raw_keywords, re.IGNORECASE)
            if category_match:
                category = category_match.group(1).lower()
                logger.info(f"Определена тематика: {category}")
            
            # Извлекаем ключевые слова
            keywords_match = re.search(r"KEYWORDS:\s*(.+)$", raw_keywords, re.IGNORECASE | re.MULTILINE)
            
            if keywords_match:
                keywords_text = keywords_match.group(1).strip()
                keywords_list = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
                
                if keywords_list and len(keywords_list) >= 2:
                    keywords = keywords_list[:2]
                else:
                    # Недостаточно ключевых слов, используем запасные
                    keywords = get_fallback_keywords(category, topic)
            else:
                # Не нашли ключевые слова, разбираем весь текст, ищем запятые
                keywords_list = [kw.strip() for kw in raw_keywords.split(',') if kw.strip()]
                
                if len(keywords_list) >= 2:
                    # Берем последние два элемента, возможно это и есть ключевые слова
                    keywords = keywords_list[-2:]
                else:
                    # Используем запасные ключевые слова по категории
                    keywords = get_fallback_keywords(category, topic)
            
            logger.info(f"Итоговые ключевые слова для поиска: {keywords}")

        except OpenAIError as e:
            logger.error(f"Ошибка OpenRouter API при генерации ключевых слов: {e}")
            # Резервные ключевые слова в зависимости от темы
            keywords = get_fallback_keywords("general", topic)
        except Exception as e:
             logger.exception(f"Неизвестная ошибка при генерации ключевых слов: {e}")
             keywords = get_fallback_keywords("general", topic)
             
    def get_fallback_keywords(category: str, topic: str) -> List[str]:
        """Возвращает запасные ключевые слова в зависимости от категории"""
        category = category.lower()
        
        # Словарь запасных ключевых слов по категориям
        fallback_dict = {
            "finance": ["stock market", "financial chart"],
            "business": ["business meeting", "office workspace"],
            "travel": ["travel destination", "landscape"],
            "tech": ["technology", "digital workspace"],
            "lifestyle": ["lifestyle", "daily routine"],
            "health": ["healthcare", "wellness"],
            "education": ["education", "learning"],
            "art": ["creative art", "design"],
            "politics": ["politics", "government"],
            "food": ["culinary", "restaurant"],
            "sport": ["sports activity", "competition"],
            "fashion": ["fashion style", "clothing"],
        }
        
        # Если категория существует, берем из словаря
        if category in fallback_dict:
            logger.info(f"Используем запасные ключевые слова для категории '{category}'")
            return fallback_dict[category]
        
        # Иначе пытаемся определить категорию по теме
        for cat, keywords in fallback_dict.items():
            if cat in topic.lower():
                logger.info(f"Категория определена из темы: '{cat}'")
                return keywords
        
        # Если не нашли подходящей категории, используем общие
        logger.info("Используем общие запасные ключевые слова")
        return ["professional photo", "high quality"]

    # --- ШАГ 1: Генерация текста поста (асинхронно) ---
    async def generate_text():
        nonlocal generated_text
        text_prompt = f"""Напиши текст для поста в Telegram на тему "{topic}" в стиле "{style}".
Постарайся сделать текст интересным, структурированным и объемом примерно 2-4 абзаца.
Избегай общих фраз, старайся дать конкретику или задать вопрос аудитории.
Не используй в тексте упоминания "Тема:", "Стиль:", "Абзац 1:" и т.п. Просто напиши сам текст поста.
ВАЖНО: Используй ТОЛЬКО русский алфавит и стандартные знаки препинания. Не используй никаких спецсимволов, эмодзи или иностранных символов.
"""
        try:
            logger.info("Отправка запроса на генерацию текста поста...")
            response = await client.chat.completions.create(
                model="deepseek/deepseek-chat",
                messages=[{"role": "user", "content": text_prompt}],
                temperature=0.7,
                max_tokens=1000
            )
            raw_text = response.choices[0].message.content.strip()
            
            # Очистка текста от потенциально проблемных символов
            cleaned_text = ""
            for char in raw_text:
                # Оставляем только буквы русского и английского алфавита, цифры и стандартные знаки препинания
                if char.isalnum() or char.isspace() or char in '.,!?:;-_()[]{}«»"\'%+=/':
                    cleaned_text += char
                else:
                    cleaned_text += ' ' # Заменяем проблемные символы пробелами
            
            generated_text = cleaned_text.strip()
            logger.info("Текст поста успешно сгенерирован.")
        except OpenAIError as e:
            logger.error(f"Ошибка OpenRouter API при генерации текста поста: {e}")
            generated_text = f"// Ошибка генерации текста: {e}"
        except Exception as e:
             logger.exception(f"Неизвестная ошибка при генерации текста поста: {e}")
             generated_text = f"// Неизвестная ошибка генерации текста"

    # --- Запускаем генерацию ключевых слов и текста параллельно --- 
    await asyncio.gather(
        generate_keywords(),
        generate_text()
    )

    # --- ШАГ 2: Поиск изображений (после генерации ключевых слов) --- 
    found_images: List[FoundImage] = []
    if UNSPLASH_ACCESS_KEY and keywords:
        found_images = await search_unsplash_images(
            keywords=keywords, 
            access_key=UNSPLASH_ACCESS_KEY, 
            count=IMAGE_RESULTS_COUNT, 
            request_limit=IMAGE_SEARCH_COUNT,
            category=category
        )
    
    # --- Формируем сообщение для ответа --- 
    if generated_text.startswith("// Ошибка"):
        message = "Ошибка при генерации текста. "
    else:
        message = "Текст успешно сгенерирован. "
        
    if found_images:
        message += f"Найдено изображений: {len(found_images)}."
    elif UNSPLASH_ACCESS_KEY:
        message += "Изображения не найдены."
    else:
        message += "Поиск изображений пропущен (нет ключа Unsplash)."

    logger.info(f"Итоговое сообщение: {message}")

    # --- ШАГ 3: Возвращаем результат --- 
    return PostDetailsResponse(
        generated_text=generated_text,
        found_images=found_images,
        message=message
    )

# --- АДАПТИРУЕМ функцию для поиска изображений с модулем unsplash ---
async def search_unsplash_images(
    keywords: List[str],
    category: str = "general",
    access_key: Optional[str] = None,
    count: int = 5,
    request_limit: int = 15
) -> List[FoundImage]:
    """
    Поиск изображений на Unsplash по набору ключевых слов.
    
    Args:
        keywords: Список ключевых слов для поиска.
        category: Категория контента (например, 'business', 'finance', и т.д.).
        access_key: API ключ для Unsplash (если не указан, используется UNSPLASH_ACCESS_KEY).
        count: Максимальное количество изображений для возврата.
        request_limit: Максимальное количество изображений для запроса у Unsplash.
        
    Returns:
        Список объектов FoundImage с данными изображений.
    """
    # Используем переданный ключ или глобальный
    api_key = access_key or UNSPLASH_ACCESS_KEY
    
    # Фильтруем пустые ключевые слова
    valid_keywords = [k for k in keywords if k.strip()]
    
    # Если нет валидных ключевых слов, используем запасные
    if not valid_keywords:
        logger.warning("Не найдено валидных ключевых слов для поиска изображений")
        valid_keywords = get_fallback_keywords(category)
    
    logger.info(f"Поиск изображений по ключевым словам: {valid_keywords} для категории: {category}")
    
    # Настройка цветового фильтра в зависимости от категории
    color = None  # По умолчанию без цветового фильтра
    
    # Настройка параметров для разных категорий
    if category.lower() == "business" or category.lower() == "finance":
        color = "blue"  # Голубой/синий для деловых и финансовых тем
    elif category.lower() == "health" or category.lower() == "medical":
        color = "white"  # Белый для медицинских тем
    elif category.lower() == "environment" or category.lower() == "nature":
        color = "green"  # Зелёный для экологии/природы
    elif category.lower() == "technology":
        color = "black"  # Чёрный для технологий
    
    # Проверка API ключа
    if not api_key:
        logger.error("Отсутствует API ключ Unsplash")
        return []
    
    # Базовый URL для API Unsplash
    base_url = "https://api.unsplash.com/search/photos"
    
    # Максимальное количество изображений для возврата
    max_images = count
    images = []
    
    # Создаем HTTP клиент для запросов к API
    async with httpx.AsyncClient() as client:
        # Поиск изображений для каждого ключевого слова
        for keyword in valid_keywords:
            if len(images) >= max_images:
                break
            
            try:
                # Параметры запроса
                params = {
                    "query": keyword, 
                    "per_page": min(request_limit // len(valid_keywords), 30)
                }
                
                if color:
                    params["color"] = color
                
                # Добавляем заголовки с ключом API
                headers = {
                    "Authorization": f"Client-ID {api_key}",
                    "Accept-Version": "v1"
                }
                
                logger.info(f"Отправка запроса к API Unsplash: {base_url}, params={params}")
                
                # Выполняем запрос к API
                response = await client.get(base_url, params=params, headers=headers)
                
                # Проверяем HTTP статус
                if response.status_code != 200:
                    logger.error(f"Ошибка API Unsplash: {response.status_code}, {response.text}")
                    continue
                
                # Парсим JSON ответ
                data = response.json()
                
                # Проверяем наличие результатов
                if "results" not in data or not data["results"]:
                    logger.warning(f"Нет результатов для ключевого слова: {keyword}")
                    continue
                
                # Обрабатываем результаты
                results = data["results"]
                logger.info(f"Получено {len(results)} результатов для ключевого слова '{keyword}'")
                
                for photo in results:
                    if len(images) >= max_images:
                        break
                    
                    # Извлекаем необходимые данные
                    photo_id = photo.get("id", str(uuid.uuid4()))
                    urls = photo.get("urls", {})
                    image_url = urls.get("regular", "")
                    preview_url = urls.get("small", "")
                    
                    if not image_url or not preview_url:
                        logger.warning(f"URL изображения не найден для фото {photo_id}")
                        continue
                    
                    description = photo.get("description") or photo.get("alt_description") or keyword
                    
                    # Информация об авторе
                    user = photo.get("user", {})
                    author_name = user.get("name", "")
                    author_links = user.get("links", {})
                    author_url = author_links.get("html", "")
                    
                    # Создаем объект FoundImage
                    image = FoundImage(
                        id=photo_id,
                        source="unsplash",
                        preview_url=preview_url,
                        regular_url=image_url,
                        description=description,
                        author_name=author_name,
                        author_url=author_url
                    )
                    
                    # Добавляем только уникальные изображения
                    if not any(img.id == image.id for img in images):
                        images.append(image)
                        logger.info(f"Добавлено изображение: ID={photo_id}, URL={image_url[:30]}...")
                
            except Exception as e:
                logger.exception(f"Ошибка при поиске изображений для ключевого слова {keyword}: {e}")
    
    # Проверка, найдены ли изображения
    if not images:
        logger.warning("Не найдено изображений для указанных ключевых слов")
    else:
        logger.info(f"Всего найдено {len(images)} уникальных изображений")
    
    return images

# Создаем эндпоинт для получения списка используемых каналов и их статистики
@app.get("/channels/summary", response_model=Dict[str, Any])
async def get_channels_summary():
    """Возвращает сводку по каналам: список каналов и общую статистику."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Сервис базы данных недоступен.")
        
    logger.info("Запрос сводки по каналам...")
    try:
        # Получаем список уникальных названий каналов из таблицы идей
        ideas_channels_query = supabase.table('suggested_ideas').select("channel_name").execute()
        
        # Получаем список уникальных названий каналов из таблицы постов
        posts_channels_query = supabase.table('saved_posts').select("channel_name").execute()
        
        # Получаем общее количество идей и постов
        ideas_count_query = supabase.table('suggested_ideas').select("count").execute()
        posts_count_query = supabase.table('saved_posts').select("count").execute()
        
        # Объединяем уникальные названия каналов
        all_channels = set()
        
        if hasattr(ideas_channels_query, 'data') and isinstance(ideas_channels_query.data, list):
            for item in ideas_channels_query.data:
                channel_name = item.get('channel_name')
                if channel_name:
                    all_channels.add(channel_name)
        
        if hasattr(posts_channels_query, 'data') and isinstance(posts_channels_query.data, list):
            for item in posts_channels_query.data:
                channel_name = item.get('channel_name')
                if channel_name:
                    all_channels.add(channel_name)
        
        # Получаем общее количество
        total_ideas = len(ideas_channels_query.data) if hasattr(ideas_channels_query, 'data') else 0
        total_posts = len(posts_channels_query.data) if hasattr(posts_channels_query, 'data') else 0
        
        # Формируем результат
        return {
            "channels": sorted(list(all_channels)),
            "total_ideas": total_ideas,
            "total_posts": total_posts,
            "channels_count": len(all_channels)
        }
    except APIError as e:
        logger.error(f"Ошибка API Supabase при получении сводки по каналам: {e.message}", exc_info=True)
        raise HTTPException(status_code=getattr(e, 'status_code', 500), detail=f"Ошибка базы данных: {e.message}")
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при получении сводки по каналам: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

def get_fallback_keywords(category: str = "general") -> List[str]:
    """
    Возвращает запасные ключевые слова на основе категории контента.
    
    Args:
        category: Категория контента
        
    Returns:
        Список запасных ключевых слов для данной категории
    """
    fallback_keywords = {
        "business": ["business", "office", "professional", "corporate", "meeting"],
        "finance": ["finance", "investment", "stock market", "money", "banking"],
        "technology": ["technology", "innovation", "digital", "computer", "future"],
        "health": ["health", "wellness", "medical", "healthcare", "medicine"],
        "education": ["education", "learning", "school", "university", "knowledge"],
        "travel": ["travel", "journey", "adventure", "destination", "vacation"],
        "food": ["food", "cuisine", "cooking", "restaurant", "meal"],
        "fashion": ["fashion", "style", "clothing", "design", "trendy"],
        "sports": ["sports", "athletics", "competition", "fitness", "game"],
        "entertainment": ["entertainment", "movie", "music", "concert", "performance"],
        "science": ["science", "research", "laboratory", "experiment", "discovery"],
        "environment": ["environment", "nature", "climate", "sustainability", "green"],
        "politics": ["politics", "government", "policy", "democracy", "election"],
        "general": ["professional", "minimalist", "modern", "clean", "abstract"]
    }
    
    category_lower = category.lower()
    if category_lower in fallback_keywords:
        return fallback_keywords[category_lower]
    else:
        logger.warning(f"Категория '{category}' не найдена. Используем общие ключевые слова.")
        return fallback_keywords["general"]

async def generate_keywords(post_text: str, language: str = "russian") -> Tuple[List[str], str]:
    """
    Генерирует ключевые слова для поиска изображений на основе текста поста.
    
    Args:
        post_text: Текст поста
        language: Язык поста
        
    Returns:
        Кортеж из списка ключевых слов и определенной категории
    """
    try:
        logger.info(f"Генерация ключевых слов для поста длиной {len(post_text)} символов")
        
        # Идентификация категории контента
        prompt_category = f"""
        Определи основную категорию для данного текста. Выбери ТОЛЬКО ОДНУ категорию из следующих:
        business, finance, technology, health, education, travel, food, fashion, sports, entertainment, science, environment, politics, general.
        
        Возвращай ТОЛЬКО название категории, без дополнительных пояснений.
        
        Текст: {post_text[:500]}
        """
        
        # Генерация категории контента
        completion = await openai_client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[
                {"role": "system", "content": "Ты - эксперт по категоризации контента. Твоя задача - определить категорию контента из предложенного списка."},
                {"role": "user", "content": prompt_category}
            ],
            max_tokens=50,
            temperature=0.5
        )
        
        # Извлечение категории из ответа модели
        category = completion.choices[0].message.content.strip().lower()
        logger.info(f"Определена категория контента: {category}")
        
        # Если категория не соответствует ожидаемым, используем общую
        valid_categories = ["business", "finance", "technology", "health", "education", "travel", 
                           "food", "fashion", "sports", "entertainment", "science", "environment", 
                           "politics", "general"]
        
        if category not in valid_categories:
            logger.warning(f"Неизвестная категория: {category}. Используем 'general'.")
            category = "general"
        
        # Генерация ключевых слов для этой категории
        prompt_keywords = f"""
        Сгенерируй 5 ключевых слов или фраз на английском языке для поиска изображений, которые будут хорошо сочетаться с этим текстом.
        Ключевые слова должны быть релевантны содержанию текста и категории '{category}'.
        Возвращай только список ключевых слов, разделенных запятыми, без порядковых номеров или других символов.
        
        Текст: {post_text[:500]}
        """
        
        # Генерация ключевых слов
        completion = await openai_client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[
                {"role": "system", "content": "Ты - эксперт по генерации ключевых слов для поиска изображений."},
                {"role": "user", "content": prompt_keywords}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        keywords_text = completion.choices[0].message.content.strip()
        
        # Разбиваем ключевые слова по запятым и удаляем начальные/конечные пробелы
        keywords = [k.strip() for k in keywords_text.split(',')]
        
        # Удаляем пустые ключевые слова
        keywords = [k for k in keywords if k]
        
        logger.info(f"Сгенерированы ключевые слова: {keywords}")
        
        return keywords, category
        
    except Exception as e:
        logger.error(f"Ошибка при генерации ключевых слов: {str(e)}")
        # Возвращаем запасные ключевые слова в случае ошибки
        return get_fallback_keywords("general"), "general"

# Роут для обслуживания фронтенда (React SPA)
@app.get("/", include_in_schema=False)
async def serve_index():
    # Проверяем, установлен ли флаг SPA_ROUTES_CONFIGURED
    if SPA_ROUTES_CONFIGURED:
        logger.debug("Запрос к / пропущен, так как SPA_ROUTES_CONFIGURED=True")
        # Возвращаем 404, чтобы FastAPI перешел к следующему обработчику
        raise HTTPException(status_code=404, detail="Redirecting to new handler")
    
    index_path = os.path.join(static_folder, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        logging.error(f"Файл index.html не найден по пути: {index_path}")
        raise HTTPException(status_code=404, detail="Файл index.html не найден")

# Роут для перенаправления всех неизвестных путей на React Router
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    # Проверяем, установлен ли флаг SPA_ROUTES_CONFIGURED
    if SPA_ROUTES_CONFIGURED:
        logger.debug(f"Запрос к /{full_path} пропущен, так как SPA_ROUTES_CONFIGURED=True")
        # Возвращаем 404, чтобы FastAPI перешел к следующему обработчику
        raise HTTPException(status_code=404, detail="Redirecting to new handler")
    
    # Если запрашивается API-эндпоинт, не обрабатываем его здесь
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    # Проверяем, существует ли файл статики
    requested_file = os.path.join(static_folder, full_path)
    if os.path.exists(requested_file) and os.path.isfile(requested_file):
        return FileResponse(requested_file)
    
    # Для остальных запросов возвращаем index.html (для работы React Router)
    index_path = os.path.join(static_folder, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        logging.error(f"Файл index.html не найден по пути: {index_path}")
        raise HTTPException(status_code=404, detail="Файл index.html не найден")

# Добавляем посредник для логирования запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Расширенное логирование всех входящих запросов для отладки"""
    path = request.url.path
    method = request.method
    user_id = request.headers.get("x-telegram-user-id", "не определен")
    logger.info(f"Запрос: {method} {path} | User ID: {user_id}")
    
    # Логируем все заголовки для отладки
    headers_str = ", ".join([f"{k}: {v}" for k, v in request.headers.items()])
    logger.debug(f"Заголовки запроса: {headers_str}")
    
    # Продолжаем обработку запроса
    try:
        response = await call_next(request)
        logger.info(f"Ответ: {path} - Статус: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Ошибка при обработке запроса {path}: {str(e)}", exc_info=True)
        raise

# Монтируем статические файлы ПОСЛЕ определения всех API-эндпоинтов
# Это гарантирует, что API-эндпоинты будут иметь приоритет
if SHOULD_MOUNT_STATIC:
    # Устанавливаем флаг, что мы используем новые маршруты
    SPA_ROUTES_CONFIGURED = True
    logger.info("Установлен флаг SPA_ROUTES_CONFIGURED=True для предотвращения конфликтов маршрутов")
    
    # Перечисляем все API-маршруты, чтобы исключить их из обработки static middleware
    API_PATHS = [
        "/analyze", 
        "/generate-plan", 
        "/posts", 
        "/ideas", 
        "/upload-image", 
        "/generate-post-details",
        "/channels/summary"
    ]
    
    # Определяем особый middleware для обработки запросов к статическим файлам
    @app.middleware("http")
    async def static_files_middleware(request: Request, call_next):
        """Middleware для обработки запросов к статическим файлам с учетом приоритета API"""
        path = request.url.path
        method = request.method
        
        # Если метод и путь соответствуют API-эндпоинту, пропускаем запрос дальше
        for api_path in API_PATHS:
            if path.startswith(api_path):
                logger.debug(f"Запрос {method} {path} обрабатывается как API-запрос")
                return await call_next(request)
        
        # Если путь не соответствует API, и это GET-запрос, проверяем наличие файла
        if method == "GET":
            # Обрабатываем корневой путь отдельно
            if path == "/":
                file_path = os.path.join(static_folder, "index.html")
            else:
                # Убираем начальный / для получения относительного пути
                relative_path = path.lstrip("/")
                file_path = os.path.join(static_folder, relative_path)
                
            # Если файл существует, возвращаем его
            if os.path.exists(file_path) and os.path.isfile(file_path):
                logger.debug(f"Запрос {path} обрабатывается как запрос статического файла")
                return FileResponse(file_path)
        
        # Во всех остальных случаях продолжаем цепочку middleware
        return await call_next(request)
    
    # Добавляем маршрут для обработки всех оставшихся GET-запросов к статическим файлам
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_static_files(full_path: str):
        """Обработка всех запросов к статическим файлам, не перехваченных middleware"""
        logger.info(f"Запрос к статическому файлу: {full_path}")
        
        # Формируем полный путь к файлу
        file_path = os.path.join(static_folder, full_path)
        
        # Проверяем существование файла
        if os.path.exists(file_path) and os.path.isfile(file_path):
            logger.debug(f"Файл найден, отдаем: {file_path}")
            return FileResponse(file_path)
        
        # Если файл не найден, попробуем вернуть index.html для SPA маршрутизации
        index_path = os.path.join(static_folder, "index.html")
        if os.path.exists(index_path):
            logger.debug(f"Файл не найден, возвращаем index.html для SPA маршрутизации: {full_path}")
            return FileResponse(index_path)
        
        # Если даже index.html нет, вернем 404
        logger.warning(f"Файл не найден и нет index.html: {full_path}")
        raise HTTPException(status_code=404, detail=f"Файл не найден: {full_path}")
    
    # Монтируем статические файлы для обработки всех остальных запросов
    # Это будет запасной вариант, если наш middleware не обработал запрос
    app.mount("/static", StaticFiles(directory=static_folder), name="static")
    logger.info("Статические файлы успешно смонтированы и настроены с учетом приоритета API-запросов")

# Добавляем функцию для получения примеров постов (заглушек)
def get_sample_posts(channel_name: str) -> List[str]:
    """Возвращает примеры постов для анализа, если не удалось получить реальные."""
    logger.info(f"Используем примеры постов для канала {channel_name}")
    
    # Базовые примеры постов
    sample_posts = [
        f"Добро пожаловать в канал {channel_name}! Здесь мы обсуждаем интересные темы и делимся полезной информацией.",
        f"Сегодня поговорим о важных аспектах в тематике канала {channel_name}. Тема очень актуальна для нашей аудитории.",
        f"В этом посте мы разберем 5 ключевых моментов, которые помогут вам лучше понять концепцию нашего канала {channel_name}.",
        f"Новости и обновления в нашей сфере! Канал {channel_name} всегда держит вас в курсе самых важных событий.",
        f"Полезные советы для наших подписчиков. Канал {channel_name} заботится о том, чтобы вы получали только качественный контент."
    ]
    
    return sample_posts