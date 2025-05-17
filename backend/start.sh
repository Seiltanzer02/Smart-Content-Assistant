#!/bin/bash

echo "Запуск приложения из директории: $(pwd)"
echo "=== ДИАГНОСТИКА: Файл backend/start.sh запускается ==="

# Проверка и загрузка переменных окружения
if [ -f .env ]; then
    echo "Используем локальный файл .env..."
    source .env
else
    echo "Используем переменные окружения из Render..."
fi

# Проверка существования необходимых переменных окружения
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_ANON_KEY" ]; then
    echo "ОШИБКА: Отсутствуют необходимые переменные окружения SUPABASE_URL или SUPABASE_ANON_KEY"
    exit 1
fi

# Запуск принудительных миграций (игнорируем ошибки)
echo "Запуск принудительных миграций..."
python execute_migrations.py || true

# Запуск скрипта для прямого обновления таблиц (игнорируем ошибки)
echo "Запуск скрипта для прямого обновления таблиц..."
python move_temp_files.py || true

# Запуск стандартных миграций (игнорируем ошибки)
echo "Запуск стандартных миграций..."
python migrate.py || true

# Запуск приложения
echo "Запуск приложения..."
if [ -z "$PORT" ]; then
    PORT=8000
fi
uvicorn main:app --host 0.0.0.0 --port $PORT 