from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from services.supabase_subscription_service import SupabaseSubscriptionService
from main import supabase, logger

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
async def generate_content_plan(request: Request, req: PlanGenerationRequest):
    # Заглушка для генерации плана
    return PlanGenerationResponse(plan=[], message="План сгенерирован (заглушка)")

@router.get("/ideas", response_model=SuggestedIdeasResponse)
async def get_saved_ideas(request: Request, channel_name: Optional[str] = None):
    # Заглушка для получения идей
    return SuggestedIdeasResponse(ideas=[], message="Идеи получены (заглушка)")

@router.post("/save-suggested-idea", response_model=Dict[str, Any])
async def save_suggested_idea(idea_data: Dict[str, Any], request: Request):
    # Заглушка для сохранения одной идеи
    return {"success": True, "message": "Идея сохранена (заглушка)"}

@router.post("/save-suggested-ideas", response_model=Dict[str, Any])
async def save_suggested_ideas_batch(payload: SaveIdeasRequest, request: Request):
    # Заглушка для пакетного сохранения идей
    return {"success": True, "message": "Идеи сохранены (заглушка)"} 