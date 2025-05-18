from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

from utils.partner_referral import get_partner_referral_service, PartnerReferralService
import asyncpg

# Настройка логирования
logger = logging.getLogger('partner_router')

# Определяем router
router = APIRouter(
    prefix="/partner",
    tags=["partner"],
    responses={404: {"description": "Not found"}},
)

# Модели данных
class PartnerLinkResponse(BaseModel):
    user_id: int
    partner_link: str

class ReferralStatsResponse(BaseModel):
    user_id: int
    referred_users: int
    rewards_received: int
    partner_link: Optional[str] = None

class ReferralRequest(BaseModel):
    referrer_id: int
    referred_id: int

# Функция для получения сервиса работы с партнерскими ссылками
async def get_referral_service():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL не указан в переменных окружения")
    
    pool = await asyncpg.create_pool(db_url)
    return await get_partner_referral_service(pool)

# Маршруты API
@router.get("/link/{user_id}", response_model=PartnerLinkResponse)
async def get_partner_link(user_id: int, service: PartnerReferralService = Depends(get_referral_service)):
    """
    Получить или создать партнерскую ссылку для пользователя
    """
    try:
        partner_link = await service.get_partner_link(user_id)
        return {"user_id": user_id, "partner_link": partner_link}
    except Exception as e:
        logger.error(f"Ошибка при получении партнерской ссылки: {e}")
        raise HTTPException(status_code=500, detail=f"Не удалось получить партнерскую ссылку: {str(e)}")

@router.get("/stats/{user_id}", response_model=ReferralStatsResponse)
async def get_referral_stats(user_id: int, service: PartnerReferralService = Depends(get_referral_service)):
    """
    Получить статистику по реферальной программе пользователя
    """
    try:
        stats = await service.get_referral_stats(user_id)
        return stats
    except Exception as e:
        logger.error(f"Ошибка при получении статистики рефералов: {e}")
        raise HTTPException(status_code=500, detail=f"Не удалось получить статистику рефералов: {str(e)}")

@router.post("/track", response_model=Dict[str, Any])
async def track_referral(request: ReferralRequest, service: PartnerReferralService = Depends(get_referral_service)):
    """
    Отслеживать реферальную активность (когда пользователь приходит по партнерской ссылке)
    """
    try:
        await service.track_referral(request.referrer_id, request.referred_id)
        return {"success": True, "message": "Реферал успешно отслежен"}
    except Exception as e:
        logger.error(f"Ошибка при отслеживании реферала: {e}")
        raise HTTPException(status_code=500, detail=f"Не удалось отследить реферал: {str(e)}")

# Импорт модуля os
import os 