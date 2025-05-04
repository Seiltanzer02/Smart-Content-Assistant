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
from fastapi import FastAPI, HTTPException, Request, Depends, Response, File, UploadFile, Form
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from dotenv import load_dotenv
from dateutil.relativedelta import relativedelta

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
logger = logging.getLogger('main')

# Конфигурация приложения и БД
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or OPENAI_API_KEY  # Используем OpenAI API ключ как запасной вариант

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

# ===========================================
# === ВСЕ ОПРЕДЕЛЕНИЯ API МАРШРУТОВ ЗДЕСЬ ===
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
            raise HTTPException(status_code=400, detail="user_id is required")
            
        # Получение сервиса подписок
        subscription_service = await get_subscription_service()
        
        # Запрос на получение данных подписки
        subscription_data = await subscription_service.get_subscription(int(user_id))
        
        # Добавляем заголовки для предотвращения кэширования
        response = JSONResponse(content=dict(subscription_data))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        # Логирование успешного запроса
        logger.info(f"Получен статус подписки для user_id={user_id}: {subscription_data}")
        
        return response
    except ValueError as ve:
        logger.error(f"Ошибка преобразования user_id: {ve}")
        raise HTTPException(status_code=400, detail=f"Invalid user_id format: {str(ve)}")
    except Exception as e:
        logger.error(f"Ошибка при получении статуса подписки: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching subscription status: {str(e)}")

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
            raise HTTPException(status_code=400, detail="user_id is required")
            
        # Получение сервиса подписок
        subscription_service = await get_subscription_service()
        
        # Прямой запрос в БД на проверку премиум-статуса
        has_premium = await subscription_service.check_premium_directly(int(user_id))
        
        # Добавляем заголовки для предотвращения кэширования
        response = JSONResponse(content={"has_premium": has_premium, "user_id": user_id})
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        # Логирование успешного запроса
        logger.info(f"Прямая проверка премиум для user_id={user_id}: {has_premium}")
        
        return response
    except ValueError as ve:
        logger.error(f"Ошибка преобразования user_id: {ve}")
        raise HTTPException(status_code=400, detail=f"Invalid user_id format: {str(ve)}")
    except Exception as e:
        logger.error(f"Ошибка при прямой проверке премиум: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking premium status: {str(e)}")

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
    # ... (реализация) ...
    pass # Заглушка

@app.put("/posts/{post_id}", response_model=SavedPostResponse)
async def update_post(post_id: str, request: Request, post_data: PostData):
     # ... (реализация) ...
    pass # Заглушка

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

# --- Добавьте сюда ВСЕ остальные ваши API-эндпоинты ---
# @app.get("/ideas", ...)
# @app.post("/save-suggested-ideas", ...)
# @app.get("/channel-analysis", ...)
# @app.get("/images", ...)
# @app.post("/save-image", ...)
# @app.get("/images/{image_id}", ...)
# @app.get("/post-images/{post_id}", ...)
# @app.get("/image-proxy/{image_id}", ...)
# @app.get("/fix-schema", ...)
# @app.get("/check-schema", ...)
# @app.get("/recreate-schema", ...)
# @app.post("/telegram/webhook", ...)
# @app.post("/bot/webhook", ...)
# @app.post("/payment/confirm", ...)
# @app.post("/payment/webhook", ...)
# @app.get("/health", ...)

# ===========================================
# === КОНЕЦ ОПРЕДЕЛЕНИЙ API МАРШРУТОВ ===
# ===========================================


# --- МОНТИРОВАНИЕ СТАТИЧЕСКИХ ФАЙЛОВ И SPA ---
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
        index_path = os.path.join(static_files_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
             logger.error(f"Файл index.html не найден в {static_files_path}")
             raise HTTPException(status_code=404, detail="Index file not found")

    # ВАЖНО: Список API-путей должен быть точным и актуальным!
    # Это предотвратит перехват API-запросов SPA-обработчиком
    api_paths = [
        "/api/",
        "/docs",
        "/openapi.json",
        "/subscription/",
        "/direct_premium_check",
        "/posts",
        "/analyze",
        "/generate-",
        "/images",
        "/ideas",
        "/telegram/",
        "/bot/",
        "/payment/",
        "/health"
    ]

    # Middleware для корректной обработки API-запросов
    @app.middleware("http")
    async def api_priority_middleware(request: Request, call_next):
        # Проверяем, является ли путь API-запросом
        path = request.url.path
        is_api_request = any(path.startswith(api_prefix) for api_prefix in api_paths)
        
        # Если это API-запрос, пропускаем его через основной обработчик
        if is_api_request:
            logger.debug(f"API запрос: {path}")
            return await call_next(request)
        
        # Для других путей - стандартное поведение
        response = await call_next(request)
        return response

    # Перехват всех остальных путей для SPA-роутинга
    # Этот обработчик должен быть САМЫМ ПОСЛЕДНИМ
    @app.get("/{rest_of_path:path}", include_in_schema=False)
    async def serve_spa_catch_all(request: Request, rest_of_path: str):
        # Проверка api_paths уже в middleware, здесь для дополнительной защиты
        if any(rest_of_path.startswith(prefix.lstrip('/')) for prefix in api_paths):
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

    # Принудительная проверка премиум
    @app.get("/force-premium-status/{user_id}", include_in_schema=True)
    async def force_premium_status(user_id: str):
        """
        Прямая проверка премиум-статуса по ID пользователя без использования ORM.
        Этот метод имеет максимальный приоритет перед SPA-обработчиком.
        """
        try:
            # Преобразование user_id в число
            try:
                user_id_int = int(user_id)
            except ValueError:
                return JSONResponse(
                    content={"has_premium": False, "error": "Invalid user_id format"},
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
                )
            
            # Получение данных из БД
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                logger.error("DATABASE_URL не указан в переменных окружения")
                return JSONResponse(
                    content={"has_premium": False, "error": "DB connection error"},
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
                )
            
            # Прямой запрос к базе данных
            conn = await asyncpg.connect(db_url)
            try:
                # Проверяем наличие активной подписки
                query = """
                SELECT COUNT(*) 
                FROM subscriptions 
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
                    FROM subscriptions 
                    WHERE user_id = $1 
                      AND is_active = TRUE
                      AND end_date > NOW()
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
                    "analysis_count": 9999 if has_premium else 1,
                    "post_generation_count": 9999 if has_premium else 1
                }
                
                logger.info(f"Проверка премиума для пользователя {user_id}: {result}")
                return JSONResponse(
                    content=result,
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
                )
                
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error in force_premium_status: {e}")
            return JSONResponse(
                content={"has_premium": False, "error": str(e)},
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )

else:
    logger.warning(f"Папка статических файлов SPA не найдена: {static_files_path}")
    logger.warning("Фронтенд не будет обслуживаться. Работают только API эндпоинты.")

# --- Запуск сервера (если используется __main__) ---
if __name__ == "__main__":
    # ... (проверка переменных окружения) ...
    # check_required_env_vars() # Убедитесь, что эта функция существует или добавьте ее
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Запуск сервера на http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port) # Используем app напрямую 