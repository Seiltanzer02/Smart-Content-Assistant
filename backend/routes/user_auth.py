from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Dict, Any, Optional
from backend.services.telegram_subscription_check import check_user_channel_subscription, send_subscription_prompt
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/check-channel-subscription")
async def check_channel_subscription_route(request: Request):
    """
    Проверяет, подписан ли пользователь на целевой канал.
    Если нет - отправляет сообщение с предложением подписаться.
    """
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id or not telegram_user_id.isdigit():
        logger.warning(f"Попытка проверки подписки без валидного Telegram ID: {telegram_user_id}")
        return {"subscribed": False, "error": "Не удалось определить Telegram ID"}
    
    user_id = int(telegram_user_id)
    try:
        logger.info(f"Проверка подписки для пользователя {user_id}")
        is_subscribed = await check_user_channel_subscription(user_id)
        
        if not is_subscribed:
            logger.info(f"Пользователь {user_id} не подписан на канал. Отправляем сообщение.")
            await send_subscription_prompt(user_id)
        else:
            logger.info(f"Пользователь {user_id} подписан на канал.")
            
        return {"subscribed": is_subscribed}
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки для пользователя {user_id}: {e}")
        return {"subscribed": False, "error": str(e)} 