from fastapi import APIRouter, Request
from backend.utils.check_subscription import is_user_subscribed, send_subscription_message
import os

router = APIRouter()

@router.post("/check-subscription")
async def check_subscription(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    if not user_id:
        return {"ok": False, "error": "user_id required"}
    try:
        user_id = int(user_id)
    except Exception:
        return {"ok": False, "error": "user_id must be int"}
    channel_username = os.getenv("TARGET_CHANNEL_USERNAME")
    channel_link = f"https://t.me/{channel_username.lstrip('@')}"
    is_subscribed = await is_user_subscribed(user_id)
    if is_subscribed:
        return {"ok": True, "subscribed": True}
    else:
        await send_subscription_message(user_id, channel_link)
        return {
            "ok": True,
            "subscribed": False,
            "channel_link": channel_link,
            "message": "Подпишитесь на канал для доступа к приложению"
        } 