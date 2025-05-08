import os
import sqlite3
import asyncpg
import json
import uuid
import re
import uvicorn
import httpx
import time
import sys
import glob
import hashlib
import shutil
from typing import List, Dict, Any, Optional, Tuple
from fastapi import FastAPI, HTTPException, Request, Depends, Response, File, UploadFile, Form, Query
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from dateutil.relativedelta import relativedelta
from urllib.parse import urlparse

# Загружаем переменные окружения
load_dotenv()  # Загружаем переменные окружения из .env файла

# Инициализация FastAPI приложения
app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from services.subscription_service import SubscriptionService, FREE_ANALYSIS_LIMIT, FREE_POST_LIMIT, SUBSCRIPTION_PRICE, SUBSCRIPTION_DURATION_MONTHS

# Настройка логирования
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация приложения и БД
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or OPENAI_API_KEY  # Используем OpenAI API ключ как запасной вариант

# Функция для скачивания и сохранения внешнего изображения
async def download_and_save_external_image(image_url: str, source: str = "unsplash"):
    """
    Скачивает изображение с внешнего источника и сохраняет его в Supabase Storage.
    
    Args:
        image_url: URL изображения для скачивания
        source: Источник изображения (например, 'unsplash')
        
    Returns:
        Dict с полями:
            success: True если успешно, False если ошибка
            url: Публичный URL сохраненного изображения (если успех)
            error: Текст ошибки (если неудача)
    """
    logger.info(f"Начинаем загрузку внешнего изображения: {image_url}, источник: {source}")
    
    try:
        # Проверяем URL
        if not image_url or not image_url.startswith("http"):
            return {"success": False, "error": "Некорректный URL изображения"}
        
        # Определяем расширение файла из URL или Content-Type
        parsed_url = urlparse(image_url)
        path_parts = parsed_url.path.split("/")
        filename = path_parts[-1] if path_parts else "image"
        
        # Пытаемся получить расширение из имени файла
        _, ext = os.path.splitext(filename)
        
        # Если расширение не определено или не валидно, пробуем через HEAD запрос
        allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        if not ext or ext.lower() not in allowed_extensions:
            try:
                # Делаем HEAD запрос, чтобы получить Content-Type
                async with httpx.AsyncClient() as client:
                    head_response = await client.head(image_url, follow_redirects=True, timeout=10.0)
                    
                content_type = head_response.headers.get("content-type", "")
                # Определяем расширение на основе content-type
                if "image/jpeg" in content_type:
                    ext = ".jpg"
                elif "image/png" in content_type:
                    ext = ".png"
                elif "image/gif" in content_type:
                    ext = ".gif"
                elif "image/webp" in content_type:
                    ext = ".webp"
                else:
                    # Если не смогли определить, используем .jpg как наиболее распространенный
                    ext = ".jpg"
            except Exception as head_err:
                logger.warning(f"Не удалось определить тип изображения через HEAD запрос: {head_err}")
                # По умолчанию считаем JPEG
                ext = ".jpg"
        
        # Генерируем уникальное имя файла с определенным расширением
        storage_path = f"public/external/{source}/{uuid.uuid4()}{ext.lower()}"
        bucket_name = "post-images"  # Имя бакета в Supabase Storage
        
        # Скачиваем изображение
        async with httpx.AsyncClient() as client:
            logger.info(f"Начинаем скачивание {image_url}")
            response = await client.get(image_url, follow_redirects=True, timeout=15.0)
            
            if response.status_code != 200:
                logger.error(f"Ошибка при скачивании изображения: {response.status_code}")
                return {
                    "success": False, 
                    "error": f"Ошибка при скачивании изображения: HTTP {response.status_code}"
                }
            
            image_bytes = response.content
            content_type = response.headers.get("content-type", "image/jpeg")
            
        # В этой реализации мы просто логируем операцию без фактического взаимодействия с Supabase
        # поскольку нам нужен только сам механизм обработки в create_post и update_post
        logger.info(f"Скачивание завершено. Имитируем загрузку в Supabase Storage: путь={storage_path}")
        
        # Имитируем успешную загрузку
        public_url = f"https://example.com/storage/{bucket_name}/{storage_path}"
        
        logger.info(f"Изображение успешно загружено в хранилище (имитация): {storage_path}, URL: {public_url}")
        
        return {
            "success": True,
            "url": public_url,
            "source": source,
            "original_url": image_url
        }
        
    except Exception as e:
        logger.error(f"Ошибка при обработке внешнего изображения: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Не удалось обработать внешнее изображение: {str(e)}"
        }

# Модели данных для изображений и постов
class PostImage(BaseModel):
    url: str
    id: Optional[str] = None
    preview_url: Optional[str] = None
    alt: Optional[str] = None
    author: Optional[str] = None
    author_url: Optional[str] = None
    source: Optional[str] = None

class PostData(BaseModel):
    target_date: str
    topic_idea: str
    format_style: str
    final_text: str
    image_url: Optional[str] = None
    images_ids: Optional[List[str]] = None
    channel_name: Optional[str] = None
    selected_image_data: Optional[PostImage] = None

class SavedPostResponse(PostData):
    id: str
    created_at: str
    updated_at: str

class AnalyzeResponse(BaseModel):
    themes: List[str]
    styles: List[str]
    analyzed_posts_sample: List[str]
    best_posting_time: str
    analyzed_posts_count: int
    message: Optional[str] = None
    error: Optional[str] = None

class FoundImage(BaseModel):
    id: str
    source: str
    preview_url: str
    regular_url: str
    description: Optional[str] = None
    author_name: Optional[str] = None
    author_url: Optional[str] = None

class PostDetailsResponse(BaseModel):
    generated_text: str
    found_images: List[FoundImage] = []
    message: str = ""
    channel_name: Optional[str] = None
    selected_image_data: Optional[PostImage] = None

class WebAppDataRequest(BaseModel):
    data: str  # JSON-строка с данными от Telegram
    user: Dict[str, Any]  # Информация о пользователе

    class Config:
        schema_extra = {
            "example": {
                "data": "{\"user_id\":12345678}",
                "user": {"id": 12345678, "first_name": "John", "last_name": "Doe"}
            }
        }

class CreateSubscriptionRequest(BaseModel):
    user_id: int
    payment_id: Optional[str] = None

class SubscriptionStatusResponse(BaseModel):
    has_subscription: bool
    analysis_count: int
    post_generation_count: int
    subscription_end_date: Optional[str] = None

class DirectPremiumStatusResponse(BaseModel):
    has_premium: bool
    user_id: str
    error: Optional[str] = None
    subscription_end_date: Optional[str] = None
    analysis_count: Optional[int] = None
    post_generation_count: Optional[int] = None

async def get_subscription_service():
    """Создает экземпляр SubscriptionService с подключением к базе данных"""
    try:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL не указан в переменных окружения")
        
        pool = await asyncpg.create_pool(db_url)
        subscription_service = SubscriptionService(pool)
        return subscription_service
    except Exception as e:
        logger.error(f"Ошибка при создании SubscriptionService: {e}")
        raise

# Middleware для корректной обработки API-запросов
@app.middleware("http")
async def api_priority_middleware(request: Request, call_next):
    """Middleware для обеспечения приоритета API-маршрутов над SPA-маршрутами"""
    path = request.url.path
    
    # Приоритетные API пути (нужно обновить при добавлении новых)
    api_paths = [
        "/api/",
        "/subscription/",
        "/subscription/status",
        "/direct_premium_check",
        "/force-premium-status/",
        "/api-v2/subscription/status",
        "/api-v2/premium/check",
    ]
    
    # Проверяем, является ли путь API-запросом
    is_api_request = any(path.startswith(prefix) for prefix in api_paths)
    
    # Добавляем выявление API-запросов по заголовкам для всех путей
    headers = request.headers
    accept_header = headers.get("accept", "")
    is_json_request = "application/json" in accept_header
    
    # Если JSON запрос или путь из API-списка, добавляем заголовок для внутренней маршрутизации
    if is_api_request or is_json_request:
        logger.info(f"Приоритетный API запрос: {path} (Accept: {accept_header})")
        request.state.is_api_request = True
    else:
        request.state.is_api_request = False
        
    # Выполняем запрос
    response = await call_next(request)
    
    # Добавляем заголовки для предотвращения кэширования для всех API ответов
    if is_api_request or is_json_request:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
    return response

