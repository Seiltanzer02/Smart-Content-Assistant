import os
import httpx
from backend.main import logger

async def get_star_referral_link(user_id: int) -> str:
    """
    Получает официальную реферальную ссылку Stars для пользователя через Telegram API (payments.connectStarRefBot).
    Возвращает ссылку или выбрасывает исключение при ошибке.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    bot_id = os.getenv("TELEGRAM_API_ID")
    if not bot_token or not bot_id:
        logger.error("TELEGRAM_BOT_TOKEN или TELEGRAM_API_ID не заданы в окружении")
        raise Exception("TELEGRAM_BOT_TOKEN или TELEGRAM_API_ID не заданы в окружении")
    url = f"https://api.telegram.org/bot{bot_token}/payments.connectStarRefBot"
    payload = {
        "bot": int(bot_id),
        "peer": int(user_id)
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload)
        data = response.json()
        if not data.get("ok"):
            logger.error(f"Ошибка Telegram API при получении реферальной ссылки: {data}")
            raise Exception(f"Ошибка Telegram API: {data}")
        link = data["result"].get("referral_link") or data["result"].get("link")
        if not link:
            logger.error(f"Не удалось получить ссылку из ответа Telegram: {data}")
            raise Exception("Не удалось получить реферальную ссылку из ответа Telegram")
        return link 