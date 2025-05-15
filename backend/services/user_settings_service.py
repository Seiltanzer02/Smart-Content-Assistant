# Сервис для работы с пользовательскими настройками
from fastapi import Request, HTTPException
from typing import Optional, Dict, Any
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
            # Если поле is_subscribed_to_channel не передано, устанавливаем по умолчанию в False
            if "is_subscribed_to_channel" not in data_to_save:
                data_to_save["is_subscribed_to_channel"] = False
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

async def check_channel_subscription(user_id: int, channel_username: str) -> Dict[str, Any]:
    """
    Проверяет, подписан ли пользователь на канал.
    Возвращает словарь с результатами проверки.
    """
    try:
        from backend.main import send_telegram_message
        import os
        import httpx
        import json
        
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not telegram_token:
            logger.error("Отсутствует TELEGRAM_BOT_TOKEN при проверке подписки")
            return {"success": False, "is_subscribed": False, "error": "Токен Telegram не настроен"}
            
        # Проверяем, подписан ли пользователь на канал через getChatMember
        chat_id = f"@{channel_username.strip('@')}"
        telegram_api_url = f"https://api.telegram.org/bot{telegram_token}/getChatMember"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(telegram_api_url, json={
                    "chat_id": chat_id,
                    "user_id": user_id
                })
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok") and result.get("result"):
                        status = result["result"].get("status")
                        # Пользователь подписан, если статус один из: creator, administrator, member
                        is_subscribed = status in ["creator", "administrator", "member"]
                        return {"success": True, "is_subscribed": is_subscribed, "status": status}
                    else:
                        logger.error(f"Неожиданный ответ от Telegram API: {result}")
                        return {"success": False, "is_subscribed": False, "error": "Неожиданный ответ от Telegram API"}
                else:
                    logger.error(f"Ошибка при запросе к Telegram API: {response.status_code} {response.text}")
                    return {"success": False, "is_subscribed": False, "error": f"Ошибка Telegram API: {response.status_code}"}
            except Exception as e:
                logger.error(f"Исключение при запросе к Telegram API: {e}")
                return {"success": False, "is_subscribed": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки на канал: {e}")
        return {"success": False, "is_subscribed": False, "error": str(e)}

async def update_subscription_status(user_id: int, is_subscribed: bool) -> Dict[str, Any]:
    """
    Обновляет статус подписки пользователя на канал в базе данных.
    """
    try:
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            return {"success": False, "error": "База данных недоступна"}
            
        # Проверяем, есть ли уже настройки для пользователя
        result = supabase.table("user_settings").select("*").eq("user_id", user_id).maybe_single().execute()
        now = datetime.now().isoformat()
        
        if not result.data:
            # Создаем новые настройки
            new_settings = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "is_subscribed_to_channel": is_subscribed,
                "created_at": now,
                "updated_at": now
            }
            insert_result = supabase.table("user_settings").insert(new_settings).execute()
            if hasattr(insert_result, 'data') and len(insert_result.data) > 0:
                logger.info(f"Создана запись о подписке для пользователя {user_id}: {is_subscribed}")
                return {"success": True, "is_subscribed": is_subscribed}
            else:
                logger.error(f"Ошибка при создании записи о подписке: {insert_result}")
                return {"success": False, "error": "Ошибка сохранения данных"}
        else:
            # Обновляем существующие настройки
            update_data = {
                "is_subscribed_to_channel": is_subscribed,
                "updated_at": now
            }
            update_result = supabase.table("user_settings").update(update_data).eq("user_id", user_id).execute()
            if hasattr(update_result, 'data') and len(update_result.data) > 0:
                logger.info(f"Обновлен статус подписки для пользователя {user_id}: {is_subscribed}")
                return {"success": True, "is_subscribed": is_subscribed}
            else:
                logger.error(f"Ошибка при обновлении статуса подписки: {update_result}")
                return {"success": False, "error": "Ошибка обновления данных"}
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса подписки: {e}")
        return {"success": False, "error": str(e)} 