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
    """Выполнение SQL запроса напрямую через RPC API"""
    try:
        logger.info(f"Выполнение SQL запроса напрямую: {sql_query[:50]}...")
        
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
            return False
            
        # Используем только RPC API, так как SQL API недоступен (404)
        url = f"{supabase_url}/rest/v1/rpc/exec_sql"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}", 
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        response = requests.post(url, json={"query": sql_query}, headers=headers)
        
        if response.status_code in [200, 201, 204]:
            logger.info("SQL запрос выполнен успешно через RPC")
            return True
        else:
            logger.error(f"Ошибка при выполнении через RPC: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Исключение при выполнении SQL запроса: {str(e)}")
        return False

def execute_sql_individually(sql_content: str) -> bool:
    """Выполнение SQL запросов по отдельности через RPC"""
    try:
        logger.info("Разбиение SQL скрипта на отдельные команды...")
        
        # Получаем данные из переменных окружения
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
            return False
        
        # Разбиваем SQL на отдельные команды
        sql_commands = []
        current_command = ""
        in_function_body = False
        in_comment = False
        
        for line in sql_content.splitlines():
            stripped_line = line.strip()
            
            # Пропускаем пустые строки
            if not stripped_line:
                continue
                
            # Обрабатываем комментарии
            if stripped_line.startswith('--'):
                continue
                
            # Отслеживаем начало и конец блоков функций
            if "DO $$" in stripped_line:
                in_function_body = True
                current_command += line + "\n"
                continue
                
            if in_function_body:
                current_command += line + "\n"
                if "END $$;" in stripped_line:
                    in_function_body = False
                    sql_commands.append(current_command)
                    current_command = ""
                continue
                
            # Обычные SQL команды
            current_command += line + "\n"
            if stripped_line.endswith(';') and not in_function_body:
                sql_commands.append(current_command)
                current_command = ""
        
        # Добавляем последнюю команду, если она не закончилась точкой с запятой
        if current_command.strip():
            sql_commands.append(current_command)
            
        logger.info(f"Найдено {len(sql_commands)} SQL команд для выполнения")
        
        # Вызовы RPC exec_sql
        rpc_url = f"{supabase_url}/rest/v1/rpc/exec_sql"
        rpc_headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}", 
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        # Непосредственное выполнение SQL через SQL API
        sql_url = f"{supabase_url}/rest/v1/sql"
        sql_headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        success = True
        for i, cmd in enumerate(sql_commands):
            if not cmd.strip():
                continue
                
            logger.info(f"Выполнение команды {i+1}/{len(sql_commands)}")
            
            # Удаляем блоки DO $$ ... END $$; из запроса, извлекая внутренности
            if "DO $$" in cmd and "END $$;" in cmd:
                # Извлекаем SQL из блока DO
                start_idx = cmd.find("DO $$") + 5
                end_idx = cmd.find("END $$;")
                if start_idx > 0 and end_idx > start_idx:
                    inner_sql = cmd[start_idx:end_idx].strip()
                    
                    # Ищем SQL операторы внутри блока DO
                    if "ALTER TABLE" in inner_sql:
                        clean_cmd = inner_sql.replace("BEGIN", "").replace("END", "").replace("IF NOT EXISTS", "").strip()
                        # Извлекаем команды ALTER TABLE
                        alter_commands = []
                        for line in clean_cmd.split("\n"):
                            line = line.strip()
                            if line.startswith("ALTER TABLE") and ";" in line:
                                alter_commands.append(line)
                            elif line.startswith("CREATE INDEX") and ";" in line:
                                alter_commands.append(line)
                        
                        # Выполняем каждую команду ALTER TABLE отдельно
                        for alter_cmd in alter_commands:
                            logger.info(f"Выполнение команды ALTER TABLE: {alter_cmd[:50]}...")
                            try:
                                # Сначала пробуем через RPC
                                response = requests.post(rpc_url, json={"query": alter_cmd}, headers=rpc_headers)
                                
                                if response.status_code not in [200, 201, 204]:
                                    logger.warning(f"Ошибка при выполнении через RPC: {response.status_code} - {response.text}")
                                    
                                    # Затем пробуем через SQL API
                                    sql_response = requests.post(sql_url, json={"query": alter_cmd}, headers=sql_headers)
                                    
                                    if sql_response.status_code not in [200, 201, 204]:
                                        logger.error(f"Ошибка при выполнении через SQL API: {sql_response.status_code} - {sql_response.text}")
                                        success = False
                                    else:
                                        logger.info("Команда выполнена успешно через SQL API")
                                else:
                                    logger.info("Команда выполнена успешно через RPC")
                            except Exception as e:
                                logger.error(f"Ошибка при выполнении команды: {str(e)}")
                                success = False
                        
                        continue
            
            # Проверяем, есть ли в команде CREATE OR REPLACE FUNCTION
            if "CREATE OR REPLACE FUNCTION" in cmd:
                logger.info(f"Пропуск создания функции: {cmd[:50]}...")
                continue
            
            # Для обычных команд пробуем выполнить через RPC, затем через SQL API
            try:
                # Сначала пробуем через RPC
                response = requests.post(rpc_url, json={"query": cmd}, headers=rpc_headers)
                
                if response.status_code not in [200, 201, 204]:
                    logger.warning(f"Ошибка при выполнении через RPC: {response.status_code} - {response.text}")
                    
                    # Затем пробуем через SQL API
                    sql_response = requests.post(sql_url, json={"query": cmd}, headers=sql_headers)
                    
                    if sql_response.status_code not in [200, 201, 204]:
                        logger.error(f"Ошибка при выполнении через SQL API: {sql_response.status_code} - {sql_response.text}")
                        success = False
                    else:
                        logger.info(f"Команда {i+1} выполнена успешно через SQL API")
                else:
                    logger.info(f"Команда {i+1} выполнена успешно через RPC")
            except Exception as e:
                logger.error(f"Ошибка при выполнении команды {i+1}: {str(e)}")
                success = False
        
        return success
    except Exception as e:
        logger.error(f"Ошибка при выполнении SQL команд: {str(e)}")
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

