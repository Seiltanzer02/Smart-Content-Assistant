#!/usr/bin/env python
"""
Скрипт для исправления отступов в файле main.py

Скрипт ищет строки с 'try:' без правильного отступа после них и исправляет эти проблемы.
Это решает ошибку 'IndentationError: expected an indented block after try statement'
"""

import os
import sys
import logging
import tempfile
import shutil

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_indentation(target_file=None):
    """
    Исправляет отступы после операторов try: в указанном файле.
    
    Args:
        target_file (str, optional): Путь к файлу для исправления. Если не указан,
                                   используется main.py в текущей директории.
    
    Returns:
        bool: True если были внесены изменения, иначе False
    """
    try:
        # Определение файла для исправления
        if target_file is None:
            target_file = os.path.join(os.path.dirname(__file__), "main.py")
        
        logger.info(f"Проверка и исправление отступов в файле: {target_file}")
        
        # Проверка существования файла
        if not os.path.exists(target_file):
            logger.error(f"Файл {target_file} не найден")
            return False
        
        # Чтение содержимого файла
        with open(target_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Признак того, что были внесены изменения
        changes_made = False
        
        # Поиск и исправление проблем с отступами после try:
        for i in range(len(lines) - 1):
            # Ищем строку с try: без отступа в следующей строке
            if lines[i].strip().endswith('try:'):
                next_line = lines[i + 1]
                # Если следующая строка не имеет отступа (не начинается с пробелов)
                if next_line.strip() and not next_line.startswith(' ') and not next_line.startswith('\t'):
                    # Определяем отступ текущей строки и применяем дополнительный отступ
                    current_indent = len(lines[i]) - len(lines[i].lstrip())
                    indent_str = ' ' * (current_indent + 4)  # Добавляем 4 пробела
                    
                    # Добавляем отступ к следующей строке
                    lines[i + 1] = indent_str + next_line.lstrip()
                    changes_made = True
                    logger.info(f"Исправлен отступ в строке {i+2}: {next_line.strip()}")
        
        # Если были внесены изменения, записываем файл заново
        if changes_made:
            # Сначала записываем во временный файл
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as temp:
                temp.writelines(lines)
                temp_name = temp.name
            
            # Затем заменяем оригинальный файл
            shutil.move(temp_name, target_file)
            logger.info(f"Файл {target_file} успешно исправлен")
            return True
        else:
            logger.info("Не найдено проблем с отступами в файле")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при исправлении отступов: {str(e)}")
        return False

def fix_telegram_webhook_function(target_file=None):
    """
    Специально исправляет функцию telegram_webhook, которая часто ломается.
    
    Args:
        target_file (str, optional): Путь к файлу для исправления. Если не указан,
                                   используется main.py в текущей директории.
    
    Returns:
        bool: True если были внесены изменения, иначе False
    """
    try:
        # Определение файла для исправления
        if target_file is None:
            target_file = os.path.join(os.path.dirname(__file__), "main.py")
        
        logger.info(f"Исправление функции telegram_webhook в файле: {target_file}")
        
        # Проверка существования файла
        if not os.path.exists(target_file):
            logger.error(f"Файл {target_file} не найден")
            return False
        
        # Чтение содержимого файла
        with open(target_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ищем функцию telegram_webhook
        webhook_start = "@app.post(\"/telegram/webhook\")"
        if webhook_start not in content:
            logger.error("Функция telegram_webhook не найдена в файле")
            return False
        
        # Исправленная версия функции telegram_webhook
        corrected_function = """@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Вебхук для обработки обновлений от бота Telegram."""
    try:
        # Получаем данные запроса
        data = await request.json()
        logger.info(f"Получен вебхук от Telegram: {data}")
        
        # Проверяем, есть ли сообщение
        message = data.get('message')
        if not message:
            return {"ok": True}
        
        # Получаем ID пользователя и текст сообщения
        user_id = message.get('from', {}).get('id')
        text = message.get('text', '')
        
        # Дополнительное логирование
        logger.info(f"Обрабатываем сообщение от пользователя {user_id}: {text}")
        
        # Если это команда /start с параметром check_premium или команда /check_premium
        if text.startswith('/start check_premium') or text == '/check_premium':
            logger.info(f"Пользователь {user_id} запросил проверку премиум-статуса")
            
            # Проверяем премиум-статус пользователя через REST API вместо прямого подключения к БД
            try:
                # Проверяем, инициализирован ли Supabase клиент
                if not supabase:
                    logger.error("Supabase клиент не инициализирован")
                    await send_telegram_message(user_id, "Ошибка: сервис базы данных временно недоступен. Пожалуйста, попробуйте позже.")
                    return {"ok": False, "error": "Supabase client not initialized"}
                
                # Запрос к базе данных через Supabase клиент
                try:
                    result = supabase.table("user_subscription").select("*").eq("user_id", int(user_id)).maybe_single().execute()
                    logger.info(f"Результат проверки премиум-статуса для пользователя {user_id}: {result}")
                    
                    # Проверяем, есть ли данные о подписке
                    subscription_data = result.data
                    has_premium = False
                    end_date_str = "Неизвестно"
                    
                    if subscription_data and subscription_data.get('is_active'):
                        # Получаем дату окончания подписки
                        end_date = subscription_data.get('end_date')
                        if end_date:
                            # Проверяем, не истекла ли подписка
                            from datetime import datetime, timezone
                            end_date_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                            current_date = datetime.now(timezone.utc)
                            
                            if end_date_dt > current_date:
                                has_premium = True
                                # Форматируем дату для отображения
                                end_date_str = end_date_dt.strftime("%d.%m.%Y %H:%M")
                                logger.info(f"Пользователь {user_id} имеет активную премиум-подписку до {end_date_str}")
                            else:
                                logger.info(f"У пользователя {user_id} истекла премиум-подписка: {end_date}")
                        else:
                            logger.warning(f"У пользователя {user_id} нет даты окончания подписки в БД")
                    else:
                        logger.info(f"У пользователя {user_id} нет активной подписки в БД")
                    
                    # Отправляем сообщение в зависимости от статуса
                    if has_premium:
                        reply_text = f"✅ У вас активирован ПРЕМИУМ доступ!\nДействует до: {end_date_str}\nОбновите страницу приложения, чтобы увидеть изменения."
                    else:
                        reply_text = "❌ У вас нет активной ПРЕМИУМ подписки.\nДля получения премиум-доступа оформите подписку в приложении."
                    
                    # Отправляем ответ пользователю
                    await send_telegram_message(user_id, reply_text)
                    
                    return {"ok": True, "has_premium": has_premium}
                except Exception as api_error:
                    logger.error(f"Ошибка при проверке премиум-статуса через REST API: {api_error}")
                    # Попробуем альтернативный способ проверки, используя REST API напрямую через httpx
                    try:
                        supabase_url = os.getenv("SUPABASE_URL")
                        supabase_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
                        
                        if not supabase_url or not supabase_key:
                            raise ValueError("Отсутствуют SUPABASE_URL или SUPABASE_KEY")
                        
                        # Формируем запрос к REST API Supabase
                        headers = {
                            "apikey": supabase_key,
                            "Authorization": f"Bearer {supabase_key}",
                            "Content-Type": "application/json"
                        }
                        
                        async with httpx.AsyncClient() as client:
                            response = await client.get(
                                f"{supabase_url}/rest/v1/user_subscription",
                                headers=headers,
                                params={
                                    "select": "*",
                                    "user_id": f"eq.{user_id}",
                                    "is_active": "eq.true"
                                }
                            )
                            
                            if response.status_code == 200:
                                subscriptions = response.json()
                                
                                # Проверяем подписки на активность и срок
                                from datetime import datetime, timezone
                                # ИСПРАВЛЕНО: Создаем datetime с UTC timezone
                                current_date = datetime.now(timezone.utc)
                                active_subscriptions = []
                                
                                for sub in subscriptions:
                                    # Проверяем, что подписка активна и не истекла
                                    if sub.get('is_active'):
                                        end_date = sub.get('end_date')
                                        if end_date:
                                            end_date_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                            if end_date_dt > current_date:
                                                active_subscriptions.append(sub)
                                                # Форматируем дату для отображения
                                                end_date_str = end_date_dt.strftime("%d.%m.%Y %H:%M")
                                
                                has_premium = len(active_subscriptions) > 0
                                
                                if has_premium:
                                    reply_text = f"✅ У вас активирован ПРЕМИУМ доступ!\nДействует до: {end_date_str}\nОбновите страницу приложения, чтобы увидеть изменения."
                                else:
                                    reply_text = "❌ У вас нет активной ПРЕМИУМ подписки.\nДля получения премиум-доступа оформите подписку в приложении."
                                
                                # Отправляем ответ пользователю
                                await send_telegram_message(user_id, reply_text)
                                
                                return {"ok": True, "has_premium": has_premium}
                            else:
                                logger.error(f"Ошибка при запросе к Supabase REST API: {response.status_code} - {response.text}")
                                raise Exception(f"HTTP Error: {response.status_code}")
                    
                    except Exception as httpx_error:
                        logger.error(f"Ошибка при проверке премиум-статуса через httpx: {httpx_error}")
                        await send_telegram_message(user_id, "Ошибка подключения к базе данных. Пожалуйста, попробуйте позже.")
                        return {"ok": False, "error": str(httpx_error)}
            
            except Exception as e:
                logger.error(f"Ошибка при проверке премиум-статуса: {e}")
                await send_telegram_message(user_id, f"Произошла ошибка при проверке статуса подписки. Пожалуйста, попробуйте позже.")
                return {"ok": False, "error": str(e)}
        
        # ... остальная обработка вебхуков ...
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука Telegram: {e}")
        return {"ok": False, "error": str(e)}"""
        
        # Заменяем существующую функцию на исправленную
        pattern_start = "@app.post(\"/telegram/webhook\")"
        # Ищем следующий декоратор маршрута после функции webhook
        pattern_end = "@app."
        
        # Находим позицию начала функции
        start_pos = content.find(pattern_start)
        if start_pos == -1:
            logger.error("Не удалось найти начало функции telegram_webhook")
            return False
        
        # Находим позицию следующего декоратора маршрута после нашей функции
        end_pos = content.find(pattern_end, start_pos + len(pattern_start))
        if end_pos == -1:
            # Если не найден следующий декоратор, ищем начало следующей функции
            end_pos = content.find("async def ", start_pos + len(pattern_start) + 100)  # Пропускаем определение самой функции
            
            if end_pos == -1:
                logger.error("Не удалось найти конец функции telegram_webhook")
                return False
        
        # Получаем текст до функции и после функции
        before = content[:start_pos]
        after = content[end_pos:]
        
        # Создаем новое содержимое файла
        new_content = before + corrected_function + "\n\n" + after
        
        # Записываем во временный файл
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as temp:
            temp.write(new_content)
            temp_name = temp.name
        
        # Заменяем оригинальный файл
        shutil.move(temp_name, target_file)
        logger.info(f"Функция telegram_webhook успешно исправлена в файле {target_file}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при исправлении функции telegram_webhook: {str(e)}")
        return False

def main():
    """Основная функция для запуска скрипта из командной строки."""
    logger.info("Запуск скрипта исправления отступов...")
    
    # Исправление общих отступов
    indentation_fixed = fix_indentation()
    
    # Исправление функции telegram_webhook
    webhook_fixed = fix_telegram_webhook_function()
    
    if indentation_fixed or webhook_fixed:
        logger.info("Внесены исправления в файл. Рекомендуется перезапустить приложение.")
        return True
    else:
        logger.info("Исправления не требуются.")
        return False

if __name__ == "__main__":
    main() 