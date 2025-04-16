#!/bin/bash
# Скрипт для запуска приложения на Render

set -e  # Остановка скрипта при ошибках

# Получение директории скрипта
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
BACKEND_DIR="$SCRIPT_DIR/backend"

echo "Запуск приложения из директории: $SCRIPT_DIR"

# Не создаем .env файл, т.к. переменные установлены в Render
echo "Использую переменные окружения из Render..."

# Проверка наличия файла telegram_utils.py
if [ ! -f "$BACKEND_DIR/telegram_utils.py" ]; then
    echo "ОШИБКА: Файл telegram_utils.py отсутствует в директории $BACKEND_DIR"
    exit 1
fi

# Запускаем скрипт миграции для создания таблиц
echo "Запуск миграций базы данных..."
cd $BACKEND_DIR && python migrate.py || {
    echo "Предупреждение: Миграции не были применены полностью, но продолжаем запуск приложения..."
}

echo "Запуск приложения..."
if [ "$USE_GUNICORN" = "true" ]; then
    # Запуск через gunicorn
    exec gunicorn --chdir $BACKEND_DIR -k uvicorn.workers.UvicornWorker wsgi:app --bind 0.0.0.0:${PORT:-8000} --workers 2
else
    # Запуск через uvicorn напрямую
    cd $BACKEND_DIR && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
fi 