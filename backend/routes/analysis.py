from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
from services.supabase_subscription_service import SupabaseSubscriptionService
from backend.services.analysis_service import analyze_channel
from backend.telegram_utils import get_telegram_posts, get_telegram_posts_via_http, get_sample_posts
from backend.deepseek_utils import analyze_content_with_deepseek
from datetime import datetime
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
async def analyze_channel_router(request: Request, req: AnalyzeRequest):
    return await analyze_channel(request, req) 