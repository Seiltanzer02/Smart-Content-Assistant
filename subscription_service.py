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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        try:
            logger.info(f"Запрос информации о подписке для пользователя {user_id}")
            
            # Проверяем наличие активной подписки
            has_subscription = await self.check_premium_directly(user_id)
            
            # Получаем информацию о текущей/последней подписке
            subscription_info = await self.pool.fetchrow("""
                SELECT 
                    id, 
                    start_date, 
                    end_date, 
                    is_active 
                FROM subscriptions 
                WHERE user_id = $1 
                ORDER BY end_date DESC 
                LIMIT 1
            """, user_id)
            
            # Расчет количества оставшихся анализов и генераций
            # В премиум-версии - без ограничений, в бесплатной - ограниченное количество
            # Можно настроить эти значения как требуется
            base_analysis_count = 1  # Базовое количество анализов для бесплатных пользователей
            base_post_generation_count = 1  # Базовое количество генераций постов для бесплатных пользователей
            
            if has_subscription:
                analysis_count = float('inf')  # Бесконечно для премиум
                post_generation_count = float('inf')  # Бесконечно для премиум
                logger.info(f"Пользователь {user_id} имеет активную премиум-подписку")
            else:
                # Для бесплатных пользователей - базовое количество минус использованное
                used_analysis = await self.get_used_analysis_count(user_id)
                used_post_gen = await self.get_used_post_generation_count(user_id)
                
                analysis_count = max(0, base_analysis_count - used_analysis)
                post_generation_count = max(0, base_post_generation_count - used_post_gen)
                logger.info(f"Пользователь {user_id} использовал {used_analysis} анализов и {used_post_gen} генераций")
            
            # Форматирование данных ответа
            response = {
                "has_subscription": has_subscription,
                "analysis_count": analysis_count if analysis_count != float('inf') else 9999,
                "post_generation_count": post_generation_count if post_generation_count != float('inf') else 9999
            }
            
            # Если есть подписка, добавляем дату окончания
            if subscription_info and has_subscription:
                response["subscription_end_date"] = subscription_info["end_date"].isoformat()
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о подписке: {e}")
            # Возвращаем базовые данные в случае ошибки
            return {
                "has_subscription": False,
                "analysis_count": 0,
                "post_generation_count": 0,
                "error": str(e)
            }
    
    async def check_premium_directly(self, user_id: int) -> bool:
        """
        Прямая проверка наличия активной премиум-подписки.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если у пользователя есть активная подписка, иначе False
        """
        try:
            logger.info(f"Прямая проверка премиум-статуса для пользователя {user_id}")
            
            # Проверяем наличие активной подписки с учетом времени окончания
            count = await self.pool.fetchval("""
                SELECT COUNT(*) 
                FROM subscriptions 
                WHERE user_id = $1 
                  AND is_active = TRUE 
                  AND end_date > NOW()
            """, user_id)
            
            has_premium = count > 0
            logger.info(f"Пользователь {user_id} имеет premium={has_premium} (найдено {count} активных подписок)")
            
            return has_premium
            
        except Exception as e:
            logger.error(f"Ошибка при проверке премиум-статуса: {e}")
            return False
    
    async def get_used_analysis_count(self, user_id: int) -> int:
        """
        Получает количество использованных анализов каналов.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Количество использованных анализов
        """
        try:
            # Пример запроса - может потребоваться настройка под вашу схему БД
            count = await self.pool.fetchval("""
                SELECT COUNT(*) 
                FROM channel_analysis 
                WHERE user_id = $1
            """, user_id)
            
            return count or 0
            
        except Exception as e:
            logger.error(f"Ошибка при получении количества использованных анализов: {e}")
            return 0
    
    async def get_used_post_generation_count(self, user_id: int) -> int:
        """
        Получает количество использованных генераций постов.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Количество использованных генераций
        """
        try:
            # Пример запроса - может потребоваться настройка под вашу схему БД
            count = await self.pool.fetchval("""
                SELECT COUNT(*) 
                FROM saved_posts 
                WHERE user_id = $1 
                  AND is_generated = TRUE
            """, user_id)
            
            return count or 0
            
        except Exception as e:
            logger.error(f"Ошибка при получении количества использованных генераций: {e}")
            return 0
    
    async def create_subscription(self, user_id: int, months: int = 1, payment_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Создает новую подписку для пользователя.
        
        Args:
            user_id: ID пользователя
            months: Длительность подписки в месяцах
            payment_id: ID платежа (опционально)
            
        Returns:
            Словарь с информацией о созданной подписке
        """
        try:
            now = datetime.now(timezone.utc)
            end_date = now + timedelta(days=30 * months)
            
            # Используем транзакцию для обеспечения целостности
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Сначала деактивируем все существующие подписки
                    await conn.execute("""
                        UPDATE subscriptions 
                        SET is_active = FALSE, updated_at = NOW() 
                        WHERE user_id = $1 AND is_active = TRUE
                    """, user_id)
                    
                    # Создаем новую подписку
                    subscription_id = await conn.fetchval("""
                        INSERT INTO subscriptions 
                            (user_id, start_date, end_date, payment_id, is_active) 
                        VALUES 
                            ($1, $2, $3, $4, TRUE) 
                        RETURNING id
                    """, user_id, now, end_date, payment_id)
            
            logger.info(f"Создана новая подписка id={subscription_id} для пользователя {user_id}")
            
            return {
                "id": subscription_id,
                "user_id": user_id,
                "start_date": now.isoformat(),
                "end_date": end_date.isoformat(),
                "is_active": True,
                "payment_id": payment_id
            }
            
        except Exception as e:
            logger.error(f"Ошибка при создании подписки: {e}")
            raise 