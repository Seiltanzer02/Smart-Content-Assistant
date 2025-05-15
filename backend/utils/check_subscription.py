import os
import httpx

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHANNEL_USERNAME = os.getenv("TARGET_CHANNEL_USERNAME")  # Например, '@my_channel'

async def is_user_subscribed(user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на канал.
    """
    if not TELEGRAM_BOT_TOKEN or not TARGET_CHANNEL_USERNAME:
        raise Exception("TELEGRAM_BOT_TOKEN или TARGET_CHANNEL_USERNAME не заданы в переменных окружения")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChatMember"
    params = {
        "chat_id": TARGET_CHANNEL_USERNAME,
        "user_id": user_id
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()
        if not data.get("ok"):
            return False
        status = data["result"]["status"]
        return status in ("member", "administrator", "creator")

async def send_subscription_message(user_id: int, channel_link: str):
    """
    Отправляет пользователю сообщение с просьбой подписаться на канал.
    """
    if not TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text = (
        f"Чтобы пользоваться приложением, подпишитесь на наш канал: {channel_link}\n"
        "После подписки вернитесь в приложение и нажмите 'Проверить подписку'."
    )
    payload = {
        "chat_id": user_id,
        "text": text,
        "disable_web_page_preview": True
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload) 