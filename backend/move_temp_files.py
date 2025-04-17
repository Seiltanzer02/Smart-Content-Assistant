#!/usr/bin/env python
"""
Скрипт для прямого добавления недостающих столбцов в таблицы
"""

import os
import logging
import requests
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

def add_columns():
    # Добавление колонок и индексов для хранения URL авторов
    try:
        # Добавление колонки author_url
        client.table('posts').insert({"id": "00000000-0000-0000-0000-000000000000", "author_url": "test"}).execute()
        print("Column 'author_url' already exists")
    except Exception as e:
        if "column \"author_url\" of relation \"posts\" does not exist" in str(e):
            try:
                # Добавляем колонку отдельным запросом
                client.query("ALTER TABLE posts ADD COLUMN author_url TEXT").execute()
                print("Added 'author_url' column to 'posts' table")
                
                # Создаем индекс отдельным запросом
                client.query("CREATE INDEX idx_posts_author_url ON posts (author_url)").execute()
                print("Created index on 'author_url' column")
            except Exception as e2:
                print(f"Error adding author_url column or index: {str(e2)}")
        else:
            print(f"Unknown error: {str(e)}")
    
    # Аналогично для других колонок, которые нужно добавить
    try:
        # Проверка существования колонки prompt_id
        client.table('posts').insert({"id": "00000000-0000-0000-0000-000000000000", "prompt_id": "test"}).execute()
        print("Column 'prompt_id' already exists")
    except Exception as e:
        if "column \"prompt_id\" of relation \"posts\" does not exist" in str(e):
            try:
                # Добавляем колонку отдельным запросом
                client.query("ALTER TABLE posts ADD COLUMN prompt_id TEXT").execute()
                print("Added 'prompt_id' column to 'posts' table")
                
                # Создаем индекс отдельным запросом
                client.query("CREATE INDEX idx_posts_prompt_id ON posts (prompt_id)").execute()
                print("Created index on 'prompt_id' column")
            except Exception as e2:
                print(f"Error adding prompt_id column or index: {str(e2)}")
        else:
            print(f"Unknown error: {str(e)}")

def add_missing_columns() -> bool:
    """Добавление недостающих столбцов напрямую через клиент Supabase"""
    logger.info("Добавление столбцов напрямую через клиент Supabase...")
    
    # Инициализация клиента Supabase
    supabase = init_supabase()
    if not supabase:
        logger.error("Не удалось инициализировать клиент Supabase")
        return False
    
    # Проверка подключения к Supabase
    try:
        result = supabase.table("suggested_ideas").select("id").limit(1).execute()
        logger.info("Подключение к Supabase работает")
    except Exception as e:
        logger.error(f"Ошибка при подключении к Supabase: {str(e)}")
        return False
    
    # Добавление столбца author_url в таблицу saved_images
    logger.info("Добавление столбца author_url в таблицу saved_images")
    try:
        # Выполняем каждую команду по отдельности
        # Добавление столбца
        alter_sql = """
        ALTER TABLE IF EXISTS saved_images 
        ADD COLUMN IF NOT EXISTS author_url TEXT
        """
        
        result = supabase.rpc("exec_sql_array_json", {"query": alter_sql}).execute()
        
        # Создание индекса
        index_sql = """
        CREATE INDEX IF NOT EXISTS idx_saved_images_author_url 
        ON saved_images(author_url)
        """
        
        result = supabase.rpc("exec_sql_array_json", {"query": index_sql}).execute()
        
        logger.info("Столбец author_url успешно добавлен в таблицу saved_images")
    except Exception as e:
        logger.error(f"Ошибка при добавлении столбца author_url: {str(e)}")
        # Пробуем добавить столбец напрямую через REST API
        try:
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_ANON_KEY')
            
            url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json"
            headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json"
            }
            
            # Выполняем команды по отдельности
            commands = [
                """ALTER TABLE IF EXISTS saved_images ADD COLUMN IF NOT EXISTS author_url TEXT""",
                """CREATE INDEX IF NOT EXISTS idx_saved_images_author_url ON saved_images(author_url)"""
            ]
            
            for cmd in commands:
                response = requests.post(url, json={"query": cmd}, headers=headers)
                if response.status_code in [200, 204]:
                    logger.info(f"Команда выполнена успешно: {cmd[:50]}...")
                else:
                    logger.warning(f"Ошибка при выполнении команды: {cmd[:50]}... - {response.status_code} - {response.text}")
        except Exception as e2:
            logger.error(f"Ошибка при альтернативном добавлении столбца author_url: {str(e2)}")
    
    # Добавление столбца analyzed_posts_count в таблицу channel_analysis
    logger.info("Добавление столбца analyzed_posts_count в таблицу channel_analysis")
    try:
        # Выполняем каждую команду по отдельности
        # Добавление столбца
        alter_sql = """
        ALTER TABLE IF EXISTS channel_analysis 
        ADD COLUMN IF NOT EXISTS analyzed_posts_count INTEGER DEFAULT 0
        """
        
        result = supabase.rpc("exec_sql_array_json", {"query": alter_sql}).execute()
        
        # Создание индекса
        index_sql = """
        CREATE INDEX IF NOT EXISTS idx_channel_analysis_analyzed_posts_count 
        ON channel_analysis(analyzed_posts_count)
        """
        
        result = supabase.rpc("exec_sql_array_json", {"query": index_sql}).execute()
        
        logger.info("Столбец analyzed_posts_count успешно добавлен в таблицу channel_analysis")
    except Exception as e:
        logger.error(f"Ошибка при добавлении столбца analyzed_posts_count: {str(e)}")
        # Пробуем добавить столбец напрямую через REST API
        try:
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_ANON_KEY')
            
            url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json"
            headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json"
            }
            
            # Выполняем команды по отдельности
            commands = [
                """ALTER TABLE IF EXISTS channel_analysis ADD COLUMN IF NOT EXISTS analyzed_posts_count INTEGER DEFAULT 0""",
                """CREATE INDEX IF NOT EXISTS idx_channel_analysis_analyzed_posts_count ON channel_analysis(analyzed_posts_count)"""
            ]
            
            for cmd in commands:
                response = requests.post(url, json={"query": cmd}, headers=headers)
                if response.status_code in [200, 204]:
                    logger.info(f"Команда выполнена успешно: {cmd[:50]}...")
                else:
                    logger.warning(f"Ошибка при выполнении команды: {cmd[:50]}... - {response.status_code} - {response.text}")
        except Exception as e2:
            logger.error(f"Ошибка при альтернативном добавлении столбца analyzed_posts_count: {str(e2)}")
    
    logger.info("Столбцы успешно добавлены или уже существуют")
    return True

def main():
    """Главная функция скрипта"""
    logger.info("Запуск создания недостающих столбцов...")
    if add_missing_columns():
        logger.info("Добавление столбцов выполнено успешно")
    else:
        logger.error("Не удалось добавить столбцы")

if __name__ == "__main__":
    main() 