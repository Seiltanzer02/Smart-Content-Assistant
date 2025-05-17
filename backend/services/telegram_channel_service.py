import httpx
import os
import json
from backend.main import logger # Предполагается, что logger уже настроен в main

async def send_telegram_message(chat_id: int, text: str, reply_markup: dict = None):
    """
    Отправляет сообщение пользователю через Telegram Bot API.
    """
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения.")
        return False

    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML", # Используем HTML для возможности вставки ссылок
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()  # Проверка на HTTP ошибки
            # logger.info(f"Сообщение успешно отправлено пользователю {chat_id}. Ответ: {response.json()}") # Может быть слишком многословно
            logger.info(f"Сообщение успешно отправлено пользователю {chat_id}.")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Ошибка при отправке сообщения пользователю {chat_id}: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Исключение при отправке сообщения пользователю {chat_id}: {e}")
            return False

async def check_channel_subscription(user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на целевой канал.
    Возвращает True, если подписан, иначе False.
    """
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    target_channel_username = os.getenv("TARGET_CHANNEL_USERNAME")

    if not telegram_bot_token or not target_channel_username:
        logger.error("TELEGRAM_BOT_TOKEN или TARGET_CHANNEL_USERNAME не найдены в переменных окружения.")
        return False # Не можем проверить без этих данных

    target_channel_id = target_channel_username
    # Если это не ID и не начинается с @, добавляем @
    if not target_channel_username.startswith("@") and not target_channel_username.startswith("-100"):
        target_channel_id = f"@{target_channel_username}"
        
    url = f"https://api.telegram.org/bot{telegram_bot_token}/getChatMember"
    params = {
        "chat_id": target_channel_id,
        "user_id": user_id
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status() # Проверка на ошибки HTTP (4xx, 5xx)
            member_data = response.json()
            
            if member_data.get("ok"):
                status = member_data.get("result", {}).get("status")
                logger.info(f"Статус пользователя {user_id} в канале {target_channel_id}: {status}")
                if status in ["creator", "administrator", "member"]:
                    return True
                # Все остальные статусы (restricted, left, kicked) означают, что пользователь не является активным участником
                return False
            else:
                # Если ok=false, это ошибка со стороны Telegram API
                logger.warning(f"Ошибка от Telegram API при проверке подписки для user_id {user_id} на канал {target_channel_id}: {member_data.get('description')}")
                # Например, "Chat not found", "User not found", "Bot is not a member of the channel chat"
                return False
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка при проверке подписки user_id {user_id} на {target_channel_id}: {e.response.status_code} - {e.response.text}")
            # Некоторые ошибки (например, user_id не найден в чате) могут приходить как HTTP 400/403 с описанием
            # Если Telegram вернул ошибку, что пользователь не найден, это равносильно отсутствию подписки.
            if e.response.status_code == 400 and "user not found" in e.response.text.lower():
                return False
            # Если бот не администратор или удален из канала, он тоже не сможет проверить.
            # В большинстве случаев при ошибке запроса к getChatMember безопаснее считать, что подписки нет или она не может быть проверена.
            return False
        except Exception as e:
            logger.error(f"Общее исключение при проверке подписки user_id {user_id} на {target_channel_id}: {e}", exc_info=True)
            return False # При любой другой ошибке считаем, что проверка не удалась

async def handle_subscription_check_request(user_id: int, chat_id: int) -> bool:
    """
    Проверяет подписку и уведомляет пользователя.
    Возвращает True, если пользователь подписан и может продолжить, иначе False.
    """
    is_subscribed = await check_channel_subscription(user_id)
    target_channel_username = os.getenv("TARGET_CHANNEL_USERNAME")
    
    channel_link = "наш канал" # Запасной текст
    if target_channel_username:
        if target_channel_username.startswith("@"):
            channel_link = f"https://t.me/{target_channel_username[1:]}"
        elif target_channel_username.startswith("https://t.me/"):
            channel_link = target_channel_username
        elif not target_channel_username.startswith("-100"): # Предполагаем публичное имя без @
            channel_link = f"https://t.me/{target_channel_username}"
        else: # Это ID типа -100...
            logger.warning(f"Целевой канал {target_channel_username} является ID. " \
                           f"Для корректной ссылки рекомендуется использовать @имя_канала или полную инвайт-ссылку в TARGET_CHANNEL_USERNAME.")
            channel_link = f"канал ({target_channel_username})"


    if not is_subscribed:
        message_text = (
            f"Для доступа ко всем функциям приложения, пожалуйста, подпишитесь на {channel_link}\n\n"
            "После подписки, вернитесь в приложение или нажмите кнопку ниже."
        )
        
        button_url = channel_link
        if not channel_link.startswith("https://"):
            safe_username = target_channel_username.replace('@', '') if target_channel_username else ""
            if safe_username and not safe_username.startswith("-100") :
                 button_url = f"https://t.me/{safe_username}"
            else: 
                button_url = None 
                logger.warning(f"Не удалось сформировать корректный URL для кнопки 'Перейти к каналу' для {target_channel_username}")

        inline_keyboard = [[{"text": "✅ Проверить подписку", "callback_data": "check_subscription_callback"}]]
        if button_url: 
            inline_keyboard.append([{"text": "Перейти к каналу", "url": button_url}])
        
        reply_markup = {"inline_keyboard": inline_keyboard}
        
        await send_telegram_message(chat_id=chat_id, text=message_text, reply_markup=reply_markup)
        return False
    
    return True 