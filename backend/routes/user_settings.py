import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

# Импортируем supabase и logger из родительского main.py (backend/main.py)
from ..main import supabase, logger
from backend.services.user_settings_service import get_user_settings as main_get_user_settings, update_user_settings as main_update_user_settings

router = APIRouter()

# === МОДЕЛИ PYDANTIC ДЛЯ USER_SETTINGS ===
class UserSettingsBase(BaseModel):
    channelName: Optional[str] = None
    selectedChannels: List[str] = Field(default_factory=list)
    allChannels: List[str] = Field(default_factory=list)

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
# === КОНЕЦ API ЭНДПОИНТОВ USER_SETTINGS === 