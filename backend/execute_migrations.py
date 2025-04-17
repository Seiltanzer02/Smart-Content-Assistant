#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Скрипт для выполнения SQL миграций в базе данных Supabase.
Поддерживает выполнение всех миграций, отдельной миграции или пользовательского SQL.
"""

import os
import sys
import argparse
import logging
from typing import Optional, Tuple, List, Dict, Any, Union
from datetime import datetime
from pathlib import Path

from supabase import create_client, Client
from dotenv import load_dotenv

from logger_config import setup_logger

# Инициализация логгера
logger = setup_logger("execute_migrations")

# Определение пути к директории миграций
MIGRATIONS_DIR = Path(__file__).parent / 'migrations'

def parse_args() -> argparse.Namespace:
    """
    Разбор аргументов командной строки.
    """
    parser = argparse.ArgumentParser(description='Выполнение SQL миграций в базе данных Supabase')
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--file', type=str, help='Имя файла миграции для выполнения')
    group.add_argument('--all', action='store_true', help='Выполнить все миграции')
    group.add_argument('--custom', type=str, help='Выполнить произвольный SQL запрос')
    
    parser.add_argument('--verbose', action='store_true', help='Подробный вывод логов')
    
    return parser.parse_args()

def init_supabase() -> Optional[Client]:
    """
    Инициализирует клиент Supabase, используя переменные окружения.
    
    Returns:
        Client: Клиент Supabase или None, если инициализация не удалась.
    """
    load_dotenv()
    
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_ANON_KEY")  # Изменено с SUPABASE_KEY на SUPABASE_ANON_KEY
    
    if not supabase_url or not supabase_key:
        logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
        return None
    
    try:
        supabase = create_client(supabase_url, supabase_key)
        logger.info("Supabase клиент успешно инициализирован")
        return supabase
    except Exception as e:
        logger.error(f"Ошибка при инициализации Supabase: {e}")
        return None

def execute_sql_direct(supabase: Client, sql: str) -> Optional[Dict[str, Any]]:
    """
    Выполняет SQL запрос напрямую через REST API Supabase.
    
    Args:
        supabase: Клиент Supabase
        sql: SQL запрос для выполнения
        
    Returns:
        Dict[str, Any]: Результат выполнения запроса или None в случае ошибки
    """
    try:
        # Используем exec_sql_array_json вместо exec_sql
        response = supabase.rpc('exec_sql_array_json', {"query": sql}).execute()
        
        # Проверка на ошибки в ответе
        if hasattr(response, 'data'):
            if isinstance(response.data, dict) and response.data.get('error'):
                error_info = response.data.get('error', {})
                error_message = error_info.get('message', 'Неизвестная ошибка')
                logger.error(f"Ошибка при выполнении SQL: {error_message}")
                return None
            return {"success": True, "data": response.data}
        return {"success": True}
    except Exception as e:
        logger.error(f"Ошибка при выполнении SQL через RPC: {e}")
        return None

def execute_sql_query_direct(supabase: Client, sql: str) -> Optional[List[Dict[str, Any]]]:
    """
    Выполняет SQL запрос, который возвращает данные, и возвращает результат.
    
    Args:
        supabase: Клиент Supabase
        sql: SQL запрос для выполнения
        
    Returns:
        List[Dict[str, Any]]: Результат выполнения запроса или None в случае ошибки
    """
    try:
        # Используем exec_sql_array_json вместо exec_sql
        response = supabase.rpc('exec_sql_array_json', {"query": sql}).execute()
        
        if not hasattr(response, 'data'):
            logger.error("Отсутствуют данные в ответе")
            return None
            
        # Для exec_sql_array_json возвращается прямой массив результатов
        result_data = response.data
        if result_data is None:
            return []
            
        # Если получили словарь с ошибкой
        if isinstance(result_data, dict) and result_data.get('error'):
            error_message = result_data.get('message', 'Неизвестная ошибка')
            logger.error(f"Ошибка при выполнении SQL запроса: {error_message}")
            return None
            
        # Возвращаем данные как список словарей
        return result_data if isinstance(result_data, list) else [result_data]
    except Exception as e:
        logger.error(f"Ошибка при выполнении SQL запроса через RPC: {e}")
        return None

def check_migrations_table(supabase: Client) -> bool:
    """
    Проверяет наличие таблицы _migrations и создает её, если она не существует.
    
    Args:
        supabase: Клиент Supabase
        
    Returns:
        bool: True, если таблица существует или была успешно создана, иначе False
    """
    logger.info("Проверка наличия таблицы _migrations")
    
    # Проверяем существование таблицы
    sql_check = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = '_migrations'
    ) as exists;
    """
    
    result = execute_sql_query_direct(supabase, sql_check)
    if result is None:
        logger.error("Не удалось проверить наличие таблицы _migrations")
        return False
    
    table_exists = result[0].get('exists', False) if result and len(result) > 0 else False
    
    if table_exists:
        logger.info("Таблица _migrations уже существует")
        return True
    
    # Создаем таблицу _migrations, если она не существует
    logger.info("Создание таблицы _migrations")
    sql_create = """
    CREATE TABLE IF NOT EXISTS _migrations (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_migrations_name ON _migrations(name);
    """
    
    result = execute_sql_direct(supabase, sql_create)
    if result is None:
        logger.error("Не удалось создать таблицу _migrations")
        return False
    
    logger.info("Таблица _migrations успешно создана")
    return True

