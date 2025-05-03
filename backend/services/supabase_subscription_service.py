from datetime import datetime, timedelta
import logging
from typing import Dict, Any, Optional
from dateutil.relativedelta import relativedelta

# Константы для бесплатных лимитов
FREE_ANALYSIS_LIMIT = 2
FREE_POST_LIMIT = 2
SUBSCRIPTION_DURATION_MONTHS = 1

logger = logging.getLogger("subscription_service")

class SupabaseSubscriptionService:
    def __init__(self, supabase_client):
        """Инициализирует сервис с клиентом Supabase."""
        self.supabase = supabase_client
    
    async def get_user_usage(self, user_id: int) -> Dict[str, Any]:
        """Получает статистику использования бесплатных функций."""
        try:
            # Получаем данные о текущем использовании
            result = self.supabase.table("user_usage_stats").select("*").eq("user_id", user_id).execute()
            
            if result.data and len(result.data) > 0:
                usage_data = result.data[0]
                
                # Проверяем, не нужно ли сбросить счетчики
                reset_at_str = usage_data.get("reset_at")
                if reset_at_str:
                    try:
                        # Парсим дату сброса
                        if 'Z' in reset_at_str:
                            reset_at = datetime.fromisoformat(reset_at_str.replace('Z', '+00:00'))
                        else:
                            reset_at = datetime.fromisoformat(reset_at_str)
                        
                        # Если дата сброса в прошлом, сбрасываем счетчики
                        if datetime.now() >= reset_at:
                            return await self.reset_usage_counters(user_id)
                    except Exception as date_error:
                        logger.error(f"Ошибка при парсинге даты сброса счетчиков: {date_error}")
                
                return usage_data
            
            # Если записи нет, создаем новую
            now = datetime.now()
            next_reset_date = now + relativedelta(months=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            new_record = {
                "user_id": user_id,
                "analysis_count": 0,
                "post_generation_count": 0,
                "reset_at": next_reset_date.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }
            
            create_result = self.supabase.table("user_usage_stats").insert(new_record).execute()
            
            if create_result.data and len(create_result.data) > 0:
                return create_result.data[0]
            
            return new_record
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики использования: {e}")
            # Возвращаем дефолтные значения в случае ошибки
            return {"user_id": user_id, "analysis_count": 0, "post_generation_count": 0}
    
    async def increment_analysis_usage(self, user_id: int) -> Dict[str, Any]:
        """Увеличивает счетчик использования анализа."""
        try:
            # Сначала получаем текущую статистику
            usage = await self.get_user_usage(user_id)
            
            # Обновляем счетчик
            update_data = {
                "analysis_count": usage.get("analysis_count", 0) + 1,
                "updated_at": datetime.now().isoformat()
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
                "updated_at": datetime.now().isoformat()
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
                    # Парсим дату окончания
                    if 'Z' in end_date_str:
                        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    else:
                        end_date = datetime.fromisoformat(end_date_str)
                    
                    # Проверяем, не истекла ли подписка
                    if end_date <= datetime.now():
                        # Подписка истекла, деактивируем её
                        self.supabase.table("user_subscription").update({"is_active": False}).eq("id", subscription.get("id")).execute()
                        logger.info(f"Деактивирована истекшая подписка пользователя {user_id}")
                        return None
                except Exception as date_error:
                    logger.error(f"Ошибка при парсинге даты окончания подписки: {date_error}")
            
            return subscription
            
        except Exception as e:
            logger.error(f"Ошибка при получении подписки: {e}")
            return None
    
    async def create_subscription(self, user_id: int, payment_id: str = None) -> Dict[str, Any]:
        """Создает новую подписку."""
        try:
            now = datetime.now()
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
        # Проверяем наличие подписки
        has_subscription = await self.has_active_subscription(user_id)
        if has_subscription:
            return True
        
        # Проверяем использование бесплатного лимита
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
        try:
            # Устанавливаем дату следующего сброса на первое число следующего месяца
            next_reset_date = datetime.now() + relativedelta(months=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Обновляем счетчики и дату сброса
            update_data = {
                "analysis_count": 0,
                "post_generation_count": 0,
                "reset_at": next_reset_date.isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table("user_usage_stats").update(update_data).eq("user_id", user_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            
            # Если запись не найдена, создаем новую
            new_record = {
                "user_id": user_id,
                "analysis_count": 0,
                "post_generation_count": 0,
                "reset_at": next_reset_date.isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            create_result = self.supabase.table("user_usage_stats").insert(new_record).execute()
            
            if create_result.data and len(create_result.data) > 0:
                return create_result.data[0]
            
            return new_record
            
        except Exception as e:
            logger.error(f"Ошибка при сбросе счетчиков использования: {e}")
            return {"user_id": user_id, "analysis_count": 0, "post_generation_count": 0}
    
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
                if 'Z' in reset_at_str:
                    reset_at = datetime.fromisoformat(reset_at_str.replace('Z', '+00:00'))
                else:
                    reset_at = datetime.fromisoformat(reset_at_str)
                    
                # Проверяем, нужно ли сбросить счетчики
                if datetime.now() >= reset_at:
                    # Сбрасываем счетчики и устанавливаем новую дату сброса
                    return await self.reset_usage_counters(user_id)
            except Exception as date_error:
                logger.error(f"Ошибка при парсинге даты сброса счетчиков: {date_error}")
                # В случае ошибки парсинга, сбрасываем счетчики
                return await self.reset_usage_counters(user_id)
            
            # Если сброс не требуется, возвращаем текущие данные
            return usage
            
        except Exception as e:
            logger.error(f"Ошибка при проверке сброса счетчиков использования: {e}")
            return {"user_id": user_id, "analysis_count": 0, "post_generation_count": 0} 