from fastapi import APIRouter, Request, HTTPException
import logging
import os
from backend.services.telegram_subscription_check import check_user_channel_subscription, send_subscription_prompt

router = APIRouter()
logger = logging.getLogger("subscription_routes")

@router.post("/subscription_check")
async def subscription_check_special(request: Request):
    """
    Специальный эндпоинт для проверки подписки на канал.
    Использует нестандартный URL-путь, который не конфликтует с маршрутизацией фронтенда.
    """
    logger.info("Запрос на нестандартный эндпоинт проверки подписки")
    
    # Получаем ID пользователя
    try:
        body = await request.json()
        user_id = body.get("user_id")
        if not user_id and "X-Telegram-User-Id" in request.headers:
            user_id = request.headers.get("X-Telegram-User-Id")
        
        logger.info(f"Проверка подписки для user_id: {user_id}")
        
        if not user_id or (isinstance(user_id, str) and not user_id.isdigit()):
            return {
                "subscribed": False,
                "error": "Не указан ID пользователя Telegram",
                "special_endpoint": True
            }
        
        user_id_int = int(user_id)
        
        # Проверяем переменные окружения
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        channel_username = os.getenv("TARGET_CHANNEL_USERNAME")
        
        if not bot_token or not channel_username:
            return {
                "subscribed": False,
                "error": "Отсутствуют необходимые переменные окружения",
                "special_endpoint": True
            }
        
        # Проверяем подписку
        is_subscribed = await check_user_channel_subscription(user_id_int)
        logger.info(f"Результат проверки подписки через спец. эндпоинт: {is_subscribed}")
        
        if not is_subscribed:
            try:
                await send_subscription_prompt(user_id_int)
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления: {e}")
        
        return {
            "subscribed": is_subscribed,
            "user_id": user_id_int,
            "channel": channel_username.lstrip("@"),
            "special_endpoint": True
        }
        
    except Exception as e:
        logger.exception(f"Ошибка при обработке запроса: {e}")
        return {
            "subscribed": False,
            "error": str(e),
            "special_endpoint": True
        } 