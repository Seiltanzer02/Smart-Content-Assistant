import os
import httpx
from fastapi import HTTPException

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHANNEL_USERNAME = os.getenv("TARGET_CHANNEL_USERNAME")  # Пример: "@my_channel"

if not TELEGRAM_BOT_TOKEN or not TARGET_CHANNEL_USERNAME:
    raise RuntimeError("TELEGRAM_BOT_TOKEN и TARGET_CHANNEL_USERNAME должны быть заданы в переменных окружения")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

async def check_user_channel_subscription(user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на канал. Если бот не админ — возвращает False.
    """
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
                # Если бот не админ или канал не найден — не падаем, просто считаем, что не подписан
                return False
            status = data["result"]["status"]
            # Подписан, если статус member, administrator, creator
            return status in ("member", "administrator", "creator")
    except Exception:
        # Любая ошибка — считаем, что не подписан
        return False

async def send_subscription_prompt(user_id: int):
    """
    Отправляет пользователю сообщение с красивой кнопкой для подписки на канал.
    """
    channel = TARGET_CHANNEL_USERNAME.lstrip("@")
    url = f"{TELEGRAM_API_URL}/sendMessage"
    text = (
        f"Чтобы пользоваться приложением, подпишитесь на наш канал:"
    )
    reply_markup = {
        "inline_keyboard": [[
            {"text": "Перейти в канал", "url": f"https://t.me/{channel}"}
        ]]
    }
    payload = {
        "chat_id": user_id,
        "text": text,
        "reply_markup": reply_markup,
        "disable_web_page_preview": True
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload) 