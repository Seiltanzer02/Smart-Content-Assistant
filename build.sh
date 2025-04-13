#!/bin/bash
# Скрипт для сборки приложения на Render

set -e  # Остановка скрипта при ошибках

# Получение директории скрипта
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
STATIC_DIR="$BACKEND_DIR/static"

echo "Директория сборки: $SCRIPT_DIR"

# Проверка наличия Python и установка зависимостей бэкенда
echo "Установка зависимостей Python..."
python -m pip install --upgrade pip
pip install -r "$BACKEND_DIR/requirements.txt"

# Проверка наличия NVM и установка Node.js
echo "Проверка наличия NVM..."
if [ -s "$HOME/.nvm/nvm.sh" ]; then
    echo "NVM найден, использую его для установки Node.js"
    . "$HOME/.nvm/nvm.sh"
    nvm install 18 || echo "Node.js уже установлен"
    nvm use 18
else
    echo "NVM не найден, проверяю наличие Node.js..."
    if ! command -v node &> /dev/null; then
        echo "Node.js не найден, требуется установить NVM и Node.js вручную"
        exit 1
    fi
fi

# Вывод версий для отладки
echo "Версия Node.js: $(node -v)"
echo "Версия npm: $(npm -v)"

# Установка зависимостей для фронтенда
echo "Установка зависимостей npm..."
cd "$FRONTEND_DIR"
npm ci

# Сборка фронтенда
echo "Сборка фронтенда..."
npm run build

# Создание директории для статических файлов
if [ ! -d "$STATIC_DIR" ]; then
    echo "Создание директории для статических файлов: $STATIC_DIR"
    mkdir -p "$STATIC_DIR"
fi

# Копирование собранного фронтенда в папку статических файлов бэкенда
echo "Копирование собранного фронтенда в $STATIC_DIR..."
cp -R "$FRONTEND_DIR/dist/"* "$STATIC_DIR/"

echo "Сборка завершена успешно! Используйте start.sh для запуска приложения." 