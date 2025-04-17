@echo off
REM Скрипт для развертывания приложения и запуска миграций на Windows

echo === Установка зависимостей ===
pip install -r requirements.txt

echo === Принудительное добавление недостающих столбцов ===
python move_temp_files.py

echo === Запуск стандартных миграций ===
python migrate.py
if %ERRORLEVEL% NEQ 0 (
    echo Стандартные миграции завершились с ошибкой, запускаем принудительные миграции...
    python execute_migrations.py
) else (
    echo Стандартные миграции выполнены успешно.
)

echo === Запуск приложения ===
uvicorn main:app --host 0.0.0.0 --port 8000 