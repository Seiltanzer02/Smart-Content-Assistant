#!/usr/bin/env python
"""
Скрипт для применения миграций к базе данных Supabase.
"""

import os
import logging
import sys
import json
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
import glob
import time
from typing import List, Optional, Tuple, Dict, Any, Union
from os.path import dirname, abspath, join, basename

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

def execute_sql_direct(supabase: Client, sql_query: str) -> bool:
    """Выполнение SQL запроса напрямую через REST API."""
    try:
        logger.info(f"Выполнение SQL запроса напрямую: {sql_query[:50]}...")
        
        # Получаем данные из переменных окружения
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
            return False
        
        # Проверяем наличие функции exec_sql
        check_sql = """
        SELECT EXISTS (
            SELECT FROM pg_proc 
            WHERE proname = 'exec_sql' 
            AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        ) as exists;
        """
        
        # Прямой запрос к базе данных через REST API
        url = f"{supabase_url}/rest/v1/rpc/exec_sql"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        # Сначала проверяем наличие функции exec_sql
        test_response = requests.post(url, json={"query": check_sql}, headers=headers)
        
        # Если функция не существует и мы пытаемся её создать
        if test_response.status_code != 200 and "CREATE OR REPLACE FUNCTION exec_sql" in sql_query:
            logger.info("Создаем функцию exec_sql напрямую через SQL запрос...")
            
            # Используем прямой SQL API для создания функции
            sql_url = f"{supabase_url}/rest/v1/sql"
            sql_headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
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
            sql_url = f"{supabase_url}/rest/v1/sql"
            sql_headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
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

def execute_sql_query_direct(supabase: Client, sql_query: str) -> List[Dict[str, Any]]:
    """Выполнение SQL запроса напрямую через REST API и возврат результатов."""
    try:
        logger.info(f"Выполнение SQL запроса с возвратом результатов: {sql_query[:50]}...")
        
        # Получаем данные из переменных окружения
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
            return []
        
        # Проверяем наличие функции exec_sql
        check_sql = """
        SELECT EXISTS (
            SELECT FROM pg_proc 
            WHERE proname = 'exec_sql' 
            AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        ) as exists;
        """
        
        # Прямой запрос к базе данных через REST API
        url = f"{supabase_url}/rest/v1/rpc/exec_sql"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        # Сначала проверяем наличие функции exec_sql
        test_response = requests.post(url, json={"query": check_sql}, headers=headers)
        
        # Если функция не существует, используем прямой SQL API
        if test_response.status_code != 200:
            logger.warning("Функция exec_sql не найдена, используем прямой SQL API")
            sql_url = f"{supabase_url}/rest/v1/sql"
            sql_headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
            
            sql_response = requests.post(sql_url, json={"query": sql_query}, headers=sql_headers)
            
            if sql_response.status_code == 200:
                logger.info("SQL запрос выполнен успешно через прямой SQL API")
                return sql_response.json()
            else:
                logger.error(f"Ошибка при выполнении SQL запроса через прямой SQL API: {sql_response.status_code} - {sql_response.text}")
                return []
        
        # Стандартное выполнение через exec_sql если функция существует
        response = requests.post(url, json={"query": sql_query}, headers=headers)
        
        if response.status_code == 200:
            logger.info("SQL запрос выполнен успешно")
            return response.json()
        else:
            # Если ошибка, пробуем через прямой SQL API
            logger.warning(f"Ошибка при выполнении SQL запроса через exec_sql: {response.status_code} - {response.text}")
            
            sql_url = f"{supabase_url}/rest/v1/sql"
            sql_headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
            
            sql_response = requests.post(sql_url, json={"query": sql_query}, headers=sql_headers)
            
            if sql_response.status_code == 200:
                logger.info("SQL запрос выполнен успешно через прямой SQL API")
                return sql_response.json()
            else:
                logger.error(f"Ошибка при выполнении SQL запроса: {sql_response.status_code} - {sql_response.text}")
                return []
    except Exception as e:
        logger.error(f"Исключение при выполнении SQL запроса: {str(e)}")
        return []

