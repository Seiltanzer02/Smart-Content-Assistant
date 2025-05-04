#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import asyncio
import logging
import asyncpg
import aiohttp
import json
import time
import psutil
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("monitoring.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("monitoring")

# Настройки мониторинга
MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "300"))  # 5 минут по умолчанию
MAX_RETRIES = 3
NOTIFY_EMAILS = os.getenv("NOTIFY_EMAILS", "").split(",")
SMTP_SERVER = os.getenv("SMTP_SERVER", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
API_URL = os.getenv("API_URL", "http://localhost:8000")

async def check_database():
    """Проверяет подключение к базе данных и её состояние"""
    logger.info("Проверка подключения к базе данных...")
    conn_string = os.getenv("DATABASE_URL")
    
    if not conn_string:
        logger.error("Переменная окружения DATABASE_URL не установлена")
        return False, "DATABASE_URL не установлена"
    
    try:
        # Подключение к базе данных
        conn = await asyncpg.connect(conn_string)
        
        # Проверка состояния базы данных
        server_time = await conn.fetchval("SELECT NOW()")
        db_size = await conn.fetchval("SELECT pg_database_size(current_database())")
        
        # Получаем статистику по таблицам
        tables_stats = await conn.fetch("""
            SELECT 
                relname as table_name, 
                n_live_tup as row_count,
                pg_size_pretty(pg_total_relation_size(relid)) as total_size
            FROM pg_stat_user_tables 
            ORDER BY n_live_tup DESC
        """)
        
        # Проверка замедленных запросов
        slow_queries = await conn.fetch("""
            SELECT pid, now() - query_start as duration, query 
            FROM pg_stat_activity 
            WHERE state = 'active' AND now() - query_start > '5 seconds'::interval 
            ORDER BY duration DESC
        """)
        
        await conn.close()
        
        # Формируем отчет
        report = {
            "status": "ok",
            "server_time": server_time.isoformat(),
            "db_size_bytes": db_size,
            "tables": [dict(t) for t in tables_stats],
            "slow_queries_count": len(slow_queries),
            "slow_queries": [dict(q) for q in slow_queries],
        }
        
        return True, report
    
    except Exception as e:
        logger.error(f"Ошибка при проверке базы данных: {e}")
        return False, str(e)

async def check_api_endpoints():
    """Проверяет API-эндпоинты"""
    logger.info("Проверка API-эндпоинтов...")
    
    endpoints = [
        "/health",
        "/subscription/status"  # будет ошибка 401, но проверит доступность
    ]
    
    results = {}
    
    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints:
            url = f"{API_URL}{endpoint}"
            try:
                start_time = time.time()
                async with session.get(url) as response:
                    response_time = time.time() - start_time
                    status = response.status
                    
                    # Для эндпоинта подписки ожидаем 401 (требуется аутентификация)
                    expected_status = 401 if endpoint == "/subscription/status" else 200
                    is_success = status == expected_status
                    
                    results[endpoint] = {
                        "status": status,
                        "response_time_ms": round(response_time * 1000, 2),
                        "is_success": is_success
                    }
            except Exception as e:
                results[endpoint] = {
                    "status": "error",
                    "error": str(e),
                    "is_success": False
                }
    
    # Общий результат
    all_success = all(result.get("is_success", False) for result in results.values())
    
    return all_success, results

async def check_system_resources():
    """Проверяет системные ресурсы"""
    logger.info("Проверка системных ресурсов...")
    
    try:
        # Использование CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Использование памяти
        memory = psutil.virtual_memory()
        
        # Использование диска
        disk = psutil.disk_usage('/')
        
        # Проверяем процесс сервера, если он запущен на той же машине
        server_process = None
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if 'python' in proc.info['name'].lower() and any('main.py' in cmd for cmd in proc.info['cmdline'] if cmd):
                server_process = {
                    "pid": proc.info['pid'],
                    "cpu_percent": proc.cpu_percent(interval=0.1),
                    "memory_percent": proc.memory_percent(),
                    "create_time": datetime.fromtimestamp(proc.create_time()).isoformat()
                }
                break
        
        report = {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": round(memory.available / (1024 * 1024), 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
            "server_process": server_process
        }
        
        # Определяем успешность проверки
        is_success = (
            cpu_percent < 90 and 
            memory.percent < 90 and 
            disk.percent < 90
        )
        
        return is_success, report
    
    except Exception as e:
        logger.error(f"Ошибка при проверке системных ресурсов: {e}")
        return False, str(e)

def send_email_alert(subject, message):
    """Отправляет оповещение по email"""
    if not SMTP_SERVER or not SMTP_USER or not SMTP_PASSWORD or not NOTIFY_EMAILS:
        logger.warning("Настройки SMTP не заданы, оповещение не отправлено")
        return False
    
    try:
        # Создаем сообщение
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = ", ".join(NOTIFY_EMAILS)
        msg['Subject'] = subject
        
        # Добавляем текст
        msg.attach(MIMEText(message, 'plain'))
        
        # Подключаемся к серверу и отправляем
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Оповещение отправлено: {subject}")
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при отправке оповещения: {e}")
        return False

async def run_monitoring():
    """Запускает все проверки и формирует отчет"""
    logger.info("Запуск мониторинга...")
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    # Проверка базы данных
    db_success, db_result = await check_database()
    report["checks"]["database"] = {
        "success": db_success,
        "result": db_result
    }
    
    # Проверка API
    api_success, api_result = await check_api_endpoints()
    report["checks"]["api"] = {
        "success": api_success,
        "result": api_result
    }
    
    # Проверка системных ресурсов
    system_success, system_result = await check_system_resources()
    report["checks"]["system"] = {
        "success": system_success,
        "result": system_result
    }
    
    # Общий результат
    all_success = db_success and api_success and system_success
    report["overall_success"] = all_success
    
    # Записываем отчет в файл
    with open(f"monitoring_report_{int(time.time())}.json", "w") as f:
        json.dump(report, f, indent=2)
    
    # Если есть проблемы, отправляем оповещение
    if not all_success:
        subject = "ВНИМАНИЕ: Проблемы с сервисом Content Manager"
        message = f"Обнаружены проблемы при мониторинге:\n\n"
        
        if not db_success:
            message += f"- Проблемы с базой данных: {db_result}\n"
        if not api_success:
            message += f"- Проблемы с API: {json.dumps(api_result, indent=2)}\n"
        if not system_success:
            message += f"- Проблемы с системными ресурсами: {json.dumps(system_result, indent=2)}\n"
        
        send_email_alert(subject, message)
    
    return report

async def continuous_monitoring():
    """Запускает мониторинг с заданной периодичностью"""
    while True:
        try:
            report = await run_monitoring()
            logger.info(f"Мониторинг завершен: общий статус = {report['overall_success']}")
        except Exception as e:
            logger.error(f"Ошибка при выполнении мониторинга: {e}")
        
        # Ждем до следующей проверки
        logger.info(f"Следующая проверка через {MONITOR_INTERVAL} секунд")
        await asyncio.sleep(MONITOR_INTERVAL)

if __name__ == "__main__":
    logger.info("Запуск системы мониторинга...")
    
    # Если передан аргумент --once, выполняем мониторинг один раз
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        asyncio.run(run_monitoring())
    else:
        # Запускаем непрерывный мониторинг
        asyncio.run(continuous_monitoring()) 