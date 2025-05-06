# Основные библиотеки
import os
import sys
import json
import logging
import asyncio
import httpx
import tempfile
import shutil
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

# FastAPI компоненты
from fastapi import FastAPI, Request, File, UploadFile, HTTPException, Query, Path, Response, Header, Depends, Form, Body
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

# Telethon
from telethon import TelegramClient
from telethon.errors import ChannelInvalidError, ChannelPrivateError, UsernameNotOccupiedError

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация FastAPI
app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Можно указать конкретные домены вместо "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение к Telegram (опционально, если нужно)
telegram_api_id = os.getenv("TELEGRAM_API_ID")
telegram_api_hash = os.getenv("TELEGRAM_API_HASH")
telegram_client = None

# Глобальные переменные
supabase = None

# Эндпоинт для обработки Telegram вебхуков
@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Вебхук для обработки обновлений от бота Telegram."""
    try:
        # Получаем данные запроса
        data = await request.json()
        logger.info(f"Получен вебхук от Telegram: {data}")
        
        # Проверяем, есть ли pre_checkout_query - обработаем его первым
        if "pre_checkout_query" in data:
            pre_checkout_query = data["pre_checkout_query"]
            query_id = pre_checkout_query.get("id")
            
            if query_id:
                logger.info(f"Обработка pre_checkout_query с ID: {query_id}")
                # Подтверждаем pre_checkout_query автоматически
                bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
                if not bot_token:
                    logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
                    return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not found"}
                
                # Отправляем ответ Telegram API
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"https://api.telegram.org/bot{bot_token}/answerPreCheckoutQuery",
                        json={
                            "pre_checkout_query_id": query_id,
                            "ok": True
                        }
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"pre_checkout_query успешно подтвержден: {response.json()}")
                        return {"ok": True, "message": "Pre-checkout query confirmed"}
                    else:
                        logger.error(f"Ошибка при подтверждении pre_checkout_query: {response.status_code} - {response.text}")
                        return {"ok": False, "error": f"Failed to confirm pre-checkout query: {response.status_code}"}
            
            return {"ok": False, "error": "Invalid pre_checkout_query format"}
        
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
            logger.info(f"Получена команда проверки премиума от пользователя {user_id}")
            
            try:
                # Проверяем премиум-статус пользователя через REST API вместо прямого подключения к БД
                # Проверяем, инициализирован ли Supabase клиент
                if not supabase:
                    logger.error("Supabase клиент не инициализирован")
                    await send_telegram_message(user_id, "Ошибка сервера: не удалось подключиться к базе данных. Пожалуйста, сообщите администратору.")
                    return {"ok": True, "error": "Supabase client not initialized"}
                
                # Запрашиваем активные подписки для пользователя через REST API
                try:
                    subscription_query = supabase.table("user_subscription").select("*").eq("user_id", user_id).eq("is_active", True).execute()
                    
                    logger.info(f"Результат запроса подписки через REST API: {subscription_query}")
                    
                    has_premium = False
                    end_date_str = 'неизвестно'
                    
                    # Проверяем результаты запроса
                    if hasattr(subscription_query, 'data') and subscription_query.data:
                        from datetime import datetime, timezone
                        
                        # Проверяем подписки на активность и срок
                        # ИСПРАВЛЕНО: Создаем datetime с UTC timezone
                        current_date = datetime.now(timezone.utc)
                        active_subscriptions = []
                        
                        for subscription in subscription_query.data:
                            end_date = subscription.get("end_date")
                            if end_date:
                                try:
                                    # Преобразуем дату из строки в объект datetime
                                    if isinstance(end_date, str):
                                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                    
                                    # Если дата окончания в будущем, добавляем в активные
                                    if end_date > current_date:
                                        active_subscriptions.append(subscription)
                                except Exception as e:
                                    logger.error(f"Ошибка при обработке даты подписки {end_date}: {e}")
                        
                        # Если есть активные подписки, устанавливаем has_premium = True
                        if active_subscriptions:
                            has_premium = True
                            # Берем самую позднюю дату окончания
                            latest_subscription = max(active_subscriptions, key=lambda x: x.get("end_date"))
                            end_date = latest_subscription.get("end_date")
                            if isinstance(end_date, str):
                                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                            end_date_str = end_date.strftime('%d.%m.%Y %H:%M')
                    
                    logger.info(f"Результат проверки подписки для {user_id}: has_premium={has_premium}, end_date={end_date_str}")
                    
                    # Формируем текст ответа
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
                                
                                for subscription in subscriptions:
                                    end_date = subscription.get("end_date")
                                    if end_date:
                                        try:
                                            # Преобразуем дату из строки в объект datetime
                                            if isinstance(end_date, str):
                                                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                            
                                            # Если дата окончания в будущем, добавляем в активные
                                            if end_date > current_date:
                                                active_subscriptions.append(subscription)
                                        except Exception as e:
                                            logger.error(f"Ошибка при обработке даты подписки {end_date}: {e}")
                                
                                # Если есть активные подписки, устанавливаем has_premium = True
                                has_premium = bool(active_subscriptions)
                                end_date_str = 'неизвестно'
                                
                                if active_subscriptions:
                                    # Берем самую позднюю дату окончания
                                    latest_subscription = max(active_subscriptions, key=lambda x: x.get("end_date"))
                                    end_date = latest_subscription.get("end_date")
                                    if isinstance(end_date, str):
                                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                    end_date_str = end_date.strftime('%d.%m.%Y %H:%M')
                                
                                logger.info(f"Результат проверки подписки через httpx для {user_id}: has_premium={has_premium}, end_date={end_date_str}")
                                
                                # Формируем текст ответа
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
        
        # Проверяем, есть ли успешный платеж
        if 'successful_payment' in message:
            logger.info(f"Получен успешный платеж от пользователя {user_id}")
            try:
                payment_data = message['successful_payment']
                invoice_payload = payment_data.get('invoice_payload', '')
                
                logger.info(f"Данные платежа: {payment_data}")
                logger.info(f"Payload: {invoice_payload}")
                
                # Парсим payload из платежа для определения типа подписки
                subscription_type = "standard"  # По умолчанию
                subscription_days = 30  # По умолчанию 1 месяц
                
                # Пытаемся получить тип подписки и длительность из payload
                if invoice_payload:
                    try:
                        # Предполагаем, что payload имеет формат JSON или разделитель
                        if invoice_payload.startswith('{') and invoice_payload.endswith('}'):
                            # JSON формат
                            payload_data = json.loads(invoice_payload)
                            subscription_type = payload_data.get('type', subscription_type)
                            subscription_days = payload_data.get('days', subscription_days)
                        else:
                            # Формат с разделителем
                            parts = invoice_payload.split(':')
                            if len(parts) >= 2:
                                subscription_type = parts[0]
                                try:
                                    subscription_days = int(parts[1])
                                except ValueError:
                                    pass  # Оставляем значение по умолчанию
                    except Exception as payload_error:
                        logger.error(f"Ошибка при парсинге invoice_payload: {payload_error}")
                
                # Записываем информацию о платеже в базу данных
                if supabase:
                    try:
                        # Получаем текущие UTC дату и время
                        start_date = datetime.now(timezone.utc)
                        # Вычисляем дату окончания подписки
                        end_date = start_date + timedelta(days=subscription_days)
                        
                        # Проверяем, есть ли уже активная подписка для этого пользователя
                        existing_subscription = supabase.table("user_subscription").select("*").eq("user_id", user_id).eq("is_active", True).execute()
                        
                        if hasattr(existing_subscription, 'data') and existing_subscription.data:
                            # Деактивируем существующую подписку
                            for subscription in existing_subscription.data:
                                subscription_id = subscription.get('id')
                                if subscription_id:
                                    supabase.table("user_subscription").update({"is_active": False}).eq("id", subscription_id).execute()
                                    logger.info(f"Деактивирована существующая подписка с ID {subscription_id} для пользователя {user_id}")
                        
                        # Создаем новую запись о подписке
                        new_subscription = {
                            "user_id": user_id,
                            "subscription_type": subscription_type,
                            "start_date": start_date.isoformat(),
                            "end_date": end_date.isoformat(),
                            "is_active": True,
                            "payment_data": json.dumps(payment_data)
                        }
                        
                        # Вставляем новую запись
                        subscription_result = supabase.table("user_subscription").insert(new_subscription).execute()
                        
                        if hasattr(subscription_result, 'data') and subscription_result.data:
                            logger.info(f"Успешно создана подписка для пользователя {user_id} до {end_date.strftime('%d.%m.%Y %H:%M')}")
                            
                            # Отправляем пользователю сообщение об успешной активации подписки
                            await send_telegram_message(
                                user_id, 
                                f"✅ ПРЕМИУМ подписка успешно активирована!\n"
                                f"Тип подписки: {subscription_type}\n"
                                f"Действует до: {end_date.strftime('%d.%m.%Y %H:%M')}\n\n"
                                f"Теперь вы можете пользоваться всеми премиум-функциями. Обновите страницу приложения, чтобы увидеть изменения."
                            )
                            
                            return {"ok": True, "message": "Subscription activated successfully"}
                        else:
                            logger.error(f"Ошибка при создании подписки: {subscription_result}")
                            await send_telegram_message(user_id, "Произошла ошибка при активации подписки. Пожалуйста, обратитесь в поддержку.")
                            return {"ok": False, "error": "Failed to create subscription record"}
                    
                    except Exception as db_error:
                        logger.error(f"Ошибка при обработке подписки в базе данных: {db_error}")
                        await send_telegram_message(user_id, "Произошла ошибка при обработке платежа. Пожалуйста, обратитесь в поддержку.")
                        return {"ok": False, "error": str(db_error)}
                else:
                    logger.error("Supabase клиент не инициализирован для обработки платежа")
                    await send_telegram_message(user_id, "Ошибка сервера: не удалось обработать платеж. Пожалуйста, обратитесь в поддержку.")
                    return {"ok": False, "error": "Supabase client not initialized"}
            
            except Exception as payment_error:
                logger.error(f"Ошибка при обработке платежа: {payment_error}")
                await send_telegram_message(user_id, "Произошла ошибка при обработке платежа. Пожалуйста, обратитесь в поддержку.")
                return {"ok": False, "error": str(payment_error)}
        
        # Обработка остальных типов сообщений
        return {"ok": True, "message": "Webhook processed successfully"}
    
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука Telegram: {e}")
        return {"ok": False, "error": str(e)}

# Функция для отправки сообщений пользователям Telegram
async def send_telegram_message(user_id, text):
    """Отправляет сообщение пользователю Telegram."""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
            return False
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": user_id,
                    "text": text,
                    "parse_mode": "HTML"  # Можно использовать HTML для форматирования
                }
            )
            
            if response.status_code == 200:
                logger.info(f"Сообщение успешно отправлено пользователю {user_id}")
                return True
            else:
                logger.error(f"Ошибка при отправке сообщения: {response.status_code} - {response.text}")
                return False
    
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения в Telegram: {e}")
        return False
