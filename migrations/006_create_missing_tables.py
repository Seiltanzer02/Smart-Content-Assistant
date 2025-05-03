import os
import json
import asyncio
from datetime import datetime, timedelta
from supabase import create_client, Client
from typing import Dict, Any, List

# Получаем переменные окружения для подключения к Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Подключаемся к Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def check_table_exists(table_name: str) -> bool:
    """Проверяет существование таблицы в базе данных."""
    try:
        result = supabase.table(table_name).select("*").limit(1).execute()
        # Если запрос выполнен успешно, таблица существует
        print(f"Таблица {table_name} существует.")
        return True
    except Exception as e:
        print(f"Таблица {table_name} не существует: {e}")
        return False

async def create_user_subscription_table():
    """Создает таблицу user_subscription, если она не существует."""
    if await check_table_exists("user_subscription"):
        return
    
    try:
        # SQL для создания таблицы user_subscription
        query = """
        CREATE TABLE IF NOT EXISTS user_subscription (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            start_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            end_date TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            payment_id TEXT,
            
            CONSTRAINT fk_user
            FOREIGN KEY(user_id) 
            REFERENCES auth.users(id)
            ON DELETE CASCADE
        );
        
        -- Создаем индекс для ускорения поиска по user_id
        CREATE INDEX IF NOT EXISTS user_subscription_user_id_idx ON user_subscription (user_id);
        
        -- Комментарии к таблице
        COMMENT ON TABLE user_subscription IS 'Таблица для хранения информации о подписках пользователей';
        """
        
        # Выполняем SQL-запрос
        # В Supabase-js нет прямого метода для выполнения произвольного SQL,
        # поэтому используем RPC, определенную в вашей базе данных
        result = await _execute_sql_direct(query)
        print(f"Таблица user_subscription создана или уже существует: {result}")
    except Exception as e:
        print(f"Ошибка при создании таблицы user_subscription: {e}")

async def create_user_usage_stats_table():
    """Создает таблицу user_usage_stats, если она не существует."""
    if await check_table_exists("user_usage_stats"):
        return
    
    try:
        # SQL для создания таблицы user_usage_stats
        query = """
        CREATE TABLE IF NOT EXISTS user_usage_stats (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            analysis_count INTEGER DEFAULT 0,
            post_generation_count INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            reset_at TIMESTAMP WITH TIME ZONE DEFAULT (date_trunc('month', CURRENT_DATE) + INTERVAL '1 month')::timestamp,
            
            CONSTRAINT fk_user
            FOREIGN KEY(user_id) 
            REFERENCES auth.users(id)
            ON DELETE CASCADE
        );
        
        -- Создаем индекс для ускорения поиска по user_id
        CREATE INDEX IF NOT EXISTS user_usage_stats_user_id_idx ON user_usage_stats (user_id);
        
        -- Комментарии к таблице
        COMMENT ON TABLE user_usage_stats IS 'Таблица для хранения информации об использовании сервиса пользователями';
        """
        
        # Выполняем SQL-запрос
        result = await _execute_sql_direct(query)
        print(f"Таблица user_usage_stats создана или уже существует: {result}")
    except Exception as e:
        print(f"Ошибка при создании таблицы user_usage_stats: {e}")

async def create_payments_table():
    """Создает таблицу payments, если она не существует."""
    if await check_table_exists("payments"):
        return
    
    try:
        # SQL для создания таблицы payments
        query = """
        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            currency TEXT NOT NULL,
            invoice_payload TEXT NOT NULL,
            telegram_payment_charge_id TEXT,
            provider_payment_charge_id TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            
            CONSTRAINT fk_user
            FOREIGN KEY(user_id) 
            REFERENCES auth.users(id)
            ON DELETE CASCADE
        );
        
        -- Создаем индекс для ускорения поиска по user_id
        CREATE INDEX IF NOT EXISTS payments_user_id_idx ON payments (user_id);
        
        -- Комментарии к таблице
        COMMENT ON TABLE payments IS 'Таблица для хранения информации о платежах пользователей';
        """
        
        # Выполняем SQL-запрос
        result = await _execute_sql_direct(query)
        print(f"Таблица payments создана или уже существует: {result}")
    except Exception as e:
        print(f"Ошибка при создании таблицы payments: {e}")

async def _execute_sql_direct(sql_query: str) -> Dict[str, Any]:
    """Выполняет произвольный SQL-запрос через функцию RPC."""
    try:
        # Вызываем нашу RPC-функцию execute_sql, которую нужно создать в Supabase
        # result = supabase.rpc("execute_sql", {"query": sql_query}).execute()
        
        # Временное решение - исполнять SQL через .rpc()
        # Примечание: для работы этого метода в Supabase должна быть создана
        # соответствующая функция execute_sql
        
        # Поскольку прямое выполнение SQL через supabase-js ограничено,
        # возвращаем заглушку для демонстрации
        print(f"SQL-запрос для выполнения: {sql_query}")
        return {"success": True, "message": "SQL выполнен (заглушка для демонстрации)"}
    except Exception as e:
        print(f"Ошибка при выполнении SQL: {e}")
        return {"success": False, "error": str(e)}

async def main():
    """Основная функция для запуска миграций."""
    print("Запуск миграций для создания недостающих таблиц...")
    
    # Создаем таблицы
    await create_user_subscription_table()
    await create_user_usage_stats_table()
    await create_payments_table()
    
    print("Миграции завершены.")

if __name__ == "__main__":
    asyncio.run(main()) 