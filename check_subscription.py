#!/usr/bin/env python3
"""
Диагностический скрипт для проверки статуса подписки пользователя в базе данных.
Использование: python check_subscription.py <user_id>
"""

import os
import sys
import json
import asyncio
import logging
import asyncpg
from datetime import datetime, timezone

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SubscriptionChecker:
    def __init__(self, db_url=None):
        self.db_url = db_url or os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL не указан в переменных окружения")
        self.pool = None
        
    async def connect(self):
        """Устанавливает соединение с базой данных"""
        try:
            self.pool = await asyncpg.create_pool(self.db_url)
            logger.info("Успешное подключение к базе данных")
        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            raise
    
    async def check_user_subscription(self, user_id):
        """Проверяет статус подписки пользователя"""
        if not self.pool:
            await self.connect()
            
        try:
            # Получаем информацию о подписке
            query = """
            SELECT id, user_id, start_date, end_date, payment_id, is_active, created_at, updated_at
            FROM subscriptions
            WHERE user_id = $1
            ORDER BY end_date DESC
            """
            subscriptions = await self.pool.fetch(query, int(user_id))
            
            if not subscriptions:
                logger.info(f"Пользователь {user_id} не имеет записей о подписках в базе данных")
                return {
                    "status": "not_found",
                    "message": f"Пользователь {user_id} не имеет записей о подписках в базе данных",
                    "subscriptions": []
                }
            
            # Форматируем результаты
            result = []
            for sub in subscriptions:
                now = datetime.now(timezone.utc)
                is_active = sub['is_active'] and sub['end_date'] > now
                
                subscription_info = {
                    "id": sub['id'],
                    "user_id": sub['user_id'],
                    "start_date": sub['start_date'].isoformat() if sub['start_date'] else None,
                    "end_date": sub['end_date'].isoformat() if sub['end_date'] else None,
                    "payment_id": sub['payment_id'],
                    "db_is_active": sub['is_active'],
                    "calculated_is_active": is_active,
                    "created_at": sub['created_at'].isoformat() if sub['created_at'] else None,
                    "updated_at": sub['updated_at'].isoformat() if sub['updated_at'] else None,
                    "time_left_days": (sub['end_date'] - now).days if sub['end_date'] else None
                }
                result.append(subscription_info)
            
            # Проверка наличия активной подписки
            active_subscription = next((s for s in result if s["calculated_is_active"]), None)
            status = "active" if active_subscription else "expired"
            
            return {
                "status": status,
                "message": f"Пользователь {user_id} имеет {'активную' if status == 'active' else 'истекшую'} подписку",
                "subscriptions": result,
                "active_subscription": active_subscription
            }
                
        except Exception as e:
            logger.error(f"Ошибка при проверке подписки: {e}")
            return {
                "status": "error",
                "message": f"Ошибка при проверке подписки: {str(e)}",
                "subscriptions": []
            }
    
    async def close(self):
        """Закрывает соединение с базой данных"""
        if self.pool:
            await self.pool.close()
            logger.info("Соединение с базой данных закрыто")


async def main():
    """Основная функция скрипта"""
    if len(sys.argv) < 2:
        print("Использование: python check_subscription.py <user_id>")
        return
    
    user_id = sys.argv[1]
    
    try:
        checker = SubscriptionChecker()
        result = await checker.check_user_subscription(user_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        await checker.close()
    except Exception as e:
        logger.error(f"Ошибка в работе скрипта: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 