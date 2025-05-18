import os
import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("channel_subscription")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHANNEL_USERNAME = os.getenv("TARGET_CHANNEL_USERNAME")  # Пример: "@my_channel"

if not TELEGRAM_BOT_TOKEN or not TARGET_CHANNEL_USERNAME:
    logger.warning("TELEGRAM_BOT_TOKEN или TARGET_CHANNEL_USERNAME не заданы в переменных окружения")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else ""

class ChannelSubscriptionService:
    """
    Сервис для проверки и управления подпиской пользователя на канал
    """
    
    @staticmethod
    async def check_user_channel_subscription(user_id: int) -> bool:
        """
        Проверяет, подписан ли пользователь на канал.
        """
        if not TELEGRAM_BOT_TOKEN or not TARGET_CHANNEL_USERNAME:
            logger.error("Отсутствуют переменные окружения для проверки подписки на канал")
            return False
            
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
                    # Если бот не админ в канале — будет ошибка
                    logger.error(f"Ошибка Telegram API при проверке подписки: {data.get('description')}")
                    return False
                status = data["result"]["status"]
                # Подписан, если статус member, administrator, creator
                return status in ("member", "administrator", "creator")
        except Exception as e:
            logger.error(f"Ошибка при проверке подписки на канал: {e}")
            return False
    
    @staticmethod
    async def get_subscription_status(request: Request, user_id: int = None) -> JSONResponse:
        """
        Получает статус подписки пользователя на канал с форматированным ответом для API
        """
        if user_id is None:
            # Пытаемся получить ID из заголовка запроса
            user_id_str = request.headers.get("X-Telegram-User-Id")
            if not user_id_str:
                return JSONResponse(
                    content={
                        "success": False,
                        "is_subscribed": False,
                        "error": "Не указан идентификатор пользователя"
                    },
                    status_code=401
                )
            try:
                user_id = int(user_id_str)
            except ValueError:
                return JSONResponse(
                    content={
                        "success": False,
                        "is_subscribed": False,
                        "error": "Некорректный идентификатор пользователя"
                    },
                    status_code=400
                )
        
        try:
            # Проверяем подписку
            is_subscribed = await ChannelSubscriptionService.check_user_channel_subscription(user_id)
            
            # Формируем ответ
            channel_name = TARGET_CHANNEL_USERNAME.lstrip("@") if TARGET_CHANNEL_USERNAME else "неизвестно"
            return JSONResponse(
                content={
                    "success": True,
                    "is_subscribed": is_subscribed,
                    "channel": channel_name,
                    "user_id": user_id,
                    "subscription_required": True
                },
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
        except Exception as e:
            logger.error(f"Ошибка при получении статуса подписки: {e}")
            return JSONResponse(
                content={
                    "success": False,
                    "is_subscribed": False,
                    "error": str(e)
                },
                status_code=500
            )
    
    @staticmethod
    def get_channel_subscription_url() -> str:
        """
        Возвращает URL для подписки на канал
        """
        if not TARGET_CHANNEL_USERNAME:
            return ""
            
        channel = TARGET_CHANNEL_USERNAME.lstrip("@")
        return f"https://t.me/{channel}"
            
    @staticmethod
    async def send_subscription_prompt(user_id: int):
        """
        Отправляет пользователю сообщение с просьбой подписаться на канал.
        """
        if not TELEGRAM_BOT_TOKEN or not TARGET_CHANNEL_USERNAME:
            logger.error("Отсутствуют переменные окружения для отправки сообщения")
            return False
            
        channel = TARGET_CHANNEL_USERNAME.lstrip("@")
        url = f"{TELEGRAM_API_URL}/sendMessage"
        text = (
            f"Чтобы пользоваться приложением, подпишитесь на наш канал: "
            f"https://t.me/{channel}\n\n"
            f"После подписки вернитесь в приложение и нажмите 'Проверить подписку'."
        )
        payload = {
            "chat_id": user_id,
            "text": text,
            "disable_web_page_preview": True
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload)
                data = resp.json()
                return data.get("ok", False)
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения о подписке: {e}")
            return False 