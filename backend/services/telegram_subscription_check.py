import os
import httpx
import logging
from fastapi import HTTPException

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHANNEL_USERNAME = os.getenv("TARGET_CHANNEL_USERNAME")  # Пример: "@my_channel"

logger.info(f"TELEGRAM_BOT_TOKEN присутствует: {bool(TELEGRAM_BOT_TOKEN)}")
logger.info(f"TARGET_CHANNEL_USERNAME: {TARGET_CHANNEL_USERNAME}")

if not TELEGRAM_BOT_TOKEN or not TARGET_CHANNEL_USERNAME:
    raise RuntimeError("TELEGRAM_BOT_TOKEN и TARGET_CHANNEL_USERNAME должны быть заданы в переменных окружения")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

async def check_user_channel_subscription(user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на канал.
    """
    try:
        # Убедимся, что user_id это целое число
        user_id = int(user_id)
        channel = TARGET_CHANNEL_USERNAME.lstrip("@")
        
        logger.info(f"Проверка подписки для пользователя ID: {user_id} в канале: @{channel}")
        
        url = f"{TELEGRAM_API_URL}/getChatMember"
        params = {
            "chat_id": f"@{channel}",
            "user_id": user_id
        }
        
        logger.info(f"Запрос к API Telegram: {url} с параметрами: {params}")
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            logger.info(f"Статус ответа API: {resp.status_code}")
            logger.info(f"Тело ответа API: {resp.text}")
            
            data = resp.json()
            
            if not data.get("ok"):
                error_msg = f"Ошибка Telegram API: {data.get('description')}"
                logger.error(error_msg)
                raise HTTPException(status_code=500, detail=error_msg)
            
            status = data["result"]["status"]
            logger.info(f"Статус пользователя в канале: {status}")
            
            # Подписан, если статус member, administrator, creator
            is_subscribed = status in ("member", "administrator", "creator")
            logger.info(f"Результат проверки подписки: {is_subscribed}")
            
            return is_subscribed
    except Exception as e:
        logger.exception(f"Исключение при проверке подписки: {e}")
        raise

async def send_subscription_prompt(user_id: int):
    """
    Отправляет пользователю сообщение с просьбой подписаться на канал.
    """
    try:
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
        
        logger.info(f"Отправка сообщения о подписке пользователю {user_id}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            logger.info(f"Статус отправки сообщения: {response.status_code}")
            logger.info(f"Тело ответа при отправке сообщения: {response.text}")
            
            return response.json()
    except Exception as e:
        logger.exception(f"Ошибка при отправке сообщения: {e}")
        return {"ok": False, "error": str(e)} 