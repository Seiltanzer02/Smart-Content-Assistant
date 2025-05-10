# Сервис для работы с пользовательскими настройками
from fastapi import Request, HTTPException
from typing import Optional
from backend.main import supabase, logger
import uuid
from datetime import datetime

async def get_user_settings(request: Request):
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос настроек пользователя без идентификации Telegram")
            raise HTTPException(status_code=401, detail="Для доступа к настройкам необходимо авторизоваться через Telegram")
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        result = supabase.table("user_settings").select("*").eq("user_id", int(telegram_user_id)).maybe_single().execute()
        if not hasattr(result, 'data') or not result.data:
            logger.info(f"Настройки пользователя {telegram_user_id} не найдены, возвращаем пустой объект")
            return None
        return result.data
    except Exception as e:
        logger.error(f"Ошибка при получении настроек пользователя: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при получении настроек пользователя: {str(e)}")

async def update_user_settings(settings_data, request: Request):
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос обновления настроек без идентификации Telegram")
            raise HTTPException(status_code=401, detail="Для обновления настроек необходимо авторизоваться через Telegram")
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        # Проверяем, есть ли уже настройки для пользователя
        result = supabase.table("user_settings").select("*").eq("user_id", int(telegram_user_id)).maybe_single().execute()
        now = datetime.now().isoformat()
        data_to_save = settings_data.dict() if hasattr(settings_data, 'dict') else dict(settings_data)
        data_to_save["user_id"] = int(telegram_user_id)
        data_to_save["updated_at"] = now
        if not result.data:
            # Создаем новые настройки
            data_to_save["id"] = str(uuid.uuid4())
            data_to_save["created_at"] = now
            insert_result = supabase.table("user_settings").insert(data_to_save).execute()
            if hasattr(insert_result, 'data') and len(insert_result.data) > 0:
                logger.info(f"Созданы новые настройки для пользователя {telegram_user_id}")
                return insert_result.data[0]
            else:
                logger.error(f"Ошибка при создании настроек: {insert_result}")
                raise HTTPException(status_code=500, detail="Ошибка при создании настроек пользователя")
        else:
            # Обновляем существующие настройки
            update_result = supabase.table("user_settings").update(data_to_save).eq("user_id", int(telegram_user_id)).execute()
            if hasattr(update_result, 'data') and len(update_result.data) > 0:
                logger.info(f"Обновлены настройки для пользователя {telegram_user_id}")
                return update_result.data[0]
            else:
                logger.error(f"Ошибка при обновлении настроек: {update_result}")
                raise HTTPException(status_code=500, detail="Ошибка при обновлении настроек пользователя")
    except Exception as e:
        logger.error(f"Ошибка при обновлении настроек пользователя: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении настроек пользователя: {str(e)}") 