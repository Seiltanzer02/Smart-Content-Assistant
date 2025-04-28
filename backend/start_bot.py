#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Скрипт для запуска Telegram-бота для подписки
"""

import logging
from telegram_bot import bot

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Запуск бота в режиме polling"""
    logger.info("Запуск бота для обработки подписок")
    try:
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    main() 