#!/bin/bash
# Скрипт для запуска приложения на Render

set -e  # Остановка скрипта при ошибках

# Получение директории скрипта
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
BACKEND_DIR="$SCRIPT_DIR/backend"

echo "Запуск приложения из директории: $BACKEND_DIR"

# Переход в директорию бэкенда
cd "$BACKEND_DIR"

# Проверка наличия .env файла и создание, если отсутствует
if [ ! -f .env ]; then
    echo "Файл .env не найден, создаю из шаблона..."
    cp ../.env.example .env
    echo "Файл .env создан из шаблона. Пожалуйста, проверьте и обновите значения при необходимости."
fi

echo "Добавление дополнительных настроек для Telegram WebApp..."
# Добавляем переменную для отладки WebApp
echo "VITE_DEBUG_TELEGRAM_WEBAPP=true" >> .env
# Добавляем дополнительную переменную для проверки интеграции
echo "VITE_TELEGRAM_WEB_APP_VERSION=8.0" >> .env

echo "Запуск приложения..."
exec gunicorn main:app --bind 0.0.0.0:10000 --workers 2 --worker-class uvicorn.workers.UvicornWorker 