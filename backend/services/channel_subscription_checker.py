import os
import httpx
from fastapi import HTTPException
from backend.main import logger, supabase

# ENVIRONMENT VARIABLES
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHANNEL_USERNAME = os.getenv("TARGET_CHANNEL_USERNAME")  # without @ or with @ - will be cleaned

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN env var is missing")
if not TARGET_CHANNEL_USERNAME:
    raise RuntimeError("TARGET_CHANNEL_USERNAME env var is missing")

TARGET_CHANNEL_CLEAN = TARGET_CHANNEL_USERNAME.lstrip("@")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def _telegram_get_chat_member(user_id: int):
    """Call getChatMember for the target channel"""
    url = f"{TELEGRAM_API_URL}/getChatMember"
    params = {
        "chat_id": f"@{TARGET_CHANNEL_CLEAN}",
        "user_id": user_id,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params=params)
    data = r.json()
    if not data.get("ok"):
        err = data.get("description")
        logger.warning(f"Telegram getChatMember returned error for user {user_id}: {err}")
        raise HTTPException(status_code=500, detail=f"Telegram API error: {err}")
    return data["result"]


async def _telegram_send_prompt(user_id: int):
    """Send subscription prompt message to user"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    text = (
        f"Чтобы пользоваться приложением, подпишитесь на наш канал: https://t.me/{TARGET_CHANNEL_CLEAN}\n\n"
        f"После подписки вернитесь в мини-приложение и нажмите кнопку \"Проверить подписку\"."
    )
    payload = {
        "chat_id": user_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(url, json=payload)


async def check_subscription_and_prompt(user_id: int) -> bool:
    """Return True if user subscribed, else False (after sending prompt). Also caches flag in user_settings."""
    try:
        member = await _telegram_get_chat_member(user_id)
        status = member.get("status")
        subscribed = status in {"member", "administrator", "creator"}
    except HTTPException:
        # propagate API error
        raise
    except Exception as e:
        logger.error(f"Unexpected error while checking subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Cache to Supabase user_settings for convenience (non-critical)
    try:
        if supabase:
            existing = supabase.table("user_settings").select("id").eq("user_id", user_id).maybe_single().execute()
            if existing.data:
                supabase.table("user_settings").update({"is_subscribed_to_channel": subscribed}).eq("user_id", user_id).execute()
            else:
                supabase.table("user_settings").insert({
                    "user_id": user_id,
                    "is_subscribed_to_channel": subscribed,
                }).execute()
    except Exception as db_err:
        logger.warning(f"Cannot update is_subscribed_to_channel flag: {db_err}")

    if not subscribed:
        # Send prompt (fire-and-forget)
        try:
            await _telegram_send_prompt(user_id)
        except Exception as send_err:
            logger.warning(f"Cannot send subscription prompt: {send_err}")

    return subscribed 