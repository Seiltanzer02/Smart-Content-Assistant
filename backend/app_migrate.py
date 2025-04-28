#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Простой скрипт для выполнения миграции пользовательской таблицы
"""

import os
import sys
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def apply_migration():
    """Применяет миграцию для создания таблицы app_users"""
    # Загружаем переменные окружения
    load_dotenv()
    
    # Получаем данные для подключения
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_KEY")
        return False
    
    try:
        # Инициализируем клиент Supabase
        supabase = create_client(supabase_url, supabase_key)
        logger.info("Supabase клиент успешно инициализирован")
        
        # Путь к файлу миграции
        migration_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                     "migrations", "02_create_users_table.sql")
        
        if not os.path.exists(migration_path):
            logger.error(f"Файл миграции не найден: {migration_path}")
            return False
        
        # Читаем SQL из файла
        with open(migration_path, 'r', encoding='utf-8') as file:
            sql = file.read()
        
        logger.info("Выполнение миграции для создания таблицы app_users")
        
        # Выполняем SQL запрос на создание таблицы
        response = supabase.rpc('exec_sql', {"query": sql}).execute()
        
        if hasattr(response, "error") and response.error:
            logger.error(f"Ошибка при выполнении миграции: {response.error}")
            return False
        
        logger.info("Миграция успешно выполнена")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграции: {e}")
        return False

if __name__ == "__main__":
    success = apply_migration()
    if success:
        logger.info("Таблица app_users успешно создана")
    else:
        logger.error("Не удалось создать таблицу app_users")
        sys.exit(1) 