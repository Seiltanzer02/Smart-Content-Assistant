#!/usr/bin/env python
"""
Конфигурация логирования для приложения
"""

import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name, log_file, level=logging.INFO):
    """
    Настраивает и возвращает логгер с заданным именем,
    который записывает логи в файл и в консоль
    """
    # Создаём директорию для логов, если её нет
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настройка форматирования логов
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Создаём обработчик для записи в файл с ротацией
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # Создаём обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Настраиваем логгер
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Удаляем все существующие обработчики, чтобы избежать дублирования
    logger.handlers = []
    
    # Добавляем обработчики
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger 