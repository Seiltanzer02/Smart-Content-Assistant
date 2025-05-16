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
    logger.info("Получен GET-запрос на /api/check-channel-subscription")
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    logger.info(f"Идентификатор пользователя из заголовка: {telegram_user_id}")
    
    if not telegram_user_id or not telegram_user_id.isdigit():
        logger.warning(f"Некорректный Telegram ID: {telegram_user_id}")
        return {"subscribed": False, "error": "Не удалось определить Telegram ID"}
    
    user_id = int(telegram_user_id)
    try:
        logger.info(f"Проверка подписки для пользователя {user_id}")
        is_subscribed = await check_user_channel_subscription(user_id)
        logger.info(f"Результат проверки подписки для пользователя {user_id}: {is_subscribed}")
        
        if not is_subscribed:
            logger.info(f"Отправка запроса на подписку пользователю {user_id}")
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
    logger.info("Получен POST-запрос на /api/check-channel-subscription")
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    logger.info(f"Идентификатор пользователя из заголовка: {telegram_user_id}")
    
    if not telegram_user_id or not telegram_user_id.isdigit():
        logger.warning(f"Некорректный Telegram ID: {telegram_user_id}")
        return {"subscribed": False, "error": "Не удалось определить Telegram ID"}
    
    user_id = int(telegram_user_id)
    try:
        logger.info(f"Проверка подписки для пользователя {user_id}")
        is_subscribed = await check_user_channel_subscription(user_id)
        logger.info(f"Результат проверки подписки для пользователя {user_id}: {is_subscribed}")
        
        if not is_subscribed:
            logger.info(f"Отправка запроса на подписку пользователю {user_id}")
            await send_subscription_prompt(user_id)
        
        return {"subscribed": is_subscribed}
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки на канал (POST): {e}")
        return {"subscribed": False, "error": str(e)} 