#!/usr/bin/env python
"""
Скрипт для применения миграций к базе данных Supabase.
"""

import os
import logging
import sys
from dotenv import load_dotenv
from supabase import create_client, Client
import glob
import time
from typing import List, Optional

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv(override=True)

def init_supabase() -> Optional[Client]:
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

def run_migrations(supabase: Client) -> None:
    """Запуск SQL миграций"""
    try:
        migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")
        logger.info(f"Поиск миграций в директории: {migrations_dir}")
        
        # Получаем список SQL файлов и сортируем их по имени
        sql_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
        logger.info(f"Найдено миграций: {len(sql_files)}")
        
        if not sql_files:
            logger.warning(f"SQL файлы для миграции не найдены в {migrations_dir}")
            return
        
        for sql_file in sql_files:
            try:
                file_name = os.path.basename(sql_file)
                logger.info(f"Применение миграции: {file_name}")
                
                # Читаем содержимое SQL файла
                with open(sql_file, 'r', encoding='utf-8') as f:
                    sql_content = f.read()
                
                logger.info(f"Загружено SQL-содержимое: {len(sql_content)} байт")
                
                # Проверяем подключение
                try:
                    supabase.table("_migrations").select("*").limit(1).execute()
                    logger.info("Проверка подключения прошла успешно")
                except Exception as conn_err:
                    logger.warning(f"Таблица _migrations может не существовать: {str(conn_err)}")
                
                # Используем PostgreSQL функционал с содержимым файла
                result = supabase.rpc('run_sql', {'sql_query': sql_content}).execute()
                
                logger.info(f"Миграция успешно применена: {file_name}")
            except Exception as e:
                logger.error(f"Ошибка при применении миграции {file_name}: {str(e)}")
                logger.error(f"Детали: {type(e).__name__}: {str(e)}")
    except Exception as e:
        logger.error(f"Общая ошибка при запуске миграций: {str(e)}")

def create_rpc_function(supabase: Client) -> None:
    """Создание RPC функции для выполнения произвольных SQL запросов."""
    try:
        # SQL для создания функции run_sql
        sql = """
        DROP FUNCTION IF EXISTS run_sql(text);
        
        CREATE OR REPLACE FUNCTION run_sql(sql_query TEXT)
        RETURNS JSONB
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        DECLARE
            result JSONB;
        BEGIN
            EXECUTE sql_query;
            result := '{"status": "success"}'::JSONB;
            RETURN result;
        EXCEPTION WHEN OTHERS THEN
            result := jsonb_build_object('status', 'error', 'message', SQLERRM);
            RETURN result;
        END;
        $$;
        """
        
        # Выполнение запроса через REST API, так как supabase-py не поддерживает DDL напрямую
        headers = {
            "apikey": os.getenv("SUPABASE_ANON_KEY"),
            "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        import requests
        url = f"{os.getenv('SUPABASE_URL')}/rest/v1/rpc/run_sql"
        
        try:
            # Сначала пробуем удалить функцию, если она существует
            drop_sql = "DROP FUNCTION IF EXISTS run_sql(text);"
            drop_response = requests.post(url, json={"sql_query": drop_sql}, headers=headers)
            logger.info(f"Результат удаления функции run_sql: {drop_response.status_code}")
        except Exception as drop_err:
            logger.warning(f"Ошибка при удалении функции run_sql: {str(drop_err)}")
        
        # Создаем функцию заново
        response = requests.post(url, json={"sql_query": sql}, headers=headers)
        
        if response.status_code == 200:
            logger.info("RPC функция run_sql успешно создана")
        else:
            logger.error(f"Ошибка при создании RPC функции: {response.status_code} - {response.text}")
            
            # Попробуем создать функцию без предварительного DROP
            simplified_sql = """
            CREATE OR REPLACE FUNCTION run_sql(sql_query TEXT)
            RETURNS JSONB
            LANGUAGE plpgsql
            SECURITY DEFINER
            AS $$
            DECLARE
                result JSONB;
            BEGIN
                EXECUTE sql_query;
                result := '{"status": "success"}'::JSONB;
                RETURN result;
            EXCEPTION WHEN OTHERS THEN
                result := jsonb_build_object('status', 'error', 'message', SQLERRM);
                RETURN result;
            END;
            $$;
            """
            retry_response = requests.post(url, json={"sql_query": simplified_sql}, headers=headers)
            if retry_response.status_code == 200:
                logger.info("RPC функция run_sql успешно создана при повторной попытке")
            else:
                logger.error(f"Повторная ошибка при создании RPC функции: {retry_response.status_code} - {retry_response.text}")
            
    except Exception as e:
        logger.error(f"Ошибка при создании RPC функции: {str(e)}")

def main():
    """Основная функция для запуска миграций."""
    logger.info("Запуск процесса миграции базы данных...")
    
    supabase = init_supabase()
    if not supabase:
        logger.error("Не удалось инициализировать Supabase. Миграции не будут применены.")
        return
    
    # Создаем RPC функцию для выполнения SQL
    create_rpc_function(supabase)
    
    # Запускаем миграции
    run_migrations(supabase)
    
    logger.info("Процесс миграции завершен.")

if __name__ == "__main__":
    main() 