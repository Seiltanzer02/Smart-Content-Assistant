import os
import httpx
import requests
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

def setup_affiliate_program(commission_permille=100, duration_months=3):
    """
    Настройка программы аффилиатов для мини-приложения Telegram через updateStarRefProgram.
    commission_permille: комиссия в промилле (100 = 10%)
    duration_months: длительность в месяцах (по умолчанию 3)
    """
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    bot_id = 7854381237  # Числовой ID бота
    if not token:
        logger.error('TELEGRAM_BOT_TOKEN не задан в окружении')
        raise Exception('TELEGRAM_BOT_TOKEN не задан в окружении')
    url = f"https://api.telegram.org/bot{token}/updateStarRefProgram"
    data = {
        'bot': bot_id,
        'commission_permille': commission_permille,
        'duration_months': duration_months
    }
    logger.info(f"Настраиваю аффилиатную программу: {data}")
    response = requests.post(url, json=data)
    logger.info(f"Ответ Telegram: {response.status_code} {response.text}")
    return response.json() 