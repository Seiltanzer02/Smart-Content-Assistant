import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from supabase_py_async.lib.utils import APIError # Убедитесь, что этот импорт корректен

# Импортируем supabase и logger из родительского main.py (backend/main.py)
from ..main import supabase, logger

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
async def get_user_settings(
    request: Request,
    user_id: int = Depends(get_telegram_user_id_from_request)
):
    """
    Получение пользовательских настроек.
    """
    if not supabase:
        logger.error("Supabase клиент не инициализирован при получении настроек пользователя")
        raise HTTPException(status_code=503, detail="База данных недоступна")

    try:
        response = await asyncio.to_thread(
            supabase.table("user_settings")
            .select("*")
            .eq("user_id", user_id)
            .maybe_single()
            .execute
        )
        if response.data:
            return UserSettingsResponse(**response.data)
        return None # Возвращаем None если настроек нет, фронтенд обработает
    except APIError as e:
        logger.error(f"Supabase APIError при получении настроек пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {e.message}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при получении настроек пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.put("/settings", response_model=UserSettingsResponse)
async def update_user_settings(
    settings_data: UserSettingsCreate,
    request: Request,
    user_id: int = Depends(get_telegram_user_id_from_request)
):
    """
    Обновление или создание пользовательских настроек.
    """
    if not supabase:
        logger.error("Supabase клиент не инициализирован при обновлении настроек пользователя")
        raise HTTPException(status_code=503, detail="База данных недоступна")

    now = datetime.now(timezone.utc)
    
    data_to_save = settings_data.model_dump() if hasattr(settings_data, 'model_dump') else settings_data.dict()
    data_to_save["user_id"] = user_id
    data_to_save["updated_at"] = now.isoformat() # Сохраняем в ISO формате

    try:
        existing_settings_response = await asyncio.to_thread(
            supabase.table("user_settings")
            .select("id") 
            .eq("user_id", user_id)
            .maybe_single()
            .execute
        )

        if existing_settings_response.data:
            response = await asyncio.to_thread(
                supabase.table("user_settings")
                .update(data_to_save)
                .eq("user_id", user_id)
                .execute
            )
        else:
            data_to_save["created_at"] = now.isoformat() # Сохраняем в ISO формате
            response = await asyncio.to_thread(
                supabase.table("user_settings")
                .insert(data_to_save)
                .execute
            )
        
        if response.data:
            return UserSettingsResponse(**response.data[0])
        else:
            logger.error(f"Ошибка при сохранении настроек пользователя {user_id}: ответ Supabase не содержит данных. Response: {response}")
            raise HTTPException(status_code=500, detail="Не удалось сохранить настройки пользователя")

    except APIError as e:
        logger.error(f"Supabase APIError при сохранении настроек пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {e.message}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при сохранении настроек пользователя {user_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
# === КОНЕЦ API ЭНДПОИНТОВ USER_SETTINGS === 