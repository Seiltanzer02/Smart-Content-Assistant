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

# Запускаем скрипт миграции для создания таблиц
echo "Запуск миграций базы данных..."
python migrate.py

echo "Запуск приложения..."
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} 