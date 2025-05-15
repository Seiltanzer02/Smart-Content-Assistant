import httpx
import os
import logging

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHANNEL_USERNAME = os.getenv("TARGET_CHANNEL_USERNAME")

async def get_chat_member(user_id: int, chat_id: str):
    """Получает информацию о участнике чата."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set.")
        return None
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChatMember"
    params = {"chat_id": chat_id, "user_id": user_id}
    async with httpx.AsyncClient() as client:
        try:
            logger.debug(f"Requesting getChatMember for user {user_id} in chat {chat_id}")
            response = await client.get(url, params=params)
            response.raise_for_status()
            logger.debug(f"getChatMember response for user {user_id}: {response.json()}")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting chat member for user {user_id} in chat {chat_id}: {e.response.status_code} - {e.response.text}")
            # Если пользователь не найден в канале, API может вернуть ошибку 400 или корректный ответ со статусом 'left'/'kicked'
            # Обрабатываем как потенциально валидный ответ для дальнейшего анализа статуса
            try:
                return e.response.json()
            except Exception: # Если тело ответа не JSON
                return {"ok": False, "description": e.response.text, "error_code": e.response.status_code} 
        except Exception as e:
            logger.error(f"General exception in get_chat_member for user {user_id} in {chat_id}: {e}")
            return None

async def check_user_subscription_status(user_id: int) -> bool:
    """Проверяет статус подписки пользователя на целевой канал."""
    if not TARGET_CHANNEL_USERNAME:
        logger.warning("TARGET_CHANNEL_USERNAME is not set. Subscription check bypassed, assuming subscribed.")
        return True # Если канал не задан, не блокируем приложение
        
    channel_id_for_api = TARGET_CHANNEL_USERNAME if TARGET_CHANNEL_USERNAME.startswith('@') else f"@{TARGET_CHANNEL_USERNAME}"
    
    member_info = await get_chat_member(user_id, channel_id_for_api)
    
    if member_info and member_info.get("ok"):
        status = member_info.get("result", {}).get("status")
        # Допустимые статусы для активной подписки
        valid_statuses = ["member", "administrator", "creator"]
        if status in valid_statuses:
            logger.info(f"User {user_id} IS SUBSCRIBED to {channel_id_for_api} with status: {status}")
            return True
        else:
            logger.info(f"User {user_id} IS NOT SUBSCRIBED to {channel_id_for_api}. Status: {status}")
            return False
    else:
        # Ошибка при получении статуса или неверно указан TARGET_CHANNEL_USERNAME
        # или бот не имеет доступа к каналу (например, не админ в приватном канале)
        description = member_info.get("description", "No description") if member_info else "No member_info"
        error_code = member_info.get("error_code", "N/A") if member_info else "N/A"
        logger.warning(f"Could not determine subscription status for user {user_id} in {channel_id_for_api}. Defaulting to NOT SUBSCRIBED. API Response/Description: {description} (Code: {error_code})")
        return False

async def send_telegram_message(user_id: int, text: str, reply_markup: dict = None):
    """Отправляет сообщение пользователю через Telegram бота."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Cannot send message.")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": user_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"Message sent to user {user_id}. Response: {response.json().get('ok')}")
            return response.json().get('ok', False)
        except httpx.HTTPStatusError as e:
            logger.error(f"Error sending message to user {user_id}: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"General exception in send_telegram_message for user {user_id}: {e}")
            return False

async def send_subscription_prompt_message(user_id: int):
    """Отправляет пользователю сообщение с просьбой подписаться на канал."""
    if not TARGET_CHANNEL_USERNAME:
        logger.error("TARGET_CHANNEL_USERNAME is not set. Cannot send subscription prompt.")
        return False
    
    # Удаляем @ из имени канала для ссылки, если он есть
    channel_name_for_link = TARGET_CHANNEL_USERNAME.replace('@', '')
    channel_link = f"https://t.me/{channel_name_for_link}"
    
    message_text = (
        f"👋 Чтобы пользоваться всеми функциями нашего приложения, пожалуйста, подпишитесь на наш канал: {channel_link}\n\n"
        "После подписки вернитесь в приложение и нажмите кнопку 'Проверить подписку'."
    )
    
    inline_keyboard = {
        "inline_keyboard": [
            [{"text": "Перейти на канал", "url": channel_link}]
        ]
    }
    return await send_telegram_message(user_id, message_text, reply_markup=inline_keyboard) 