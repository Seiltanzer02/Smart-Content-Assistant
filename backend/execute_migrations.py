#!/usr/bin/env python
"""
Скрипт для принудительного выполнения миграций SQL 
в случае проблем со стандартным механизмом миграций
"""

import os
import logging
import sys
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
import glob
from os.path import dirname, abspath, join, basename

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

def execute_sql_direct(sql_query: str) -> bool:
    """Выполнение SQL запроса напрямую через REST API"""
    try:
        logger.info(f"Выполнение SQL запроса напрямую: {sql_query[:50]}...")
        
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
            return False
            
        # Выполнение запроса через SQL API
        sql_url = f"{supabase_url}/rest/v1/sql"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        response = requests.post(sql_url, json={"query": sql_query}, headers=headers)
        
        if response.status_code in [200, 201, 204]:
            logger.info("SQL запрос выполнен успешно")
            return True
        else:
            logger.error(f"Ошибка при выполнении SQL запроса: {response.status_code} - {response.text}")
            
            # Пробуем выполнить запрос через RPC если есть функция exec_sql
            try:
                url = f"{supabase_url}/rest/v1/rpc/exec_sql"
                rpc_headers = {
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}", 
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                }
                
                rpc_response = requests.post(url, json={"query": sql_query}, headers=rpc_headers)
                
                if rpc_response.status_code in [200, 201, 204]:
                    logger.info("SQL запрос выполнен успешно через RPC")
                    return True
                else:
                    logger.error(f"Ошибка при выполнении через RPC: {rpc_response.status_code} - {rpc_response.text}")
                    return False
            except Exception as rpc_err:
                logger.error(f"Ошибка при выполнении запроса через RPC: {str(rpc_err)}")
                return False
    except Exception as e:
        logger.error(f"Исключение при выполнении SQL запроса: {str(e)}")
        return False

def execute_sql_individually(sql_content: str) -> bool:
    """Выполнение SQL запросов по отдельности"""
    try:
        logger.info("Разбиение SQL скрипта на отдельные команды...")
        
        # Разбиваем SQL на отдельные команды
        sql_commands = []
        current_command = ""
        in_function_body = False
        
        for line in sql_content.splitlines():
            line = line.strip()
            
            # Пропускаем пустые строки и комментарии
            if not line or line.startswith('--'):
                continue
                
            # Отслеживаем начало и конец блоков функций
            if "DO $$" in line:
                in_function_body = True
                current_command += line + "\n"
                continue
                
            if in_function_body:
                current_command += line + "\n"
                if "END $$;" in line:
                    in_function_body = False
                    sql_commands.append(current_command)
                    current_command = ""
                continue
                
            # Обычные SQL команды
            current_command += line + "\n"
            if line.endswith(';'):
                sql_commands.append(current_command)
                current_command = ""
        
        # Добавляем последнюю команду, если она не закончилась точкой с запятой
        if current_command.strip():
            sql_commands.append(current_command)
            
        logger.info(f"Найдено {len(sql_commands)} SQL команд для выполнения")
        
        success = True
        for i, cmd in enumerate(sql_commands):
            if not cmd.strip():
                continue
                
            logger.info(f"Выполнение команды {i+1}/{len(sql_commands)}: {cmd[:50]}...")
            if not execute_sql_direct(cmd):
                logger.error(f"Ошибка при выполнении команды {i+1}")
                success = False
                # Но продолжаем выполнение остальных команд
            
        return success
    except Exception as e:
        logger.error(f"Исключение при разборе SQL: {str(e)}")
        return False

def create_exec_sql_function() -> bool:
    """Создание функции exec_sql для выполнения SQL запросов через RPC"""
    logger.info("Создание функции exec_sql...")
    
    sql = """
    CREATE OR REPLACE FUNCTION exec_sql(query text) 
    RETURNS text
    LANGUAGE plpgsql
    SECURITY DEFINER
    AS $$
    DECLARE
        result text;
    BEGIN
        EXECUTE query;
        GET DIAGNOSTICS result = ROW_COUNT;
        RETURN result || ' rows affected';
    EXCEPTION WHEN OTHERS THEN
        RETURN SQLERRM;
    END;
    $$;
    """
    
    return execute_sql_direct(sql)

def create_json_functions() -> bool:
    """Создание функций для работы с JSON результатами"""
    logger.info("Создание функций для работы с JSON...")
    
    # SQL для создания функции exec_sql_json
    sql_json = """
    CREATE OR REPLACE FUNCTION exec_sql_json(query text)
    RETURNS json
    LANGUAGE plpgsql
    SECURITY DEFINER
    AS $$
    DECLARE
        result json;
    BEGIN
        EXECUTE query INTO result;
        RETURN result;
    EXCEPTION WHEN OTHERS THEN
        RETURN json_build_object(
            'error', true,
            'message', SQLERRM,
            'detail', SQLSTATE
        );
    END;
    $$;
    """
    
    # SQL для создания функции exec_sql_array_json
    sql_array = """
    CREATE OR REPLACE FUNCTION exec_sql_array_json(query text)
    RETURNS json
    LANGUAGE plpgsql
    SECURITY DEFINER
    AS $$
    DECLARE
        result json;
    BEGIN
        EXECUTE 'SELECT json_agg(t) FROM (' || query || ') t' INTO result;
        RETURN COALESCE(result, '[]'::json);
    EXCEPTION WHEN OTHERS THEN
        RETURN json_build_object(
            'error', true,
            'message', SQLERRM,
            'detail', SQLSTATE
        );
    END;
    $$;
    """
    
    success1 = execute_sql_direct(sql_json)
    success2 = execute_sql_direct(sql_array)
    
    return success1 and success2

