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

# Подготовка файлов Python
echo "Подготовка каталогов Python..."
# Создаем __init__.py если их нет
[ -f backend/__init__.py ] || echo "# Python package" > backend/__init__.py
[ -d backend/migrations ] || mkdir -p backend/migrations
[ -f backend/migrations/__init__.py ] || echo "# Python package" > backend/migrations/__init__.py

# Проверяем наличие telegram_utils.py
if [ ! -f backend/telegram_utils.py ]; then
    echo "ОШИБКА: Файл telegram_utils.py отсутствует!"
    exit 1
fi

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

# Создаем скрипт запуска
echo "Создание скрипта запуска start.sh..."
cat > start.sh << 'EOF'
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

# Запуск миграций базы данных
echo "Запуск миграций базы данных..."
python -m backend.migrate

# Запуск скрипта для прямого обновления таблиц
echo "Запуск скрипта для прямого обновления таблиц..."
python -m backend.move_temp_files

# Запуск приложения
echo "Запуск приложения..."
cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}
EOF

# Делаем скрипт исполняемым
chmod +x start.sh

echo "Сборка завершена успешно! Используйте start.sh для запуска приложения." 