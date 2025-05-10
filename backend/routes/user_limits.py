from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
from services.supabase_subscription_service import SupabaseSubscriptionService
from main import supabase, logger

router = APIRouter()

@router.post("/api/user/init-usage", response_model=Dict[str, Any])
async def init_user_usage(request: Request):
    """Инициализирует запись лимитов для пользователя, если её нет."""
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
        logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
        return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})
    try:
        subscription_service = SupabaseSubscriptionService(supabase)
        usage = await subscription_service.get_user_usage(int(telegram_user_id))
        return usage
    except Exception as e:
        logger.error(f"Ошибка при инициализации лимитов для пользователя {telegram_user_id}: {e}")
        # Возвращаем базовые лимиты даже в случае ошибки
        from datetime import datetime, timezone, timedelta
        return {
            "user_id": int(telegram_user_id),
            "analysis_count": 0,
            "post_generation_count": 0,
            "ideas_generation_count": 0,
            "reset_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
        } 