def create_exec_sql_function(supabase: Client) -> bool:
    """
    Создает функцию exec_sql_array_json для выполнения произвольных SQL запросов, если она не существует.
    
    Args:
        supabase: Клиент Supabase
        
    Returns:
        bool: True, если функция существует или была успешно создана, иначе False
    """
    logger.info("Проверка наличия функции exec_sql_array_json")
    
    # Проверяем существование функции простым тестовым запросом
    test_sql = "SELECT 1 as test"
    test_result = execute_sql_query_direct(supabase, test_sql)
    
    if test_result is not None:
        logger.info("Функция exec_sql_array_json уже существует и работает")
        return True
    
    # Создаем функцию exec_sql_array_json, если она не существует
    logger.info("Создание функции exec_sql_array_json")
    sql_create = """
    CREATE OR REPLACE FUNCTION exec_sql_array_json(query text)
    RETURNS json
    LANGUAGE plpgsql
    SECURITY DEFINER
    AS $$
    DECLARE
        result json;
    BEGIN
        EXECUTE 'SELECT json_agg(t) FROM (' || query || ') AS t' INTO result;
        RETURN COALESCE(result, '[]'::json);
    EXCEPTION WHEN OTHERS THEN
        RETURN json_build_object(
            'error', true,
            'message', SQLERRM,
            'detail', SQLSTATE
        );
    END;
    $$;

    -- Устанавливаем права на функцию
    GRANT EXECUTE ON FUNCTION exec_sql_array_json(text) TO service_role;
    GRANT EXECUTE ON FUNCTION exec_sql_array_json(text) TO anon;
    GRANT EXECUTE ON FUNCTION exec_sql_array_json(text) TO authenticated;
    """
    
    # Создаем функцию напрямую через SQL API
    try:
        url = f"{os.environ.get('SUPABASE_URL')}/rest/v1/sql"
        import requests
        headers = {
            "apikey": os.environ.get("SUPABASE_ANON_KEY"),
            "Authorization": f"Bearer {os.environ.get('SUPABASE_ANON_KEY')}",
            "Content-Type": "application/json"
        }
        response = requests.post(url, json={"query": sql_create}, headers=headers)
        
        if response.status_code in [200, 201, 204]:
            logger.info("Функция exec_sql_array_json успешно создана через SQL API")
            return True
        else:
            logger.error(f"Ошибка при создании функции exec_sql_array_json через SQL API: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Исключение при создании функции exec_sql_array_json: {e}")
        return False

def is_migration_applied(supabase: Client, migration_name: str) -> bool:
    """
    Проверяет, была ли уже применена данная миграция.
    
    Args:
        supabase: Клиент Supabase
        migration_name: Имя файла миграции
        
    Returns:
        bool: True, если миграция уже применена, иначе False
    """
    sql = f"""
    SELECT EXISTS (
        SELECT FROM _migrations 
        WHERE name = '{migration_name}'
    ) as exists;
    """
    
    result = execute_sql_query_direct(supabase, sql)
    if result is None:
        logger.error(f"Не удалось проверить статус миграции {migration_name}")
        return False
    
    return result[0].get('exists', False) if result and len(result) > 0 else False

def record_migration(supabase: Client, migration_name: str) -> bool:
    """
    Записывает информацию о выполненной миграции в таблицу _migrations.
    
    Args:
        supabase: Клиент Supabase
        migration_name: Имя файла миграции
        
    Returns:
        bool: True, если запись успешно добавлена, иначе False
    """
    sql = f"""
    INSERT INTO _migrations (name)
    VALUES ('{migration_name}')
    ON CONFLICT (name) DO NOTHING;
    """
    
    result = execute_sql_direct(supabase, sql)
    if result is None:
        logger.error(f"Не удалось записать информацию о миграции {migration_name}")
        return False
    
    return True

def get_migration_files() -> List[str]:
    """
    Получает список всех файлов миграций в порядке их выполнения.
    
    Returns:
        List[str]: Список имен файлов миграций
    """
    if not MIGRATIONS_DIR.exists():
        logger.error(f"Директория миграций не найдена: {MIGRATIONS_DIR}")
        return []
    
    # Получаем все SQL файлы и сортируем их по имени
    migration_files = sorted([
        f.name for f in MIGRATIONS_DIR.glob('*.sql')
        if f.is_file() and f.name.endswith('.sql')
    ])
    
    return migration_files

