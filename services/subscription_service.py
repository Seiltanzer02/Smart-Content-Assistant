from datetime import datetime, timedelta
import asyncpg
from dateutil.relativedelta import relativedelta
from common.db_service import DBService

FREE_ANALYSIS_LIMIT = 2
FREE_POST_LIMIT = 2
SUBSCRIPTION_PRICE = 70  # в Stars
SUBSCRIPTION_DURATION_MONTHS = 1

class SubscriptionService:
    def __init__(self, pool: asyncpg.Pool):
        self.db = DBService(pool)
        
    async def get_user_usage(self, user_id: int):
        """Получает статистику использования бесплатных функций"""
        query = """
        SELECT * FROM user_usage_stats WHERE user_id = $1
        """
        
        stats = await self.db.fetchrow(query, user_id)
        
        if not stats:
            # Если записи нет, создаем новую
            query = """
            INSERT INTO user_usage_stats (user_id, analysis_count, post_generation_count)
            VALUES ($1, 0, 0)
            RETURNING *
            """
            stats = await self.db.fetchrow(query, user_id)
            
        return stats
        
    async def increment_analysis_usage(self, user_id: int):
        """Увеличивает счетчик использования анализа"""
        query = """
        UPDATE user_usage_stats
        SET analysis_count = analysis_count + 1, updated_at = NOW()
        WHERE user_id = $1
        RETURNING *
        """
        
        stats = await self.db.fetchrow(query, user_id)
        
        if not stats:
            # Если записи нет, создаем новую
            stats = await self.get_user_usage(user_id)
            query = """
            UPDATE user_usage_stats
            SET analysis_count = analysis_count + 1, updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """
            stats = await self.db.fetchrow(query, user_id)
            
        return stats
        
    async def increment_post_usage(self, user_id: int):
        """Увеличивает счетчик использования генерации постов"""
        query = """
        UPDATE user_usage_stats
        SET post_generation_count = post_generation_count + 1, updated_at = NOW()
        WHERE user_id = $1
        RETURNING *
        """
        
        stats = await self.db.fetchrow(query, user_id)
        
        if not stats:
            # Если записи нет, создаем новую
            stats = await self.get_user_usage(user_id)
            query = """
            UPDATE user_usage_stats
            SET post_generation_count = post_generation_count + 1, updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """
            stats = await self.db.fetchrow(query, user_id)
            
        return stats
        
    async def get_subscription(self, user_id: int):
        """Получает активную подписку пользователя (упрощенная версия)"""
        # Прямой запрос на активную подписку
        query = """
        SELECT * FROM user_subscription 
        WHERE user_id = $1 AND is_active = TRUE AND end_date > NOW()
        ORDER BY end_date DESC
        LIMIT 1
        """
        try:
            # Используем DBService, который теперь должен работать с asyncpg pool
        subscription = await self.db.fetchrow(query, user_id)
            if subscription:
                print(f"[DEBUG SubService] Найдена активная подписка для {user_id}: ID={subscription['id']}, end_date={subscription['end_date']}")
            else:
                print(f"[DEBUG SubService] Активная подписка для {user_id} не найдена.")
        return subscription
        except Exception as e:
            # Логируем ошибку, но не прерываем работу полностью, просто возвращаем None
            print(f"[ERROR SubService] Ошибка при получении подписки для {user_id}: {e}")
            # Возможно, стоит добавить более детальное логирование
            # import traceback
            # print(traceback.format_exc())
            return None
        
    async def create_subscription(self, user_id: int, payment_id: str = None):
        """Создает новую подписку"""
        end_date = datetime.now() + relativedelta(months=SUBSCRIPTION_DURATION_MONTHS)
        
        query = """
        INSERT INTO user_subscription 
        (user_id, end_date, payment_id)
        VALUES ($1, $2, $3)
        RETURNING *
        """
        
        subscription = await self.db.fetchrow(query, user_id, end_date, payment_id)
        return subscription
        
    async def has_active_subscription(self, user_id: int):
        """Проверяет, есть ли у пользователя активная подписка"""
        subscription = await self.get_subscription(user_id)
        return subscription is not None
        
    async def can_analyze_channel(self, user_id: int):
        """Проверяет, может ли пользователь анализировать канал"""
        # Проверяем наличие подписки
        has_subscription = await self.has_active_subscription(user_id)
        if has_subscription:
            return True # Если подписка есть, всегда разрешаем
            
        # Если подписки нет, проверяем использование бесплатного лимита
        usage = await self.get_user_usage(user_id)
        return usage["analysis_count"] < FREE_ANALYSIS_LIMIT
        
    async def can_generate_post(self, user_id: int):
        """Проверяет, может ли пользователь генерировать посты"""
        # Проверяем наличие подписки
        has_subscription = await self.has_active_subscription(user_id)
        if has_subscription:
            return True # Если подписка есть, всегда разрешаем
            
        # Если подписки нет, проверяем использование бесплатного лимита
        usage = await self.get_user_usage(user_id)
        return usage["post_generation_count"] < FREE_POST_LIMIT 