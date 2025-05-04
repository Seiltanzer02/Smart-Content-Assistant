#!/usr/bin/env python3
"""
Сервис для работы с подписками пользователей.
"""

import logging
import asyncpg
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("subscription_service.log")
    ]
)
logger = logging.getLogger(__name__)

# Константы для бесплатного режима
FREE_ANALYSIS_LIMIT = 1    # Количество анализов для бесплатного режима
FREE_POST_LIMIT = 1        # Количество генераций постов для бесплатного режима
SUBSCRIPTION_PRICE = 1     # Цена подписки в Stars
SUBSCRIPTION_DURATION_MONTHS = 1  # Продолжительность подписки в месяцах

class SubscriptionService:
    """Класс для работы с подписками пользователей"""
    
    def __init__(self, pool):
        """
        Инициализирует сервис с пулом соединений.
        
        Args:
            pool: Пул соединений asyncpg
        """
        self.pool = pool
    
    async def get_subscription(self, user_id: int) -> Dict[str, Any]:
        """
        Получает информацию о подписке пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь с информацией о подписке
        """
        logger.info(f"Запрос информации о подписке для пользователя {user_id}")
        
        try:
            # Проверка наличия активной подписки
            has_subscription, subscription_end_date = await self.check_has_active_subscription(user_id)
            
            # Определение лимитов в зависимости от наличия подписки
            analysis_count = 9999 if has_subscription else FREE_ANALYSIS_LIMIT
            post_generation_count = 9999 if has_subscription else FREE_POST_LIMIT
            
            subscription_data = {
                "has_subscription": has_subscription,
                "analysis_count": analysis_count,
                "post_generation_count": post_generation_count
            }
            
            # Добавляем дату окончания подписки, если она есть
            if subscription_end_date:
                subscription_data["subscription_end_date"] = subscription_end_date.isoformat()
            
            logger.info(f"Результат запроса для {user_id}: {subscription_data}")
            return subscription_data
        
        except Exception as e:
            logger.error(f"Ошибка при получении информации о подписке для пользователя {user_id}: {e}")
            # В случае ошибки возвращаем статус без подписки
            return {
                "has_subscription": False,
                "analysis_count": FREE_ANALYSIS_LIMIT,
                "post_generation_count": FREE_POST_LIMIT,
                "error": str(e)
            }
    
    async def check_has_active_subscription(self, user_id: int) -> tuple[bool, Optional[datetime]]:
        """
        Проверяет, есть ли у пользователя активная подписка.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Tuple[bool, Optional[datetime]]: 
                - флаг наличия активной подписки
                - дата окончания активной подписки (None если подписки нет)
        """
        try:
            # Запрос для проверки наличия активной подписки
            query = """
            SELECT end_date 
            FROM user_subscription 
            WHERE user_id = $1 
            AND is_active = TRUE 
            AND end_date > NOW() 
            ORDER BY end_date DESC 
            LIMIT 1
            """
            subscription_end_date = await self.pool.fetchval(query, user_id)
            
            has_subscription = subscription_end_date is not None
            
            if has_subscription:
                logger.info(f"Пользователь {user_id} имеет активную подписку до {subscription_end_date}")
            else:
                logger.info(f"Пользователь {user_id} не имеет активной подписки")
            
            return has_subscription, subscription_end_date
        
        except Exception as e:
            logger.error(f"Ошибка при проверке подписки для пользователя {user_id}: {e}")
            return False, None
    
    async def check_premium_directly(self, user_id: int) -> bool:
        """
        Прямая проверка премиум-статуса пользователя.
        Используется для быстрой проверки без дополнительных данных.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            bool: True если у пользователя есть премиум, иначе False
        """
        try:
            async with self.pool.acquire() as conn:
                # Проверяем наличие активной подписки напрямую
                query = """
                SELECT COUNT(*) 
                FROM user_subscription 
                WHERE user_id = $1 
                  AND is_active = TRUE 
                  AND end_date > NOW()
                """
                count = await conn.fetchval(query, user_id)
                has_premium = count > 0
                
                logger.info(f"Прямая проверка премиума для пользователя {user_id}: {has_premium}")
                return has_premium
                
        except Exception as e:
            logger.error(f"Ошибка при прямой проверке премиума для пользователя {user_id}: {e}")
            return False
    
    async def create_subscription(self, user_id: int, payment_id: str, months: int = SUBSCRIPTION_DURATION_MONTHS) -> Dict[str, Any]:
        """
        Создает новую подписку для пользователя.
        
        Args:
            user_id: ID пользователя
            payment_id: ID платежа
            months: Количество месяцев подписки
            
        Returns:
            Словарь с информацией о созданной подписке
        """
        try:
            # Деактивируем существующие подписки
            await self.deactivate_user_subscriptions(user_id)
            
            # Определяем даты начала и окончания подписки
            start_date = datetime.now(timezone.utc)
            end_date = start_date + timedelta(days=30 * months)
            
            async with self.pool.acquire() as conn:
                # Выполняем транзакцию для создания подписки
                async with conn.transaction():
                    # Создаем новую активную подписку
                    query = """
                    INSERT INTO user_subscription 
                    (user_id, start_date, end_date, payment_id, is_active, created_at, updated_at) 
                    VALUES ($1, $2, $3, $4, TRUE, NOW(), NOW()) 
                    RETURNING id, user_id, start_date, end_date, payment_id, is_active
                    """
                    
                    # Выполняем запрос с проверкой на ошибки
                    subscription = await conn.fetchrow(
                        query, 
                        user_id, 
                        start_date, 
                        end_date, 
                        payment_id
                    )
                    
                    if not subscription:
                        raise Exception("Не удалось создать подписку")
                    
                    # Преобразуем результат в словарь
                    result = dict(subscription)
                    
                    # Добавляем строковое представление дат для JSON
                    result["start_date_iso"] = start_date.isoformat()
                    result["end_date_iso"] = end_date.isoformat()
                    
                    logger.info(f"Создана подписка для пользователя {user_id}: ID {result['id']}")
                    return result
                    
        except Exception as e:
            logger.error(f"Ошибка при создании подписки для пользователя {user_id}: {e}")
            raise
    
    async def deactivate_user_subscriptions(self, user_id: int) -> int:
        """
        Деактивирует все существующие подписки пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            int: Количество деактивированных подписок
        """
        try:
            async with self.pool.acquire() as conn:
                query = """
                UPDATE user_subscription 
                SET is_active = FALSE, updated_at = NOW() 
                WHERE user_id = $1 AND is_active = TRUE 
                RETURNING id
                """
                
                deactivated = await conn.fetch(query, user_id)
                count = len(deactivated)
                
                if count > 0:
                    deactivated_ids = [row['id'] for row in deactivated]
                    logger.info(f"Деактивировано {count} подписок для пользователя {user_id}: {deactivated_ids}")
                else:
                    logger.info(f"Не найдено активных подписок для деактивации для пользователя {user_id}")
                
                return count
                
        except Exception as e:
            logger.error(f"Ошибка при деактивации подписок для пользователя {user_id}: {e}")
            raise
    
    async def extend_subscription(self, user_id: int, payment_id: str, months: int = SUBSCRIPTION_DURATION_MONTHS) -> Dict[str, Any]:
        """
        Продлевает текущую подписку пользователя.
        
        Args:
            user_id: ID пользователя
            payment_id: ID платежа
            months: Количество месяцев продления
            
        Returns:
            Словарь с информацией о продленной подписке
        """
        try:
            async with self.pool.acquire() as conn:
                # Проверяем наличие активной подписки
                current_subscription_query = """
                SELECT id, end_date 
                FROM user_subscription 
                WHERE user_id = $1 
                  AND is_active = TRUE 
                  AND end_date > NOW() 
                ORDER BY end_date DESC 
                LIMIT 1
                """
                current_subscription = await conn.fetchrow(current_subscription_query, user_id)
                
                async with conn.transaction():
                    if current_subscription:
                        # Если есть активная подписка, продлеваем ее
                        current_end_date = current_subscription['end_date']
                        new_end_date = current_end_date + timedelta(days=30 * months)
                        
                        update_query = """
                        UPDATE user_subscription 
                        SET end_date = $1, 
                            payment_id = $2, 
                            updated_at = NOW() 
                        WHERE id = $3 
                        RETURNING id, user_id, start_date, end_date, payment_id, is_active
                        """
                        
                        updated = await conn.fetchrow(
                            update_query, 
                            new_end_date, 
                            payment_id, 
                            current_subscription['id']
                        )
                        
                        result = dict(updated)
                        result["extended"] = True
                        logger.info(f"Продлена подписка #{result['id']} для пользователя {user_id} до {new_end_date}")
                        
                    else:
                        # Если нет активной подписки, создаем новую
                        logger.info(f"Нет активной подписки для пользователя {user_id}, создаем новую")
                        result = await self.create_subscription(user_id, payment_id, months)
                        result["extended"] = False
                    
                    # Добавляем строковое представление дат для JSON
                    if "start_date_iso" not in result and "start_date" in result:
                        result["start_date_iso"] = result["start_date"].isoformat()
                    if "end_date_iso" not in result and "end_date" in result:
                        result["end_date_iso"] = result["end_date"].isoformat()
                    
                    return result
                    
        except Exception as e:
            logger.error(f"Ошибка при продлении подписки для пользователя {user_id}: {e}")
            raise
            
    async def get_subscription_history(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получает историю подписок пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список словарей с информацией о подписках
        """
        try:
            query = """
            SELECT 
                id, 
                user_id, 
                start_date, 
                end_date, 
                payment_id, 
                is_active, 
                created_at, 
                updated_at 
            FROM user_subscription 
            WHERE user_id = $1 
            ORDER BY created_at DESC
            """
            
            async with self.pool.acquire() as conn:
                subscriptions = await conn.fetch(query, user_id)
                
                # Преобразуем результаты в список словарей
                result = []
                for sub in subscriptions:
                    sub_dict = dict(sub)
                    # Добавляем строковое представление дат для JSON
                    for date_field in ['start_date', 'end_date', 'created_at', 'updated_at']:
                        if date_field in sub_dict and sub_dict[date_field]:
                            sub_dict[f"{date_field}_iso"] = sub_dict[date_field].isoformat()
                    result.append(sub_dict)
                
                logger.info(f"Получена история подписок для пользователя {user_id}: {len(result)} записей")
                return result
                
        except Exception as e:
            logger.error(f"Ошибка при получении истории подписок для пользователя {user_id}: {e}")
            raise 