import os
import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Response, status

from telegram_utils import create_subscription_invoice, verify_payment_data
from user_service import UserService

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание маршрутизатора для API
router = APIRouter(prefix="/subscription", tags=["subscription"])

@router.get("/status")
async def check_subscription_status(user_id: str):
    """
    Проверка статуса подписки пользователя
    
    Args:
        user_id: ID пользователя в Telegram
        
    Returns:
        Dict[str, Any]: Информация о статусе подписки
    """
    # Проверяем наличие корректного user_id
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=400, detail="Не указан ID пользователя")
    
    try:
        status = UserService.check_subscription_status(user_id)
        return {
            "success": True,
            "status": status
        }
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса подписки: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@router.post("/create-invoice")
async def create_invoice(user_id: str):
    """
    Создание счета для оплаты подписки
    
    Args:
        user_id: ID пользователя в Telegram
        
    Returns:
        Dict[str, Any]: URL инвойса и статус операции
    """
    # Проверяем наличие корректного user_id
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=400, detail="Не указан ID пользователя")
    
    try:
        # Проверяем наличие пользователя в базе
        user = UserService.get_or_create_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Создаем инвойс для оплаты
        invoice_url = create_subscription_invoice(user_id)
        
        if not invoice_url:
            raise HTTPException(status_code=500, detail="Не удалось создать счет для оплаты")
        
        return {
            "success": True,
            "invoice_url": invoice_url
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при создании счета: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@router.post("/webhook")
async def payment_webhook(request: Request):
    """
    Webhook для обработки уведомлений о платежах от Telegram
    
    Args:
        request: Запрос с данными о платеже
        
    Returns:
        Dict[str, Any]: Статус обработки платежа
    """
    try:
        # Получаем данные из запроса
        payment_data = await request.json()
        logger.info(f"Получены данные о платеже: {json.dumps(payment_data)}")
        
        # Проверяем валидность данных о платеже
        user_id, is_valid = verify_payment_data(payment_data)
        
        if not is_valid:
            logger.warning("Получены некорректные данные о платеже")
            return {"success": False, "message": "Некорректные данные о платеже"}
        
        # Обновляем информацию о подписке пользователя
        success, message = UserService.update_subscription(user_id)
        
        if success:
            logger.info(f"Подписка успешно обновлена для пользователя {user_id}")
            return {"success": True, "message": message}
        else:
            logger.error(f"Ошибка при обновлении подписки: {message}")
            return {"success": False, "message": message}
            
    except Exception as e:
        logger.error(f"Ошибка при обработке webhook: {e}")
        return {"success": False, "message": f"Внутренняя ошибка сервера: {str(e)}"}

@router.post("/use-free-analysis")
async def use_free_analysis(user_id: str):
    """
    Использование бесплатной попытки анализа
    
    Args:
        user_id: ID пользователя в Telegram
        
    Returns:
        Dict[str, Any]: Статус операции и обновленная информация о подписке
    """
    # Проверяем наличие корректного user_id
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=400, detail="Не указан ID пользователя")
    
    try:
        # Списываем одну бесплатную попытку
        success = UserService.use_free_analysis(user_id)
        
        if not success:
            return {
                "success": False,
                "message": "Не осталось бесплатных попыток для анализа",
                "status": UserService.check_subscription_status(user_id)
            }
        
        return {
            "success": True,
            "message": "Бесплатная попытка анализа использована",
            "status": UserService.check_subscription_status(user_id)
        }
    except Exception as e:
        logger.error(f"Ошибка при использовании бесплатной попытки анализа: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@router.post("/use-free-post-details")
async def use_free_post_details(user_id: str):
    """
    Использование бесплатной попытки получения деталей поста
    
    Args:
        user_id: ID пользователя в Telegram
        
    Returns:
        Dict[str, Any]: Статус операции и обновленная информация о подписке
    """
    # Проверяем наличие корректного user_id
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=400, detail="Не указан ID пользователя")
    
    try:
        # Списываем одну бесплатную попытку
        success = UserService.use_free_post_details(user_id)
        
        if not success:
            return {
                "success": False,
                "message": "Не осталось бесплатных попыток для деталей поста",
                "status": UserService.check_subscription_status(user_id)
            }
        
        return {
            "success": True,
            "message": "Бесплатная попытка получения деталей поста использована",
            "status": UserService.check_subscription_status(user_id)
        }
    except Exception as e:
        logger.error(f"Ошибка при использовании бесплатной попытки деталей поста: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@router.get("/can-analyze")
async def can_analyze(user_id: str):
    """
    Проверка возможности анализа канала
    
    Args:
        user_id: ID пользователя в Telegram
        
    Returns:
        Dict[str, Any]: Статус и причина (если доступа нет)
    """
    # Проверяем наличие корректного user_id
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=400, detail="Не указан ID пользователя")
    
    try:
        status = UserService.check_subscription_status(user_id)
        
        # Если есть активная подписка или остались бесплатные попытки
        if status["has_subscription"] or status["free_analysis_count"] > 0:
            return {
                "success": True,
                "can_analyze": True,
                "message": "Доступ разрешен",
                "status": status
            }
        else:
            return {
                "success": True,
                "can_analyze": False,
                "message": "Необходима подписка или бесплатные попытки исчерпаны",
                "status": status
            }
    except Exception as e:
        logger.error(f"Ошибка при проверке возможности анализа: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@router.get("/can-get-post-details")
async def can_get_post_details(user_id: str):
    """
    Проверка возможности получения деталей поста
    
    Args:
        user_id: ID пользователя в Telegram
        
    Returns:
        Dict[str, Any]: Статус и причина (если доступа нет)
    """
    # Проверяем наличие корректного user_id
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=400, detail="Не указан ID пользователя")
    
    try:
        status = UserService.check_subscription_status(user_id)
        
        # Если есть активная подписка или остались бесплатные попытки
        if status["has_subscription"] or status["free_post_details_count"] > 0:
            return {
                "success": True,
                "can_get_details": True,
                "message": "Доступ разрешен",
                "status": status
            }
        else:
            return {
                "success": True,
                "can_get_details": False,
                "message": "Необходима подписка или бесплатные попытки исчерпаны",
                "status": status
            }
    except Exception as e:
        logger.error(f"Ошибка при проверке возможности получения деталей поста: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}") 