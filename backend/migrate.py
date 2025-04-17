#!/usr/bin/env python
"""
Скрипт для применения миграций к базе данных Supabase.
"""

import os
import logging
import sys
import json
from dotenv import load_dotenv
from supabase import create_client, Client
import glob
import time
from typing import List, Optional, Tuple, Dict, Any
import requests

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

def execute_sql_direct(sql_query: str) -> bool:
    """Выполнение SQL запроса напрямую через REST API."""
    try:
        logger.info(f"Выполнение SQL запроса напрямую: {sql_query[:50]}...")
        
        # Проверяем наличие функции exec_sql
        check_sql = """
        SELECT EXISTS (
            SELECT FROM pg_proc 
            WHERE proname = 'exec_sql' 
            AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        ) as exists;
        """
        
        # Прямой запрос к базе данных через REST API
        url = f"{os.getenv('SUPABASE_URL')}/rest/v1/rpc/exec_sql"
        headers = {
            "apikey": os.getenv("SUPABASE_ANON_KEY"),
            "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        # Сначала проверяем наличие функции exec_sql
        test_response = requests.post(url, json={"query": check_sql}, headers=headers)
        
        # Если функция не существует и мы пытаемся её создать
        if test_response.status_code != 200 and "CREATE OR REPLACE FUNCTION exec_sql" in sql_query:
            logger.info("Создаем функцию exec_sql напрямую через SQL запрос...")
            
            # Используем прямой SQL API для создания функции
            sql_url = f"{os.getenv('SUPABASE_URL')}/rest/v1/sql"
            sql_headers = {
                "apikey": os.getenv("SUPABASE_ANON_KEY"),
                "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            
            sql_response = requests.post(sql_url, json={"query": sql_query}, headers=sql_headers)
            
            if sql_response.status_code in [200, 201, 204]:
                logger.info("SQL запрос выполнен успешно через прямой SQL API")
                return True
            else:
                logger.error(f"Ошибка при выполнении SQL запроса через прямой SQL API: {sql_response.status_code} - {sql_response.text}")
                return False
        
        # Стандартное выполнение через exec_sql если функция существует
        response = requests.post(url, json={"query": sql_query}, headers=headers)
        
        if response.status_code in [200, 201, 204]:
            logger.info("SQL запрос выполнен успешно")
            return True
        else:
            # Если функция exec_sql не существует, пробуем выполнить запрос напрямую через SQL API
            logger.warning(f"Ошибка при выполнении SQL запроса через exec_sql: {response.status_code} - {response.text}")
            
            # Используем прямой SQL API
            sql_url = f"{os.getenv('SUPABASE_URL')}/rest/v1/sql"
            sql_headers = {
                "apikey": os.getenv("SUPABASE_ANON_KEY"),
                "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            
            sql_response = requests.post(sql_url, json={"query": sql_query}, headers=sql_headers)
            
            if sql_response.status_code in [200, 201, 204]:
                logger.info("SQL запрос выполнен успешно через прямой SQL API")
                return True
            else:
                logger.error(f"Ошибка при выполнении SQL запроса: {sql_response.status_code} - {sql_response.text}")
                return False
    except Exception as e:
        logger.error(f"Исключение при выполнении SQL запроса: {str(e)}")
        return False

def execute_sql_query_direct(sql_query: str) -> Tuple[bool, List[Dict[str, Any]]]:
    """Выполнение SQL запроса напрямую через REST API и возврат результатов."""
    try:
        logger.info(f"Выполнение SQL запроса с возвратом результатов: {sql_query[:50]}...")
        
        # Проверяем наличие функции exec_sql
        check_sql = """
        SELECT EXISTS (
            SELECT FROM pg_proc 
            WHERE proname = 'exec_sql' 
            AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        ) as exists;
        """
        
        # Прямой запрос к базе данных через REST API
        url = f"{os.getenv('SUPABASE_URL')}/rest/v1/rpc/exec_sql"
        headers = {
            "apikey": os.getenv("SUPABASE_ANON_KEY"),
            "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        # Сначала проверяем наличие функции exec_sql
        test_response = requests.post(url, json={"query": check_sql}, headers=headers)
        
        # Если функция не существует, используем прямой SQL API
        if test_response.status_code != 200:
            logger.warning("Функция exec_sql не найдена, используем прямой SQL API")
            sql_url = f"{os.getenv('SUPABASE_URL')}/rest/v1/sql"
            sql_headers = {
                "apikey": os.getenv("SUPABASE_ANON_KEY"),
                "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
            
            sql_response = requests.post(sql_url, json={"query": sql_query}, headers=sql_headers)
            
            if sql_response.status_code == 200:
                logger.info("SQL запрос выполнен успешно через прямой SQL API")
                return True, sql_response.json()
            else:
                logger.error(f"Ошибка при выполнении SQL запроса через прямой SQL API: {sql_response.status_code} - {sql_response.text}")
                return False, []
        
        # Стандартное выполнение через exec_sql если функция существует
        response = requests.post(url, json={"query": sql_query}, headers=headers)
        
        if response.status_code == 200:
            logger.info("SQL запрос выполнен успешно")
            return True, response.json()
        else:
            # Если ошибка, пробуем через прямой SQL API
            logger.warning(f"Ошибка при выполнении SQL запроса через exec_sql: {response.status_code} - {response.text}")
            
            sql_url = f"{os.getenv('SUPABASE_URL')}/rest/v1/sql"
            sql_headers = {
                "apikey": os.getenv("SUPABASE_ANON_KEY"),
                "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
            
            sql_response = requests.post(sql_url, json={"query": sql_query}, headers=sql_headers)
            
            if sql_response.status_code == 200:
                logger.info("SQL запрос выполнен успешно через прямой SQL API")
                return True, sql_response.json()
            else:
                logger.error(f"Ошибка при выполнении SQL запроса: {sql_response.status_code} - {sql_response.text}")
                return False, []
    except Exception as e:
        logger.error(f"Исключение при выполнении SQL запроса: {str(e)}")
        return False, []

def check_table_exists(table_name: str) -> bool:
    """Проверка существования таблицы в базе данных."""
    try:
        logger.info(f"Проверка существования таблицы: {table_name}")
        sql = f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = '{table_name}'
        ) as exists;
        """
        
        success, result = execute_sql_query_direct(sql)
        
        if not success or not result:
            logger.warning(f"Не удалось проверить существование таблицы {table_name}")
            return False
        
        exists = result[0].get("exists", False)
        logger.info(f"Таблица {table_name} {'существует' if exists else 'не существует'}")
        return exists
    except Exception as e:
        logger.error(f"Ошибка при проверке существования таблицы {table_name}: {str(e)}")
        return False

def create_migrations_table():
    """Создание таблицы _migrations для отслеживания выполненных миграций."""
    logger.info("Создание таблицы _migrations...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS _migrations (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        executed_at BIGINT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS idx_migrations_name ON _migrations(name);
    
    COMMENT ON TABLE _migrations IS 'Таблица для отслеживания выполненных миграций SQL';
    """
    
    if execute_sql_direct(sql):
        logger.info("Таблица _migrations успешно создана")
        return True
    else:
        logger.error("Не удалось создать таблицу _migrations")
        return False

def execute_sql_individually(sql_content: str) -> bool:
    """Выполнение SQL запросов по отдельности, разбивая на отдельные команды."""
    try:
        logger.info("Разбиение SQL скрипта на отдельные команды...")
        
        # Разбиваем SQL на отдельные команды
        # Используем простое разделение по символу ';'
        sql_commands = [cmd.strip() for cmd in sql_content.split(';') if cmd.strip()]
        
        success = True
        
        # Прямой запрос к базе данных через REST API
        sql_url = f"{os.getenv('SUPABASE_URL')}/rest/v1/sql"
        sql_headers = {
            "apikey": os.getenv("SUPABASE_ANON_KEY"),
            "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        for i, cmd in enumerate(sql_commands):
            if not cmd.strip():
                continue
                
            logger.info(f"Выполнение команды {i+1}/{len(sql_commands)}: {cmd[:50]}...")
            
            # Пропускаем комментарии
            if cmd.strip().startswith('--'):
                logger.info(f"Пропуск комментария")
                continue
                
            # Пропускаем блоки DO
            if "DO $$" in cmd:
                logger.warning(f"Пропуск блока DO $$, который не может быть выполнен через SQL API")
                continue
            
            sql_response = requests.post(sql_url, json={"query": cmd}, headers=sql_headers)
            
            if sql_response.status_code in [200, 201, 204]:
                logger.info(f"Команда {i+1} выполнена успешно")
            else:
                logger.error(f"Ошибка при выполнении команды {i+1}: {sql_response.status_code} - {sql_response.text}")
                success = False
        
        return success
    except Exception as e:
        logger.error(f"Исключение при выполнении SQL запросов по отдельности: {str(e)}")
        return False

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
        
        # Проверяем наличие таблицы _migrations
        try:
            # Используем Supabase клиент для проверки таблицы
            test_migrations_table = supabase.table("_migrations").select("*").limit(1).execute()
            logger.info("Таблица _migrations существует")
        except Exception as e:
            logger.warning(f"Ошибка при проверке таблицы _migrations: {str(e)}")
            # Пробуем создать таблицу через supabase клиент
            try:
                logger.info("Попытка создать таблицу _migrations через REST API...")
                
                # Используем admin_key для создания таблицы
                admin_url = f"{os.getenv('SUPABASE_URL')}/rest/v1"
                admin_headers = {
                    "apikey": os.getenv("SUPABASE_ANON_KEY"),
                    "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                }
                
                # Проверяем, существуют ли другие таблицы
                tables_response = requests.get(f"{admin_url}/suggested_ideas?select=id&limit=1", headers=admin_headers)
                if tables_response.status_code == 200:
                    logger.info("Доступ к таблицам через REST API работает, но создание _migrations невозможно без функции exec_sql")
                else:
                    logger.warning(f"Невозможно создать таблицу _migrations: {tables_response.status_code} - {tables_response.text}")
            except Exception as create_err:
                logger.error(f"Не удалось создать таблицу _migrations: {str(create_err)}")
        
        exec_sql_available = check_exec_sql_function(supabase)
        
        # Проверяем доступ к Supabase Tables API
        try:
            tables_result = supabase.table("suggested_ideas").select("id").limit(1).execute()
            logger.info(f"Таблицы доступны через Supabase клиент")
            tables_accessible = True
        except Exception as tables_err:
            logger.warning(f"Ошибка доступа к таблицам: {str(tables_err)}")
            tables_accessible = False
        
        # Если таблицы доступны, но exec_sql недоступен, пропускаем миграции
        if tables_accessible and not exec_sql_available:
            logger.info("Таблицы доступны, но функция exec_sql недоступна. Пропускаем миграции.")
            return
        
        for sql_file in sql_files:
            try:
                file_name = os.path.basename(sql_file)
                logger.info(f"Применение миграции: {file_name}")
                
                # Проверяем, не была ли миграция уже выполнена
                if is_migration_executed(file_name):
                    logger.info(f"Миграция {file_name} уже была выполнена ранее, пропускаем")
                    continue
                
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
                
                migration_applied = False
                
                # Если доступна функция exec_sql, используем её
                if exec_sql_available:
                    # Используем PostgreSQL функционал через exec_sql
                    url = f"{os.getenv('SUPABASE_URL')}/rest/v1/rpc/exec_sql"
                    headers = {
                        "apikey": os.getenv("SUPABASE_ANON_KEY"),
                        "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal"
                    }
                    
                    # Параметр должен называться "query" согласно определению exec_sql в миграциях
                    response = requests.post(url, json={"query": sql_content}, headers=headers)
                    
                    if response.status_code == 200:
                        logger.info(f"Миграция успешно применена через exec_sql: {file_name}")
                        migration_applied = True
                    else:
                        logger.warning(f"Ошибка при применении миграции через exec_sql: {response.status_code} - {response.text}")
                
                # Если миграция не применена через exec_sql, пробуем прямой метод
                if not migration_applied:
                    logger.info(f"Применение миграции напрямую через SQL API: {file_name}")
                    
                    # Для 003_add_author_url_column.sql пробуем выполнить по частям
                    if file_name == "003_add_author_url_column.sql":
                        logger.info("Применение миграции 003 по отдельным командам...")
                        if execute_sql_individually(sql_content):
                            logger.info(f"Миграция успешно применена по частям: {file_name}")
                            migration_applied = True
                        else:
                            logger.error(f"Не удалось применить миграцию по частям: {file_name}")
                    else:
                        # Для остальных файлов используем стандартный метод
                        if execute_sql_direct(sql_content):
                            logger.info(f"Миграция успешно применена напрямую: {file_name}")
                            migration_applied = True
                        else:
                            logger.error(f"Не удалось применить миграцию: {file_name}")
                            
                            # Пробуем выполнить по частям как резервный метод
                            logger.info(f"Пробуем выполнить миграцию {file_name} по отдельным командам...")
                            if execute_sql_individually(sql_content):
                                logger.info(f"Миграция успешно применена по частям: {file_name}")
                                migration_applied = True
                            else:
                                logger.error(f"Не удалось применить миграцию даже по частям: {file_name}")
                                raise Exception("Ошибка применения миграции")
                
                # Если миграция была успешно применена, записываем в таблицу _migrations
                if migration_applied:
                    record_migration_execution(file_name)
                
            except Exception as e:
                logger.error(f"Ошибка при применении миграции {file_name}: {str(e)}")
                logger.error(f"Детали: {type(e).__name__}: {str(e)}")
                
                # Проверяем, содержит ли миграция создание exec_sql - если да, создаем функцию напрямую
                if "CREATE OR REPLACE FUNCTION exec_sql" in sql_content:
                    logger.info("Попытка создать функцию exec_sql напрямую...")
                    exec_sql_definition = """
                    CREATE OR REPLACE FUNCTION exec_sql(query text) RETURNS void AS $$
                    BEGIN
                        EXECUTE query;
                    END;
                    $$ LANGUAGE plpgsql SECURITY DEFINER;
                    """
                    if execute_sql_direct(exec_sql_definition):
                        logger.info("Функция exec_sql успешно создана напрямую")
                        # Обновляем статус доступности функции
                        exec_sql_available = True
                        # Повторяем попытку миграции
                        logger.info(f"Повторная попытка миграции: {file_name}")
                        if execute_sql_direct(sql_content):
                            logger.info(f"Миграция успешно применена напрямую при повторной попытке: {file_name}")
                            record_migration_execution(file_name)
                        else:
                            logger.error(f"Не удалось применить миграцию при повторной попытке: {file_name}")
                
    except Exception as e:
        logger.error(f"Общая ошибка при запуске миграций: {str(e)}")

def is_migration_executed(migration_name: str) -> bool:
    """Проверка, была ли миграция выполнена ранее."""
    sql = f"""
    SELECT EXISTS (
        SELECT FROM _migrations
        WHERE name = '{migration_name}'
    ) as exists;
    """
    
    success, results = execute_sql_query_direct(sql)
    if success and results and len(results) > 0:
        exists = results[0].get('exists', False)
        return exists
    
    return False

def record_migration_execution(migration_name: str) -> bool:
    """Запись информации о выполненной миграции."""
    try:
        logger.info(f"Запись информации о выполненной миграции: {migration_name}")
        timestamp = int(time.time())
        
        sql = f"""
        INSERT INTO _migrations (name, executed_at)
        VALUES ('{migration_name}', {timestamp})
        ON CONFLICT (name) DO NOTHING;
        """
        
        # Сначала пробуем стандартный способ
        if execute_sql_direct(sql):
            logger.info(f"Информация о миграции {migration_name} успешно записана")
            return True
            
        # Используем REST API клиент Supabase напрямую
        logger.info("Попытка записать информацию о миграции через API...")
        
        supabase_url = os.getenv('SUPABASE_URL')
        if not supabase_url:
            logger.error("URL Supabase не найден")
            return False
            
        api_key = os.getenv('SUPABASE_ANON_KEY')
        if not api_key:
            logger.error("API ключ Supabase не найден")
            return False
            
        url = f"{supabase_url}/rest/v1/_migrations"
        headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        data = {
            "name": migration_name,
            "executed_at": timestamp
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code in [200, 201, 204]:
            logger.info(f"Информация о миграции {migration_name} успешно записана через API")
            return True
        else:
            # Если возникла ошибка конфликта (миграция уже применена), тоже считаем успехом
            if response.status_code == 409:
                logger.info(f"Миграция {migration_name} уже записана в таблицу")
                return True
            logger.error(f"Ошибка при записи информации о миграции через API: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Исключение при записи информации о миграции: {str(e)}")
        return False

def check_exec_sql_function(supabase: Client) -> bool:
    """Проверка наличия функции exec_sql в базе данных."""
    try:
        url = f"{os.getenv('SUPABASE_URL')}/rest/v1/rpc/exec_sql"
        headers = {
            "apikey": os.getenv("SUPABASE_ANON_KEY"),
            "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        # Пытаемся вызвать функцию с тестовым запросом
        response = requests.post(url, json={"query": "SELECT 1"}, headers=headers)
        
        if response.status_code in [200, 201, 204]:
            logger.info("Функция exec_sql существует и работает корректно")
            return True
        else:
            logger.warning(f"Проверка функции exec_sql вернула код {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.warning(f"Ошибка при проверке функции exec_sql: {str(e)}")
        return False

def create_exec_sql_function(supabase: Client) -> bool:
    """Создание функции exec_sql для выполнения SQL запросов через RPC"""
    try:
        logger.info("Проверка наличия функции exec_sql...")
        
        # Проверяем существование функции через прямой SQL запрос
        check_sql = """
        SELECT EXISTS (
            SELECT FROM pg_proc 
            WHERE proname = 'exec_sql' 
            AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        ) as exists;
        """
        
        success, results = execute_sql_query_direct(check_sql)
        
        if success and results and len(results) > 0 and results[0].get('exists', False):
            logger.info("Функция exec_sql уже существует")
            return True
            
        # Функция не существует, создаем её
        logger.info("Создание функции exec_sql...")
        
        # SQL для создания функции
        create_function_sql = """
        CREATE OR REPLACE FUNCTION exec_sql(query text) RETURNS json AS $$
        DECLARE
            result json;
        BEGIN
            EXECUTE query;
            result := json_build_object('success', true);
            RETURN result;
        EXCEPTION WHEN OTHERS THEN
            result := json_build_object(
                'success', false,
                'error', SQLERRM,
                'detail', SQLSTATE
            );
            RETURN result;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        """
        
        # Попытка создать функцию через прямой SQL запрос
        if execute_sql_direct(create_function_sql):
            logger.info("Функция exec_sql успешно создана")
            return True
        else:
            logger.error("Не удалось создать функцию exec_sql напрямую")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при создании функции exec_sql: {str(e)}")
        return False

def check_migrations_table() -> bool:
    """Проверка наличия таблицы миграций и её создание при необходимости."""
    logger.info("Проверка наличия таблицы _migrations...")
    
    try:
        # Проверка существования таблицы
        check_sql = """
        SELECT EXISTS (
            SELECT FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename = '_migrations'
        ) as exists;
        """
        
        success, results = execute_sql_query_direct(check_sql)
        
        if success and results and len(results) > 0 and results[0].get('exists', False):
            logger.info("Таблица _migrations уже существует")
            return True
            
        # Таблица не существует, создаем её
        logger.info("Создание таблицы _migrations...")
        
        # SQL для создания таблицы
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS _migrations (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            executed_at BIGINT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        -- Создание индекса для ускорения поиска по имени миграции
        CREATE INDEX IF NOT EXISTS idx_migrations_name ON _migrations(name);
        
        -- Добавление комментария к таблице
        COMMENT ON TABLE _migrations IS 'Таблица для отслеживания выполненных миграций SQL';
        """
        
        # Попытка создать таблицу через прямой SQL запрос
        if execute_sql_direct(create_table_sql):
            logger.info("Таблица _migrations успешно создана")
            return True
        else:
            logger.error("Не удалось создать таблицу _migrations напрямую")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при создании таблицы _migrations: {str(e)}")
        return False

def create_base_tables_directly():
    """Создание базовых таблиц напрямую через клиент Supabase."""
    logger.info("Попытка создать базовые таблицы напрямую...")
    
    # Используем клиент Supabase для проверки существования таблиц
    supabase = init_supabase()
    if not supabase:
        logger.error("Не удалось инициализировать Supabase для создания таблиц")
        return
    
    try:
        # Проверяем доступность таблицы suggested_ideas
        try:
            result = supabase.table("suggested_ideas").select("id").limit(1).execute()
            logger.info("Таблица suggested_ideas существует")
            tables_exist = True
        except Exception:
            logger.warning("Таблица suggested_ideas не найдена")
            tables_exist = False
        
        # Если таблицы уже существуют, пропускаем создание
        if tables_exist:
            logger.info("Базовые таблицы уже существуют, пропускаем их создание")
            return
        
        logger.warning("Таблицы не существуют, но создать их через API не получится без функции exec_sql")
        logger.info("Рекомендуется создать таблицы вручную через SQL редактор Supabase")
            
    except Exception as e:
        logger.error(f"Ошибка при проверке/создании базовых таблиц: {str(e)}")

def skip_migrations():
    """Пропуск миграций и переход к приложению при проблемах с SQL API."""
    logger.warning("Пропуск миграций из-за ограничений Supabase SQL API в текущей среде")
    logger.info("Приложение продолжит работу, полагаясь на существующую структуру базы данных")
    # Здесь могут быть дополнительные действия, если необходимо

def get_executed_migrations() -> List[str]:
    """Получение списка уже выполненных миграций из таблицы _migrations."""
    logger.info("Получение списка выполненных миграций...")
    
    try:
        sql = "SELECT name FROM _migrations ORDER BY executed_at ASC;"
        success, result = execute_sql_query_direct(sql)
        
        if not success or not result:
            logger.error(f"Ошибка при получении выполненных миграций")
            return []
            
        executed_migrations = [row.get('name') for row in result]
        logger.info(f"Найдено {len(executed_migrations)} выполненных миграций")
        return executed_migrations
        
    except Exception as e:
        logger.error(f"Ошибка при получении выполненных миграций: {str(e)}")
        return []

def main():
    """Основная функция для запуска миграций."""
    logger.info("Запуск процесса миграции базы данных...")
    
    supabase = init_supabase()
    if not supabase:
        logger.error("Не удалось инициализировать Supabase. Миграции не будут применены.")
        return
    
    # Проверка доступа к базе данных
    logger.info("Проверка доступа к базе данных...")
    try:
        tables_result = supabase.table("suggested_ideas").select("id").limit(1).execute()
        logger.info(f"Успешное подключение к базе данных через Supabase клиент")
        db_accessible = True
    except Exception as e:
        logger.warning(f"Ошибка при проверке доступа к базе данных: {str(e)}")
        db_accessible = False
    
    # Проверяем наличие функции exec_sql
    has_exec_sql = check_exec_sql_function(supabase)
    
    if not has_exec_sql:
        logger.warning("Функция exec_sql не найдена, попытка создать её")
        if create_exec_sql_function(supabase):
            logger.info("Функция exec_sql успешно создана")
        else:
            logger.warning("Не удалось создать функцию exec_sql, продолжаем без неё")
    
    # Если таблицы не доступны, но есть функция exec_sql, создаем базовые таблицы
    if not db_accessible and has_exec_sql:
        create_base_tables_directly()
    # Если есть доступ к таблицам, но нет функции exec_sql, скипаем миграции
    elif db_accessible and not has_exec_sql:
        logger.info("Таблицы доступны, но функция exec_sql недоступна. Пропускаем миграции.")
        skip_migrations()
    else:
        # Запускаем миграции, если есть доступ к таблицам или функция exec_sql
        run_migrations(supabase)
    
    logger.info("Процесс миграции завершен.")

if __name__ == "__main__":
    main() 