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

def execute_sql_direct(sql: str) -> bool:
    """Выполнение SQL напрямую через SQL API Supabase."""
    try:
        url = f"{os.getenv('SUPABASE_URL')}/rest/v1/sql"
        headers = {
            "apikey": os.getenv("SUPABASE_ANON_KEY"),
            "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
            "Content-Type": "text/plain",  # Для SQL API нужен text/plain
            "Prefer": "return=minimal"
        }
        
        logger.info(f"Выполнение SQL напрямую через {url}")
        response = requests.post(url, data=sql, headers=headers)
        
        if response.status_code == 200:
            logger.info(f"SQL запрос успешно выполнен напрямую через SQL API")
            return True
        else:
            logger.error(f"Ошибка выполнения SQL напрямую: {response.status_code} - {response.text}")
            logger.error(f"Содержимое ответа: {response.content}")
            # Логирование заголовков для отладки
            logger.error(f"Заголовки ответа: {dict(response.headers)}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при прямом выполнении SQL: {str(e)}")
        return False

def execute_sql_query_direct(sql: str) -> Tuple[bool, List[Dict[str, Any]]]:
    """Выполнение SQL-запроса напрямую через SQL API Supabase с возвратом результатов."""
    try:
        url = f"{os.getenv('SUPABASE_URL')}/rest/v1/sql"
        headers = {
            "apikey": os.getenv("SUPABASE_ANON_KEY"),
            "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
            "Content-Type": "text/plain",
            "Accept": "application/json"  # Ожидаем JSON в ответе
        }
        
        logger.info(f"Выполнение SQL-запроса с возвратом данных через {url}")
        response = requests.post(url, data=sql, headers=headers)
        
        if response.status_code == 200:
            try:
                results = response.json()
                logger.info(f"SQL-запрос успешно выполнен, получено {len(results)} строк")
                return True, results
            except json.JSONDecodeError:
                logger.error(f"Не удалось декодировать JSON из ответа: {response.text}")
                return False, []
        else:
            logger.error(f"Ошибка выполнения SQL-запроса: {response.status_code} - {response.text}")
            return False, []
    except Exception as e:
        logger.error(f"Ошибка при выполнении SQL-запроса: {str(e)}")
        return False, []

def check_table_exists(table_name: str) -> bool:
    """Проверка существования таблицы в базе данных."""
    sql = f"""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = '{table_name}'
    ) as exists;
    """
    
    success, results = execute_sql_query_direct(sql)
    if success and results and len(results) > 0:
        exists = results[0].get('exists', False)
        logger.info(f"Таблица {table_name} {'существует' if exists else 'не существует'}")
        return exists
    
    logger.warning(f"Не удалось проверить существование таблицы {table_name}")
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
        if not check_table_exists('_migrations'):
            logger.warning("Таблица _migrations не существует, создаём...")
            if not create_migrations_table():
                logger.error("Не удалось создать таблицу _migrations, миграции могут не отслеживаться корректно")
        
        exec_sql_available = check_exec_sql_function(supabase)
        
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
                    if execute_sql_direct(sql_content):
                        logger.info(f"Миграция успешно применена напрямую: {file_name}")
                        migration_applied = True
                    else:
                        logger.error(f"Не удалось применить миграцию: {file_name}")
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
    sql = f"""
    INSERT INTO _migrations (name, executed_at)
    VALUES ('{migration_name}', {int(time.time())})
    ON CONFLICT (name) DO NOTHING;
    """
    
    return execute_sql_direct(sql)

