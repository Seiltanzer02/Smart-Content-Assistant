from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from services.supabase_subscription_service import SupabaseSubscriptionService
from backend.main import supabase, logger, generate_content_plan, get_saved_ideas, save_suggested_idea, save_suggested_ideas_batch

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
    return await save_suggested_ideas_batch(payload, request) 