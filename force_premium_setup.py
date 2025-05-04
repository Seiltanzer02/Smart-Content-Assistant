#!/usr/bin/env python3
"""
Скрипт для принудительной активации премиум-подписки для тестового пользователя.

Использование:
    python force_premium_setup.py <user_id>
    
Если user_id не указан, будет использоваться ID 427032240.
"""

import asyncio
import asyncpg
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Тестовый ID пользователя
TEST_USER_ID = 427032240

class PremiumSetup:
    def __init__(self, db_url=None, user_id=None):
        self.db_url = db_url or os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL не указан в переменных окружения")
        
        self.user_id = int(user_id) if user_id else TEST_USER_ID
        self.pool = None
    
    async def connect(self):
        """Подключение к базе данных"""
        try:
            self.pool = await asyncpg.create_pool(self.db_url)
            logger.info("Успешное подключение к базе данных")
        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            raise
    
    async def close(self):
        """Закрытие соединения с базой данных"""
        if self.pool:
            await self.pool.close()
            logger.info("Соединение с базой данных закрыто")
    
    async def check_current_status(self):
        """Проверка текущего статуса подписки"""
        try:
            query = """
            SELECT 
                id, user_id, start_date, end_date, payment_id, is_active, 
                created_at, updated_at
            FROM user_subscription
            WHERE user_id = $1
            ORDER BY end_date DESC
            """
            subscriptions = await self.pool.fetch(query, self.user_id)
            
            logger.info(f"Найдено {len(subscriptions)} записей о подписках для пользователя {self.user_id}")
            
            for sub in subscriptions:
                logger.info(f"ID: {sub['id']}, active: {sub['is_active']}, "
                           f"start: {sub['start_date']}, end: {sub['end_date']}")
            
            return subscriptions
        except Exception as e:
            logger.error(f"Ошибка при проверке подписок: {e}")
            raise
    
    async def force_premium(self, months=1):
        """Принудительная активация премиум-подписки"""
        try:
            # Деактивируем все существующие подписки
            deactivate_query = """
            UPDATE user_subscription
            SET is_active = FALSE, updated_at = NOW()
            WHERE user_id = $1
            """
            await self.pool.execute(deactivate_query, self.user_id)
            logger.info(f"Деактивированы все существующие подписки для пользователя {self.user_id}")
            
            # Создаем новую активную подписку
            now = datetime.now(timezone.utc)
            end_date = now + timedelta(days=30 * months)
            
            insert_query = """
            INSERT INTO user_subscription 
                (user_id, start_date, end_date, payment_id, is_active, created_at, updated_at)
            VALUES 
                ($1, $2, $3, $4, TRUE, NOW(), NOW())
            RETURNING id
            """
            payment_id = f"force_premium_{now.strftime('%Y%m%d%H%M%S')}"
            
            subscription_id = await self.pool.fetchval(
                insert_query, 
                self.user_id, 
                now, 
                end_date, 
                payment_id
            )
            
            logger.info(f"Создана новая премиум-подписка (ID: {subscription_id}) для пользователя {self.user_id}")
            logger.info(f"Срок действия: с {now.isoformat()} по {end_date.isoformat()}")
            
            return {
                "id": subscription_id,
                "user_id": self.user_id,
                "start_date": now,
                "end_date": end_date,
                "is_active": True,
                "payment_id": payment_id
            }
        except Exception as e:
            logger.error(f"Ошибка при создании премиум-подписки: {e}")
            raise

async def main():
    """Основная функция"""
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        user_id = str(TEST_USER_ID)
    
    try:
        logger.info(f"Запуск принудительной активации премиума для пользователя {user_id}")
        setup = PremiumSetup(user_id=user_id)
        
        await setup.connect()
        
        logger.info("Проверка текущего статуса подписки...")
        current_subscriptions = await setup.check_current_status()
        
        if current_subscriptions:
            # Проверяем, есть ли уже активная подписка
            now = datetime.now(timezone.utc)
            active_sub = next((s for s in current_subscriptions 
                              if s['is_active'] and s['end_date'] > now), None)
            
            if active_sub:
                logger.info(f"У пользователя уже есть активная подписка до {active_sub['end_date']}")
                choice = input("Продолжить и создать новую подписку? [y/N]: ")
                if choice.lower() != 'y':
                    logger.info("Операция отменена пользователем")
                    return
        
        # Запрашиваем срок подписки
        months_str = input("Введите срок подписки в месяцах [1]: ").strip() or "1"
        months = int(months_str)
        
        # Активируем премиум
        logger.info(f"Активация премиум-подписки на {months} месяц(ев)...")
        result = await setup.force_premium(months)
        
        logger.info(f"Премиум-подписка успешно активирована для пользователя {user_id}")
        logger.info(f"ID подписки: {result['id']}")
        logger.info(f"Срок действия: с {result['start_date'].isoformat()} по {result['end_date'].isoformat()}")
        
        # Проверяем результат
        logger.info("Проверка обновленного статуса...")
        await setup.check_current_status()
        
        await setup.close()
    except Exception as e:
        logger.error(f"Ошибка при выполнении скрипта: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 