#!/usr/bin/env python
"""
Скрипт для исправления проблемы со столбцом updated_at в таблице channel_analysis
"""

import os
import logging
from dotenv import load_dotenv
from migrate import init_supabase, execute_sql_direct

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv(override=True)

def main():
    """Основная функция скрипта"""
    logger.info("Запуск скрипта для добавления столбца updated_at и обновления кэша схемы")
    
    # Инициализация Supabase клиента
    supabase = init_supabase()
    if not supabase:
        logger.error("Не удалось инициализировать Supabase")
        return False
    
    # SQL-команда для добавления столбца и обновления кэша схемы
    sql = """
    -- Добавление столбца updated_at в таблицу channel_analysis
    ALTER TABLE channel_analysis 
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    
    -- Обновление схемы кэша для таблиц
    NOTIFY pgrst, 'reload schema';
    """
    
    # Выполнение SQL-команды
    result = execute_sql_direct(supabase, sql)
    
    if result:
        logger.info("Столбец updated_at успешно добавлен и кэш схемы обновлен")
        return True
    else:
        logger.error("Не удалось добавить столбец updated_at или обновить кэш схемы")
        return False

if __name__ == "__main__":
    main() 