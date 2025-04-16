#!/usr/bin/env python
"""
Скрипт для применения миграций к базе данных Supabase.
"""

import os
import sys
import time
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv(override=True)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

def apply_migrations():
    """Применяет SQL-миграции к базе данных."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        logger.error("Отсутствуют необходимые переменные окружения для подключения к Supabase")
        sys.exit(1)
    
    # Инициализация клиента Supabase
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info("Клиент Supabase успешно инициализирован")
    except Exception as e:
        logger.error(f"Ошибка инициализации клиента Supabase: {e}")
        sys.exit(1)
    
    # Создание хранимой процедуры pgfunction, если её нет
    try:
        create_pgfunction_sql = """
        CREATE OR REPLACE FUNCTION pgfunction(sql text)
        RETURNS VOID AS $$
        BEGIN
            EXECUTE sql;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        """
        
        # Пытаемся выполнить SQL напрямую
        response = supabase.from_("").rpc("pg_query", {"query": create_pgfunction_sql}).execute()
        
        if hasattr(response, 'error') and response.error:
            # Если не получается создать функцию через pg_query, пробуем альтернативный вариант
            logger.warning(f"Невозможно создать pgfunction через pg_query: {response.error}")
            logger.info("Попытка прямого выполнения SQL...")
            
            # Можно попробовать SQL запрос через REST API и POST
            # Но это рискованно с точки зрения безопасности
            logger.warning("Прямое выполнение SQL через REST API не поддерживается")
        else:
            logger.info("Хранимая процедура pgfunction успешно создана или обновлена")
    except Exception as e:
        logger.warning(f"Ошибка при создании pgfunction: {e}")
        logger.warning("Продолжаем выполнение, предполагая, что pgfunction существует")
    
    # Путь к папке с миграциями
    migration_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migration")
    
    if not os.path.exists(migration_folder):
        logger.warning(f"Папка с миграциями не найдена: {migration_folder}")
        return
    
    # Получение списка SQL-файлов
    migration_files = sorted([
        f for f in os.listdir(migration_folder) 
        if f.endswith(".sql") and os.path.isfile(os.path.join(migration_folder, f))
    ])
    
    if not migration_files:
        logger.warning("SQL-файлы для миграции не найдены")
        return
    
    logger.info(f"Найдено {len(migration_files)} файлов миграции: {', '.join(migration_files)}")
    
    # Применение миграций
    for file_name in migration_files:
        file_path = os.path.join(migration_folder, file_name)
        logger.info(f"Применение миграции из файла: {file_name}")
        
        try:
            # Чтение SQL из файла
            with open(file_path, 'r', encoding='utf-8') as file:
                sql = file.read()
            
            # Пробуем применить SQL миграцию
            try:
                # Сначала через pgfunction
                result = supabase.rpc("pgfunction", {"sql": sql}).execute()
                
                if hasattr(result, 'error') and result.error:
                    logger.error(f"Ошибка при выполнении миграции {file_name} через pgfunction: {result.error}")
                    
                    # Пробуем прямое выполнение через pg_query как запасной вариант
                    logger.info(f"Попытка прямого выполнения SQL из файла {file_name}...")
                    result = supabase.from_("").rpc("pg_query", {"query": sql}).execute()
                    
                    if hasattr(result, 'error') and result.error:
                        logger.error(f"Ошибка при прямом выполнении SQL из файла {file_name}: {result.error}")
                    else:
                        logger.info(f"Миграция {file_name} успешно применена через прямое выполнение SQL")
                else:
                    logger.info(f"Миграция {file_name} успешно применена через pgfunction")
            except Exception as e:
                logger.error(f"Ошибка при выполнении миграции {file_name}: {e}")
                
                # Пробуем разбить SQL на отдельные команды и выполнить по одной
                logger.info(f"Попытка разбить SQL из {file_name} на отдельные команды и выполнить их...")
                
                # Простое разделение на отдельные команды по ";", не идеально, но может помочь
                commands = sql.split(';')
                success_count = 0
                
                for i, cmd in enumerate(commands):
                    cmd = cmd.strip()
                    if not cmd:  # Пропускаем пустые команды
                        continue
                    
                    try:
                        # Добавляем ";" обратно, так как это может быть важно для SQL
                        cmd_result = supabase.from_("").rpc("pg_query", {"query": cmd + ";"}).execute()
                        
                        if not hasattr(cmd_result, 'error') or not cmd_result.error:
                            success_count += 1
                        else:
                            logger.error(f"Ошибка при выполнении команды {i+1} из {file_name}: {cmd_result.error}")
                    except Exception as cmd_err:
                        logger.error(f"Ошибка при выполнении команды {i+1} из {file_name}: {cmd_err}")
                
                if success_count > 0:
                    logger.info(f"Успешно выполнено {success_count} из {len(commands)} команд из файла {file_name}")
                
        except Exception as e:
            logger.error(f"Ошибка при применении миграции {file_name}: {e}")
    
    logger.info("Применение миграций завершено")

if __name__ == "__main__":
    # Ждем несколько секунд для обеспечения готовности базы данных
    logger.info("Ожидание готовности базы данных...")
    time.sleep(5)
    
    # Применяем миграции
    apply_migrations() 