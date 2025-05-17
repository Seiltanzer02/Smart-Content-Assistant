from fastapi import APIRouter, Request
import logging
from backend.services.telegram_subscription_check import check_user_channel_subscription, send_subscription_prompt

logger = logging.getLogger(__name__)

# Создаем отдельный роутер без префикса пути
router = APIRouter()

@router.get("/channel-subscription-check/{user_id}", status_code=200)
async def channel_subscription_check(user_id: int, request: Request):
    """
    Проверяет, подписан ли пользователь на канал. Возвращает JSON с результатом.
    Эндпоинт определен в отдельном роутере, который подключается к основному приложению.
    """
    logger.info(f"[CHANNEL-SUBSCRIPTION-CHECK] Проверка подписки для пользователя: {user_id}")
    try:
        is_subscribed = await check_user_channel_subscription(int(user_id))
        logger.info(f"[CHANNEL-SUBSCRIPTION-CHECK] Результат проверки для {user_id}: {is_subscribed}")
    except Exception as e:
        logger.error(f"[CHANNEL-SUBSCRIPTION-CHECK] Ошибка: {e}")
        return {"subscribed": False, "message": f"Ошибка проверки подписки: {str(e)}"}
    
    if is_subscribed:
        return {"subscribed": True, "message": "Вы подписаны на канал!"}
    else:
        await send_subscription_prompt(int(user_id))
        return {
            "subscribed": False,
            "message": "Чтобы пользоваться приложением, подпишитесь на наш канал и нажмите 'Проверить подписку'!"
        } 