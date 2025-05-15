from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from backend.services.supabase_subscription_service import SupabaseSubscriptionService
from backend.services.ideas_service import generate_content_plan, get_saved_ideas, save_suggested_idea, save_suggested_ideas_batch
from backend.main import logger, supabase

class PlanGenerationRequest(BaseModel):
    themes: List[str]
    styles: List[str]
    period_days: int = Field(7, gt=0, le=30)
    channel_name: str

class PlanItem(BaseModel):
    day: int
    topic_idea: str
    format_style: str

class PlanGenerationResponse(BaseModel):
    plan: List[PlanItem] = []
    message: Optional[str] = None

class SuggestedIdeasResponse(BaseModel):
    ideas: List[Dict[str, Any]] = []
    message: Optional[str] = None

class SaveIdeasRequest(BaseModel):
    ideas: List[Dict[str, Any]]
    channel_name: Optional[str] = None

router = APIRouter()

@router.post("/generate-plan", response_model=PlanGenerationResponse)
async def generate_content_plan_router(request: Request, req: PlanGenerationRequest):
    return await generate_content_plan(request, req)

@router.get("/ideas", response_model=SuggestedIdeasResponse)
async def get_saved_ideas_router(request: Request, channel_name: Optional[str] = None):
    return await get_saved_ideas(request, channel_name)

@router.post("/save-suggested-idea", response_model=Dict[str, Any])
async def save_suggested_idea_router(idea_data: Dict[str, Any], request: Request):
    return await save_suggested_idea(idea_data, request)

@router.post("/save-suggested-ideas", response_model=Dict[str, Any])
async def save_suggested_ideas_batch_router(payload: SaveIdeasRequest, request: Request):
    # Проверяем лимиты только если сохраняется набор идей от генерации плана
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if telegram_user_id and len(payload.ideas) > 3:  # Если больше 3 идей, скорее всего это результат генерации плана
        subscription_service = SupabaseSubscriptionService(supabase)
        can_generate = await subscription_service.can_generate_idea(int(telegram_user_id))
        if not can_generate:
            usage = await subscription_service.get_user_usage(int(telegram_user_id))
            reset_at = usage.get("reset_at")
            return JSONResponse(
                status_code=403,
                content={
                    "error": f"Достигнут лимит в 3 генерации идей для бесплатной подписки. Следующая попытка будет доступна после: {reset_at}. Лимиты обновляются каждые 3 дня. Оформите подписку для снятия ограничений."
                }
            )
    
    return await save_suggested_ideas_batch(payload, request) 