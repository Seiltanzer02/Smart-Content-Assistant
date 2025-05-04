#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import subprocess
import json
from datetime import datetime
import argparse

# Определение версий для отслеживания
APP_VERSION = "1.1.0"  # Обновите при изменениях в логике подписок
DB_VERSION = "1.0.1"   # Обновите при изменениях в схеме БД

def log(message):
    """Вывод сообщения с меткой времени"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def check_files():
    """Проверяет наличие и актуальность файлов"""
    log("Проверка файлов...")
    
    # Проверка наличия основных файлов
    required_files = [
        "main_fixed.py",
        "services/subscription_service.py",
        "frontend/src/api/subscription.ts",
        "frontend/src/components/SubscriptionWidget.tsx"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        log(f"ОШИБКА: Отсутствуют необходимые файлы: {', '.join(missing_files)}")
        return False
    
    # Проверка версий файлов
    if os.path.exists("main_fixed.py.new"):
        with open("main_fixed.py", "r") as f_old, open("main_fixed.py.new", "r") as f_new:
            old_content = f_old.read()
            new_content = f_new.read()
            
            if "NoCacheMiddleware" not in old_content and "NoCacheMiddleware" in new_content:
                log("ВНИМАНИЕ: main_fixed.py не содержит последних изменений (NoCacheMiddleware)")
                return False
    
    log("Проверка файлов завершена успешно")
    return True

def update_files():
    """Обновляет файлы до актуальной версии"""
    log("Обновление файлов...")
    
    # Создание бэкапа
    backup_time = datetime.now().strftime("%Y%m%d%H%M%S")
    if os.path.exists("main_fixed.py"):
        shutil.copy2("main_fixed.py", f"main_fixed.py.backup.{backup_time}")
        log(f"Создан бэкап main_fixed.py -> main_fixed.py.backup.{backup_time}")
    
    # Обновление main_fixed.py
    if os.path.exists("main_fixed.py.new"):
        shutil.copy2("main_fixed.py.new", "main_fixed.py")
        log("main_fixed.py обновлен")
    
    # Обновление версионного файла
    create_version_file()
    
    log("Обновление файлов завершено")
    return True

def create_version_file():
    """Создает/обновляет файл с версией приложения"""
    version_info = {
        "app_version": APP_VERSION,
        "db_version": DB_VERSION,
        "updated_at": datetime.now().isoformat(),
    }
    
    with open("version.json", "w") as f:
        json.dump(version_info, f, indent=2)
    
    log(f"Создан файл версии: app_version={APP_VERSION}, db_version={DB_VERSION}")

def check_environment():
    """Проверяет переменные окружения"""
    log("Проверка переменных окружения...")
    
    required_env_vars = ["DATABASE_URL", "TELEGRAM_BOT_TOKEN"]
    missing_vars = []
    
    for var in required_env_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        log(f"ОШИБКА: Отсутствуют необходимые переменные окружения: {', '.join(missing_vars)}")
        return False
    
    log("Проверка переменных окружения завершена успешно")
    return True

def check_db_connection():
    """Проверяет подключение к базе данных"""
    log("Проверка подключения к базе данных...")
    
    try:
        # Используем скрипт проверки подписки для проверки соединения
        result = subprocess.run(
            [sys.executable, "check_subscription.py", "--connection-check"],
            capture_output=True,
            text=True,
            check=True
        )
        log("Подключение к базе данных работает")
        return True
    except subprocess.CalledProcessError as e:
        log(f"ОШИБКА: Не удалось подключиться к базе данных: {e.stderr}")
        return False

def restart_server():
    """Перезапускает сервер"""
    log("Перезапуск сервера...")
    
    try:
        # Пример команды для перезапуска через systemd
        # subprocess.run(["sudo", "systemctl", "restart", "content-manager"], check=True)
        
        # Если не используется systemd, можно адаптировать под свою систему
        log("ПРИМЕЧАНИЕ: Фактический перезапуск не выполнен - требуется настройка под вашу систему")
        log("Выполните перезапуск сервера вручную")
        return True
    except subprocess.CalledProcessError as e:
        log(f"ОШИБКА: Не удалось перезапустить сервер: {e}")
        return False

def run_deployment_check(args):
    """Запускает проверку развертывания и обновление при необходимости"""
    log("Запуск проверки развертывания...")
    
    # Создаем файл версии, если он отсутствует
    if not os.path.exists("version.json"):
        create_version_file()
    
    # Проверяем файлы
    files_ok = check_files()
    if not files_ok and args.fix:
        files_ok = update_files()
    
    # Проверяем переменные окружения
    env_ok = check_environment()
    
    # Проверяем подключение к БД
    db_ok = check_db_connection() if env_ok else False
    
    # Перезапускаем сервер при необходимости
    if args.restart and files_ok and env_ok and db_ok:
        restart_ok = restart_server()
    else:
        restart_ok = True
    
    # Вывод итогового статуса
    log("\nРезультаты проверки развертывания:")
    log(f"- Файлы: {'OK' if files_ok else 'ОШИБКА'}")
    log(f"- Переменные окружения: {'OK' if env_ok else 'ОШИБКА'}")
    log(f"- Подключение к БД: {'OK' if db_ok else 'ОШИБКА'}")
    log(f"- Перезапуск сервера: {'OK' if restart_ok else 'ОШИБКА'}")
    
    all_ok = files_ok and env_ok and db_ok and restart_ok
    log(f"\nИтог: {'Успешно' if all_ok else 'Есть проблемы'}")
    
    return all_ok

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Проверка и обновление развертывания")
    parser.add_argument("--fix", action="store_true", help="Автоматически исправлять проблемы")
    parser.add_argument("--restart", action="store_true", help="Перезапустить сервер после обновления")
    
    args = parser.parse_args()
    success = run_deployment_check(args)
    
    sys.exit(0 if success else 1) 