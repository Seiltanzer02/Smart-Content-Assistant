#!/usr/bin/env python
"""
Скрипт для исправления проблем с отсутствующими столбцами в таблицах
и обновления кэша схемы в Supabase
"""

import os
import asyncio
import logging
import sys
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv(override=True)

async def execute_sql_direct(query):
    """Выполняет SQL-запрос напрямую через Supabase RPC API"""
    try:
        # Получение URL и ключа Supabase
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            logger.error("Не найдены переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY")
            return None

        import httpx
        
        # Прямой запрос через API
        url = f"{supabase_url}/rest/v1/rpc/exec_sql"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json={"query": query}, headers=headers)
        
        if response.status_code in [200, 204]:
            logger.info(f"SQL-запрос успешно выполнен: {query[:50]}...")
            return {
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else None
            }
        else:
            logger.error(f"Ошибка при выполнении SQL-запроса: {response.status_code} - {response.text}")
            return {
                "status_code": response.status_code,
                "error": response.text
            }
            
    except Exception as e:
        logger.error(f"Исключение при выполнении SQL-запроса: {str(e)}")
        return None

async def fix_database_schema():
    """Функция для исправления схемы базы данных"""
    logger.info("Запуск скрипта для добавления отсутствующих столбцов и обновления кэша схемы")
    
    # SQL-команда для добавления столбца updated_at в таблицу channel_analysis
    sql_updated_at = """
    ALTER TABLE channel_analysis 
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    """
    
    # SQL-команда для добавления столбца preview_url в таблицу saved_images
    sql_preview_url = """
    ALTER TABLE saved_images 
    ADD COLUMN IF NOT EXISTS preview_url TEXT;
    """
    
    # SQL-команда для обновления кэша схемы
    sql_refresh_schema = """
    NOTIFY pgrst, 'reload schema';
    """
    
    # Выполнение SQL-команд
    result_updated_at = await execute_sql_direct(sql_updated_at)
    if not result_updated_at or result_updated_at.get("status_code") not in [200, 204]:
        logger.error("Не удалось добавить столбец updated_at")
        return False
    
    result_preview_url = await execute_sql_direct(sql_preview_url)
    if not result_preview_url or result_preview_url.get("status_code") not in [200, 204]:
        logger.error("Не удалось добавить столбец preview_url")
        return False
    
    # Обновление кэша схемы
    result_refresh = await execute_sql_direct(sql_refresh_schema)
    if not result_refresh or result_refresh.get("status_code") not in [200, 204]:
        logger.error("Не удалось обновить кэш схемы")
        return False
    
    logger.info("Столбцы updated_at и preview_url успешно добавлены и кэш схемы обновлен")
    return True

async def main():
    """Основная функция скрипта"""
    result = await fix_database_schema()
    if result:
        logger.info("Скрипт успешно выполнен")
        return 0
    else:
        logger.error("Скрипт завершился с ошибками")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 