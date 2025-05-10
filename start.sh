#!/bin/bash
# Скрипт для запуска приложения на Render

set -e  # Остановка скрипта при ошибках

echo "Запуск приложения из директории: $(pwd)"

# Установка переменных окружения
if [ -f .env ]; then
    echo "Использую переменные окружения из файла .env..."
    export $(grep -v '^#' .env | xargs)
else
    echo "Использую переменные окружения из Render..."
fi

# Установка недостающих зависимостей
echo "Установка необходимых зависимостей..."
pip install httpx==0.27.0 beautifulsoup4==4.12.0 bs4==0.0.1

# Создание __init__.py в каждой директории, если их нет
echo "Создание необходимых __init__.py файлов..."
touch backend/__init__.py
touch backend/routes/__init__.py
touch services/__init__.py

# Запуск миграций базы данных
echo "Запуск миграций базы данных..."
python -m backend.migrate

# Запуск скрипта для прямого обновления таблиц
echo "Запуск скрипта для прямого обновления таблиц..."
python -m backend.move_temp_files

# Запуск приложения
echo "Запуск приложения..."
uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000} 