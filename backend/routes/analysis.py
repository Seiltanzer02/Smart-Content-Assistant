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
    """Анализирует Telegram канал и возвращает данные анализа."""
    # Получаем ID пользователя из заголовка
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    logger.info(f"Начинаем анализ канала от пользователя: {telegram_user_id}")
    
    # Проверяем валидность ID
    if not telegram_user_id or telegram_user_id == '123456789' or not telegram_user_id.isdigit():
        logger.error(f"Некорректный или отсутствующий Telegram ID: {telegram_user_id}")
        return JSONResponse(status_code=401, content={"error": "Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram."})
    
    try:
        # Инициализируем сервис подписки
        subscription_service = SupabaseSubscriptionService(supabase)
        logger.info(f"Проверяем возможность анализа для пользователя {telegram_user_id}")
        
        # Проверяем, может ли пользователь анализировать канал
        can_analyze = await subscription_service.can_analyze_channel(int(telegram_user_id))
        
        if not can_analyze:
            logger.warning(f"Превышен лимит анализа для пользователя {telegram_user_id}")
            return JSONResponse(status_code=403, content={"error": "Достигнут лимит анализа каналов для бесплатной подписки. Оформите подписку для снятия ограничений."})
        
        logger.info(f"Пользователь {telegram_user_id} может анализировать канал, выполняем анализ")
        
        # Здесь должна быть логика анализа канала
        # Для примера возвращаем заглушку
        
        # Увеличиваем счетчик после успешного анализа
        try:
            logger.info(f"Увеличиваем счетчик анализа для пользователя {telegram_user_id}")
            await subscription_service.increment_analysis_usage(int(telegram_user_id))
            logger.info(f"Счетчик анализа успешно увеличен для пользователя {telegram_user_id}")
        except Exception as counter_error:
            logger.error(f"Ошибка при увеличении счетчика анализа: {counter_error}")
        
        # Возвращаем результат анализа (заглушка)
        return AnalyzeResponse(
            themes=["тема 1", "тема 2"],
            styles=["стиль 1", "стиль 2"],
            analyzed_posts_sample=["пример поста 1", "пример поста 2"],
            best_posting_time="18:00-20:00",
            analyzed_posts_count=10,
            message="Анализ выполнен успешно (заглушка)"
        )
    except Exception as e:
        logger.error(f"Ошибка при анализе канала для пользователя {telegram_user_id}: {e}")
        return JSONResponse(
            status_code=500, 
            content={"error": f"Внутренняя ошибка сервера: {str(e)}"}
        ) 