def check_table_exists(supabase: Client, table_name: str) -> bool:
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
        
        result = execute_sql_query_direct(supabase, sql)
        
        if not result:
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

def run_migrations(supabase: Client):
    """
    Ищет и применяет все SQL миграции из директории migrations
    """
    try:
        # Проверяем таблицу миграций
        if not check_migrations_table(supabase):
            logger.error("Не удалось проверить/создать таблицу миграций, останавливаем процесс миграции")
            return
        
        # Получаем список уже выполненных миграций
        executed_migrations = get_executed_migrations(supabase)
        logger.info(f"Найдено {len(executed_migrations)} выполненных миграций")
        
        # Находим все файлы миграций
        migration_files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "migrations", "*.sql")))
        logger.info(f"Найдено {len(migration_files)} файлов миграций")
        
        # Применяем только новые миграции
        for migration_file in migration_files:
            migration_name = os.path.basename(migration_file)
            
            # Пропускаем уже выполненные миграции
            if migration_name in executed_migrations:
                logger.info(f"Миграция {migration_name} уже выполнена, пропускаем")
                continue
            
            logger.info(f"Применение миграции: {migration_name}")
            
            try:
                # Читаем содержимое файла миграции
                with open(migration_file, 'r', encoding='utf-8') as f:
                    sql_query = f.read()
                
                # Выполняем миграцию
                result = execute_sql_direct(supabase, sql_query)
                success = result is not None
                
                # Записываем информацию о выполненной миграции
                record_migration(supabase, migration_name, success)
                
                if success:
                    logger.info(f"Миграция {migration_name} успешно применена")
                else:
                    logger.error(f"Миграция {migration_name} не была применена успешно")
            except Exception as e:
                logger.error(f"Ошибка при применении миграции {migration_name}: {str(e)}")
                record_migration(supabase, migration_name, False)
                raise
        
        logger.info("Все миграции успешно применены")
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграций: {str(e)}")
        raise

def get_executed_migrations(supabase: Client):
    """
    Получает список уже выполненных миграций из таблицы _migrations
    """
    try:
        result = execute_sql_query_direct(supabase, "SELECT name FROM _migrations WHERE success = true ORDER BY applied_at")
        
        # Преобразуем результат в список имен миграций
        if result and isinstance(result, list):
            return [row.get('name', '') for row in result]
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении списка выполненных миграций: {str(e)}")
        return []

def record_migration(supabase: Client, migration_name: str, success: bool):
    """
    Записывает информацию о выполненной миграции в таблицу _migrations
    """
    success_value = "true" if success else "false"
    sql = f"""
    INSERT INTO _migrations (name, applied_at, success) 
    VALUES ('{migration_name}', NOW(), {success_value})
    """
    try:
        execute_sql_direct(supabase, sql)
        status = "успешно" if success else "с ошибкой"
        logger.info(f"Миграция {migration_name} записана в журнал ({status})")
    except Exception as e:
        logger.error(f"Ошибка при записи информации о миграции {migration_name}: {str(e)}")
        raise

def check_migrations_table(supabase: Client) -> bool:
    """Проверка существования таблицы _migrations и создание ее при отсутствии."""
    try:
        logger.info("Проверка существования таблицы _migrations")
        
        table_exists = check_table_exists(supabase, "_migrations")
        
        if not table_exists:
            logger.info("Таблица _migrations не существует. Создание...")
            sql = """
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                success BOOLEAN NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_migrations_name ON _migrations(name);
            """
            
            result = execute_sql_direct(supabase, sql)
            
            if not result:
                logger.error("Не удалось создать таблицу _migrations")
                return False
                
            logger.info("Таблица _migrations успешно создана")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при проверке/создании таблицы _migrations: {str(e)}")
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

