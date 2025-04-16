#!/usr/bin/env python
"""
Скрипт для применения миграций к базе данных Supabase.
"""

import os
import sys
import time
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv(override=True)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

def apply_migrations():
    """Применяет SQL-миграции к базе данных."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        logger.error("Отсутствуют необходимые переменные окружения для подключения к Supabase")
        sys.exit(1)
    
    # Инициализация клиента Supabase
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info("Клиент Supabase успешно инициализирован")
    except Exception as e:
        logger.error(f"Ошибка инициализации клиента Supabase: {e}")
        sys.exit(1)
    
    # Путь к папке с миграциями
    migration_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migration")
    
    if not os.path.exists(migration_folder):
        logger.warning(f"Папка с миграциями не найдена: {migration_folder}")
        return
    
    # Получение списка SQL-файлов
    migration_files = sorted([
        f for f in os.listdir(migration_folder) 
        if f.endswith(".sql") and os.path.isfile(os.path.join(migration_folder, f))
    ])
    
    if not migration_files:
        logger.warning("SQL-файлы для миграции не найдены")
        return
    
    logger.info(f"Найдено {len(migration_files)} файлов миграции: {', '.join(migration_files)}")
    
    # Применение миграций
    for file_name in migration_files:
        file_path = os.path.join(migration_folder, file_name)
        logger.info(f"Применение миграции из файла: {file_name}")
        
        try:
            # Чтение SQL из файла
            with open(file_path, 'r', encoding='utf-8') as file:
                sql = file.read()
            
            # Выполнение SQL через Supabase
            result = supabase.rpc("pgfunction", {"sql": sql}).execute()
            
            if hasattr(result, 'error') and result.error:
                logger.error(f"Ошибка при выполнении миграции {file_name}: {result.error}")
            else:
                logger.info(f"Миграция {file_name} успешно применена")
        
        except Exception as e:
            logger.error(f"Ошибка при применении миграции {file_name}: {e}")
    
    logger.info("Применение миграций завершено")

if __name__ == "__main__":
    # Ждем несколько секунд для обеспечения готовности базы данных
    logger.info("Ожидание готовности базы данных...")
    time.sleep(5)
    
    # Применяем миграции
    apply_migrations() 