#!/usr/bin/env python
"""
Скрипт для применения миграций к базе данных Supabase.
"""

import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client
import glob
import time

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

def init_supabase():
    """Инициализация клиента Supabase"""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not supabase_key:
        logger.error("SUPABASE_URL или SUPABASE_ANON_KEY не найдены в переменных окружения")
        return None
    
    try:
        logger.info(f"Подключение к Supabase: {supabase_url}")
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        logger.error(f"Ошибка при инициализации Supabase: {e}")
        return None

def run_migrations():
    """Запуск SQL миграций"""
    supabase = init_supabase()
    if not supabase:
        logger.error("Невозможно запустить миграции без клиента Supabase")
        return False
    
    migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")
    logger.info(f"Поиск миграций в директории: {migrations_dir}")
    
    # Получаем список SQL файлов и сортируем их по имени
    migration_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
    logger.info(f"Найдено миграций: {len(migration_files)}")
    
    for file_path in migration_files:
        file_name = os.path.basename(file_path)
        logger.info(f"Применение миграции: {file_name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Выполняем SQL запрос через REST API
            response = supabase.table("_migrations").insert({
                "name": file_name,
                "executed_at": int(time.time())
            }).execute()
            
            # Выполнение SQL запросов напрямую через строку
            result = supabase.postgrest.schema('public').rpc('exec_sql', {'query': sql_content}).execute()
            logger.info(f"Миграция {file_name} успешно применена")
                
        except Exception as e:
            logger.error(f"Ошибка при применении миграции {file_name}: {e}")
            return False
    
    return True

if __name__ == "__main__":
    logger.info("Запуск миграций...")
    if run_migrations():
        logger.info("Все миграции успешно применены!")
    else:
        logger.error("Миграции не были применены из-за ошибок")
        exit(1) 