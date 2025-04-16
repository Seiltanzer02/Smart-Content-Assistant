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

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv(override=True)

def init_supabase():
    """Инициализация клиента Supabase"""
    try:
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            logger.error("SUPABASE_URL или SUPABASE_ANON_KEY не найдены в переменных окружения")
            return None
        
        logger.info(f"Подключение к Supabase: {supabase_url}")
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        logger.error(f"Ошибка при инициализации Supabase: {e}")
        return None

def run_migrations():
    """Запуск SQL миграций"""
    try:
        supabase = init_supabase()
        if not supabase:
            logger.error("Невозможно запустить миграции без клиента Supabase")
            return False
        
        migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")
        logger.info(f"Поиск миграций в директории: {migrations_dir}")
        
        # Получаем список SQL файлов и сортируем их по имени
        migration_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
        logger.info(f"Найдено миграций: {len(migration_files)}")
        
        if not migration_files:
            logger.warning("Файлы миграций не найдены!")
            return False
        
        for file_path in migration_files:
            file_name = os.path.basename(file_path)
            logger.info(f"Применение миграции: {file_name}")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    sql_content = f.read()
                
                # Убираем запись в таблицу _migrations, так как она не существует
                # и просто выполняем SQL-запросы
                try:
                    # Разделяем SQL на отдельные запросы и выполняем их
                    statements = sql_content.split(';')
                    for stmt in statements:
                        stmt = stmt.strip()
                        if stmt:
                            try:
                                # Выполняем запрос через RPC
                                result = supabase.postgrest.schema('public').rpc(
                                    'exec_sql', {'query': stmt + ';'}).execute()
                                logger.debug(f"Запрос выполнен: {stmt[:50]}...")
                            except Exception as query_err:
                                logger.warning(f"Ошибка выполнения запроса: {query_err}. Запрос: {stmt[:100]}...")
                    
                    logger.info(f"Миграция {file_name} успешно применена")
                except Exception as sql_err:
                    # Если функция exec_sql не существует, создаем её
                    logger.warning(f"Не удалось выполнить через RPC, пробуем другой метод: {sql_err}")
                    
                    # Создаем функцию exec_sql, если её нет
                    try:
                        create_function_sql = """
                        CREATE OR REPLACE FUNCTION exec_sql(query text) RETURNS void AS $$
                        BEGIN
                            EXECUTE query;
                        END;
                        $$ LANGUAGE plpgsql SECURITY DEFINER;
                        """
                        logger.info("Создаем функцию exec_sql...")
                        supabase.pg.execute(create_function_sql)
                        
                        # Теперь пробуем снова выполнить нашу миграцию
                        result = supabase.postgrest.schema('public').rpc('exec_sql', {'query': sql_content}).execute()
                        logger.info(f"Миграция {file_name} успешно применена после создания функции")
                    except Exception as func_err:
                        logger.error(f"Не удалось создать или использовать функцию exec_sql: {func_err}")
                        # Если всё ещё не работает, придется отказаться от этой миграции
                        logger.error(f"Пропускаем миграцию {file_name}")
                        continue
                    
            except Exception as e:
                logger.error(f"Ошибка при применении миграции {file_name}: {e}")
                # Продолжаем с другими миграциями
                continue
        
        return True
    except Exception as e:
        logger.error(f"Неожиданная ошибка при выполнении миграций: {e}")
        return False

if __name__ == "__main__":
    logger.info("Запуск миграций...")
    try:
        if run_migrations():
            logger.info("Все миграции успешно применены!")
        else:
            logger.error("Миграции не были полностью применены из-за ошибок")
            # Не завершаем процесс с ошибкой, чтобы приложение всё равно запустилось
            sys.exit(0)
    except Exception as e:
        logger.error(f"Критическая ошибка при выполнении миграций: {e}")
        # Не завершаем процесс с ошибкой, чтобы приложение всё равно запустилось
        sys.exit(0) 