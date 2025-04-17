#!/usr/bin/env python
"""
Скрипт для прямого добавления недостающих столбцов в таблицы через клиент Supabase.
Используется как обходной путь, если стандартные миграции не работают.
"""

import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv(override=True)

def init_supabase() -> Client:
    """Инициализация клиента Supabase"""
    try:
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
            return None
        
        logger.info(f"Подключение к Supabase: {supabase_url}")
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        logger.error(f"Ошибка при инициализации Supabase: {str(e)}")
        return None

def add_columns_directly(supabase: Client):
    """Добавление столбцов напрямую через Supabase клиент"""
    try:
        logger.info("Добавление столбцов напрямую через клиент Supabase...")
        
        # Проверка подключения к базе
        try:
            test = supabase.table("suggested_ideas").select("id").limit(1).execute()
            logger.info("Подключение к Supabase работает")
        except Exception as e:
            logger.error(f"Ошибка подключения к Supabase: {str(e)}")
            return False
        
        # Добавляем столбец author_url в saved_images
        try:
            logger.info("Добавление столбца author_url в таблицу saved_images")
            query = """
            ALTER TABLE IF EXISTS saved_images 
            ADD COLUMN IF NOT EXISTS author_url TEXT;
            
            CREATE INDEX IF NOT EXISTS idx_saved_images_author_url 
            ON saved_images(author_url);
            """
            
            # Выполнение через RPC
            result = supabase.rpc("exec_sql", {"query": query}).execute()
            logger.info("Столбец author_url успешно добавлен в таблицу saved_images")
        except Exception as e:
            logger.warning(f"Ошибка при добавлении столбца author_url: {str(e)}")
            logger.info("Возможно, столбец уже существует")
        
        # Добавляем столбец analyzed_posts_count в channel_analysis
        try:
            logger.info("Добавление столбца analyzed_posts_count в таблицу channel_analysis")
            query = """
            ALTER TABLE IF EXISTS channel_analysis 
            ADD COLUMN IF NOT EXISTS analyzed_posts_count INTEGER DEFAULT 0;
            
            CREATE INDEX IF NOT EXISTS idx_channel_analysis_analyzed_posts_count 
            ON channel_analysis(analyzed_posts_count);
            """
            
            # Выполнение через RPC
            result = supabase.rpc("exec_sql", {"query": query}).execute()
            logger.info("Столбец analyzed_posts_count успешно добавлен в таблицу channel_analysis")
        except Exception as e:
            logger.warning(f"Ошибка при добавлении столбца analyzed_posts_count: {str(e)}")
            logger.info("Возможно, столбец уже существует")
        
        return True
    except Exception as e:
        logger.error(f"Общая ошибка при добавлении столбцов: {str(e)}")
        return False

def main():
    """Основная функция для запуска обновления таблиц."""
    logger.info("Запуск создания недостающих столбцов...")
    
    # Инициализация клиента Supabase
    supabase = init_supabase()
    if not supabase:
        logger.error("Не удалось инициализировать клиент Supabase")
        return False
    
    # Добавление столбцов напрямую
    if add_columns_directly(supabase):
        logger.info("Столбцы успешно добавлены или уже существуют")
    else:
        logger.error("Ошибка при добавлении столбцов")
    
    return True

if __name__ == "__main__":
    main() 