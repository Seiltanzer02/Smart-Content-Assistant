#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Скрипт для настройки webhook для Telegram-бота
"""

import os
import sys
import logging
import requests
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

def setup_webhook():
    """Настройка webhook для бота"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL")
    
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        return False
    
    if not webhook_url:
        logger.error("WEBHOOK_URL не найден в переменных окружения")
        logger.info("Пример: https://ваш-домен.ru/telegram-webhook")
        return False
    
    # URL для настройки webhook
    api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    
    # Параметры webhook
    params = {
        "url": webhook_url,
        "allowed_updates": ["message", "pre_checkout_query", "successful_payment"]
    }
    
    try:
        # Отправляем запрос на настройку webhook
        response = requests.post(api_url, json=params)
        data = response.json()
        
        if response.status_code == 200 and data.get("ok"):
            logger.info(f"Webhook успешно настроен: {webhook_url}")
            logger.info(f"Ответ API: {data}")
            return True
        else:
            logger.error(f"Ошибка при настройке webhook: {data}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при настройке webhook: {e}")
        return False

def delete_webhook():
    """Удаление webhook для бота"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        return False
    
    # URL для удаления webhook
    api_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
    
    try:
        # Отправляем запрос на удаление webhook
        response = requests.get(api_url)
        data = response.json()
        
        if response.status_code == 200 and data.get("ok"):
            logger.info("Webhook успешно удален")
            return True
        else:
            logger.error(f"Ошибка при удалении webhook: {data}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при удалении webhook: {e}")
        return False

def get_webhook_info():
    """Получение информации о webhook"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        return None
    
    # URL для получения информации о webhook
    api_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
    
    try:
        # Отправляем запрос на получение информации о webhook
        response = requests.get(api_url)
        data = response.json()
        
        if response.status_code == 200 and data.get("ok"):
            logger.info(f"Информация о webhook: {data['result']}")
            return data['result']
        else:
            logger.error(f"Ошибка при получении информации о webhook: {data}")
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении информации о webhook: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python setup_webhook.py [setup|delete|info]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "setup":
        if setup_webhook():
            print("Webhook успешно настроен")
            sys.exit(0)
        else:
            print("Ошибка при настройке webhook")
            sys.exit(1)
    elif command == "delete":
        if delete_webhook():
            print("Webhook успешно удален")
            sys.exit(0)
        else:
            print("Ошибка при удалении webhook")
            sys.exit(1)
    elif command == "info":
        info = get_webhook_info()
        if info:
            print(f"URL: {info.get('url')}")
            print(f"Pending updates: {info.get('pending_update_count')}")
            print(f"Last error: {info.get('last_error_message') or 'None'}")
            sys.exit(0)
        else:
            print("Ошибка при получении информации о webhook")
            sys.exit(1)
    else:
        print("Неизвестная команда. Используйте: setup, delete или info")
        sys.exit(1) 