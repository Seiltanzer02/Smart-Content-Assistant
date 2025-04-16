#!/bin/bash
# Скрипт для сборки приложения на Render

set -e  # Остановка скрипта при ошибках

# Получаем текущую директорию
BUILD_DIR=$(pwd)
echo "Директория сборки: $BUILD_DIR"

# Установка зависимостей Python
echo "Установка зависимостей Python..."
pip install --upgrade pip
pip install -r backend/requirements.txt

# Проверка наличия NVM и использование корректной версии Node.js
echo "Проверка наличия NVM..."
if [ -d "$HOME/.nvm" ]; then
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    nvm install 18 || echo "Не удалось установить Node.js 18, продолжаем с текущей версией"
    nvm use 18 || echo "Не удалось переключиться на Node.js 18, продолжаем с текущей версией"
else
    echo "NVM не найден, проверяю наличие Node.js..."
fi

# Отображаем версии
node -v && echo "Версия Node.js: $(node -v)"
npm -v && echo "Версия npm: $(npm -v)"

# Устанавливаем зависимости npm для фронтенда
echo "Установка зависимостей npm..."
cd frontend && npm install

# Собираем фронтенд
echo "Сборка фронтенда..."
npm run build

# Возвращаемся в корневую директорию
cd ..

# Создаем директорию для статических файлов, если её нет
mkdir -p backend/static

# Копируем собранное приложение в директорию статических файлов
echo "Копирование собранного фронтенда в $BUILD_DIR/backend/static..."
cp -r frontend/dist/* backend/static/

echo "Сборка завершена успешно! Используйте start.sh для запуска приложения." 