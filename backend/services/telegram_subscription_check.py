import os
import httpx
from fastapi import HTTPException, APIRouter, Request

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHANNEL_USERNAME = os.getenv("TARGET_CHANNEL_USERNAME")  # Пример: "@my_channel"

if not TELEGRAM_BOT_TOKEN or not TARGET_CHANNEL_USERNAME:
    raise RuntimeError("TELEGRAM_BOT_TOKEN и TARGET_CHANNEL_USERNAME должны быть заданы в переменных окружения")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

async def check_user_channel_subscription(user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на канал.
    """
    channel = TARGET_CHANNEL_USERNAME.lstrip("@")
    url = f"{TELEGRAM_API_URL}/getChatMember"
    params = {
        "chat_id": f"@{channel}",
        "user_id": user_id
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()
        if not data.get("ok"):
            # Если бот не админ в канале — будет ошибка
            raise HTTPException(status_code=500, detail=f"Ошибка Telegram API: {data.get('description')}")
        status = data["result"]["status"]
        # Подписан, если статус member, administrator, creator
        return status in ("member", "administrator", "creator")

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

router = APIRouter()

@router.get("/api/user/check-channel-subscription", status_code=200)
async def check_channel_subscription(request: Request):
    """
    Проверяет, подписан ли пользователь на целевой канал.
    Требует заголовок X-Telegram-User-Id.
    """
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id or not telegram_user_id.isdigit():
        return {"has_channel_subscription": False, "error": "Некорректный или отсутствующий Telegram ID"}
    try:
        user_id = int(telegram_user_id)
        is_subscribed = await check_user_channel_subscription(user_id)
        return {"has_channel_subscription": is_subscribed}
    except HTTPException as e:
        return {"has_channel_subscription": False, "error": str(e.detail)}
    except Exception as e:
        return {"has_channel_subscription": False, "error": str(e)} 