def create_all_sql_functions() -> bool:
    """Создание всех необходимых SQL функций для работы с миграциями"""
    logger.info("Создание функций для работы с SQL...")
    
    # Создаем функцию exec_sql
    exec_sql_created = create_exec_sql_function()
    if not exec_sql_created:
        logger.error("Не удалось создать функцию exec_sql")
        return False
    
    # Создаем функцию exec_sql_json
    exec_sql_json = """
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
    
    if not execute_sql_direct(exec_sql_json):
        logger.error("Не удалось создать функцию exec_sql_json")
        return False
    
    # Создаем функцию exec_sql_array_json
    exec_sql_array_json = """
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
    
    if not execute_sql_direct(exec_sql_array_json):
        logger.error("Не удалось создать функцию exec_sql_array_json")
        return False
    
    logger.info("Все SQL функции успешно созданы")
    return True

def main():
    """Основная функция для запуска миграций"""
    logger.info("Запуск принудительных миграций...")
    
    # Удаление старых функций (на случай конфликтов)
    try:
        # Базовое соединение для проверки доступности сервера
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
            return False
        
        # Проверяем, отвечает ли сервер
        url = f"{supabase_url}/rest/v1/suggested_ideas?select=id&limit=1"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}"
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            logger.info("Соединение с Supabase работает")
        else:
            logger.error(f"Ошибка при проверке соединения с Supabase: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при проверке соединения с Supabase: {str(e)}")
        return False
        
    # Создаем все необходимые SQL функции
    if create_all_sql_functions():
        logger.info("Все необходимые SQL функции успешно созданы")
    else:
        logger.error("Не удалось создать все необходимые SQL функции")
        
    # Добавляем недостающие столбцы напрямую
    if add_missing_columns():
        logger.info("Недостающие столбцы успешно добавлены")
    else:
        logger.error("Ошибка при добавлении недостающих столбцов")
        
    # Создаем таблицу _migrations если она не существует
    create_migrations_table_sql = """
    CREATE TABLE IF NOT EXISTS _migrations (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_migrations_name ON _migrations(name);
    """
    
    if execute_sql_direct(create_migrations_table_sql):
        logger.info("Таблица _migrations успешно создана (если не существовала)")
    else:
        logger.error("Ошибка при создании таблицы _migrations")
        
    # Запускаем все миграции вручную
    if run_migrations_manually():
        logger.info("Все миграции успешно применены")
    else:
        logger.error("Были ошибки при применении миграций")
        
    logger.info("Процесс принудительных миграций завершен")
    return True

if __name__ == "__main__":
    main() 