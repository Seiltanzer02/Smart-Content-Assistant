import os
import httpx
from fastapi import Request
from log import logger

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
            logger.info(f"Получена команда проверки премиума от пользователя {user_id}")
            
            # Проверяем премиум-статус пользователя через REST API вместо прямого подключения к БД
            try:
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
        
        # ... остальная обработка вебхуков ...
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука Telegram: {e}")
        return {"ok": False, "error": str(e)} 