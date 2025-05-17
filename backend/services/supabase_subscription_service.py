from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, Any, Optional
from dateutil.relativedelta import relativedelta
import httpx
import os

# Константы для бесплатных лимитов
FREE_ANALYSIS_LIMIT = 5
FREE_POST_LIMIT = 2
FREE_IDEAS_LIMIT = 3
SUBSCRIPTION_DURATION_MONTHS = 1
# ПЕРИОД СБРОСА ЛИМИТОВ
RESET_PERIOD_DAYS = 3  # Сброс каждые 3 дня
RESET_PERIOD_MINUTES = None  # Отключено, используем дни

logger = logging.getLogger("subscription_service")

class SupabaseSubscriptionService:
    def __init__(self, supabase_client):
        """Инициализирует сервис с клиентом Supabase."""
        self.supabase = supabase_client
    
    async def get_user_usage(self, user_id: int) -> Dict[str, Any]:
        """Получает статистику использования бесплатных функций."""
        try:
            now = datetime.now(timezone.utc)
            logger.info(f"Получение статистики для пользователя {user_id}. Текущая дата: {now.isoformat()}")
            
            result = self.supabase.table("user_usage_stats").select("*").eq("user_id", user_id).execute()
            
            if result.data and len(result.data) > 0:
                usage_data = result.data[0]
                logger.info(f"Найдены данные статистики для пользователя {user_id}: {usage_data}")
                
                reset_at_str = usage_data.get("reset_at")
                logger.info(f"Дата сброса для пользователя {user_id}: {reset_at_str}")
                
                if reset_at_str:
                    try:
                        # Стандартизируем формат даты
                        if 'Z' in reset_at_str:
                            reset_at_str = reset_at_str.replace('Z', '+00:00')
                        
                        # Используем fromisoformat для парсинга ISO 8601 формата
                        reset_at = datetime.fromisoformat(reset_at_str)
                        
                        # Проверяем наличие информации о часовом поясе
                        if reset_at.tzinfo is None:
                            logger.info(f"Дата сброса не содержит информации о часовом поясе, добавляем UTC: {reset_at_str}")
                            reset_at = reset_at.replace(tzinfo=timezone.utc)
                        
                        logger.info(f"Сравниваем даты: now={now.isoformat()}, reset_at={reset_at.isoformat()}")
                        
                        # Проверяем, нужно ли сбросить счетчики
                        if now >= reset_at:
                            logger.info(f"Срок сброса счетчиков наступил для пользователя {user_id}")
                            return await self.reset_usage_counters(user_id)
                        else:
                            logger.info(f"Счетчики еще актуальны для пользователя {user_id}")
                    except Exception as date_error:
                        logger.error(f"Ошибка при обработке даты '{reset_at_str}' для пользователя {user_id}: {date_error}", exc_info=True)
                        # В случае ошибки парсинга даты сбрасываем счетчики
                        return await self.reset_usage_counters(user_id)
                
                # Если все проверки прошли, возвращаем данные использования
                return usage_data
            
            # Если записи нет — создаём с reset_at через 3 дня
            logger.info(f"Запись для пользователя {user_id} не найдена. Создаем новую.")
            next_reset = now + timedelta(days=RESET_PERIOD_DAYS)  # Сброс через 3 дня
            new_record = {
                "user_id": user_id,
                "analysis_count": 0,
                "post_generation_count": 0,
                "ideas_generation_count": 0,
                "reset_at": next_reset.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }
            
            logger.info(f"Создаем новую запись для пользователя {user_id}: {new_record}")
            
            try:
                insert_result = self.supabase.table("user_usage_stats").insert(new_record).execute()
                if insert_result.data and len(insert_result.data) > 0:
                    logger.info(f"Запись успешно создана для пользователя {user_id}")
                    return insert_result.data[0]
                else:
                    logger.warning(f"Странное поведение при создании записи для пользователя {user_id}. Возвращаем новую запись напрямую.")
                    return new_record
            except Exception as insert_error:
                logger.error(f"Ошибка при создании записи для пользователя {user_id}: {insert_error}", exc_info=True)
                return new_record
        except Exception as e:
            logger.error(f"Общая ошибка при получении статистики использования для user_id {user_id}: {e}", exc_info=True)
            return {
                "user_id": user_id, 
                "analysis_count": 0, 
                "post_generation_count": 0, 
                "ideas_generation_count": 0,
                "reset_at": (datetime.now(timezone.utc) + timedelta(days=RESET_PERIOD_DAYS)).isoformat()
            }
    
    async def increment_analysis_usage(self, user_id: int) -> Dict[str, Any]:
        """Увеличивает счетчик использования анализа."""
        try:
            usage = await self.get_user_usage(user_id)
            update_data = {
                "analysis_count": usage.get("analysis_count", 0) + 1,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            result = self.supabase.table("user_usage_stats").update(update_data).eq("user_id", user_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return usage
        except Exception as e:
            logger.error(f"Ошибка при увеличении счетчика анализа: {e}")
            return {"user_id": user_id, "analysis_count": 0, "post_generation_count": 0}
    
    async def increment_post_usage(self, user_id: int) -> Dict[str, Any]:
        """Увеличивает счетчик использования генерации постов."""
        try:
            # Сначала получаем текущую статистику
            usage = await self.get_user_usage(user_id)
            
            # Обновляем счетчик
            update_data = {
                "post_generation_count": usage.get("post_generation_count", 0) + 1,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            result = self.supabase.table("user_usage_stats").update(update_data).eq("user_id", user_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            
            return usage
            
        except Exception as e:
            logger.error(f"Ошибка при увеличении счетчика генерации постов: {e}")
            return {"user_id": user_id, "analysis_count": 0, "post_generation_count": 0}
    
    async def get_subscription(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает активную подписку пользователя с проверкой даты окончания."""
        try:
            # Получаем все подписки пользователя, отсортированные по дате окончания
            result = self.supabase.table("user_subscription").select("*").eq("user_id", user_id).order("end_date", desc=True).execute()
            
            if not result.data or len(result.data) == 0:
                return None
            
            # Проверяем самую последнюю подписку
            subscription = result.data[0]
            
            # Проверяем флаг is_active и дату окончания
            is_active = subscription.get("is_active", False)
            end_date_str = subscription.get("end_date")
            
            if not is_active:
                return None
                
            # Проверяем дату окончания, если она указана
            if end_date_str:
                try:
                    # Парсим дату окончания используя datetime.fromisoformat
                    end_date = datetime.fromisoformat(end_date_str)
                    
                    # Убеждаемся, что дата имеет информацию о часовом поясе
                    if end_date.tzinfo is None:
                        end_date = end_date.replace(tzinfo=timezone.utc)
                    
                    now_utc = datetime.now(timezone.utc)
                    if end_date <= now_utc:
                        # Подписка истекла, деактивируем её
                        self.supabase.table("user_subscription").update({"is_active": False}).eq("id", subscription.get("id")).execute()
                        logger.info(f"Деактивирована истекшая подписка пользователя {user_id}, end_date={end_date.isoformat()}, now={now_utc.isoformat()}")
                        
                        # Отправляем уведомление пользователю о том, что подписка закончилась
                        await self.send_subscription_expiry_notification(user_id)
                        
                        return None
                except Exception as date_error:
                    logger.error(f"Ошибка при парсинге даты окончания подписки '{end_date_str}': {date_error}", exc_info=True)
            
            return subscription
            
        except Exception as e:
            logger.error(f"Ошибка при получении подписки для user_id {user_id}: {e}", exc_info=True)
            return None
    
    async def create_subscription(self, user_id: int, payment_id: str = None) -> Dict[str, Any]:
        """Создает новую подписку."""
        try:
            now = datetime.now(timezone.utc)
            end_date = now + relativedelta(months=SUBSCRIPTION_DURATION_MONTHS)
            
            subscription_data = {
                "user_id": user_id,
                "start_date": now.isoformat(),
                "end_date": end_date.isoformat(),
                "is_active": True,
                "payment_id": payment_id
            }
            
            # Сначала деактивируем все текущие подписки
            self.supabase.table("user_subscription").update({"is_active": False}).eq("user_id", user_id).execute()
            
            # Создаем новую активную подписку
            result = self.supabase.table("user_subscription").insert(subscription_data).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            
            return subscription_data
            
        except Exception as e:
            logger.error(f"Ошибка при создании подписки: {e}")
            raise e
    
    async def has_active_subscription(self, user_id: int) -> bool:
        """Проверяет, есть ли у пользователя активная подписка."""
        subscription = await self.get_subscription(user_id)
        return subscription is not None
    
    async def can_analyze_channel(self, user_id: int) -> bool:
        """Проверяет, может ли пользователь анализировать канал."""
        has_subscription = await self.has_active_subscription(user_id)
        if has_subscription:
            return True
        usage = await self.get_user_usage(user_id)
        return usage.get("analysis_count", 0) < FREE_ANALYSIS_LIMIT
    
    async def can_generate_post(self, user_id: int) -> bool:
        """Проверяет, может ли пользователь генерировать посты."""
        # Проверяем наличие подписки
        has_subscription = await self.has_active_subscription(user_id)
        if has_subscription:
            return True
        
        # Проверяем использование бесплатного лимита
        usage = await self.get_user_usage(user_id)
        return usage.get("post_generation_count", 0) < FREE_POST_LIMIT
    
    async def reset_usage_counters(self, user_id: int) -> Dict[str, Any]:
        """Сбрасывает счетчики использования и устанавливает новую дату сброса."""
        now = datetime.now(timezone.utc)
        next_reset = now + timedelta(days=RESET_PERIOD_DAYS)  # Сброс через 3 дня
        update_data = {
            "analysis_count": 0,
            "post_generation_count": 0,
            "ideas_generation_count": 0,
            "reset_at": next_reset.isoformat(),
            "updated_at": now.isoformat()
        }
        result = self.supabase.table("user_usage_stats").update(update_data).eq("user_id", user_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        # Если запись не найдена, создаём новую
        new_record = {
            "user_id": user_id,
            "analysis_count": 0,
            "post_generation_count": 0,
            "ideas_generation_count": 0,
            "reset_at": next_reset.isoformat(),
            "updated_at": now.isoformat()
        }
        self.supabase.table("user_usage_stats").insert(new_record).execute()
        return new_record
    
    async def check_reset_counters(self, user_id: int) -> Dict[str, Any]:
        """Проверяет, не пора ли сбросить счетчики использования."""
        try:
            # Получаем текущие данные использования
            usage = await self.get_user_usage(user_id)
            
            # Проверяем наличие даты сброса
            reset_at_str = usage.get("reset_at")
            if not reset_at_str:
                # Если даты сброса нет, устанавливаем ее и возвращаем данные
                return await self.reset_usage_counters(user_id)
            
            # Парсим дату сброса
            try:
                reset_at = datetime.fromisoformat(reset_at_str)
                # Проверяем наличие информации о часовом поясе
                if reset_at.tzinfo is None:
                    logger.info(f"Дата сброса не содержит информации о часовом поясе, добавляем UTC: {reset_at_str}")
                    reset_at = reset_at.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                logger.info(f"Сравниваем даты: now={now.isoformat()}, reset_at={reset_at.isoformat()}")
                # Проверяем, нужно ли сбросить счетчики
                if now >= reset_at:
                    logger.info(f"Срок сброса счетчиков наступил для пользователя {user_id}")
                    return await self.reset_usage_counters(user_id)
                else:
                    logger.info(f"Счетчики еще актуальны для пользователя {user_id}")
            except Exception as date_error:
                logger.error(f"Ошибка при парсинге или сравнении даты сброса счетчиков '{reset_at_str}': {date_error}", exc_info=True)
                # В случае ошибки парсинга, сбрасываем счетчики
                return await self.reset_usage_counters(user_id)
            
            # Если сброс не требуется, возвращаем текущие данные
            return usage
            
        except Exception as e:
            logger.error(f"Ошибка при проверке сброса счетчиков использования для user_id {user_id}: {e}", exc_info=True)
            return {"user_id": user_id, "analysis_count": 0, "post_generation_count": 0}
    
    async def can_generate_idea(self, user_id: int) -> bool:
        has_subscription = await self.has_active_subscription(user_id)
        if has_subscription:
            return True
        usage = await self.get_user_usage(user_id)
        return usage.get("ideas_generation_count", 0) < FREE_IDEAS_LIMIT

    async def increment_idea_usage(self, user_id: int) -> Dict[str, Any]:
        try:
            usage = await self.get_user_usage(user_id)
            update_data = {
                "ideas_generation_count": usage.get("ideas_generation_count", 0) + 1,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            result = self.supabase.table("user_usage_stats").update(update_data).eq("user_id", user_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return usage
        except Exception as e:
            logger.error(f"Ошибка при увеличении счетчика генерации идей: {e}")
            return {"user_id": user_id, "ideas_generation_count": 0} 

    async def send_subscription_expiry_notification(self, user_id: int) -> bool:
        """Отправляет уведомление о том, что подписка закончилась."""
        try:
            message_text = "Ваша подписка закончилась! Получите безлимитную генерацию контента всего за 70 Stars."
            
            telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
            if not telegram_token:
                logger.error(f"Отсутствует TELEGRAM_BOT_TOKEN при отправке уведомления об окончании подписки пользователю {user_id}")
                return False
                
            telegram_api_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(telegram_api_url, json={
                        "chat_id": user_id,
                        "text": message_text,
                        "parse_mode": "HTML"
                    })
                    if response.status_code == 200:
                        logger.info(f"Уведомление об окончании подписки успешно отправлено пользователю {user_id}")
                        return True
                    else:
                        logger.error(f"Ошибка при отправке уведомления об окончании подписки: {response.status_code} {response.text}")
                        return False
                except Exception as e:
                    logger.error(f"Исключение при отправке уведомления об окончании подписки в Telegram: {e}")
                    return False
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об окончании подписки: {e}")
            return False 