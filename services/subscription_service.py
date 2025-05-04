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
        """Получает активную подписку пользователя"""
        # Сначала запросим подписки только с проверкой is_active
        query_active = """
        SELECT * FROM user_subscription 
        WHERE user_id = $1 AND is_active = TRUE
        ORDER BY end_date DESC
        LIMIT 1
        """
        
        active_subscription = await self.db.fetchrow(query_active, user_id)
        
        # Если нашли активную подписку по флагу, проверим её срок
        if active_subscription:
            # Просто выведем отладочную информацию
            print(f"[DEBUG] Найдена подписка с is_active=TRUE: ID={active_subscription['id']}, end_date={active_subscription['end_date']}")
            
            # Проверим, не истек ли срок
            current_time = await self.db.fetchval("SELECT NOW()")
            if active_subscription['end_date'] > current_time:
                print(f"[DEBUG] Подписка активна, end_date > NOW(): {active_subscription['end_date']} > {current_time}")
                return active_subscription
            else:
                print(f"[DEBUG] Подписка неактивна (истек срок), end_date <= NOW(): {active_subscription['end_date']} <= {current_time}")
                # Деактивируем подписку, так как она истекла
                update_query = """
                UPDATE user_subscription 
                SET is_active = FALSE, updated_at = NOW()
                WHERE id = $1
                """
                await self.db.execute(update_query, active_subscription['id'])
                return None
        
        # Если не нашли подписку с is_active=TRUE, проверим наличие подписок, у которых срок не истек
        # Это может исправить ситуацию, когда флаг is_active=FALSE, но срок подписки не истек
        query_valid = """
        SELECT * FROM user_subscription 
        WHERE user_id = $1 AND end_date > NOW()
        ORDER BY end_date DESC
        LIMIT 1
        """
        
        valid_subscription = await self.db.fetchrow(query_valid, user_id)
        
        if valid_subscription and not valid_subscription['is_active']:
            print(f"[DEBUG] Найдена подписка с end_date > NOW(), но is_active=FALSE: ID={valid_subscription['id']}")
            # Активируем подписку, так как срок не истек
            update_query = """
            UPDATE user_subscription 
            SET is_active = TRUE, updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """
            return await self.db.fetchrow(update_query, valid_subscription['id'])
        
        # Возвращаем valid_subscription (который может быть None)
        return valid_subscription
        
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