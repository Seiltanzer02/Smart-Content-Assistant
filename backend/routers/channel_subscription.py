from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any

from backend.services.channel_subscription_service import ChannelSubscriptionService

router = APIRouter(
    prefix="/channel",
    tags=["channel_subscription"],
    responses={
        401: {"description": "Unauthorized"},
        500: {"description": "Internal server error"}
    }
)

@router.get("/subscription/status", response_model=Dict[str, Any])
async def check_channel_subscription(request: Request, user_id: Optional[str] = None):
    """
    Проверяет, подписан ли пользователь на требуемый канал Telegram.
    Возвращает статус подписки и информацию о канале.
    """
    user_id_int = None
    if user_id:
        try:
            user_id_int = int(user_id)
        except ValueError:
            return JSONResponse(
                content={
                    "success": False,
                    "is_subscribed": False,
                    "error": "Некорректный идентификатор пользователя"
                },
                status_code=400
            )
    
    return await ChannelSubscriptionService.get_subscription_status(request, user_id_int)

@router.get("/subscription/url", response_model=Dict[str, Any])
async def get_subscription_url():
    """
    Возвращает URL для подписки на канал
    """
    url = ChannelSubscriptionService.get_channel_subscription_url()
    if not url:
        return JSONResponse(
            content={
                "success": False,
                "url": "",
                "error": "URL канала не настроен"
            },
            status_code=500
        )
    
    return {
        "success": True,
        "url": url,
        "channel": url.replace("https://t.me/", "")
    } 