def check_exec_sql_function(supabase: Client) -> bool:
    """Проверка наличия функции exec_sql в базе данных."""
    try:
        # Прямой запрос через REST API для проверки существования функции
        url = f"{os.getenv('SUPABASE_URL')}/rest/v1/rpc/exec_sql"
        headers = {
            "apikey": os.getenv("SUPABASE_ANON_KEY"),
            "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY')}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        # Простой запрос, который должен выполниться без ошибок, если функция существует
        test_query = "SELECT 1 as test"
        response = requests.post(url, json={"query": test_query}, headers=headers)
        
        if response.status_code == 200:
            logger.info("Функция exec_sql существует и доступна")
            return True
        else:
            logger.warning(f"Функция exec_sql недоступна: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при проверке функции exec_sql: {str(e)}")
        return False

def create_exec_sql_function() -> bool:
    """Создание функции exec_sql через прямой SQL-запрос."""
    try:
        # SQL для создания функции exec_sql
        sql = """
        CREATE OR REPLACE FUNCTION exec_sql(query text) RETURNS void AS $$
        BEGIN
            EXECUTE query;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        """
        
        return execute_sql_direct(sql)
    except Exception as e:
        logger.error(f"Ошибка при создании функции exec_sql: {str(e)}")
        return False

def main():
    """Основная функция для запуска миграций."""
    logger.info("Запуск процесса миграции базы данных...")
    
    supabase = init_supabase()
    if not supabase:
        logger.error("Не удалось инициализировать Supabase. Миграции не будут применены.")
        return
    
    # Проверяем доступность SQL API
    logger.info("Проверка доступности SQL API...")
    sql_test = "SELECT version();"
    if execute_sql_direct(sql_test):
        logger.info("SQL API доступен и работает")
    else:
        logger.warning("SQL API недоступен или ограничен. Миграции могут не примениться корректно.")
    
    # Проверяем наличие функции exec_sql
    has_exec_sql = check_exec_sql_function(supabase)
    
    # Если нет функции exec_sql, пробуем создать её напрямую
    if not has_exec_sql:
        logger.warning("Функция exec_sql не найдена, попытка создать её напрямую")
        if create_exec_sql_function():
            logger.info("Функция exec_sql успешно создана напрямую")
        else:
            logger.warning("Не удалось создать функцию exec_sql напрямую, продолжаем без неё")
    
    # Создаем базовые таблицы напрямую, если функции exec_sql не существует
    if not has_exec_sql:
        create_base_tables_directly()
    
    # Запускаем миграции
    run_migrations(supabase)
    
    logger.info("Процесс миграции завершен.")

def create_base_tables_directly():
    """Создание базовых таблиц напрямую через SQL API."""
    logger.info("Попытка создать базовые таблицы напрямую...")
    
    # Создаем расширение uuid-ossp
    extension_sql = """
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    """
    
    if execute_sql_direct(extension_sql):
        logger.info("Расширение uuid-ossp успешно создано или уже существует")
    else:
        logger.warning("Не удалось создать расширение uuid-ossp")
    
    # Создаем функцию для обновления временной метки
    func_sql = """
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = now();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
    
    if execute_sql_direct(func_sql):
        logger.info("Функция update_updated_at_column успешно создана")
    else:
        logger.warning("Не удалось создать функцию update_updated_at_column")
    
    # SQL для создания базовых таблиц
    sql = """
    -- Таблица для хранения изображений
    CREATE TABLE IF NOT EXISTS saved_images (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        url TEXT NOT NULL,
        preview_url TEXT,
        alt TEXT,
        author TEXT,
        author_url TEXT,
        source TEXT DEFAULT 'unsplash',
        local_path TEXT,
        description TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Таблица для хранения анализа каналов
    CREATE TABLE IF NOT EXISTS channel_analysis (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id TEXT NOT NULL,
        channel_name TEXT NOT NULL,
        themes JSONB,
        styles JSONB,
        analyzed_posts_count INTEGER DEFAULT 0,
        sample_posts JSONB,
        best_posting_time TEXT,
        is_sample_data BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
    );
    
    -- Таблица для хранения предложенных идей
    CREATE TABLE IF NOT EXISTS suggested_ideas (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id TEXT NOT NULL,
        channel_name TEXT,
        topic_idea TEXT NOT NULL,
        format_style TEXT,
        relative_day INTEGER DEFAULT 0,
        is_detailed BOOLEAN DEFAULT FALSE,
        status TEXT DEFAULT 'new',
        cleaned_title TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
    );
    
    -- Таблица для хранения постов
    CREATE TABLE IF NOT EXISTS saved_posts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id TEXT NOT NULL,
        channel_name TEXT,
        topic_idea TEXT NOT NULL,
        format_style TEXT,
        final_text TEXT,
        image_url TEXT,
        images_ids TEXT[],
        target_date DATE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
    );
    
    -- Таблица для хранения связей между постами и изображениями
    CREATE TABLE IF NOT EXISTS post_images (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        post_id UUID REFERENCES saved_posts(id) ON DELETE CASCADE,
        image_id TEXT REFERENCES saved_images(id) ON DELETE SET NULL,
        user_id TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
        UNIQUE(post_id, image_id)
    );
    
    -- Индексы для таблиц
    CREATE INDEX IF NOT EXISTS idx_saved_images_user_id ON saved_images(user_id);
    CREATE INDEX IF NOT EXISTS idx_channel_analysis_user_id ON channel_analysis(user_id);
    CREATE INDEX IF NOT EXISTS idx_channel_analysis_channel_name ON channel_analysis(channel_name);
    CREATE INDEX IF NOT EXISTS idx_suggested_ideas_user_id ON suggested_ideas(user_id);
    CREATE INDEX IF NOT EXISTS idx_suggested_ideas_channel_name ON suggested_ideas(channel_name);
    CREATE INDEX IF NOT EXISTS idx_saved_posts_user_id ON saved_posts(user_id);
    CREATE INDEX IF NOT EXISTS idx_saved_posts_channel_name ON saved_posts(channel_name);
    CREATE INDEX IF NOT EXISTS idx_saved_posts_target_date ON saved_posts(target_date);
    CREATE INDEX IF NOT EXISTS idx_post_images_post_id ON post_images(post_id);
    CREATE INDEX IF NOT EXISTS idx_post_images_image_id ON post_images(image_id);
    """
    
    if execute_sql_direct(sql):
        logger.info("Базовые таблицы успешно созданы напрямую")
    else:
        logger.error("Не удалось создать базовые таблицы напрямую")
        
    # Создаем триггеры для обновления временных меток
    triggers_sql = """
    -- Триггеры для автоматического обновления полей updated_at
    DROP TRIGGER IF EXISTS update_saved_posts_updated_at ON saved_posts;
    CREATE TRIGGER update_saved_posts_updated_at
    BEFORE UPDATE ON saved_posts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
    
    DROP TRIGGER IF EXISTS update_channel_analysis_updated_at ON channel_analysis;
    CREATE TRIGGER update_channel_analysis_updated_at
    BEFORE UPDATE ON channel_analysis
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
    
    DROP TRIGGER IF EXISTS update_suggested_ideas_updated_at ON suggested_ideas;
    CREATE TRIGGER update_suggested_ideas_updated_at
    BEFORE UPDATE ON suggested_ideas
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
    """
    
    if execute_sql_direct(triggers_sql):
        logger.info("Триггеры успешно созданы напрямую")
    else:
        logger.warning("Не удалось создать триггеры напрямую")

if __name__ == "__main__":
    main() 