def execute_single_migration(supabase: Client, migration_file: str) -> bool:
    """
    Выполняет отдельную миграцию.
    
    Args:
        supabase: Клиент Supabase
        migration_file: Имя файла миграции
        
    Returns:
        bool: True, если миграция успешно выполнена, иначе False
    """
    migration_path = MIGRATIONS_DIR / migration_file
    
    if not migration_path.exists():
        logger.error(f"Файл миграции не найден: {migration_path}")
        return False
    
    # Проверяем, была ли миграция уже применена
    if is_migration_applied(supabase, migration_file):
        logger.info(f"Миграция {migration_file} уже была применена")
        return True
    
    # Читаем содержимое файла миграции
    try:
        with open(migration_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
    except Exception as e:
        logger.error(f"Ошибка при чтении файла миграции {migration_file}: {e}")
        return False
    
    # Выполняем миграцию
    logger.info(f"Выполнение миграции {migration_file}")
    result = execute_sql_direct(supabase, sql_content)
    
    if result is None:
        logger.error(f"Ошибка при выполнении миграции {migration_file}")
        return False
    
    # Записываем информацию о выполненной миграции
    if not record_migration(supabase, migration_file):
        logger.error(f"Не удалось записать информацию о миграции {migration_file}")
        return False
    
    logger.info(f"Миграция {migration_file} успешно выполнена")
    return True

def execute_all_migrations(supabase: Client) -> bool:
    """
    Выполняет все миграции, которые еще не были применены.
    
    Args:
        supabase: Клиент Supabase
        
    Returns:
        bool: True, если все миграции успешно выполнены, иначе False
    """
    migration_files = get_migration_files()
    if not migration_files:
        logger.warning("Миграционные файлы не найдены")
        return True
    
    logger.info(f"Найдено {len(migration_files)} файлов миграций")
    
    success = True
    applied_count = 0
    skipped_count = 0
    failed_count = 0
    
    for migration_file in migration_files:
        # Проверяем, была ли миграция уже применена
        if is_migration_applied(supabase, migration_file):
            logger.info(f"Миграция {migration_file} уже была применена, пропускаем")
            skipped_count += 1
            continue
            
        # Если миграция не выполнена успешно, продолжаем, но отмечаем ошибку
        if execute_single_migration(supabase, migration_file):
            applied_count += 1
        else:
            logger.error(f"Не удалось выполнить миграцию {migration_file}")
            failed_count += 1
            success = False
    
    logger.info(f"Итого: выполнено {applied_count}, пропущено {skipped_count}, не удалось выполнить {failed_count}")
    return success

def execute_custom_sql(supabase: Client, sql: str) -> bool:
    """
    Выполняет произвольный SQL запрос.
    
    Args:
        supabase: Клиент Supabase
        sql: SQL запрос для выполнения
        
    Returns:
        bool: True, если запрос успешно выполнен, иначе False
    """
    logger.info("Выполнение пользовательского SQL запроса")
    
    result = execute_sql_direct(supabase, sql)
    if result is None:
        logger.error("Ошибка при выполнении пользовательского SQL запроса")
        return False
    
    # Если запрос возвращает данные, выводим их
    if 'data' in result:
        logger.info(f"Результат выполнения SQL запроса: {result['data']}")
    
    logger.info("Пользовательский SQL запрос успешно выполнен")
    return True

def main() -> int:
    """
    Основная функция скрипта.
    
    Returns:
        int: Код возврата (0 - успех, 1 - ошибка)
    """
    try:
        # Разбор аргументов командной строки
        args = None
        try:
            args = parse_args()
        except SystemExit:
            # Если аргументы не переданы, выполняем все миграции по умолчанию
            logger.info("Аргументы не переданы, выполняем все миграции по умолчанию")
            
        # Устанавливаем уровень логирования
        if args and args.verbose:
            logger.setLevel(logging.DEBUG)
        
        # Инициализация Supabase
        supabase = init_supabase()
        if not supabase:
            return 1
        
        # Проверка наличия таблицы _migrations
        if not check_migrations_table(supabase):
            return 1
        
        # Создание функции exec_sql_array_json
        if not create_exec_sql_function(supabase):
            return 1
        
        # Выполнение миграций в зависимости от аргументов
        if not args or args.all:
            logger.info("Запуск всех миграций")
            if not execute_all_migrations(supabase):
                return 1
        elif args.file:
            logger.info(f"Запуск отдельной миграции: {args.file}")
            if not execute_single_migration(supabase, args.file):
                return 1
        elif args.custom:
            logger.info("Выполнение пользовательского SQL запроса")
            if not execute_custom_sql(supabase, args.custom):
                return 1
        
        logger.info("Выполнение миграций завершено успешно")
        return 0
    except Exception as e:
        import traceback
        logger.error(f"Непредвиденная ошибка: {e}")
        logger.debug(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main()) 