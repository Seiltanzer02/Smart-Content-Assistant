from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
from services.supabase_subscription_service import SupabaseSubscriptionService
from main import supabase, logger
from pydantic import BaseModel
from typing import List, Optional

class AnalyzeRequest(BaseModel):
    username: str

class AnalyzeResponse(BaseModel):
    themes: List[str]
    styles: List[str]
    analyzed_posts_sample: List[str]
    best_posting_time: str
    analyzed_posts_count: int
    message: Optional[str] = None
    error: Optional[str] = None

router = APIRouter()

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_channel(request: Request, req: AnalyzeRequest):
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
        logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
        return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})
    subscription_service = SupabaseSubscriptionService(supabase)
    can_analyze = await subscription_service.can_analyze_channel(int(telegram_user_id))
    if not can_analyze:
        return JSONResponse(status_code=403, content={"error": "Достигнут лимит анализа каналов для бесплатной подписки. Оформите подписку для снятия ограничений."})
    # Здесь должна быть логика анализа канала (заглушка)
    return AnalyzeResponse(
        themes=[],
        styles=[],
        analyzed_posts_sample=[],
        best_posting_time="",
        analyzed_posts_count=0,
        message="Анализ выполнен (заглушка)"
    ) 