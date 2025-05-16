from fastapi import APIRouter, Request
from backend.services.telegram_subscription_check import check_user_channel_subscription, send_subscription_prompt
import logging

# Создаем собственный логгер вместо импорта из main
logger = logging.getLogger("subscription_check")

router = APIRouter(
    prefix="/api",
    tags=["Subscription"]
)

@router.get("/check-channel-subscription")
async def check_channel_subscription_get(request: Request):
    """
    Проверяет подписку пользователя на канал (GET-метод).
    """
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id or not telegram_user_id.isdigit():
        return {"subscribed": False, "error": "Не удалось определить Telegram ID"}
    user_id = int(telegram_user_id)
    try:
        is_subscribed = await check_user_channel_subscription(user_id)
        if not is_subscribed:
            await send_subscription_prompt(user_id)
        return {"subscribed": is_subscribed}
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки на канал (GET): {e}")
        return {"subscribed": False, "error": str(e)}

@router.post("/check-channel-subscription")
async def check_channel_subscription_post(request: Request):
    """
    Проверяет подписку пользователя на канал (POST-метод).
    """
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id or not telegram_user_id.isdigit():
        return {"subscribed": False, "error": "Не удалось определить Telegram ID"}
    user_id = int(telegram_user_id)
    try:
        is_subscribed = await check_user_channel_subscription(user_id)
        if not is_subscribed:
            await send_subscription_prompt(user_id)
        return {"subscribed": is_subscribed}
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки на канал (POST): {e}")
        return {"subscribed": False, "error": str(e)} 