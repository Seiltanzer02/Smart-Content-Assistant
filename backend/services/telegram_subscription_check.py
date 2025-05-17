import os
import httpx
import logging
from fastapi import HTTPException

# Настраиваем логирование
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHANNEL_USERNAME = os.getenv("TARGET_CHANNEL_USERNAME")  # Пример: "@my_channel"

if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN не задан в переменных окружения")
if not TARGET_CHANNEL_USERNAME:
    logger.error("TARGET_CHANNEL_USERNAME не задан в переменных окружения")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else ""

async def check_user_channel_subscription(user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на канал.
    """
    if not TELEGRAM_BOT_TOKEN or not TARGET_CHANNEL_USERNAME:
        logger.error("Невозможно проверить подписку: не настроены TELEGRAM_BOT_TOKEN или TARGET_CHANNEL_USERNAME")
        return False
    
    channel = TARGET_CHANNEL_USERNAME.lstrip("@")
    url = f"{TELEGRAM_API_URL}/getChatMember"
    params = {
        "chat_id": f"@{channel}",
        "user_id": user_id
    }
    
    logger.info(f"Проверка подписки для пользователя {user_id} на канал @{channel}")
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            
            if not data.get("ok"):
                error_msg = data.get("description", "Неизвестная ошибка")
                logger.error(f"Ошибка Telegram API при проверке подписки: {error_msg}")
                
                # Проверяем типичные ошибки когда бот не админ
                if "bot is not a member" in error_msg or "administrator rights" in error_msg:
                    logger.error(f"Бот не является администратором канала @{channel}. Добавьте бота как администратора канала.")
                return False
                
            status = data["result"]["status"]
            # Подписан, если статус member, administrator, creator
            is_subscribed = status in ("member", "administrator", "creator")
            logger.info(f"Результат проверки подписки для пользователя {user_id}: {is_subscribed} (статус: {status})")
            return is_subscribed
    except Exception as e:
        logger.error(f"Исключение при проверке подписки для пользователя {user_id}: {e}")
        return False

async def send_subscription_prompt(user_id: int):
    """
    Отправляет пользователю сообщение с просьбой подписаться на канал.
    """
    if not TELEGRAM_BOT_TOKEN or not TARGET_CHANNEL_USERNAME:
        logger.error("Невозможно отправить сообщение: не настроены TELEGRAM_BOT_TOKEN или TARGET_CHANNEL_USERNAME")
        return
        
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
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                logger.info(f"Сообщение о подписке успешно отправлено пользователю {user_id}")
            else:
                logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"Исключение при отправке сообщения пользователю {user_id}: {e}") 