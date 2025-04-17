#!/usr/bin/env python
"""
Скрипт для прямого добавления недостающих столбцов в таблицы через API Supabase.
Используется как обходной путь, если стандартные миграции не работают.
"""

import os
import requests
import logging
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv(override=True)

def check_column_exists(table_name, column_name):
    """Проверка наличия столбца в таблице."""
    supabase_url = os.getenv('SUPABASE_URL')
    api_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not api_key:
        logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
        return False
    
    # SQL запрос для проверки существования столбца
    sql_query = f"""
    SELECT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = '{table_name}' 
        AND column_name = '{column_name}'
    ) as exists;
    """
    
    # Выполнение запроса через SQL REST API
    sql_url = f"{supabase_url}/rest/v1/sql"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        response = requests.post(sql_url, json={"query": sql_query}, headers=headers)
        
        if response.status_code == 200:
            results = response.json()
            if results and len(results) > 0:
                exists = results[0].get('exists', False)
                logger.info(f"Столбец {column_name} в таблице {table_name} {'существует' if exists else 'не существует'}")
                return exists
            else:
                logger.warning(f"Пустой результат при проверке столбца {column_name} в таблице {table_name}")
                return False
        else:
            logger.error(f"Ошибка при проверке столбца: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при проверке столбца {column_name} в таблице {table_name}: {str(e)}")
        return False

def add_column(table_name, column_name, column_type, default_value=None):
    """Добавление столбца в таблицу."""
    supabase_url = os.getenv('SUPABASE_URL')
    api_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not api_key:
        logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
        return False
    
    # Проверяем существование столбца
    if check_column_exists(table_name, column_name):
        logger.info(f"Столбец {column_name} уже существует в таблице {table_name}")
        return True
    
    # SQL запрос для добавления столбца
    sql_query = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
    
    # Добавляем значение по умолчанию, если оно указано
    if default_value is not None:
        sql_query += f" DEFAULT {default_value}"
    
    sql_query += ";"
    
    # Выполнение запроса через SQL REST API
    sql_url = f"{supabase_url}/rest/v1/sql"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        logger.info(f"Добавление столбца {column_name} в таблицу {table_name}")
        response = requests.post(sql_url, json={"query": sql_query}, headers=headers)
        
        if response.status_code in [200, 201, 204]:
            logger.info(f"Столбец {column_name} успешно добавлен в таблицу {table_name}")
            return True
        else:
            logger.error(f"Ошибка при добавлении столбца: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при добавлении столбца {column_name} в таблицу {table_name}: {str(e)}")
        return False

def add_all_missing_columns():
    """Добавление всех недостающих столбцов в таблицы."""
    # Список столбцов для добавления
    columns_to_add = [
        {"table_name": "saved_images", "column_name": "author_url", "column_type": "TEXT", "default_value": None},
        {"table_name": "channel_analysis", "column_name": "analyzed_posts_count", "column_type": "INTEGER", "default_value": 0}
    ]
    
    # Добавляем каждый столбец
    success = True
    for column in columns_to_add:
        result = add_column(
            column["table_name"], 
            column["column_name"], 
            column["column_type"], 
            column["default_value"]
        )
        success = success and result
    
    return success

def create_indexes():
    """Создание индексов для добавленных столбцов."""
    supabase_url = os.getenv('SUPABASE_URL')
    api_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not api_key:
        logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
        return False
    
    # Список индексов для создания
    indexes = [
        {"name": "idx_saved_images_author_url", "table": "saved_images", "column": "author_url"},
        {"name": "idx_channel_analysis_analyzed_posts_count", "table": "channel_analysis", "column": "analyzed_posts_count"}
    ]
    
    # SQL URL для выполнения запросов
    sql_url = f"{supabase_url}/rest/v1/sql"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    success = True
    
    for index in indexes:
        try:
            # Проверяем, существует ли индекс
            check_index_query = f"""
            SELECT EXISTS (
                SELECT FROM pg_indexes 
                WHERE schemaname = 'public' 
                AND tablename = '{index["table"]}' 
                AND indexname = '{index["name"]}'
            ) as exists;
            """
            
            response = requests.post(sql_url, json={"query": check_index_query}, headers=headers)
            
            if response.status_code == 200:
                results = response.json()
                if results and len(results) > 0 and results[0].get("exists", False):
                    logger.info(f"Индекс {index['name']} уже существует")
                    continue
            
            # Создаем индекс
            create_index_query = f"""
            CREATE INDEX IF NOT EXISTS {index["name"]} ON {index["table"]}({index["column"]});
            """
            
            logger.info(f"Создание индекса {index['name']} для столбца {index['column']} в таблице {index['table']}")
            response = requests.post(sql_url, json={"query": create_index_query}, headers=headers)
            
            if response.status_code in [200, 201, 204]:
                logger.info(f"Индекс {index['name']} успешно создан")
            else:
                logger.error(f"Ошибка при создании индекса {index['name']}: {response.status_code} - {response.text}")
                success = False
                
        except Exception as e:
            logger.error(f"Ошибка при создании индекса {index['name']}: {str(e)}")
            success = False
    
    return success

def main():
    """Основная функция для запуска создания недостающих столбцов."""
    logger.info("Запуск создания недостающих столбцов...")
    
    # Добавляем недостающие столбцы
    columns_result = add_all_missing_columns()
    if columns_result:
        logger.info("Все необходимые столбцы добавлены успешно")
    else:
        logger.error("Не удалось добавить некоторые столбцы")
    
    # Создаем индексы
    indexes_result = create_indexes()
    if indexes_result:
        logger.info("Все необходимые индексы созданы успешно")
    else:
        logger.error("Не удалось создать некоторые индексы")
    
    # Записываем в таблицу миграций
    if columns_result and indexes_result:
        logger.info("Все необходимые изменения выполнены успешно")
        logger.info("Операции завершены успешно")
    else:
        logger.error("Не удалось выполнить все необходимые изменения")
    
    return columns_result and indexes_result

if __name__ == "__main__":
    main() 