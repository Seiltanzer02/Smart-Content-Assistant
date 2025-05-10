from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
from backend.services.supabase_subscription_service import SupabaseSubscriptionService
from backend.main import supabase, logger

router = APIRouter()

@router.post("/api/user/init-usage", response_model=Dict[str, Any])
async def init_user_usage(request: Request):
    """Инициализирует запись лимитов для пользователя, если её нет."""
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id or not telegram_user_id.isdigit():
        return {"error": "Некорректный или отсутствующий Telegram ID"}
    subscription_service = SupabaseSubscriptionService(supabase)
    return await subscription_service.get_user_usage(int(telegram_user_id))

    # Возвращаем базовые лимиты даже в случае ошибки
    from datetime import datetime, timezone, timedelta
    return {
        "user_id": int(telegram_user_id),
        "analysis_count": 0,
        "post_generation_count": 0,
        "ideas_generation_count": 0,
        "reset_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    } 