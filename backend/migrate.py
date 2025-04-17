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
    """Выполнение SQL запроса напрямую через RPC API."""
    try:
        logger.info(f"Выполнение SQL запроса напрямую: {sql_query[:50]}...")
        
        # Получаем данные из переменных окружения
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
        
        # Стандартное выполнение через exec_sql
        response = requests.post(url, json={"query": sql_query}, headers=headers)
        
        if response.status_code in [200, 201, 204]:
            logger.info("SQL запрос выполнен успешно через RPC")
            return True
        else:
            logger.warning(f"Ошибка при выполнении SQL запроса через RPC: {response.status_code} - {response.text}")
            
            # Пробуем через Supabase клиент напрямую
            try:
                result = supabase.rpc("exec_sql", {"query": sql_query}).execute()
                logger.info("SQL запрос выполнен успешно через Supabase клиент")
                return True
            except Exception as e:
                logger.error(f"Ошибка при выполнении SQL запроса через Supabase клиент: {str(e)}")
                return False
    except Exception as e:
        logger.error(f"Исключение при выполнении SQL запроса: {str(e)}")
        return False

def execute_sql_query_direct(supabase: Client, sql_query: str) -> List[Dict[str, Any]]:
    """Выполнение SQL запроса напрямую через RPC API и возврат результатов."""
    try:
        logger.info(f"Выполнение SQL запроса с возвратом результатов: {sql_query[:50]}...")
        
        # Получаем данные из переменных окружения
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
            return []
        
        # Пробуем через клиент Supabase напрямую
        try:
            result = supabase.rpc("exec_sql_array_json", {"query": sql_query}).execute()
            if result and hasattr(result, 'data'):
                logger.info("SQL запрос выполнен успешно через Supabase клиент")
                return result.data
            else:
                logger.warning("Нет данных в ответе от exec_sql_array_json")
        except Exception as e:
            logger.warning(f"Ошибка при выполнении SQL запроса через Supabase клиент: {str(e)}")
            # Продолжаем выполнение и пробуем другой метод
        
        # Используем только RPC API с функцией exec_sql_array_json
        url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        # Если функция exec_sql_array_json не существует, создаем её
        try:
            # Проверяем наличие функции exec_sql_array_json
            create_query = """
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
            create_response = supabase.rpc("exec_sql", {"query": create_query}).execute()
            logger.info("Функция exec_sql_array_json создана/обновлена")
        except Exception as e:
            logger.warning(f"Ошибка при создании функции exec_sql_array_json: {str(e)}")
        
        # Пробуем выполнить запрос через RPC
        try:
            response = requests.post(url, json={"query": sql_query}, headers=headers)
            
            if response.status_code == 200:
                logger.info("SQL запрос выполнен успешно через RPC exec_sql_array_json")
                return response.json()
            else:
                logger.warning(f"Ошибка при выполнении SQL запроса через RPC exec_sql_array_json: {response.status_code} - {response.text}")
                
                # Если не работает exec_sql_array_json, пробуем exec_sql_json
                url2 = f"{supabase_url}/rest/v1/rpc/exec_sql_json"
                response2 = requests.post(url2, json={"query": sql_query}, headers=headers)
                
                if response2.status_code == 200:
                    logger.info("SQL запрос выполнен успешно через RPC exec_sql_json")
                    return response2.json()
                else:
                    logger.error(f"Ошибка при выполнении SQL запроса через RPC exec_sql_json: {response2.status_code} - {response2.text}")
                    return []
        except Exception as e:
            logger.error(f"Ошибка при выполнении SQL запроса через RPC: {str(e)}")
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

def run_migrations(supabase: Client) -> bool:
    """Запуск миграций"""
    try:
        # Получаем список файлов миграций
        migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")
        migration_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
        
        if not migration_files:
            logger.warning(f"Файлы миграций не найдены в {migrations_dir}")
            return False
            
        logger.info(f"Найдено {len(migration_files)} файлов миграций")
        
        # Получаем список уже выполненных миграций
        executed_migrations = get_executed_migrations(supabase)
        
        # Применяем миграции по порядку
        for migration_file in migration_files:
            file_name = os.path.basename(migration_file)
            
            if file_name in executed_migrations:
                logger.info(f"Миграция {file_name} уже применена, пропускаем")
                continue
                
            logger.info(f"Выполнение миграции {file_name}")
            
            try:
                with open(migration_file, 'r', encoding='utf-8') as f:
                    sql_content = f.read()
                
                # Проверяем, содержит ли миграция блоки DO
                if "DO $$" in sql_content or "DO $" in sql_content:
                    # Для миграций с блоками DO используем специальный обработчик
                    success = execute_do_blocks_migration(supabase, sql_content)
                else:
                    # Парсим SQL контент на отдельные команды для обычных миграций
                    commands = parse_sql_commands(sql_content)
                    
                    # Выполняем каждую команду отдельно
                    success = execute_commands_batch(supabase, commands)
                
                if success:
                    logger.info(f"Миграция {file_name} успешно выполнена")
                    # Записываем информацию о выполненной миграции
                    record_migration_execution(supabase, file_name)
                else:
                    logger.error(f"Ошибка при выполнении миграции {file_name}")
                    return False
                    
            except Exception as e:
                logger.error(f"Исключение при применении миграции {file_name}: {str(e)}")
                return False
        
        logger.info("Все миграции успешно выполнены")
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске миграций: {str(e)}")
        return False

def execute_do_blocks_migration(supabase: Client, sql_content: str) -> bool:
    """Выполнение миграции с блоками DO"""
    try:
        logger.info("Выполнение миграции с блоками DO...")
        
        # Разбиваем файл миграции на отдельные команды
        commands = []
        lines = sql_content.splitlines()
        current_command = ""
        in_do_block = False
        in_function_def = False
        
        for line in lines:
            line_stripped = line.strip()
            
            # Пропускаем пустые строки и комментарии вне блоков
            if not in_do_block and not in_function_def and (not line_stripped or line_stripped.startswith('--')):
                continue
                
            # Начало блока DO
            if line_stripped.startswith('DO '):
                in_do_block = True
                current_command = line + "\n"
                continue
                
            # Начало определения функции
            if line_stripped.startswith('CREATE OR REPLACE FUNCTION'):
                in_function_def = True
                current_command = line + "\n"
                continue
                
            # Внутри блока DO или определения функции
            if in_do_block or in_function_def:
                current_command += line + "\n"
                
                # Конец блока DO
                if in_do_block and line_stripped.endswith('$$;'):
                    in_do_block = False
                    commands.append(current_command)
                    current_command = ""
                    continue
                
                # Конец определения функции
                if in_function_def and line_stripped == '$$;':
                    in_function_def = False
                    commands.append(current_command)
                    current_command = ""
                    continue
            
            # Обычные SQL команды
            elif line_stripped.endswith(';'):
                commands.append(line)
        
        # Добавляем последнюю команду, если она есть
        if current_command:
            commands.append(current_command)
        
        # Выполняем все команды по порядку
        for i, command in enumerate(commands):
            if not command.strip():
                continue
                
            logger.info(f"Выполнение команды {i+1}/{len(commands)}...")
            
            result = execute_sql_direct(supabase, command)
            if not result:
                logger.error(f"Ошибка при выполнении команды {i+1}")
                return False
                
        return True
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграции с блоками DO: {str(e)}")
        return False

def execute_commands_batch(supabase: Client, commands: list) -> bool:
    """Выполнение набора команд SQL"""
    success = True
    
    for i, cmd in enumerate(commands):
        if not cmd.strip():
            continue
            
        # Пропускаем команды создания функций, которые мы уже создали
        if "CREATE OR REPLACE FUNCTION exec_sql" in cmd:
            logger.info("Пропуск создания функции exec_sql, так как она уже создана")
            continue
        
        # Блоки BEGIN-END обрабатываем особым образом
        if "BEGIN" in cmd and "END" in cmd:
            inner_commands = extract_commands_from_block(cmd)
            block_success = True
            
            for inner_cmd in inner_commands:
                if not inner_cmd.strip():
                    continue
                    
                inner_result = execute_sql_direct(supabase, inner_cmd)
                if not inner_result:
                    logger.error(f"Ошибка при выполнении команды внутри блока BEGIN-END: {inner_cmd[:50]}...")
                    block_success = False
                    break
                    
            if not block_success:
                success = False
                break
        else:
            # Обычные команды
            result = execute_sql_direct(supabase, cmd)
            if not result:
                logger.error(f"Ошибка при выполнении команды: {cmd[:50]}...")
                success = False
                break
    
    return success

def parse_sql_commands(sql_content: str) -> list:
    """Разбор SQL скрипта на отдельные команды"""
    commands = []
    current_command = ""
    in_function_body = False
    in_do_block = False
    
    for line in sql_content.splitlines():
        line = line.strip()
        
        # Пропускаем пустые строки и комментарии
        if not line or line.startswith('--'):
            continue
            
        # Отслеживаем начало блоков DO
        if line.startswith("DO $$") or line.startswith("DO $"):
            in_do_block = True
            current_command += line + "\n"
            continue
            
        # Обрабатываем блоки DO
        if in_do_block:
            current_command += line + "\n"
            if "END $$;" in line or "END $;" in line:
                in_do_block = False
                commands.append(current_command)
                current_command = ""
            continue
            
        # Отслеживаем функции
        if ("CREATE OR REPLACE FUNCTION" in line or "CREATE FUNCTION" in line) and not in_function_body:
            in_function_body = True
            current_command += line + "\n"
            continue
            
        if in_function_body:
            current_command += line + "\n"
            if ("$$;" in line or "LANGUAGE " in line) and ";" in line:
                in_function_body = False
                commands.append(current_command)
                current_command = ""
            continue
            
        # Обычные SQL команды
        current_command += line + "\n"
        if line.endswith(';') and not in_function_body and not in_do_block:
            commands.append(current_command)
            current_command = ""
    
    # Добавляем последнюю команду, если она осталась
    if current_command.strip():
        commands.append(current_command)
        
    return commands

def extract_commands_from_block(block_content: str) -> list:
    """Извлекаем команды из блока DO $$ BEGIN-END $$"""
    # Для блоков DO $$ ... $$ лучше не извлекать команды, а выполнять их целиком
    if "DO $$" in block_content or "DO $" in block_content:
        # Просто возвращаем весь блок как одну команду
        logger.info("Обнаружен блок DO $$, выполняем его целиком")
        return [block_content.strip()]
        
    # Для обычных блоков BEGIN-END
    begin_idx = block_content.find("BEGIN")
    end_idx = block_content.rfind("END")
    
    if begin_idx == -1 or end_idx == -1 or begin_idx >= end_idx:
        return []
        
    inner_content = block_content[begin_idx + 5:end_idx].strip()
    
    # Разбиваем на отдельные команды
    commands = []
    current_cmd = ""
    
    for line in inner_content.split('\n'):
        line = line.strip()
        if not line or line.startswith('--'):
            continue
            
        current_cmd += line + " "
        if line.endswith(';'):
            commands.append(current_cmd.strip())
            current_cmd = ""
            
    # Добавляем последнюю команду, если она осталась
    if current_cmd.strip():
        commands.append(current_cmd.strip())
        
    return commands

def get_executed_migrations(supabase: Client) -> list:
    """
    Получение списка имен уже выполненных миграций
    """
    try:
        logger.info("Получение списка выполненных миграций...")
        
        executed_migrations = []
        
        result = execute_sql_query_direct(
            supabase,
            "SELECT name FROM _migrations"
        )
        
        if result and isinstance(result, list):
            for item in result:
                if isinstance(item, dict) and "name" in item:
                    executed_migrations.append(item["name"])
                    
        logger.info(f"Найдено {len(executed_migrations)} выполненных миграций")
        return executed_migrations
    except Exception as e:
        logger.warning(f"Ошибка при получении списка выполненных миграций: {str(e)}")
        return []

def record_migration(supabase: Client, migration_name: str, success: bool):
    """
    Записывает информацию о выполненной миграции в таблицу _migrations
    """
    try:
        # Проверяем структуру таблицы _migrations
        check_columns_sql = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = '_migrations'
        """
        columns_result = execute_sql_query_direct(supabase, check_columns_sql)
        
        # Получаем список колонок
        column_names = [col.get('column_name', '') for col in columns_result] if columns_result else []
        logger.info(f"Структура таблицы _migrations: {column_names}")
        
        success_value = "true" if success else "false"
        
        # Выбираем правильный формат SQL в зависимости от структуры таблицы
        if 'applied_at' in column_names:
            sql = f"""
            INSERT INTO _migrations (name, applied_at, success) 
            VALUES ('{migration_name}', NOW(), {success_value})
            """
        elif 'executed_at' in column_names:
            sql = f"""
            INSERT INTO _migrations (name, executed_at) 
            VALUES ('{migration_name}', extract(epoch from now())::bigint)
            """
        elif 'migration_name' in column_names:
            sql = f"""
            INSERT INTO _migrations (migration_name, executed_at) 
            VALUES ('{migration_name}', CURRENT_TIMESTAMP)
            """
        else:
            # Если ни одна из известных структур не подходит, используем минимальный вариант
            sql = f"""
            INSERT INTO _migrations (name) 
            VALUES ('{migration_name}')
            """
            
        execute_sql_direct(supabase, sql)
        status = "успешно" if success else "с ошибкой"
        logger.info(f"Миграция {migration_name} записана в журнал ({status})")
    except Exception as e:
        logger.error(f"Ошибка при записи информации о миграции {migration_name}: {str(e)}")
        # Не вызываем raise, чтобы миграция не прерывалась из-за ошибки записи