def add_missing_columns() -> bool:
    """Добавление отсутствующих столбцов"""
    logger.info("Добавление недостающих столбцов в таблицы...")
    
    # SQL для добавления столбца author_url в таблицу saved_images
    sql_author_url = """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'saved_images' AND column_name = 'author_url'
        ) THEN
            ALTER TABLE saved_images ADD COLUMN author_url TEXT;
            RAISE NOTICE 'Столбец author_url добавлен в таблицу saved_images';
        ELSE
            RAISE NOTICE 'Столбец author_url уже существует в таблице saved_images';
        END IF;
        
        IF NOT EXISTS (
            SELECT FROM pg_indexes 
            WHERE tablename = 'saved_images' AND indexname = 'idx_saved_images_author_url'
        ) THEN
            CREATE INDEX idx_saved_images_author_url ON saved_images(author_url);
            RAISE NOTICE 'Индекс idx_saved_images_author_url создан';
        ELSE
            RAISE NOTICE 'Индекс idx_saved_images_author_url уже существует';
        END IF;
    END $$;
    """
    
    # SQL для добавления столбца analyzed_posts_count в таблицу channel_analysis
    sql_posts_count = """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'channel_analysis' AND column_name = 'analyzed_posts_count'
        ) THEN
            ALTER TABLE channel_analysis ADD COLUMN analyzed_posts_count INTEGER DEFAULT 0;
            RAISE NOTICE 'Столбец analyzed_posts_count добавлен в таблицу channel_analysis';
        ELSE
            RAISE NOTICE 'Столбец analyzed_posts_count уже существует в таблице channel_analysis';
        END IF;
        
        IF NOT EXISTS (
            SELECT FROM pg_indexes 
            WHERE tablename = 'channel_analysis' AND indexname = 'idx_channel_analysis_analyzed_posts_count'
        ) THEN
            CREATE INDEX idx_channel_analysis_analyzed_posts_count ON channel_analysis(analyzed_posts_count);
            RAISE NOTICE 'Индекс idx_channel_analysis_analyzed_posts_count создан';
        ELSE
            RAISE NOTICE 'Индекс idx_channel_analysis_analyzed_posts_count уже существует';
        END IF;
    END $$;
    """
    
    success1 = execute_sql_direct(sql_author_url)
    success2 = execute_sql_direct(sql_posts_count)
    
    return success1 and success2

def run_migrations_manually() -> bool:
    """Запуск миграций вручную"""
    logger.info("Запуск миграций вручную...")
    
    # Получаем список файлов миграций
    migrations_dir = join(dirname(abspath(__file__)), "migrations")
    migration_files = sorted(glob.glob(join(migrations_dir, "*.sql")))
    
    if not migration_files:
        logger.warning(f"Файлы миграций не найдены в {migrations_dir}")
        return False
        
    logger.info(f"Найдено {len(migration_files)} файлов миграций")
    
    # Применяем миграции по порядку
    success = True
    for migration_file in migration_files:
        file_name = basename(migration_file)
        logger.info(f"Применение миграции: {file_name}")
        
        try:
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
                
            if not execute_sql_individually(sql_content):
                logger.error(f"Ошибка при выполнении миграции {file_name}")
                success = False
            else:
                logger.info(f"Миграция {file_name} успешно применена")
        except Exception as e:
            logger.error(f"Исключение при применении миграции {file_name}: {str(e)}")
            success = False
            
    return success

def main():
    """Основная функция для запуска миграций"""
    logger.info("Запуск принудительных миграций...")
    
    # Инициализация Supabase
    supabase = init_supabase()
    if not supabase:
        logger.error("Не удалось инициализировать клиент Supabase")
        return False
        
    # Создаем функцию exec_sql
    if create_exec_sql_function():
        logger.info("Функция exec_sql успешно создана или обновлена")
    else:
        logger.error("Не удалось создать функцию exec_sql")
        
    # Создаем JSON функции
    if create_json_functions():
        logger.info("Функции для работы с JSON успешно созданы")
    else:
        logger.error("Не удалось создать функции для работы с JSON")
        
    # Добавляем недостающие столбцы напрямую
    if add_missing_columns():
        logger.info("Недостающие столбцы успешно добавлены")
    else:
        logger.error("Ошибка при добавлении недостающих столбцов")
        
    # Запускаем все миграции вручную
    if run_migrations_manually():
        logger.info("Все миграции успешно применены")
    else:
        logger.error("Были ошибки при применении миграций")
        
    logger.info("Процесс принудительных миграций завершен")
    return True

if __name__ == "__main__":
    main() 