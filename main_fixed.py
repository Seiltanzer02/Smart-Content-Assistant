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

# ... (остальная часть кода до первого определения /generate-invoice остается неизменной) ...

# Первое определение эндпоинта /generate-invoice остается неизменным
@app.post("/generate-invoice", response_model=Dict[str, Any])
async def generate_invoice(
    request: Request,
    subscription_service: SubscriptionService = Depends(get_subscription_service)
):
    """Генерирует инвойс для оплаты подписки Stars"""
    try:
        # Получаем данные из запроса
        data = await request.json()
        
        # Проверяем обязательные поля
        if not data.get("user_id") or not data.get("amount"):
            raise HTTPException(status_code=400, detail="Отсутствуют обязательные параметры")
        
        user_id = data["user_id"]
        amount = int(data["amount"])
        
        logger.info(f"Генерация инвойса для пользователя {user_id} на сумму {amount} Stars")
        
        # Создаем уникальный ID платежа
        payment_id = f"stars_invoice_{int(time.time())}_{user_id}"
        
        # Получаем токен бота из переменных окружения
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise HTTPException(status_code=500, detail="Отсутствует токен бота")
        
        # Создаем заголовок и описание товара
        title = "Подписка Premium"
        description = "Подписка Premium на Smart Content Assistant на 1 месяц"
        
        # Формируем URL для API запроса на создание инвойса
        api_url = f"https://api.telegram.org/bot{bot_token}/createInvoiceLink"
        
        # Формируем параметры запроса
        payload = {
            "title": title,
            "description": description,
            "payload": payment_id,
            "provider_token": "", # Для Stars оставляем пустым
            "currency": "XTR", # XTR - код для Stars
            "prices": [{"label": "Подписка Premium", "amount": amount * 100}], # В копейках (1 Star = 100 копеек)
            "max_tip_amount": 0,
            "suggested_tip_amounts": [],
            "photo_url": "https://smart-content-assistant.onrender.com/static/premium_sub.jpg", # URL изображения для счета
            "photo_width": 600,
            "photo_height": 400,
            "need_name": False,
            "need_phone_number": False,
            "need_email": False,
            "need_shipping_address": False,
            "send_phone_number_to_provider": False,
            "send_email_to_provider": False,
            "is_flexible": False
        }
        
        # Отправляем запрос к Telegram Bot API
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=payload)
            response_data = response.json()
        
        # Проверяем успешность запроса
        if not response_data.get("ok"):
            logger.error(f"Ошибка при создании инвойса: {response_data}")
            raise HTTPException(status_code=500, detail=f"Ошибка API Telegram: {response_data.get('description')}")
        
        # Получаем URL инвойса
        invoice_url = response_data.get("result")
        
        return {
            "success": True,
            "invoice_url": invoice_url,
            "payment_id": payment_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при генерации инвойса: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при генерации инвойса: {str(e)}")

# Дублирующийся блок эндпоинта /generate-invoice удален

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 