def check_exec_sql_function(supabase: Client) -> bool:
    """Проверка наличия функции exec_sql в базе данных."""
    try:
        logger.info("Проверка существования функции exec_sql...")
        
        # Получаем данные из переменных окружения
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
            return False
            
        # Проверяем через прямой SQL-запрос
        sql = """
        SELECT EXISTS (
            SELECT FROM pg_proc 
            WHERE proname = 'exec_sql' 
            AND pg_function_is_visible(oid)
        ) as exists;
        """
        
        # Пробуем выполнить проверочный запрос
        try:
            # Проверяем через SQL API
            sql_url = f"{supabase_url}/rest/v1/sql"
            sql_headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
            
            sql_response = requests.post(sql_url, json={"query": sql}, headers=sql_headers)
            
            if sql_response.status_code == 200:
                result = sql_response.json()
                if result and len(result) > 0:
                    exists = result[0].get('exists', False)
                    if exists:
                        logger.info("Функция exec_sql существует")
                        return True
                    else:
                        logger.info("Функция exec_sql не существует")
                        return False
                        
            # Если проверка через SQL API не сработала, пробуем через RPC
            url = f"{supabase_url}/rest/v1/rpc/exec_sql"
            headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            
            # Пытаемся вызвать функцию с тестовым запросом
            test_response = requests.post(url, json={"query": "SELECT 1"}, headers=headers)
            
            if test_response.status_code in [200, 201, 204]:
                logger.info("Функция exec_sql существует и работает")
                return True
            else:
                logger.info(f"Проверка функции exec_sql через RPC неудачна: {test_response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"Ошибка при проверке функции exec_sql: {str(e)}")
            return False
            
    except Exception as e:
        logger.warning(f"Ошибка при проверке функции exec_sql: {str(e)}")
        return False

def create_exec_sql_function(supabase: Client) -> bool:
    """Создание функции exec_sql для выполнения SQL запросов"""
    try:
        logger.info("Создание функции exec_sql...")
        
        # Получаем данные из переменных окружения
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
            return False
        
        # SQL для создания функции
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
        
        # Создаем функцию напрямую через SQL API
        sql_url = f"{supabase_url}/rest/v1/sql"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        response = requests.post(sql_url, json={"query": sql}, headers=headers)
        
        if response.status_code in [200, 201, 204]:
            logger.info("Функция exec_sql успешно создана")
            return True
        else:
            logger.error(f"Ошибка при создании функции exec_sql: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Исключение при создании функции exec_sql: {str(e)}")
        return False

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
    
    # Проверяем наличие функции exec_sql и создаем её, если необходимо
    has_exec_sql = check_exec_sql_function(supabase)
    
    if not has_exec_sql:
        logger.warning("Функция exec_sql не найдена, попытка создать её")
        if create_exec_sql_function(supabase):
            logger.info("Функция exec_sql успешно создана")
            has_exec_sql = True  # Обновляем статус
        else:
            logger.warning("Не удалось создать функцию exec_sql, продолжаем без неё")
    
    # Создаем таблицу миграций, если она не существует
    if has_exec_sql:
        logger.info("Проверка наличия таблицы _migrations...")
        if check_migrations_table(supabase):
            logger.info("Таблица _migrations существует или успешно создана")
        else:
            logger.warning("Не удалось проверить/создать таблицу _migrations")
            
    # Если у нас есть доступ к таблицам и функция exec_sql создана, запускаем миграции
    if db_accessible and has_exec_sql:
        run_migrations(supabase)
    # Если есть доступ к таблицам, но нет функции exec_sql, скипаем миграции
    elif db_accessible and not has_exec_sql:
        logger.info("Таблицы доступны, но функция exec_sql недоступна. Пропускаем миграции.")
        skip_migrations()
    # Если нет доступа к таблицам, пробуем создать их напрямую
    elif not db_accessible and has_exec_sql:
        create_base_tables_directly()
    else:
        logger.warning("Нет доступа к таблицам и функция exec_sql недоступна. Миграции не будут применены.")
    
    logger.info("Процесс миграции завершен.")

if __name__ == "__main__":
    main() 