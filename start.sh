#!/bin/bash
# Скрипт для запуска приложения на Render

set -e  # Остановка скрипта при ошибках

# Получение директории скрипта
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
BACKEND_DIR="$SCRIPT_DIR/backend"

echo "Запуск приложения из директории: $BACKEND_DIR"

# Переход в директорию бэкенда
cd "$BACKEND_DIR"

# Не создаем .env файл, т.к. переменные установлены в Render
echo "Использую переменные окружения из Render..."

echo "Запуск приложения..."
exec gunicorn main:app --bind 0.0.0.0:10000 --workers 2 --worker-class uvicorn.workers.UvicornWorker 