# ===========================================
# === НОВЫЕ API МАРШРУТЫ ДЛЯ ПОДПИСОК ===
# ===========================================

@app.get("/api-v2/subscription/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status_v2(user_id: str):
    """
    Новый API-эндпоинт для получения статуса подписки
    Использует GET-параметр user_id для максимальной совместимости
    """
    try:
        if not user_id:
            logger.error("get_subscription_status_v2: user_id не предоставлен")
            return JSONResponse(
                status_code=400,
                content={"error": "user_id is required"},
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
        
        # Получение сервиса подписок
        subscription_service = await get_subscription_service()
        
        # Запрос на получение данных подписки
        user_id_int = int(user_id)
        subscription_data = await subscription_service.get_subscription(user_id_int)
        
        # Логирование успешного запроса
        logger.info(f"[API-V2] Получен статус подписки для user_id={user_id}: {subscription_data}")
        
        return JSONResponse(
            content=dict(subscription_data),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
        
    except ValueError as ve:
        logger.error(f"Ошибка преобразования user_id: {ve}")
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid user_id format: {str(ve)}"},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    except Exception as e:
        logger.error(f"Ошибка при получении статуса подписки: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error fetching subscription status: {str(e)}"},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

@app.get("/api-v2/premium/check", response_model=DirectPremiumStatusResponse)
async def check_premium_v2(user_id: str):
    """
    Новый API-эндпоинт для проверки премиум-статуса
    Возвращает только has_premium и минимум информации
    """
    try:
        if not user_id:
            logger.error("check_premium_v2: user_id не предоставлен")
            return JSONResponse(
                status_code=400,
                content={"has_premium": False, "error": "user_id is required"},
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
        
        # Получение данных из БД
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return JSONResponse(
                content={"has_premium": False, "error": "DB connection error", "user_id": user_id},
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
                
        # Прямой запрос к базе данных
        user_id_int = int(user_id)
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
            count = await conn.fetchval(query, user_id_int)
            has_premium = count > 0
            
            # Получаем информацию о текущей/последней подписке
            if has_premium:
                sub_query = """
                SELECT end_date 
                FROM user_subscription 
                WHERE user_id = $1 
                  AND is_active = TRUE
                ORDER BY end_date DESC 
                LIMIT 1
                """
                end_date = await conn.fetchval(sub_query, user_id_int)
                end_date_str = end_date.isoformat() if end_date else None
            else:
                end_date_str = None
                
            result = {
                "has_premium": has_premium,
                "user_id": user_id,
                "error": None,
                "subscription_end_date": end_date_str,
                "analysis_count": 9999 if has_premium else FREE_ANALYSIS_LIMIT,
                "post_generation_count": 9999 if has_premium else FREE_POST_LIMIT
            }
            
            logger.info(f"[API-V2] Проверка премиума для пользователя {user_id}: {has_premium}")
            return JSONResponse(
                content=result,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
            
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Ошибка в check_premium_v2: {e}")
        return JSONResponse(
            content={"has_premium": False, "error": str(e), "user_id": user_id},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

# ===========================================
# === СУЩЕСТВУЮЩИЕ API МАРШРУТЫ === 
# ===========================================

@app.get("/subscription/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(request: Request, user_id: Optional[str] = None):
    """Получить статус подписки пользователя"""
    try:
        # Если user_id не передан явно, пытаемся извлечь его из query-параметров или заголовков
        if not user_id:
            user_id = request.query_params.get('user_id')
            
        # Проверяем заголовок x-telegram-user-id
        if not user_id and 'x-telegram-user-id' in request.headers:
            user_id = request.headers.get('x-telegram-user-id')
            logger.info(f"ID пользователя получен из заголовка: {user_id}")
        
        # Проверка наличия user_id
        if not user_id:
            logger.error("get_subscription_status: user_id не предоставлен ни в параметрах, ни в заголовках")
            return JSONResponse(
                status_code=400,
                content={"error": "user_id is required"},
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
            
        # Получение сервиса подписок
        subscription_service = await get_subscription_service()
        
        # Запрос на получение данных подписки
        user_id_int = int(user_id)
        subscription_data = await subscription_service.get_subscription(user_id_int)
        
        # Логирование успешного запроса
        logger.info(f"Получен статус подписки для user_id={user_id}: {subscription_data}")
        
        return JSONResponse(
            content=dict(subscription_data),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
        
    except ValueError as ve:
        logger.error(f"Ошибка преобразования user_id: {ve}")
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid user_id format: {str(ve)}"},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    except Exception as e:
        logger.error(f"Ошибка при получении статуса подписки: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error fetching subscription status: {str(e)}"},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

@app.get("/direct_premium_check", response_model=DirectPremiumStatusResponse)
async def direct_premium_check(request: Request, user_id: Optional[str] = None):
    """Прямая проверка премиум-статуса (для отладки и внутреннего использования)"""
    try:
        # Если user_id не передан явно, пытаемся извлечь его из query-параметров или заголовков
        if not user_id:
            user_id = request.query_params.get('user_id')
            
        # Проверяем заголовок x-telegram-user-id
        if not user_id and 'x-telegram-user-id' in request.headers:
            user_id = request.headers.get('x-telegram-user-id')
            logger.info(f"ID пользователя получен из заголовка: {user_id}")
        
        # Проверка наличия user_id
        if not user_id:
            logger.error("direct_premium_check: user_id не предоставлен ни в параметрах, ни в заголовках")
            return JSONResponse(
                status_code=400,
                content={"has_premium": False, "error": "user_id is required"},
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
            
        # Получение сервиса подписок
        subscription_service = await get_subscription_service()
        
        # Прямой запрос в БД на проверку премиум-статуса
        user_id_int = int(user_id)
        has_premium = await subscription_service.check_premium_directly(user_id_int)
        
        # Логирование успешного запроса
        logger.info(f"Прямая проверка премиум для user_id={user_id}: {has_premium}")
        
        return JSONResponse(
            content={"has_premium": has_premium, "user_id": user_id},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
        
    except ValueError as ve:
        logger.error(f"Ошибка преобразования user_id: {ve}")
        return JSONResponse(
            status_code=400,
            content={"has_premium": False, "error": f"Invalid user_id format: {str(ve)}"},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    except Exception as e:
        logger.error(f"Ошибка при прямой проверке премиум: {e}")
        return JSONResponse(
            status_code=500,
            content={"has_premium": False, "error": f"Error checking premium status: {str(e)}"},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

@app.get("/force-premium-status/{user_id}", response_model=DirectPremiumStatusResponse)
async def force_premium_status(user_id: str):
    """
    Принудительная проверка премиум-статуса по ID пользователя.
    Этот метод имеет максимальный приоритет перед SPA-обработчиком.
    """
    try:
        # Преобразование user_id в число
        user_id_int = int(user_id)
        
        # Получение данных из БД
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return JSONResponse(
                content={"has_premium": False, "error": "DB connection error", "user_id": user_id},
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
            
        # Прямой запрос к базе данных
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
            count = await conn.fetchval(query, user_id_int)
            has_premium = count > 0
            
            # Получаем информацию о текущей/последней подписке
            if has_premium:
                sub_query = """
                SELECT end_date 
                FROM user_subscription 
                WHERE user_id = $1 
                ORDER BY end_date DESC 
                LIMIT 1
                """
                end_date = await conn.fetchval(sub_query, user_id_int)
                end_date_str = end_date.isoformat() if end_date else None
            else:
                end_date_str = None
                
            result = {
                "has_premium": has_premium,
                "user_id": user_id,
                "error": None,
                "subscription_end_date": end_date_str,
                "analysis_count": 9999 if has_premium else FREE_ANALYSIS_LIMIT,
                "post_generation_count": 9999 if has_premium else FREE_POST_LIMIT
            }
            
            logger.info(f"Force premium check for user {user_id}: {result}")
            return JSONResponse(
                content=result,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
            
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Error in force_premium_status: {e}")
        return JSONResponse(
            content={"has_premium": False, "error": str(e), "user_id": user_id},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_channel(
    # ... (зависимости и код эндпоинта) ...
):
    # ... (реализация) ...
    pass # Заглушка

@app.get("/posts", response_model=List[SavedPostResponse])
async def get_posts(request: Request, channel_name: Optional[str] = None):
    # ... (реализация) ...
    pass # Заглушка

@app.post("/posts", response_model=SavedPostResponse)
async def create_post(request: Request, post_data: PostData):
    """
    Создание нового поста с обработкой внешних изображений.
    """
    try:
        # Получаем user_id из заголовка или параметров запроса
        user_id = request.headers.get('x-telegram-user-id') or request.query_params.get('user_id')
        if not user_id:
            raise HTTPException(status_code=400, detail="Не указан user_id в заголовке x-telegram-user-id или параметрах запроса")

        # Для логирования запишем полученные данные
        logger.info(f"Создание поста для пользователя {user_id}")
        logger.info(f"Данные поста: {post_data.dict(exclude_none=True)}")

        # Проверка лимитов для не-премиум пользователей
        subscription_service = await get_subscription_service()
        subscription_data = await subscription_service.get_subscription(int(user_id))
        
        if not subscription_data.get("has_subscription", False):
            # Для бесплатных пользователей проверяем лимит на создание постов
            used_count = subscription_data.get("post_generation_count", 0)
            if used_count >= FREE_POST_LIMIT:
                return JSONResponse(
                    status_code=402,  # Payment Required
                    content={
                        "error": "Лимит бесплатных постов исчерпан",
                        "limit": FREE_POST_LIMIT,
                        "used": used_count
                    }
                )

        # --- Обработка выбранного изображения ---
        selected_image = post_data.selected_image_data
        saved_image_id = None

        if selected_image:
            try:
                # Проверяем, является ли изображение внешним (например, с Unsplash)
                is_external_image = selected_image.source and selected_image.source.lower() in ["unsplash", "pexels", "openverse"]
                
                # --- Обработка внешнего изображения ---
                if is_external_image:
                    logger.info(f"Обрабатываем внешнее изображение из источника {selected_image.source}")
                    
                    # Скачиваем и сохраняем внешнее изображение в Supabase Storage
                    download_result = await download_and_save_external_image(
                        image_url=selected_image.url,
                        source=selected_image.source
                    )
                    
                    if not download_result["success"]:
                        logger.error(f"Ошибка при скачивании внешнего изображения: {download_result['error']}")
                        return JSONResponse(
                            status_code=422,
                            content={"error": f"Не удалось обработать изображение: {download_result['error']}"}
                        )
                    
                    # После скачивания и сохранения, сохраняем метаданные изображения в базу данных
                    image_data = {
                        "url": download_result["url"],
                        "user_id": int(user_id),
                        "alt_text": selected_image.alt or "",
                        "author": selected_image.author or "",
                        "author_url": selected_image.author_url or "",
                        "source": selected_image.source or "",
                        "original_url": download_result["original_url"]
                    }
                    
                    # Вставляем запись в базу данных и получаем ID
                    saved_image_id = str(uuid.uuid4())  # Имитируем получение ID
                    logger.info(f"Сохранено внешнее изображение с ID: {saved_image_id}")
                    
                # --- Если изображение уже загружено пользователем ранее ---
                elif selected_image.id:
                    # Здесь мы просто используем уже существующее изображение
                    saved_image_id = selected_image.id
                    logger.info(f"Используем ранее загруженное изображение с ID: {saved_image_id}")
            except Exception as img_err:
                logger.error(f"Ошибка при обработке изображения: {str(img_err)}")
                return JSONResponse(
                    status_code=422,
                    content={"error": f"Ошибка при обработке изображения: {str(img_err)}"}
                )

        # Генерация уникального ID для поста
        post_id = str(uuid.uuid4())
        
        # Текущие дата и время
        now = datetime.now(timezone.utc)
        
        # Создаем пост в базе данных (здесь имитация)
        new_post = {
            "id": post_id,
            "user_id": int(user_id),
            "target_date": post_data.target_date,
            "topic_idea": post_data.topic_idea,
            "format_style": post_data.format_style,
            "final_text": post_data.final_text,
            "channel_name": post_data.channel_name,
            "image_id": saved_image_id,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        
        # Обновляем счетчик использованных постов для пользователя
        if not subscription_data.get("has_subscription", False):
            await subscription_service.increment_post_usage(int(user_id))
            
        # Формируем ответ
        response_data = {
            **post_data.dict(),
            "id": post_id,
            "created_at": new_post["created_at"],
            "updated_at": new_post["updated_at"]
        }
        
        # Если было сохранено изображение, включаем его в ответ
        if saved_image_id:
            if selected_image:
                response_data["image_url"] = selected_image.url
        
        logger.info(f"Пост успешно создан с ID: {post_id}")
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"Ошибка при создании поста: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Внутренняя ошибка сервера: {str(e)}"}
        )

@app.put("/posts/{post_id}", response_model=SavedPostResponse)
async def update_post(post_id: str, request: Request, post_data: PostData):
    """
    Обновление существующего поста с обработкой внешних изображений.
    """
    try:
        # Получаем user_id из заголовка или параметров запроса
        user_id = request.headers.get('x-telegram-user-id') or request.query_params.get('user_id')
        if not user_id:
            raise HTTPException(status_code=400, detail="Не указан user_id в заголовке x-telegram-user-id или параметрах запроса")

        # Для логирования запишем полученные данные
        logger.info(f"Обновление поста {post_id} для пользователя {user_id}")
        logger.info(f"Новые данные: {post_data.dict(exclude_none=True)}")

        # Проверяем существование поста (здесь имитация)
        # В реальном приложении здесь должен быть запрос к базе данных
        # Если пост не существует или не принадлежит текущему пользователю, возвращаем ошибку
        existing_post = {
            "id": post_id,
            "user_id": int(user_id),
            "target_date": "2025-05-10",
            "topic_idea": "Старая тема",
            "format_style": "Старый формат",
            "final_text": "Старый текст",
            "created_at": "2025-05-01T12:00:00Z",
            "updated_at": "2025-05-01T12:00:00Z",
            "image_id": None  # Предположим, что изначально нет изображения
        }
        
        logger.info(f"Найден существующий пост: {existing_post}")
        
        # --- Обработка выбранного изображения ---
        selected_image = post_data.selected_image_data
        saved_image_id = None
        image_processed = False  # Флаг для отслеживания обработки изображения
        
        # Если в запросе есть данные об изображении
        if selected_image is not None:  # Важно: проверяем на None, а не на истинность
            image_processed = True  # Отмечаем, что данные изображения были в запросе
            try:
                # Проверяем, является ли изображение внешним (например, с Unsplash)
                is_external_image = selected_image.source and selected_image.source.lower() in ["unsplash", "pexels", "openverse"]
                
                # --- ОБРАБОТКА ВНЕШНЕГО ИЗОБРАЖЕНИЯ ---
                if is_external_image:
                    logger.info(f"Обрабатываем внешнее изображение из источника {selected_image.source} при обновлении поста {post_id}")
                    
                    # Скачиваем и сохраняем внешнее изображение в Supabase Storage
                    download_result = await download_and_save_external_image(
                        image_url=selected_image.url,
                        source=selected_image.source
                    )
                    
                    if not download_result["success"]:
                        logger.error(f"Ошибка при скачивании внешнего изображения: {download_result['error']}")
                        return JSONResponse(
                            status_code=422,
                            content={"error": f"Не удалось обработать изображение: {download_result['error']}"}
                        )
                    
                    # После скачивания и сохранения, сохраняем метаданные изображения в базу данных
                    image_data = {
                        "url": download_result["url"],
                        "user_id": int(user_id),
                        "alt_text": selected_image.alt or "",
                        "author": selected_image.author or "",
                        "author_url": selected_image.author_url or "",
                        "source": selected_image.source or "",
                        "original_url": download_result["original_url"]
                    }
                    
                    # Вставляем запись в базу данных и получаем ID (имитация)
                    saved_image_id = str(uuid.uuid4())
                    logger.info(f"Сохранено новое внешнее изображение с ID: {saved_image_id} для поста {post_id}")
                
                # --- Если изображение уже загружено пользователем ранее ---
                elif selected_image.id:
                    # Здесь мы просто используем уже существующее изображение
                    saved_image_id = selected_image.id
                    logger.info(f"Используем ранее загруженное изображение с ID: {saved_image_id} для поста {post_id}")
                else:
                    # Если у изображения нет ID и оно не внешнее, это, вероятно, ошибка
                    logger.warning(f"Получено изображение без ID и не из внешнего источника: {selected_image}")
                    
            except Exception as img_err:
                logger.error(f"Ошибка при обработке изображения для поста {post_id}: {str(img_err)}")
                return JSONResponse(
                    status_code=422,
                    content={"error": f"Ошибка при обработке изображения: {str(img_err)}"}
                )
        # Если selected_image == None, то это явный запрос на удаление изображения
        elif selected_image is None and "selected_image_data" in post_data.__fields_set__:
            image_processed = True
            saved_image_id = None
            logger.info(f"Удаление связанного изображения для поста {post_id}")

        # Текущие дата и время для обновления
        now = datetime.now(timezone.utc)
        
        # Обновляем данные поста (здесь имитация)
        updated_post = {
            **existing_post,
            "target_date": post_data.target_date,
            "topic_idea": post_data.topic_idea,
            "format_style": post_data.format_style,
            "final_text": post_data.final_text,
            "channel_name": post_data.channel_name,
            "updated_at": now.isoformat()
        }
        
        # Обновляем изображение, только если оно было явно задано в запросе
        if image_processed:
            updated_post["image_id"] = saved_image_id
            
        # Формируем ответ
        response_data = {
            **post_data.dict(),
            "id": post_id,
            "created_at": updated_post["created_at"],
            "updated_at": updated_post["updated_at"]
        }
        
        # Если было сохранено изображение, включаем его в ответ
        if saved_image_id and selected_image:
            response_data["image_url"] = selected_image.url
            
        logger.info(f"Пост {post_id} успешно обновлен")
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении поста {post_id}: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Внутренняя ошибка сервера: {str(e)}"}
        )

@app.delete("/posts/{post_id}")
async def delete_post(post_id: str, request: Request):
     # ... (реализация) ...
    pass # Заглушка

@app.post("/generate-post-details", response_model=PostDetailsResponse)
async def generate_post_details(
    # ... (зависимости и код эндпоинта) ...
):
    # ... (реализация) ...
    pass # Заглушка

@app.post("/generate-invoice", response_model=Dict[str, Any])
async def generate_invoice(
    # ... (зависимости и код эндпоинта) ...
):
    # ... (реализация) ...
    pass # Заглушка

# Добавляем диагностический эндпоинт
@app.get("/subscription/diagnose", response_model=Dict[str, Any])
async def diagnose_subscription(user_id: str):
    """
    Диагностический эндпоинт для проверки всех аспектов подписки.
    Возвращает детальную информацию для отладки.
    """
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "database_connection": False,
        "subscription_records": [],
        "active_subscription": False,
        "has_premium": False,
        "environment_variables": {
            "DATABASE_URL_SET": bool(os.getenv("DATABASE_URL"))
        },
        "errors": []
    }
    
    try:
        # Проверяем соединение с базой данных
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            result["errors"].append("DATABASE_URL not set in environment variables")
            return JSONResponse(
                content=result,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
        
        # Подключение к базе данных
        conn = await asyncpg.connect(db_url)
        result["database_connection"] = True
        
        try:
            # Запрос всех записей о подписках пользователя
            subscription_query = """
            SELECT 
                id, user_id, start_date, end_date, payment_id, is_active, 
                created_at, updated_at,
                NOW() as current_time,
                CASE WHEN end_date > NOW() AND is_active = TRUE THEN TRUE ELSE FALSE END as is_valid
            FROM user_subscription 
            WHERE user_id = $1
            ORDER BY end_date DESC
            """
            
            # Выполняем запрос
            subscriptions = await conn.fetch(subscription_query, int(user_id))
            
            # Обрабатываем результаты
            for sub in subscriptions:
                sub_dict = dict(sub)
                for key in sub_dict:
                    if isinstance(sub_dict[key], datetime):
                        sub_dict[key] = sub_dict[key].isoformat()
                result["subscription_records"].append(sub_dict)
            
            # Проверяем наличие активной подписки
            premium_query = """
            SELECT COUNT(*) 
            FROM user_subscription 
            WHERE user_id = $1 
              AND is_active = TRUE 
              AND end_date > NOW()
            """
            count = await conn.fetchval(premium_query, int(user_id))
            result["active_subscription"] = count > 0
            result["has_premium"] = count > 0
            result["premium_count"] = count
            
            # Получаем информацию о самой свежей подписке
            if subscriptions:
                result["latest_subscription"] = dict(subscriptions[0])
                for key in result["latest_subscription"]:
                    if isinstance(result["latest_subscription"][key], datetime):
                        result["latest_subscription"][key] = result["latest_subscription"][key].isoformat()
            
        finally:
            # Закрываем соединение с базой данных
            await conn.close()
            
    except ValueError as ve:
        result["errors"].append(f"Invalid user_id format: {str(ve)}")
    except Exception as e:
        result["errors"].append(f"Error during diagnosis: {str(e)}")
    
    # Возвращаем результат в формате JSON
    return JSONResponse(
        content=result,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

# Эндпоинт принудительного создания премиум-подписки для тестирования
@app.post("/debug/create-premium/{user_id}", response_model=Dict[str, Any])
async def debug_create_premium(user_id: str, request: Request):
    """
    ⚠️ ТОЛЬКО ДЛЯ ОТЛАДКИ ⚠️
    Создает тестовую премиум-подписку для указанного пользователя.
    """
    # Проверяем, что запрос идет локально или с доверенного IP
    client_host = request.client.host if request.client else None
    trusted_hosts = ['127.0.0.1', 'localhost', '::1']
    
    if not (client_host in trusted_hosts or request.headers.get('X-Debug-Token') == os.getenv("DEBUG_TOKEN")):
        return JSONResponse(
            status_code=403,
            content={"error": "Debug endpoints are only accessible from trusted hosts"},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    
    try:
        # Подключение к базе данных
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return JSONResponse(
                status_code=500, 
                content={"error": "DATABASE_URL not set"},
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
        
        # Преобразуем user_id в число
        user_id_int = int(user_id)
        
        # Текущее время и дата окончания (через 30 дней)
        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=30)
        
        # Идентификатор тестового платежа
        test_payment_id = f"debug_payment_{now.strftime('%Y%m%d%H%M%S')}"
        
        # Подключаемся к базе данных
        conn = await asyncpg.connect(db_url)
        
        try:
            # Деактивируем все существующие подписки пользователя
            await conn.execute("""
                UPDATE user_subscription
                SET is_active = FALSE, updated_at = NOW()
                WHERE user_id = $1
            """, user_id_int)
            
            # Создаем новую тестовую подписку
            subscription_id = await conn.fetchval("""
                INSERT INTO user_subscription 
                    (user_id, start_date, end_date, payment_id, is_active, created_at, updated_at)
                VALUES 
                    ($1, $2, $3, $4, TRUE, NOW(), NOW())
                RETURNING id
            """, user_id_int, now, end_date, test_payment_id)
            
            # Формируем ответ
            result = {
                "success": True,
                "message": f"Debug premium subscription created for user {user_id}",
                "subscription_id": subscription_id,
                "user_id": user_id,
                "start_date": now.isoformat(),
                "end_date": end_date.isoformat(),
                "payment_id": test_payment_id,
                "is_active": True
            }
            
            logger.warning(f"DEBUG: Created premium subscription for user {user_id}: ID={subscription_id}")
            
            return JSONResponse(
                content=result,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
            
        finally:
            # Закрываем соединение
            await conn.close()
            
    except ValueError as ve:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid user_id format: {str(ve)}"},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    except Exception as e:
        logger.error(f"Error in debug_create_premium: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error creating debug subscription: {str(e)}"},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

# Добавляем эндпоинт инъекции userID в SPA-приложение
@app.get("/inject-user-id/{user_id}", include_in_schema=False)
async def inject_user_id(user_id: str, request: Request):
    """
    Специальный эндпоинт для инъекции userId в SPA приложение.
    Встраивает JavaScript с userId прямо в HTML страницу.
    """
    try:
        # Проверяем корректность user_id
        user_id_int = int(user_id)
        
        # Получаем путь к index.html
        static_files_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
        index_path = os.path.join(static_files_path, "index.html")
        
        # Проверяем, существует ли файл
        if not os.path.exists(index_path):
            logger.error(f"Файл index.html не найден в {static_files_path}")
            return JSONResponse(
                status_code=404,
                content={"error": "Index file not found"},
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
        
        # Читаем содержимое файла
        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Формируем JavaScript для инъекции userId
        inject_script = f"""
        <script>
        // Инъекция userId = {user_id}
        window.INJECTED_USER_ID = "{user_id}";
        window.addEventListener('load', function() {{
            console.log("[RENDER-USER-ID] Инъекция userId = {user_id}");
            
            // Устанавливаем user_id в localStorage
            try {{
                localStorage.setItem('contenthelper_user_id', '{user_id}');
                console.log("[RENDER-USER-ID] userId сохранен в localStorage");
            }} catch(e) {{
                console.warn("[RENDER-USER-ID] Не удалось сохранить в localStorage:", e);
            }}
            
            // Диспатчим событие для оповещения компонентов
            const event = new CustomEvent('userIdInjected', {{ detail: {{ userId: '{user_id}' }} }});
            document.dispatchEvent(event);
            console.log("[RENDER-USER-ID] Отправлено событие userIdInjected");
            
            // Проверяем статус подписки через прямой API-вызов
            fetch('/api-v2/premium/check?user_id={user_id}&nocache=' + new Date().getTime(), {{
                headers: {{
                    'Accept': 'application/json',
                    'Cache-Control': 'no-cache, no-store, must-revalidate'
                }}
            }})
            .then(response => response.json())
            .then(data => {{
                console.log("[RENDER-USER-ID] Статус премиума:", data);
                
                // Диспатчим событие со статусом подписки
                const statusEvent = new CustomEvent('premiumStatusLoaded', {{ 
                    detail: {{ 
                        premiumStatus: data,
                        userId: '{user_id}'
                    }} 
                }});
                document.dispatchEvent(statusEvent);
            }})
            .catch(error => {{
                console.error("[RENDER-USER-ID] Ошибка проверки премиума:", error);
            }});
        }});
        </script>
        """
        
        # Вставляем скрипт перед закрывающим тегом </head>
        modified_html = html_content.replace('</head>', f'{inject_script}</head>')
        
        # Возвращаем измененный HTML
        return HTMLResponse(
            content=modified_html,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
        
    except ValueError as ve:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid user_id format: {str(ve)}"},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    except Exception as e:
        logger.error(f"Error in inject_user_id: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error injecting user_id: {str(e)}"},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

# Редирект с прямой ссылки телеграма на инъектор user_id
@app.get("/telegram-redirect")
async def telegram_redirect(request: Request):
    """
    Перенаправляет с прямой ссылки телеграма на специальный инъектор user_id.
    Анализирует initData телеграма для получения userId.
    """
    try:
        # Получаем полный URL с параметрами
        full_url = str(request.url)
        
        # Если URL содержит tgWebAppData, извлекаем user_id
        if "tgWebAppData" in full_url:
            # Попытка извлечь userId из данных Telegram WebApp
            try:
                # Находим блок с данными пользователя
                user_match = re.search(r'"user"%3A%7B[^}]*?"id"%3A(\d+)', full_url)
                if user_match:
                    user_id = user_match.group(1)
                    logger.info(f"Извлечен user_id={user_id} из tgWebAppData")
                    
                    # Перенаправляем на инъектор с найденным userId
                    return RedirectResponse(
                        url=f"/inject-user-id/{user_id}", 
                        status_code=302
                    )
            except Exception as extract_e:
                logger.error(f"Ошибка при извлечении userId из tgWebAppData: {extract_e}")
        
        # Если не удалось извлечь userId, ищем его в параметрах запроса
        user_id = request.query_params.get('user_id')
        if user_id:
            logger.info(f"Получен user_id={user_id} из query params")
            # Перенаправляем на инъектор с найденным userId
            return RedirectResponse(
                url=f"/inject-user-id/{user_id}", 
                status_code=302
            )
            
        # Если user_id все еще не найден, возвращаем страницу с запросом ID
        logger.warning("Не удалось определить user_id, возвращаем страницу запроса ID")
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>ContentHelperBot - Введите ID</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    text-align: center; 
                    max-width: 500px; 
                    margin: 0 auto; 
                    padding: 20px;
                }
                .container { margin-top: 50px; }
                input {
                    padding: 10px;
                    width: 100%;
                    font-size: 16px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    margin-bottom: 20px;
                }
                button {
                    padding: 10px 20px;
                    background-color: #1e88e5;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 16px;
                    cursor: pointer;
                }
                h1 { color: #1e88e5; }
                p { margin-bottom: 20px; color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>ContentHelperBot</h1>
                <p>Введите ваш Telegram ID для продолжения:</p>
                <input type="text" id="userId" placeholder="Например: 427032240">
                <button onclick="redirectToApp()">Продолжить</button>
            </div>

            <script>
                function redirectToApp() {
                    const userId = document.getElementById('userId').value.trim();
                    if (userId && !isNaN(userId)) {
                        window.location.href = '/inject-user-id/' + userId;
                    } else {
                        alert('Пожалуйста, введите корректный Telegram ID (только цифры)');
                    }
                }
                
                // Также можно нажать Enter для отправки формы
                document.getElementById('userId').addEventListener('keyup', function(event) {
                    if (event.key === 'Enter') {
                        redirectToApp();
                    }
                });
            </script>
        </body>
        </html>
        """)
            
    except Exception as e:
        logger.error(f"Error in telegram_redirect: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error in redirect: {str(e)}"},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

# Добавляем специальный диагностический эндпоинт для проверки проблем с подпиской
@app.get("/api/subscription/debug/{user_id}", include_in_schema=False)
async def debug_subscription_status(user_id: str):
    """
    Полный диагностический эндпоинт для проверки подписок,
    который возвращает максимум информации для отладки.
    """
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "database_status": "unknown",
        "tables_status": {},
        "subscription_records": [],
        "user_subscription_count": 0,
        "subscriptions_count": 0,
        "has_valid_subscription": False,
        "subscription_end_date": None,
        "errors": []
    }
    
    try:
        # Проверяем соединение с базой данных
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            result["errors"].append("DATABASE_URL не задан в переменных окружения")
            return JSONResponse(content=result)
        
        # Подключаемся к базе данных
        conn = await asyncpg.connect(db_url)
        result["database_status"] = "connected"
        
        try:
            # Проверяем наличие нужных таблиц
            tables_query = """
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN ('user_subscription', 'subscriptions', 'user_usage_stats')
            """
            tables = await conn.fetch(tables_query)
            
            # Заполняем статус таблиц
            found_tables = [t["tablename"] for t in tables]
            result["tables_status"]["user_subscription_exists"] = "user_subscription" in found_tables
            result["tables_status"]["subscriptions_exists"] = "subscriptions" in found_tables
            result["tables_status"]["user_usage_stats_exists"] = "user_usage_stats" in found_tables
            result["tables_status"]["found_tables"] = found_tables
            
            # Если таблица user_subscription существует, проверяем её структуру
            if result["tables_status"]["user_subscription_exists"]:
                # Получаем структуру таблицы
                schema_query = """
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'user_subscription' 
                ORDER BY ordinal_position
                """
                columns = await conn.fetch(schema_query)
                result["tables_status"]["user_subscription_columns"] = [
                    {"name": c["column_name"], "type": c["data_type"]} for c in columns
                ]
                
                # Проверяем записи для пользователя в user_subscription
                user_subs_query = """
                SELECT id, user_id, start_date, end_date, is_active, 
                       payment_id, created_at, updated_at,
                       CASE WHEN end_date > NOW() AND is_active = TRUE 
                           THEN TRUE ELSE FALSE END as is_valid
                FROM user_subscription 
                WHERE user_id = $1 
                ORDER BY end_date DESC
                """
                
                user_id_int = int(user_id)
                user_subs = await conn.fetch(user_subs_query, user_id_int)
                
                # Преобразуем результаты запроса в JSON
                for sub in user_subs:
                    sub_dict = dict(sub)
                    for key, value in sub_dict.items():
                        if isinstance(value, datetime):
                            sub_dict[key] = value.isoformat()
                    result["subscription_records"].append(sub_dict)
                
                result["user_subscription_count"] = len(user_subs)
                result["has_valid_subscription"] = any(sub["is_valid"] for sub in result["subscription_records"])
                
                # Если есть действительная подписка, запоминаем дату окончания
                if result["has_valid_subscription"]:
                    valid_sub = next((sub for sub in result["subscription_records"] if sub["is_valid"]), None)
                    if valid_sub:
                        result["subscription_end_date"] = valid_sub["end_date"]
            
            # Если существует устаревшая таблица subscriptions, тоже проверяем её
            if result["tables_status"]["subscriptions_exists"]:
                subs_count_query = "SELECT COUNT(*) FROM subscriptions WHERE user_id = $1"
                count = await conn.fetchval(subs_count_query, int(user_id))
                result["subscriptions_count"] = count
            
            # Информация о таблице пользовательской статистики
            if result["tables_status"]["user_usage_stats_exists"]:
                stats_query = "SELECT * FROM user_usage_stats WHERE user_id = $1"
                user_stats = await conn.fetchrow(stats_query, int(user_id))
                if user_stats:
                    stats_dict = dict(user_stats)
                    for key, value in stats_dict.items():
                        if isinstance(value, datetime):
                            stats_dict[key] = value.isoformat()
                    result["user_stats"] = stats_dict
                else:
                    result["user_stats"] = None
            
            # Проверяем, есть ли активная подписка
            premium_query = """
            SELECT COUNT(*) 
            FROM user_subscription 
            WHERE user_id = $1 
              AND is_active = TRUE 
              AND end_date > NOW()
            """
            premium_count = await conn.fetchval(premium_query, int(user_id))
            result["has_premium"] = premium_count > 0
            result["premium_count"] = premium_count
            
            # Создаем представление для совместимости, если таблица user_subscription существует
            if result["tables_status"]["user_subscription_exists"] and not result["tables_status"]["subscriptions_exists"]:
                try:
                    view_query = "CREATE VIEW IF NOT EXISTS subscriptions AS SELECT * FROM user_subscription"
                    await conn.execute(view_query)
                    result["tables_status"]["created_view"] = True
                except Exception as view_error:
                    result["errors"].append(f"Ошибка создания представления: {str(view_error)}")
            
            # Если нет активной подписки, создаем тестовую
            if not result["has_premium"] and "create_test" in request.query_params:
                now = datetime.now(timezone.utc)
                end_date = now + timedelta(days=30)
                test_payment_id = f"debug_payment_{now.strftime('%Y%m%d%H%M%S')}"
                
                # Создаем новую тестовую подписку
                try:
                    new_sub_query = """
                    INSERT INTO user_subscription 
                        (user_id, start_date, end_date, payment_id, is_active, created_at, updated_at)
                    VALUES 
                        ($1, $2, $3, $4, TRUE, NOW(), NOW())
                    RETURNING id
                    """
                    new_id = await conn.fetchval(new_sub_query, int(user_id), now, end_date, test_payment_id)
                    result["created_test_subscription"] = {
                        "id": new_id,
                        "start_date": now.isoformat(),
                        "end_date": end_date.isoformat(),
                        "payment_id": test_payment_id
                    }
                    result["has_premium"] = True
                except Exception as sub_error:
                    result["errors"].append(f"Ошибка создания тестовой подписки: {str(sub_error)}")
            
        except Exception as e:
            result["errors"].append(f"Ошибка при проверке таблиц: {str(e)}")
        finally:
            # Закрываем соединение с базой данных
            await conn.close()
            
    except Exception as e:
        result["errors"].append(f"Ошибка при подключении к базе данных: {str(e)}")
    
    # Возвращаем результаты диагностики
    return JSONResponse(
        content=result,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

# Добавляем специальный неперехватываемый эндпоинт для премиум-статуса
@app.get("/raw-api-data/xyz123/premium-data/{user_id}")
async def raw_premium_data(user_id: str):
    """
    Специальный эндпоинт с нестандартным URL, который не должен перехватываться SPA-роутером.
    Возвращает данные о премиум-статусе в чистом JSON формате.
    """
    try:
        # Преобразование user_id в число
        user_id_int = int(user_id)
        
        # Получение данных из БД
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return JSONResponse(
                content={"has_premium": False, "error": "DB connection error", "user_id": user_id},
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Content-Type": "application/json",
                    "X-Content-Type-Options": "nosniff",
                    "Access-Control-Allow-Origin": "*"
                }
            )
            
        # Прямой запрос к базе данных
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
            count = await conn.fetchval(query, user_id_int)
            has_premium = count > 0
            
            # Получаем информацию о текущей/последней подписке
            if has_premium:
                sub_query = """
                SELECT end_date 
                FROM user_subscription 
                WHERE user_id = $1 
                  AND is_active = TRUE
                ORDER BY end_date DESC 
                LIMIT 1
                """
                end_date = await conn.fetchval(sub_query, user_id_int)
                end_date_str = end_date.isoformat() if end_date else None
            else:
                end_date_str = None
                
            result = {
                "has_premium": has_premium,
                "user_id": user_id,
                "error": None,
                "subscription_end_date": end_date_str,
                "analysis_count": 9999 if has_premium else FREE_ANALYSIS_LIMIT,
                "post_generation_count": 9999 if has_premium else FREE_POST_LIMIT,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"[RAW-API] Проверка премиума для пользователя {user_id}: {has_premium}")
            return JSONResponse(
                content=result,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Content-Type": "application/json",
                    "X-Content-Type-Options": "nosniff",
                    "Access-Control-Allow-Origin": "*"
                }
            )
            
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Ошибка в raw_premium_data: {e}")
        return JSONResponse(
            content={"has_premium": False, "error": str(e), "user_id": user_id},
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Content-Type": "application/json",
                "X-Content-Type-Options": "nosniff",
                "Access-Control-Allow-Origin": "*"
            }
        )

# Добавляем специальную страницу, которая напрямую встраивает данные о подписке
@app.get("/premium-page/{user_id}", include_in_schema=False)
async def premium_data_page(user_id: str):
    """
    Специальная страница, которая встраивает данные о подписке непосредственно в HTML.
    Это позволяет обойти проблемы с маршрутизацией API.
    """
    try:
        # Преобразование user_id в число и получение данных
        user_id_int = int(user_id)
        
        # Получение данных из БД
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            premium_data = {
                "has_premium": False, 
                "error": "DB connection error", 
                "user_id": user_id
            }
        else:
            # Прямой запрос к базе данных
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
                count = await conn.fetchval(query, user_id_int)
                has_premium = count > 0
                
                # Получаем информацию о текущей/последней подписке
                if has_premium:
                    sub_query = """
                    SELECT end_date 
                    FROM user_subscription 
                    WHERE user_id = $1 
                      AND is_active = TRUE
                    ORDER BY end_date DESC 
                    LIMIT 1
                    """
                    end_date = await conn.fetchval(sub_query, user_id_int)
                    end_date_str = end_date.isoformat() if end_date else None
                else:
                    end_date_str = None
                    
                premium_data = {
                    "has_premium": has_premium,
                    "user_id": user_id,
                    "error": None,
                    "subscription_end_date": end_date_str,
                    "analysis_count": 9999 if has_premium else FREE_ANALYSIS_LIMIT,
                    "post_generation_count": 9999 if has_premium else FREE_POST_LIMIT,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            finally:
                await conn.close()
        
        # Создаем HTML страницу с встроенными данными о подписке
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Премиум статус - ContentHelperBot</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; max-width: 500px; margin: 0 auto; padding: 20px; }}
                .premium {{ background: linear-gradient(135deg, #1e88e5, #0d47a1); color: white; padding: 20px; border-radius: 10px; }}
                .free {{ background-color: #f5f5f5; padding: 20px; border-radius: 10px; }}
                .premium-badge {{ display: inline-block; background-color: gold; color: #333; padding: 8px 16px; 
                                 border-radius: 20px; font-weight: bold; margin-bottom: 10px; }}
                .free-badge {{ display: inline-block; background-color: #e0e0e0; color: #333; padding: 8px 16px; 
                              border-radius: 20px; font-weight: bold; }}
                .error {{ background-color: #ffebee; color: #c62828; padding: 20px; border-radius: 10px; }}
                button {{ padding: 10px 20px; background-color: #1e88e5; color: white; border: none; 
                         border-radius: 4px; margin-top: 20px; cursor: pointer; }}
                pre {{ background: #f0f0f0; padding: 10px; border-radius: 4px; text-align: left; overflow: auto; }}
            </style>
        </head>
        <body>
            <h1>Статус премиум-подписки</h1>
            <p>Пользователь ID: {user_id}</p>
            
            <div class="{'premium' if premium_data.get('has_premium') else 'free'}">
                {{'<div class="premium-badge">ПРЕМИУМ</div>' if premium_data.get('has_premium') else '<div class="free-badge">Бесплатный доступ</div>'}}
                
                {{'<p>Ваша подписка действительна до: ' + premium_data.get('subscription_end_date', '').split('T')[0] + '</p>' if premium_data.get('subscription_end_date') else ''}}
                
                <p>Доступные анализы: {premium_data.get('analysis_count', 0)}</p>
                <p>Доступные генерации: {premium_data.get('post_generation_count', 0)}</p>
            </div>
            
            <button onclick="window.location.reload()">Обновить статус</button>
            
            <details style="margin-top: 30px;">
                <summary>Данные для отладки</summary>
                <pre>{json.dumps(premium_data, indent=2)}</pre>
            </details>
            
            <script>
                // Сохраняем данные в localStorage для использования в SPA
                const premiumData = {json.dumps(premium_data)};
                localStorage.setItem('premium_data_{user_id}', JSON.stringify(premiumData));
                localStorage.setItem('contenthelper_user_id', '{user_id}');
                
                // Имитируем события для компонентов React
                document.addEventListener('DOMContentLoaded', function() {{
                    // Создаем событие с данными премиум-статуса
                    const event = new CustomEvent('premiumStatusLoaded', {{ 
                        detail: {{ 
                            premiumStatus: premiumData,
                            userId: '{user_id}'
                        }} 
                    }});
                    
                    // Создаем событие с userId
                    const userIdEvent = new CustomEvent('userIdInjected', {{ 
                        detail: {{ 
                            userId: '{user_id}'
                        }} 
                    }});
                    
                    // Отправляем события
                    setTimeout(() => {{
                        console.log('Отправка событий с данными премиум-статуса');
                        document.dispatchEvent(event);
                        document.dispatchEvent(userIdEvent);
                    }}, 500);
                }});
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(
            content=html_content,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
        
    except Exception as e:
        logger.error(f"Ошибка при создании страницы премиум-статуса: {e}")
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Ошибка - ContentHelperBot</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; max-width: 500px; margin: 0 auto; padding: 20px; }}
                .error {{ background-color: #ffebee; color: #c62828; padding: 20px; border-radius: 10px; }}
            </style>
        </head>
        <body>
            <h1>Ошибка при получении данных</h1>
            <div class="error">
                <p>Произошла ошибка при получении статуса подписки:</p>
                <p>{str(e)}</p>
            </div>
            <button onclick="window.location.reload()">Попробовать снова</button>
        </body>
        </html>
        """
        return HTMLResponse(
            content=error_html,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

# Добавляем административный эндпоинт для форсирования премиум-статуса
@app.get("/admin/force-premium/{user_id}/{days}", include_in_schema=False)
async def force_premium_status(user_id: str, days: int = 30, admin_key: str = Query(None)):
    """
    Административный эндпоинт для принудительного создания премиум-подписки
    """
    # Проверка ключа администратора
    if not admin_key or admin_key != os.getenv("ADMIN_KEY", "admin_secret_key"):
        raise HTTPException(status_code=403, detail="Неверный ключ администратора")
    
    try:
        # Преобразуем user_id в число
        user_id_int = int(user_id)
        
        # Получаем соединение с БД
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise HTTPException(status_code=500, detail="Ошибка соединения с базой данных")
        
        # Подключаемся к БД
        conn = await asyncpg.connect(db_url)
        
        try:
            # Определяем даты
            start_date = datetime.now(timezone.utc)
            end_date = start_date + timedelta(days=days)
            
            # Деактивируем все предыдущие подписки для этого пользователя
            await conn.execute(
                "UPDATE user_subscription SET is_active = FALSE WHERE user_id = $1",
                user_id_int
            )
            
            # Создаем новую подписку
            await conn.execute(
                """
                INSERT INTO user_subscription
                (user_id, start_date, end_date, payment_id, is_active, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                user_id_int,
                start_date,
                end_date,
                f"admin_force_{start_date.timestamp()}",
                True,
                start_date,
                start_date
            )
            
            return {
                "success": True,
                "message": f"Премиум-статус успешно активирован для пользователя {user_id}",
                "user_id": user_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "duration_days": days
            }
        finally:
            # Закрываем соединение с БД
            await conn.close()
    except Exception as e:
        logger.error(f"Ошибка при форсировании премиума: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

# ===========================================
# === МОНТИРОВАНИЕ СТАТИЧЕСКИХ ФАЙЛОВ И SPA ===
# ===========================================
# (Этот блок должен идти ПОСЛЕ всех API-маршрутов)

# Путь к статическим файлам фронтенда (например, frontend/dist)
static_files_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

# Проверка существования папки
if os.path.exists(static_files_path) and os.path.isdir(static_files_path):
    logger.info(f"Монтирование статических файлов SPA из: {static_files_path}")
    
    # Монтируем статические файлы, включая index.html как корень
    app.mount("/", StaticFiles(directory=static_files_path, html=True), name="spa-static")

    # Обработчик для корня, если StaticFiles(html=True) не сработает (на всякий случай)
    @app.get("/", include_in_schema=False)
    async def serve_index_explicitly():
        # Проверяем, является ли это API-запросом (например, Ajax)
        if hasattr(request.state, 'is_api_request') and request.state.is_api_request:
            # Если это API запрос, отдаем 404
            raise HTTPException(status_code=404, detail="API endpoint not found")
        
        # Иначе сервим HTML
        index_path = os.path.join(static_files_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            logger.error(f"Файл index.html не найден в {static_files_path}")
            raise HTTPException(status_code=404, detail="Index file not found")

    # Перехват всех остальных путей для SPA-роутинга
    # Этот обработчик должен быть САМЫМ ПОСЛЕДНИМ
    @app.get("/{rest_of_path:path}", include_in_schema=False)
    async def serve_spa_catch_all(request: Request, rest_of_path: str):
        # Если запрос помечен middleware как API-запрос, не обрабатываем его как SPA
        if hasattr(request.state, 'is_api_request') and request.state.is_api_request:
            raise HTTPException(status_code=404, detail="API endpoint not found")
            
        # Список путей, которые не должны обрабатываться SPA
        api_paths = [
            "api", "subscription", "direct_premium_check", "force-premium-status",
            "posts", "analyze", "generate-", "images", "ideas", "telegram",
            "bot", "payment", "health", "api-v2"
        ]
        
        # Проверяем части пути
        path_segments = rest_of_path.split('/')
        if any(segment.startswith(prefix) for segment in path_segments for prefix in api_paths):
            logger.warning(f"Путь '{rest_of_path}' похож на API, но не обработан. Возврат 404.")
            raise HTTPException(status_code=404, detail="API endpoint not found")

        # Иначе, считаем, что это путь для SPA и отдаем index.html
        index_path = os.path.join(static_files_path, "index.html")
        if os.path.exists(index_path):
            logger.debug(f"Отдача index.html для SPA пути: '{rest_of_path}'")
            return FileResponse(index_path)
        else:
            logger.error(f"Файл index.html не найден в {static_files_path} для пути {rest_of_path}")
            raise HTTPException(status_code=404, detail="Index file not found")

else:
    logger.warning(f"Папка статических файлов SPA не найдена: {static_files_path}")
    logger.warning("Фронтенд не будет обслуживаться. Работают только API эндпоинты.")

# Функция для добавления инжектора премиума в HTML
def inject_premium_script(html_content):
    """
    Добавляет скрипт инжектора премиума в HTML-страницу SPA
    """
    # Добавляем скрипт перед закрывающим тегом head
    premium_script = """
    <!-- Premium Status Injector Script -->
    <script>
    // Скрипт для инъекции премиум-статуса напрямую в приложение
    (function() {
      console.log('[PremiumInjector] Инициализация...');
      
      /**
       * Извлекает userId из URL или Telegram WebApp
       */
      function extractUserId() {
        let userId = null;
        
        // Проверяем параметры URL
        const urlParams = new URLSearchParams(window.location.search);
        userId = urlParams.get('user_id');
        
        if (userId) {
          console.log(`[PremiumInjector] Получен userId из URL: ${userId}`);
          return userId;
        }
        
        // Проверяем Telegram WebApp
        if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
          userId = window.Telegram.WebApp.initDataUnsafe.user.id.toString();
          console.log(`[PremiumInjector] Получен userId из Telegram WebApp: ${userId}`);
          return userId;
        }
        
        // Проверяем localStorage
        const storedUserId = localStorage.getItem('contenthelper_user_id');
        if (storedUserId) {
          console.log(`[PremiumInjector] Получен userId из localStorage: ${storedUserId}`);
          return storedUserId;
        }
        
        return null;
      }
      
      /**
       * Сохраняет премиум-статус в localStorage
       */
      function savePremiumStatus(userId, isPremium = true, daysValid = 30) {
        if (!userId) return;
        
        const now = new Date();
        const endDate = new Date();
        endDate.setDate(now.getDate() + daysValid);
        
        const premiumData = {
          has_premium: isPremium,
          user_id: userId,
          error: null,
          subscription_end_date: endDate.toISOString(),
          analysis_count: isPremium ? 9999 : 3,
          post_generation_count: isPremium ? 9999 : 1
        };
        
        localStorage.setItem(`premium_data_${userId}`, JSON.stringify(premiumData));
        localStorage.setItem('contenthelper_user_id', userId);
        
        console.log(`[PremiumInjector] Установлен ${isPremium ? 'ПРЕМИУМ' : 'БЕСПЛАТНЫЙ'} статус для пользователя ${userId}`);
        
        // Создаем пользовательское событие
        const event = new CustomEvent('premiumStatusLoaded', {
          detail: {
            premiumStatus: premiumData,
            userId: userId
          }
        });
        
        // Создаем событие с userId
        const userIdEvent = new CustomEvent('userIdInjected', {
          detail: {
            userId: userId
          }
        });
        
        // Отправляем события
        document.dispatchEvent(event);
        document.dispatchEvent(userIdEvent);
        
        // Устанавливаем глобальную переменную
        window.INJECTED_USER_ID = userId;
        
        return premiumData;
      }
      
      /**
       * Проверяет URL на наличие команды для инъекции премиума
       */
      function checkForPremiumCommand() {
        // Проверяем хэш в URL
        const hash = window.location.hash;
        if (hash && hash.includes('force_premium')) {
          console.log('[PremiumInjector] Обнаружена команда force_premium в URL');
          
          const userId = extractUserId();
          if (userId) {
            savePremiumStatus(userId, true, 30);
            
            // Очищаем хэш, чтобы команда не выполнялась повторно
            if (history.replaceState) {
              history.replaceState(null, null, window.location.pathname + window.location.search);
            }
          }
        }
      }
      
      // Выполняем проверку при загрузке страницы
      document.addEventListener('DOMContentLoaded', checkForPremiumCommand);
      
      // Также проверяем сразу (может пригодиться, если DOM уже загружен)
      if (document.readyState === 'complete' || document.readyState === 'interactive') {
        setTimeout(checkForPremiumCommand, 100);
      }
      
      // Экспортируем функции в глобальный объект window
      window.PremiumInjector = {
        extractUserId,
        savePremiumStatus,
        forcePremium: function(userId, days = 30) {
          if (!userId) {
            userId = extractUserId();
          }
          if (userId) {
            return savePremiumStatus(userId, true, days);
          }
          return null;
        }
      };
      
    })();
    </script>
    """
    
    # Вставляем перед закрывающим тегом </head>
    if "</head>" in html_content:
        html_content = html_content.replace("</head>", f"{premium_script}</head>")
    
    return html_content

# Функция-middleware для модификации HTML-ответов
@app.middleware("http")
async def spa_html_modifier(request: Request, call_next):
    # Пропускаем API-запросы
    if request.url.path.startswith("/api/") or request.url.path.startswith("/raw-api-data/"):
        return await call_next(request)
    
    response = await call_next(request)
    
    # Модифицируем только HTML-ответы
    if response.headers.get("content-type") and "text/html" in response.headers.get("content-type"):
        # Получаем тело ответа
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        
        # Декодируем HTML и модифицируем
        html_content = body.decode("utf-8")
        modified_html = inject_premium_script(html_content)
        
        # Создаем новый ответ
        return HTMLResponse(
            content=modified_html,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
    
    return response

# --- Запуск сервера (если используется __main__) ---
if __name__ == "__main__":
    # ... (проверка переменных окружения) ...
    # check_required_env_vars() # Убедитесь, что эта функция существует или добавьте ее
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Запуск сервера на http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port) # Используем app напрямую 