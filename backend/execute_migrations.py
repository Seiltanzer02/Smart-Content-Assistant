#!/usr/bin/env python
"""
Скрипт для выполнения миграций базы данных в Supabase
"""

import os
import sys
from logger_config import setup_logger
from dotenv import load_dotenv

# Настройка логгера
logger = setup_logger(__name__, "logs/migrations.log")

# Загрузка переменных окружения
load_dotenv()

# Путь к директории с миграциями 
MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                               "backend", "migrations")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.migrate import init_supabase, check_migrations_table, create_exec_sql_function, run_migrations

def main():
    """
    Основная функция для выполнения миграций
    """
    logger.info("Начало выполнения миграций")
    
    try:
        # Инициализация клиента Supabase
        supabase = init_supabase()
        if not supabase:
            logger.error("Не удалось инициализировать клиент Supabase")
            return False
        
        # Проверка и создание таблицы миграций
        if not check_migrations_table(supabase):
            logger.error("Не удалось создать таблицу миграций")
            return False
        
        # Создание функции для выполнения SQL
        if not create_exec_sql_function(supabase):
            logger.error("Не удалось создать функцию для выполнения SQL")
            return False
        
        # Запуск миграций
        success = run_migrations(supabase)
        if not success:
            logger.error("Выполнение миграций завершилось с ошибками")
            return False
        
        logger.info("Миграции успешно выполнены")
        return True
        
    except Exception as e:
        logger.exception(f"Произошла ошибка при выполнении миграций: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 