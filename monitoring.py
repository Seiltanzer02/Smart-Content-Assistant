#!/usr/bin/env python3
"""
Скрипт для мониторинга и проверки статуса системы подписок.
Проверяет соединение с базой данных, статус API и общее состояние системы.
"""

import os
import sys
import json
import asyncio
import logging
import asyncpg
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self, db_url=None, api_url=None, test_user_id=None):
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self.api_url = api_url or os.getenv("API_URL") or "http://localhost:8000"
        self.test_user_id = test_user_id or os.getenv("TEST_USER_ID") or "427032240"  # ID пользователя со скриншота
        
        if not self.db_url:
            raise ValueError("DATABASE_URL не указан в переменных окружения")
            
        self.pool = None
        
    async def connect_db(self):
        """Устанавливает соединение с базой данных"""
        try:
            self.pool = await asyncpg.create_pool(self.db_url)
            logger.info("Успешное подключение к базе данных")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            return False
            
    async def close_db(self):
        """Закрывает соединение с базой данных"""
        if self.pool:
            await self.pool.close()
            logger.info("Соединение с базой данных закрыто")
            
    async def check_db_connection(self):
        """Проверяет соединение с базой данных"""
        if not self.pool:
            await self.connect_db()
            
        try:
            # Проверяем, что соединение работает
            server_time = await self.pool.fetchval("SELECT NOW()")
            return {
                "status": "ok",
                "server_time": server_time.isoformat() if server_time else None,
                "message": "Соединение с базой данных работает"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Ошибка соединения с базой данных: {str(e)}"
            }
            
    async def check_subscriptions_table(self):
        """Проверяет таблицу subscriptions в базе данных"""
        if not self.pool:
            await self.connect_db()
            
        try:
            # Проверяем наличие таблицы subscriptions и ее структуру
            table_exists = await self.pool.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'subscriptions'
                )
            """)
            
            if not table_exists:
                return {
                    "status": "error",
                    "message": "Таблица subscriptions не существует"
                }
                
            # Проверяем количество записей
            count = await self.pool.fetchval("SELECT COUNT(*) FROM subscriptions")
            
            # Проверяем схему таблицы
            columns = await self.pool.fetch("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'subscriptions'
            """)
            
            columns_info = [{"name": col["column_name"], "type": col["data_type"]} for col in columns]
            
            # Проверяем необходимые индексы
            indexes = await self.pool.fetch("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'subscriptions'
            """)
            
            indexes_info = [{"name": idx["indexname"], "definition": idx["indexdef"]} for idx in indexes]
            
            return {
                "status": "ok",
                "table_exists": True,
                "records_count": count,
                "columns": columns_info,
                "indexes": indexes_info,
                "message": f"Таблица subscriptions существует и содержит {count} записей"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Ошибка при проверке таблицы subscriptions: {str(e)}"
            }
            
    async def check_active_subscriptions(self):
        """Проверяет активные подписки"""
        if not self.pool:
            await self.connect_db()
            
        try:
            # Проверяем количество активных подписок
            now = datetime.now(timezone.utc)
            active_count = await self.pool.fetchval("""
                SELECT COUNT(*) 
                FROM subscriptions 
                WHERE is_active = TRUE AND end_date > $1
            """, now)
            
            # Получаем примеры активных подписок
            active_subscriptions = await self.pool.fetch("""
                SELECT id, user_id, start_date, end_date, payment_id, is_active, created_at, updated_at
                FROM subscriptions 
                WHERE is_active = TRUE AND end_date > $1
                ORDER BY end_date DESC
                LIMIT 5
            """, now)
            
            examples = []
            for sub in active_subscriptions:
                examples.append({
                    "id": sub["id"],
                    "user_id": sub["user_id"],
                    "start_date": sub["start_date"].isoformat() if sub["start_date"] else None,
                    "end_date": sub["end_date"].isoformat() if sub["end_date"] else None,
                    "is_active": sub["is_active"],
                    "time_left_days": (sub["end_date"] - now).days if sub["end_date"] else None
                })
            
            return {
                "status": "ok",
                "active_count": active_count,
                "examples": examples,
                "current_time": now.isoformat(),
                "message": f"Найдено {active_count} активных подписок"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Ошибка при проверке активных подписок: {str(e)}"
            }
            
    def check_api_endpoint(self, endpoint: str, params: Optional[Dict[str, Any]] = None):
        """Проверяет API-эндпоинт"""
        try:
            url = f"{self.api_url}{endpoint}"
            if params:
                url += "?" + "&".join([f"{k}={v}" for k, v in params.items()])
                
            # Добавляем заголовки для предотвращения кэширования
            headers = {
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "x-telegram-user-id": self.test_user_id
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            try:
                data = response.json()
            except:
                data = {"html": response.text[:500] + "..." if len(response.text) > 500 else response.text}
                
            return {
                "status": "ok" if response.status_code == 200 else "error",
                "status_code": response.status_code,
                "response": data,
                "message": f"API-запрос к {endpoint} выполнен со статусом {response.status_code}"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Ошибка при проверке API-эндпоинта {endpoint}: {str(e)}"
            }
    
    async def check_specific_user(self, user_id: str):
        """Проверяет данные конкретного пользователя в БД"""
        if not self.pool:
            await self.connect_db()
            
        try:
            # Получаем подписки пользователя
            subscriptions = await self.pool.fetch("""
                SELECT id, user_id, start_date, end_date, payment_id, is_active, created_at, updated_at
                FROM subscriptions
                WHERE user_id = $1
                ORDER BY end_date DESC
            """, int(user_id))
            
            now = datetime.now(timezone.utc)
            
            results = []
            for sub in subscriptions:
                is_active_by_date = sub["end_date"] > now if sub["end_date"] else False
                results.append({
                    "id": sub["id"],
                    "user_id": sub["user_id"],
                    "start_date": sub["start_date"].isoformat() if sub["start_date"] else None,
                    "end_date": sub["end_date"].isoformat() if sub["end_date"] else None,
                    "payment_id": sub["payment_id"],
                    "is_active_in_db": sub["is_active"],
                    "is_active_by_date": is_active_by_date,
                    "is_truly_active": sub["is_active"] and is_active_by_date,
                    "created_at": sub["created_at"].isoformat() if sub["created_at"] else None,
                    "updated_at": sub["updated_at"].isoformat() if sub["updated_at"] else None,
                    "time_left_days": (sub["end_date"] - now).days if sub["end_date"] else None
                })
            
            # Проверяем данные пользователя через API
            api_result = self.check_api_endpoint("/subscription/status", {"user_id": user_id})
            
            return {
                "status": "ok",
                "user_id": user_id,
                "subscriptions_in_db": results,
                "subscriptions_count": len(results),
                "has_active_subscription": any(sub["is_truly_active"] for sub in results),
                "api_check": api_result,
                "current_time": now.isoformat(),
                "message": f"Проверка пользователя {user_id} выполнена, найдено {len(results)} подписок"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Ошибка при проверке пользователя {user_id}: {str(e)}"
            }
    
    async def run_full_check(self):
        """Запускает полную проверку системы"""
        results = {}
        
        # Проверка соединения с БД
        results["db_connection"] = await self.check_db_connection()
        
        # Проверка таблицы подписок
        results["subscriptions_table"] = await self.check_subscriptions_table()
        
        # Проверка активных подписок
        results["active_subscriptions"] = await self.check_active_subscriptions()
        
        # Проверка API
        results["api_status"] = self.check_api_endpoint("/subscription/status", {"user_id": self.test_user_id})
        results["api_direct_check"] = self.check_api_endpoint("/direct_premium_check", {"user_id": self.test_user_id})
        
        # Проверка тестового пользователя
        results["test_user_check"] = await self.check_specific_user(self.test_user_id)
        
        # Формирование общего статуса
        issues = []
        for key, value in results.items():
            if value.get("status") == "error":
                issues.append(f"{key}: {value.get('message')}")
                
        if issues:
            results["overall_status"] = {
                "status": "error",
                "issues": issues,
                "message": f"Обнаружены проблемы: {len(issues)}"
            }
        else:
            results["overall_status"] = {
                "status": "ok",
                "message": "Все системы работают нормально"
            }
            
        return results

async def main():
    """Основная функция скрипта"""
    # Проверка наличия аргументов
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
        check_type = "user"
    else:
        user_id = None
        check_type = "full"
        
    try:
        monitor = SystemMonitor()
        
        if check_type == "user":
            result = await monitor.check_specific_user(user_id)
        else:
            result = await monitor.run_full_check()
            
        # Вывод результата
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Закрытие соединения
        await monitor.close_db()
        
        # Выход с кодом ошибки, если есть проблемы
        if check_type == "full" and result["overall_status"]["status"] == "error":
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Ошибка при выполнении проверки: {e}")
        print(json.dumps({
            "status": "error",
            "message": f"Критическая ошибка: {str(e)}"
        }, indent=2, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 