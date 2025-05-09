#!/usr/bin/env python3
"""
Скрипт для запуска миграции по созданию таблицы user_settings
"""

import os
import asyncio
import asyncpg
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

async def run_migration():
    """Выполняет миграцию для создания таблицы user_settings"""
    # Получаем строку подключения к базе данных
    db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print("Ошибка: Не найдена строка подключения к базе данных.")
        print("Убедитесь, что переменная окружения DATABASE_URL или SUPABASE_DB_URL задана.")
        return
    
    # Путь к файлу миграции
    migration_file = os.path.join(os.path.dirname(__file__), "migrations", "user_settings.sql")
    
    if not os.path.exists(migration_file):
        print(f"Ошибка: Файл миграции не найден: {migration_file}")
        return
    
    # Чтение файла с SQL-скриптом
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    # Подключение к базе данных и выполнение миграции
    try:
        print(f"Подключение к базе данных: {db_url}")
        conn = await asyncpg.connect(db_url)
        
        print("Начало выполнения миграции...")
        await conn.execute(sql_script)
        print("Миграция успешно выполнена.")
        
        # Проверяем, что таблица создана
        check_result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'user_settings'
            );
        """)
        
        if check_result:
            print("Таблица user_settings успешно создана/обновлена.")
        else:
            print("Ошибка: Таблица user_settings не найдена после миграции.")
        
        await conn.close()
    except Exception as e:
        print(f"Ошибка при выполнении миграции: {e}")

if __name__ == "__main__":
    # Запускаем асинхронную функцию
    asyncio.run(run_migration()) 