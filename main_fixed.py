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
async def get_subscription_status(
    # ... (зависимости и код эндпоинта) ...
):
    # ... (реализация) ...
    pass # Заглушка

@app.get("/direct_premium_check", response_model=DirectPremiumStatusResponse)
async def direct_premium_check(request: Request):
    # ... (реализация) ...
    pass # Заглушка

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
    @app.get("/")
    async def serve_index_explicitly():
        index_path = os.path.join(static_files_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
             logger.error(f"Файл index.html не найден в {static_files_path}")
             raise HTTPException(status_code=404, detail="Index file not found")

    # Перехват всех остальных путей для SPA-роутинга
    # Этот обработчик должен быть САМЫМ ПОСЛЕДНИМ
    @app.get("/{rest_of_path:path}")
    async def serve_spa_catch_all(request: Request, rest_of_path: str):
        # Проверяем, не является ли путь зарезервированным для API
        # (Можно улучшить эту проверку, но для начала так)
        api_prefixes = ("/api/", "/docs", "/openapi.json", "/subscription/", "/direct_premium_check", "/posts", "/analyze", "/generate-", "/images", "/ideas", "/telegram/", "/bot/", "/payment/", "/health")
        if any(rest_of_path.startswith(prefix) for prefix in api_prefixes):
             # Если это похоже на API-путь, который не был обработан выше, возвращаем 404
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

# --- Запуск сервера (если используется __main__) ---
if __name__ == "__main__":
    # ... (проверка переменных окружения) ...
    # check_required_env_vars() # Убедитесь, что эта функция существует или добавьте ее
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Запуск сервера на http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port) # Используем app напрямую 