def check_migrations_table(supabase: Client) -> bool:
    """Проверка существования таблицы _migrations и создание её при необходимости"""
    try:
        logger.info("Проверка существования таблицы _migrations")
        
        # Проверяем существование таблицы
        table_exists = check_table_exists(supabase, "_migrations")
        
        if not table_exists:
            logger.info("Таблица _migrations не существует. Создание...")
            
            # Создаем таблицу для отслеживания миграций
            sql = """
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                executed_at BIGINT NOT NULL DEFAULT extract(epoch from now())::bigint,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_migrations_name ON _migrations(name);
            """
            
            result = execute_sql_direct(supabase, sql)
            
            if result:
                logger.info("Таблица _migrations успешно создана")
                return True
            else:
                logger.error("Не удалось создать таблицу _migrations")
                return False
        
        # Проверяем структуру таблицы _migrations
        columns_sql = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = '_migrations' AND table_schema = 'public';
        """
        
        columns_result = execute_sql_query_direct(supabase, columns_sql)
        
        columns = []
        if isinstance(columns_result, list):
            for item in columns_result:
                if isinstance(item, dict) and 'column_name' in item:
                    columns.append(item['column_name'])
        
        logger.info(f"Структура таблицы _migrations: {columns}")
        
        # Проверяем наличие поля executed_at и добавляем его, если оно отсутствует
        if 'executed_at' not in columns:
            logger.info("Поле executed_at отсутствует в таблице _migrations, добавляем...")
            
            add_column_sql = """
            ALTER TABLE _migrations 
            ADD COLUMN executed_at BIGINT NOT NULL DEFAULT extract(epoch from now())::bigint;
            """
            
            add_result = execute_sql_direct(supabase, add_column_sql)
            
            if add_result:
                logger.info("Поле executed_at успешно добавлено в таблицу _migrations")
            else:
                logger.error("Не удалось добавить поле executed_at в таблицу _migrations")
                return False
        
        logger.info("Таблица _migrations существует или успешно создана")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при проверке существования таблицы _migrations: {str(e)}")
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

def record_migration_execution(supabase: Client, migration_name: str) -> bool:
    """Запись информации о выполненной миграции"""
    try:
        logger.info(f"Запись информации о выполненной миграции: {migration_name}")
        
        sql = f"""
        INSERT INTO _migrations (name, executed_at) 
        VALUES ('{migration_name}', extract(epoch from now())::bigint);
        """
        
        result = execute_sql_direct(supabase, sql)
        
        if result:
            logger.info(f"Информация о миграции {migration_name} успешно записана")
            return True
        else:
            logger.error(f"Ошибка при записи информации о миграции {migration_name}")
            return False
    except Exception as e:
        logger.error(f"Исключение при записи информации о миграции: {str(e)}")
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