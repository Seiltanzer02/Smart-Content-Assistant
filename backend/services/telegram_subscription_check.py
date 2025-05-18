import os
import httpx
from fastapi import HTTPException, APIRouter, Request
from fastapi.responses import JSONResponse

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHANNEL_USERNAME = os.getenv("TARGET_CHANNEL_USERNAME")  # без @

if not TELEGRAM_BOT_TOKEN or not TARGET_CHANNEL_USERNAME:
    raise RuntimeError("TELEGRAM_BOT_TOKEN и TARGET_CHANNEL_USERNAME должны быть заданы в переменных окружения")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

async def check_user_channel_subscription(user_id: int) -> tuple[bool, str | None]:
    """
    Проверяет, подписан ли пользователь на канал.
    Возвращает (is_subscribed: bool, error_message: str | None)
    """
    url = f"{TELEGRAM_API_URL}/getChatMember"
    params = {
        "chat_id": f"@{TARGET_CHANNEL_USERNAME.lstrip('@')}",
        "user_id": user_id
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                error_description = data.get("description", "Неизвестная ошибка от Telegram API")
                print(f"Ошибка Telegram API при getChatMember для user {user_id} на канал @{TARGET_CHANNEL_USERNAME}: {error_description}")
                return False, error_description
            status = data.get("result", {}).get("status")
            return status in ("member", "administrator", "creator"), None
    except httpx.HTTPStatusError as e:
        print(f"HTTP ошибка при запросе к Telegram API (getChatMember): {e}")
        return False, f"Сетевая ошибка при проверке подписки: {e.response.status_code}"
    except httpx.RequestError as e:
        print(f"Сетевая ошибка при запросе к Telegram API (getChatMember): {e}")
        return False, f"Сетевая ошибка при проверке подписки: {e}"
    except Exception as e:
        print(f"Непредвиденная ошибка в check_user_channel_subscription: {e}")
        return False, f"Внутренняя ошибка сервера при проверке подписки: {str(e)}"

async def send_subscription_prompt(user_id: int):
    """
    Отправляет пользователю сообщение с просьбой подписаться на канал.
    """
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
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)

info_router = APIRouter()

@info_router.get("/api/user/channel-info", status_code=200)
async def get_channel_info():
    """
    Возвращает username канала для фронта (без @)
    """
    if not TARGET_CHANNEL_USERNAME:
        print("КРИТИЧЕСКАЯ ОШИБКА: TARGET_CHANNEL_USERNAME не установлен на сервере!")
        return JSONResponse(
            status_code=503,
            content={
                "channel_username": None, 
                "error": "Целевой канал не настроен на сервере."
            }
        )
    return JSONResponse(content={"channel_username": TARGET_CHANNEL_USERNAME.lstrip('@'), "error": None}) 