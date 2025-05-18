import os
import httpx
from fastapi import Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Получаем необходимые переменные окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHANNEL_USERNAME = os.getenv("TARGET_CHANNEL_USERNAME")  # Например: "@my_channel"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else ""

# Модели данных
class ChannelSubscriptionCheck(BaseModel):
    is_subscribed: bool
    user_id: int
    channel: str
    error: Optional[str] = None

class ChannelSubscriptionResponse(BaseModel):
    success: bool
    is_subscribed: bool
    channel_username: str
    channel_link: str
    message: str

# Вспомогательные функции
async def get_telegram_user_id_from_request(request: Request) -> int:
    """Извлекает ID пользователя Telegram из заголовков запроса."""
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

async def check_channel_subscription(user_id: int) -> ChannelSubscriptionCheck:
    """Проверяет, подписан ли пользователь на целевой канал."""
    if not TELEGRAM_BOT_TOKEN or not TARGET_CHANNEL_USERNAME:
        return ChannelSubscriptionCheck(
            is_subscribed=False,
            user_id=user_id,
            channel=TARGET_CHANNEL_USERNAME or "unknown",
            error="Отсутствуют необходимые конфигурации (TELEGRAM_BOT_TOKEN или TARGET_CHANNEL_USERNAME)"
        )
    
    channel = TARGET_CHANNEL_USERNAME.lstrip("@")
    url = f"{TELEGRAM_API_URL}/getChatMember"
    params = {
        "chat_id": f"@{channel}",
        "user_id": user_id
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            
            if not data.get("ok"):
                error_msg = data.get("description", "Неизвестная ошибка API Telegram")
                logger.error(f"Ошибка API Telegram при проверке подписки: {error_msg}")
                return ChannelSubscriptionCheck(
                    is_subscribed=False,
                    user_id=user_id,
                    channel=channel,
                    error=error_msg
                )
            
            status = data["result"]["status"]
            # Пользователь считается подписанным, если его статус: member, administrator или creator
            is_subscribed = status in ("member", "administrator", "creator")
            
            return ChannelSubscriptionCheck(
                is_subscribed=is_subscribed,
                user_id=user_id,
                channel=channel
            )
    
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки пользователя {user_id} на канал @{channel}: {e}")
        return ChannelSubscriptionCheck(
            is_subscribed=False,
            user_id=user_id,
            channel=channel,
            error=str(e)
        )

# Эндпоинты API для интеграции в основное приложение
async def check_subscription_endpoint(
    request: Request,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """Эндпоинт для проверки подписки пользователя на целевой канал."""
    # Если user_id не передан, извлекаем из заголовков
    effective_user_id = user_id or await get_telegram_user_id_from_request(request)
    
    result = await check_channel_subscription(effective_user_id)
    channel = result.channel
    
    # Формируем URL канала для удобства подписки
    channel_link = f"https://t.me/{channel}"
    
    # Формируем сообщение в зависимости от статуса подписки
    if result.is_subscribed:
        message = "Вы уже подписаны на канал! Продолжайте пользоваться нашим приложением."
    else:
        message = f"Для использования приложения, пожалуйста, подпишитесь на наш канал @{channel}"
    
    response = ChannelSubscriptionResponse(
        success=result.error is None,
        is_subscribed=result.is_subscribed,
        channel_username=channel,
        channel_link=channel_link,
        message=message
    )
    
    # Добавляем error в ответ, если есть
    response_dict = response.dict()
    if result.error:
        response_dict["error"] = result.error
    
    # Устанавливаем заголовки для предотвращения кэширования
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    
    return JSONResponse(content=response_dict, headers=headers)

async def notify_subscription_required(
    request: Request, 
    user_id: int = Depends(get_telegram_user_id_from_request)
) -> Dict[str, Any]:
    """Формирует расширенный ответ с инструкциями для пользователя по подписке на канал."""
    result = await check_channel_subscription(user_id)
    channel = result.channel
    
    # URL канала для подписки
    channel_link = f"https://t.me/{channel}"
    
    # Формируем подробное сообщение с инструкциями
    if result.is_subscribed:
        return {
            "success": True,
            "is_subscribed": True,
            "access_granted": True,
            "message": "Вы подписаны на наш канал. Спасибо за поддержку! Вы можете использовать все функции приложения."
        }
    else:
        return {
            "success": result.error is None,
            "is_subscribed": False,
            "access_granted": False,
            "channel_username": channel,
            "channel_link": channel_link,
            "message": f"Для доступа к приложению, пожалуйста, подпишитесь на наш канал: @{channel}",
            "instructions": [
                "1. Нажмите на кнопку 'Подписаться на канал'",
                "2. Вы будете перенаправлены в канал Telegram",
                "3. Нажмите кнопку 'Подписаться' или 'Join'",
                "4. Вернитесь в приложение и нажмите 'Проверить подписку'"
            ],
            "error": result.error
        } 