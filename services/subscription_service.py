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
        """Получает активную подписку пользователя (с is_active = TRUE и end_date > NOW())"""
        query = """
        SELECT * FROM user_subscription 
        WHERE user_id = $1 AND is_active = TRUE AND end_date > NOW()
        ORDER BY end_date DESC
        LIMIT 1
        """
        
        subscription = await self.db.fetchrow(query, user_id)
        return subscription
        
    async def create_or_update_subscription(self, user_id: int, payment_id: str):
        """Создает или продлевает подписку пользователя.

        Если подписки нет или она неактивна/истекла, создает новую.
        Если есть активная подписка, продлевает её на месяц от текущей даты окончания.
        """
        existing_subscription = await self.get_subscription(user_id)
        now = datetime.utcnow()

        if existing_subscription:
            # Продлеваем существующую активную подписку
            current_end_date = existing_subscription["end_date"]
            # Если подписка истекает в будущем, продлеваем от даты окончания
            start_from = max(now, current_end_date) 
            new_end_date = start_from + relativedelta(months=SUBSCRIPTION_DURATION_MONTHS)
            query = """
            UPDATE user_subscription
            SET end_date = $1, is_active = TRUE, updated_at = NOW(), payment_id = $2
            WHERE id = $3
            RETURNING *
            """
            subscription = await self.db.fetchrow(query, new_end_date, payment_id, existing_subscription["id"])
        else:
            # Создаем новую подписку
            new_end_date = now + relativedelta(months=SUBSCRIPTION_DURATION_MONTHS)
            query = """
            INSERT INTO user_subscription 
            (user_id, end_date, payment_id, is_active, start_date)
            VALUES ($1, $2, $3, TRUE, $4)
            RETURNING *
            """
            subscription = await self.db.fetchrow(query, user_id, new_end_date, payment_id, now)

        return subscription

    async def has_active_subscription(self, user_id: int):
        """Проверяет, есть ли у пользователя активная подписка"""
        subscription = await self.get_subscription(user_id)
        return subscription is not None
        
    async def can_analyze_channel(self, user_id: int):
        """Проверяет, может ли пользователь анализировать канал (учитывает подписку)"""
        if await self.has_active_subscription(user_id):
            return True
            
        usage = await self.get_user_usage(user_id)
        return usage["analysis_count"] < FREE_ANALYSIS_LIMIT
        
    async def can_generate_post(self, user_id: int):
        """Проверяет, может ли пользователь генерировать посты (учитывает подписку)"""
        if await self.has_active_subscription(user_id):
            return True
            
        usage = await self.get_user_usage(user_id)
        return usage["post_generation_count"] < FREE_POST_LIMIT 