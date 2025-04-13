#!/bin/bash
# Скрипт для запуска приложения на Render

set -e  # Прекращать выполнение при ошибках

# Директория бэкенда
BACKEND_DIR="$(dirname "$(readlink -f "$0")")/backend"

echo "Запуск приложения из директории: $BACKEND_DIR"

# Переход в директорию бэкенда
cd "$BACKEND_DIR"

# Запуск приложения
echo "Запуск приложения..."
gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT 