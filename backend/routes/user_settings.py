import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

# Импортируем supabase и logger из родительского main.py (backend/main.py)
from ..main import supabase, logger, send_telegram_message
from backend.services.user_settings_service import get_user_settings as main_get_user_settings, update_user_settings as main_update_user_settings
from backend.services.user_settings_service import check_channel_subscription, update_subscription_status

router = APIRouter()

# === МОДЕЛИ PYDANTIC ДЛЯ USER_SETTINGS ===
class UserSettingsBase(BaseModel):
    channelName: Optional[str] = None
    selectedChannels: List[str] = Field(default_factory=list)
    allChannels: List[str] = Field(default_factory=list)
    is_subscribed_to_channel: Optional[bool] = False

class UserSettingsCreate(UserSettingsBase):
    pass

class UserSettingsResponse(UserSettingsBase):
    id: uuid.UUID
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # Для Pydantic v2, заменяет orm_mode
# === КОНЕЦ МОДЕЛЕЙ USER_SETTINGS ===

class SubscriptionCheckRequest(BaseModel):
    channel_username: str = Field(..., description="Имя канала для проверки подписки")

class SubscriptionResponse(BaseModel):
    success: bool = Field(..., description="Успешно ли выполнена операция")
    is_subscribed: bool = Field(..., description="Подписан ли пользователь на канал")
    message: Optional[str] = Field(None, description="Сообщение с результатом операции")
    error: Optional[str] = Field(None, description="Сообщение об ошибке, если она произошла")

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

# === API ЭНДПОИНТЫ ДЛЯ USER_SETTINGS ===

@router.get("/settings", response_model=Optional[UserSettingsResponse])
async def get_user_settings_router(request: Request):
    return await main_get_user_settings(request)

@router.put("/settings", response_model=UserSettingsResponse)
async def update_user_settings_router(settings_data: UserSettingsCreate, request: Request):
    return await main_update_user_settings(settings_data, request)

@router.post("/check-subscription", response_model=SubscriptionResponse)
async def check_subscription_router(
    request: SubscriptionCheckRequest, 
    user_request: Request,
    user_id: int = Depends(get_telegram_user_id_from_request)
):
    """
    Проверяет, подписан ли пользователь на указанный канал
    """
    channel_username = request.channel_username.strip()
    if not channel_username:
        raise HTTPException(status_code=400, detail="Не указано имя канала")
    
    # Нормализуем имя канала (убираем @ если он есть)
    channel_username = channel_username.lstrip('@')
    
    # Проверяем подписку
    check_result = await check_channel_subscription(user_id, channel_username)
    
    if check_result["success"]:
        # Если проверка успешна, обновляем статус в БД
        await update_subscription_status(user_id, check_result["is_subscribed"])
        
        message = None
        if check_result["is_subscribed"]:
            message = "Вы подписаны на канал"
        else:
            message = "Вы не подписаны на канал"
            
            # Отправляем сообщение в чат, если пользователь не подписан
            await send_telegram_message(
                user_id, 
                f"Для использования приложения необходимо подписаться на канал @{channel_username}."
            )
        
        return {
            "success": True,
            "is_subscribed": check_result["is_subscribed"],
            "message": message
        }
    else:
        # В случае ошибки возвращаем информацию о ней
        return {
            "success": False,
            "is_subscribed": False,
            "error": check_result.get("error", "Неизвестная ошибка при проверке подписки")
        }
# === КОНЕЦ API ЭНДПОИНТОВ USER_SETTINGS === 