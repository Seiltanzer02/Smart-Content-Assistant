import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

# Импортируем supabase и logger из родительского main.py (backend/main.py)
from ..main import supabase, logger
from backend.services.user_settings_service import get_user_settings as main_get_user_settings, update_user_settings as main_update_user_settings
from backend.telegram_utils import get_official_stars_affiliate_link
import os

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

@router.post("/partnerlink")
async def get_partner_link(request: Request):
    """
    Получить и сохранить официальную партнерскую ссылку Stars для пользователя.
    """
    # Получаем user_id из заголовка Telegram WebApp
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id or not telegram_user_id.isdigit():
        raise HTTPException(status_code=400, detail="Некорректный или отсутствующий Telegram ID")
    user_id = int(telegram_user_id)
    bot_username = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_username:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN не задан в окружении")
    # Получаем username бота из токена
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.users import GetFullUserRequest
    import re
    # Если токен в формате 123456:ABC...@YourBot, то username после @
    match = re.search(r'@([\w_]+)', bot_username)
    if match:
        bot_username = '@' + match.group(1)
    else:
        # Если токен без @, используем переменную окружения VITE_TARGET_CHANNEL_USERNAME или TARGET_CHANNEL_USERNAME
        bot_username = os.getenv("VITE_TARGET_CHANNEL_USERNAME") or os.getenv("TARGET_CHANNEL_USERNAME")
        if not bot_username:
            raise HTTPException(status_code=500, detail="Не удалось определить username бота")
    # Проверяем, есть ли уже ссылка в user_settings
    user_settings = supabase.table("user_settings").select("partner_link").eq("user_id", user_id).single().execute()
    if user_settings.data and user_settings.data.get("partner_link"):
        return {"partner_link": user_settings.data["partner_link"]}
    # Получаем ссылку через Telethon
    link = await get_official_stars_affiliate_link(user_id, bot_username)
    # Сохраняем ссылку в user_settings
    supabase.table("user_settings").update({"partner_link": link}).eq("user_id", user_id).execute()
    return {"partner_link": link}
# === КОНЕЦ API ЭНДПОИНТОВ USER_SETTINGS === 