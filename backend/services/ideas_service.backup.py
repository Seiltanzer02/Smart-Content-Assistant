# Сервис для работы с идеями и генерацией плана
from fastapi import Request, HTTPException
from typing import Dict, Any, List, Optional
from backend.main import supabase, logger, OPENROUTER_API_KEY, OPENAI_API_KEY
from pydantic import BaseModel
import random
import re
import uuid
from openai import AsyncOpenAI
from backend.services.supabase_subscription_service import SupabaseSubscriptionService
from datetime import datetime

# Импорт моделей PlanItem, PlanGenerationResponse, SuggestedIdeasResponse, SaveIdeasRequest из main.py или отдельного файла моделей
# from backend.models import PlanItem, PlanGenerationResponse, SuggestedIdeasResponse, SaveIdeasRequest

# Функция очистки форматирования (можно вынести в utils)
def clean_text_formatting(text):
    if not text:
        return ""
    text = re.sub(r'#{1,6}\s*\*?\*?(?:[Дд]ень|ДЕНЬ)?\s*\d+\s*(?:[Дд]ень|ДЕНЬ)?\*?\*?', '', text)
    text = re.sub(r'^(?:\*?\*?(?:[Дд]ень|ДЕНЬ)?\s*\d+\s*(?:[Дд]ень|ДЕНЬ)?\*?\*?)', '', text)
    text = re.sub(r'\*\*|\*|__|_|#{1,6}', '', text)
    text = text.strip()
    if text and len(text) > 0:
        text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
    return text

async def get_saved_ideas(request: Request, channel_name: Optional[str] = None):
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос идей без идентификации пользователя Telegram")
            return {"message": "Для доступа к идеям необходимо авторизоваться через Telegram", "ideas": []}
        try:
            telegram_user_id = int(telegram_user_id)
        except (ValueError, TypeError):
            logger.error(f"Некорректный ID пользователя в заголовке: {telegram_user_id}")
            return {"message": "Некорректный ID пользователя", "ideas": []}
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            return {"message": "Ошибка: не удалось подключиться к базе данных", "ideas": []}
        query = supabase.table("suggested_ideas").select("*").eq("user_id", telegram_user_id)
        if channel_name:
            query = query.eq("channel_name", channel_name)
        result = query.order("created_at", desc=True).execute()
        if not hasattr(result, 'data'):
            logger.error(f"Ошибка при получении идей из БД: {result}")
            return {"message": "Не удалось получить сохраненные идеи", "ideas": []}
        ideas = []
        for item in result.data:
            idea = {
                "id": item.get("id"),
                "channel_name": item.get("channel_name"),
                "topic_idea": item.get("topic_idea"),
                "format_style": item.get("format_style"),
                "relative_day": item.get("relative_day"),
                "is_detailed": item.get("is_detailed"),
                "created_at": item.get("created_at")
            }
            if idea["topic_idea"]:
                ideas.append(idea)
            else:
                logger.warning(f"Пропущена идея без topic_idea: ID={idea.get('id', 'N/A')}")
        logger.info(f"Получено {len(ideas)} идей для пользователя {telegram_user_id}")
        return {"ideas": ideas}
    except Exception as e:
        logger.error(f"Ошибка при получении идей: {e}")
        return {"message": f"Ошибка при получении идей: {str(e)}", "ideas": []}

async def generate_content_plan(request: Request, req):
    try:
        used_backup_api = False
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос генерации плана без идентификации пользователя Telegram")
            return {"message": "Для генерации плана необходимо авторизоваться через Telegram", "plan": []}
        # Проверка лимита генерации идей
        subscription_service = SupabaseSubscriptionService(supabase)
        can_generate = await subscription_service.can_generate_idea(int(telegram_user_id))
        if not can_generate:
            usage = await subscription_service.get_user_usage(int(telegram_user_id))
            reset_at = usage.get("reset_at")
            return {
                "plan": [],
                "message": f"Достигнут лимит в 3 генерации идей для бесплатной подписки. Следующая попытка будет доступна после: {reset_at}. Лимиты обновляются каждые 3 дня. Оформите подписку для снятия ограничений.",
                "limit_reached": True,
                "reset_at": reset_at,
                "subscription_required": True
            }
        themes = req.themes
        styles = req.styles
        period_days = req.period_days
        channel_name = req.channel_name
        if not themes or not styles:
            logger.warning(f"Запрос с пустыми темами или стилями: themes={themes}, styles={styles}")
            return {"message": "Необходимо указать темы и стили для генерации плана", "plan": []}
        
        # Тестовые данные, которые добавил ChatGPT
        logger.info(f"Запрос генерации плана контента от пользователя {telegram_user_id} для канала {channel_name}")
        
        # Готовим промпт для генерации плана
        system_prompt = """Ты — опытный контент-маркетолог для Telegram-каналов.
Твоя задача — создать план публикаций на определенный период, учитывая темы и форматы канала.

План должен быть:
1. Разнообразным (разные темы и форматы)
2. Логично выстроенным (связанные темы могут идти последовательно)
3. Реалистичным для реализации

Выдай результат в JSON-формате со списком постов для каждого дня."""

        user_prompt = f"""Создай план публикаций для Telegram-канала тематики: {', '.join(themes[:5])} на {period_days} дней.

Вот список возможных форматов постов:
{', '.join(styles[:5])}

Создай план в формате JSON:
[
  {{
    "day": 1,
    "topic_idea": "Конкретная тема/идея поста",
    "format_style": "Один из предложенных форматов"
  }},
  ...
]

Необходимо создать {period_days} идей для постов - по одной на каждый день."""
        
        plan_text = None
        
        if OPENROUTER_API_KEY:
            try:
                logger.info(f"Отправка запроса на генерацию плана через OpenRouter API для канала {channel_name}")
                client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=OPENROUTER_API_KEY
                )
                
                response = await client.chat.completions.create(
                    model="meta-llama/llama-3.2-1b-instruct",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1200,
                    timeout=60,
                    extra_headers={
                        "HTTP-Referer": "https://content-manager.onrender.com",
                        "X-Title": "Smart Content Assistant"
                    }
                )
                
                if response and response.choices and len(response.choices) > 0 and response.choices[0].message and response.choices[0].message.content:
                    plan_text = response.choices[0].message.content.strip()
                    logger.info(f"Получен ответ с планом публикаций через OpenRouter API (первые 100 символов): {plan_text[:100]}...")
                elif response and hasattr(response, 'error') and response.error:
                    err_details = response.error
                    api_error_message = getattr(err_details, 'message', str(err_details))
                    logger.error(f"OpenRouter API вернул ошибку: {api_error_message}")
                    # Ошибка OpenRouter API - пробуем запасной вариант
                    raise Exception(f"OpenRouter API вернул ошибку: {api_error_message}")
                else:
                    # Проблема с ответом API
                    try:
                        logger.error(f"Некорректный или пустой ответ от OpenRouter API. Ответ: {response}")
                    except Exception as log_err:
                        logger.error(f"Не удалось залогировать тело ответа API: {log_err}")
                    # Ошибка OpenRouter API - пробуем запасной вариант
                    raise Exception("Некорректный или пустой ответ от OpenRouter API")
            except Exception as api_error:
                # В случае ошибки с OpenRouter API, проверяем наличие запасного ключа
                api_error_message = f"Ошибка соединения с OpenRouter API: {str(api_error)}"
                logger.error(f"Ошибка при запросе к OpenRouter API: {api_error}", exc_info=True)
                
                # Пробуем использовать OpenAI API как запасной вариант
                if OPENAI_API_KEY:
                    used_backup_api = True
                    logger.info(f"Попытка использования OpenAI API как запасного варианта для канала {channel_name}")
                    try:
                        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
                        
                        openai_response = await openai_client.chat.completions.create(
                            model="gpt-3.5-turbo",  # Используем GPT-3.5 Turbo как запасной вариант
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            temperature=0.7,
                            max_tokens=1200
                        )
                        
                        if openai_response and openai_response.choices and len(openai_response.choices) > 0 and openai_response.choices[0].message:
                            plan_text = openai_response.choices[0].message.content.strip()
                            logger.info(f"Получен план через запасной OpenAI API ({len(plan_text)} символов)")
                            # Сбрасываем сообщение об ошибке, так как запасной вариант сработал
                            api_error_message = None
                        else:
                            logger.error(f"Некорректный или пустой ответ от запасного OpenAI API")
                            return {
                                "plan": [],
                                "message": "Ошибка при генерации плана (некорректный ответ API).",
                                "limit_reached": False
                            }
                    except Exception as openai_error:
                        logger.error(f"Ошибка при использовании запасного OpenAI API: {openai_error}", exc_info=True)
                        return {
                            "plan": [],
                            "message": f"Ошибка при генерации плана: {str(openai_error)}",
                            "limit_reached": False
                        }
                else:
                    logger.error("Запасной OPENAI_API_KEY не настроен, невозможно использовать альтернативный API")
                    return {
                        "plan": [],
                        "message": "Ошибка при генерации плана. API для генерации недоступны.",
                        "limit_reached": False
                    }
        # Если нет OPENROUTER_API_KEY, но есть OPENAI_API_KEY, используем его напрямую
        elif OPENAI_API_KEY:
            used_backup_api = True
            logger.info(f"OPENROUTER_API_KEY отсутствует, используем OpenAI API напрямую для канала {channel_name}")
            try:
                openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
                
                openai_response = await openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",  # Используем GPT-3.5 Turbo
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1200
                )
                
                if openai_response and openai_response.choices and len(openai_response.choices) > 0 and openai_response.choices[0].message:
                    plan_text = openai_response.choices[0].message.content.strip()
                    logger.info(f"Получен план через OpenAI API ({len(plan_text)} символов)")
                else:
                    logger.error(f"Некорректный или пустой ответ от OpenAI API")
                    return {
                        "plan": [],
                        "message": "Ошибка при генерации плана (некорректный ответ API).",
                        "limit_reached": False
                    }
            except Exception as openai_error:
                api_error_message = f"Ошибка соединения с OpenAI API: {str(openai_error)}"
                logger.error(f"Ошибка при запросе к OpenAI API: {openai_error}", exc_info=True)
                return {
                    "plan": [],
                    "message": f"Ошибка при генерации плана: {str(openai_error)}",
                    "limit_reached": False
                }
        else:
            logger.error("Отсутствуют API ключи для генерации плана (OPENROUTER_API_KEY и OPENAI_API_KEY)")
            return {
                "plan": [],
                "message": "API для генерации плана недоступны.",
                "limit_reached": False
            }
        
        # Обработка полученного текста плана
        plan_items = []
        
        if plan_text:
            lines = plan_text.split('\n')
            expected_style_set = set(s.lower() for s in styles)
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                parts = line.split('::')
                if len(parts) == 3:
                    try:
                        day_part = parts[0].lower().replace('день', '').strip()
                        day = int(day_part)
                        topic_idea = clean_text_formatting(parts[1].strip())
                        format_style = clean_text_formatting(parts[2].strip())
                        
                        if format_style.lower() not in expected_style_set:
                            logger.warning(f"Стиль '{format_style}' не найден в списке допустимых стилей: {styles}")
                            format_style = random.choice(styles) if styles else format_style
                            
                        if topic_idea:
                            plan_items.append({
                                "day": day,
                                "topic_idea": topic_idea,
                                "format_style": format_style
                            })
                        else:
                            logger.warning(f"Пропущена строка плана из-за пустой темы после очистки: {line}")
                    except Exception as parse_err:
                        logger.error(f"Ошибка при парсинге строки плана: {line} — {parse_err}")
                        continue
                else:
                    logger.warning(f"Строка плана не соответствует формату 'День X:: Тема:: Стиль': {line}")
        
        # Если не удалось извлечь идеи — генерируем базовый план вручную
        if not plan_items:
            logger.warning("Не удалось извлечь идеи из ответа LLM или все строки были некорректными, генерируем базовый план.")
            for day in range(1, period_days + 1):
                random_theme = random.choice(themes) if themes else "Общая тема"
                random_style = random.choice(styles) if styles else "Общий стиль"
                plan_items.append({
                    "day": day,
                    "topic_idea": f"Пост о {random_theme}",
                    "format_style": random_style
                })
        
        # Сортируем по дням и обрезаем до нужного количества
        plan_items.sort(key=lambda x: x["day"])
        plan_items = plan_items[:period_days]
        
        # Формируем сообщение с учетом использования запасного API
        result_message = None
        if used_backup_api:
            result_message = "План сгенерирован с использованием резервного API (OpenAI)"
        
        # После успешной генерации идей увеличиваем счетчик использования
        await subscription_service.increment_idea_usage(int(telegram_user_id))
        
        return {"plan": plan_items, "message": result_message}
    except Exception as e:
        logger.error(f"Ошибка при генерации плана: {e}")
        return {"plan": [], "message": f"Ошибка при генерации плана: {str(e)}"}

async def save_suggested_idea(idea_data: Dict[str, Any], request: Request):
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос сохранения идеи без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для сохранения идеи необходимо авторизоваться через Telegram")
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        idea_to_save = idea_data.copy()
        idea_to_save["user_id"] = int(telegram_user_id)
        idea_to_save["id"] = str(uuid.uuid4())
        if "day" in idea_to_save:
            idea_to_save["relative_day"] = idea_to_save.pop("day")
        # Удаляем поле isNew, если оно есть
        if "isNew" in idea_to_save:
            del idea_to_save["isNew"]
        result = supabase.table("suggested_ideas").insert(idea_to_save).execute()
        if hasattr(result, 'data') and len(result.data) > 0:
            logger.info(f"Сохранена новая идея для пользователя {telegram_user_id}")
            return {"success": True, "id": idea_to_save["id"]}
        else:
            logger.error(f"Ошибка при сохранении идеи: {result}")
            raise HTTPException(status_code=500, detail="Ошибка при сохранении идеи")
    except Exception as e:
        logger.error(f"Ошибка при сохранении идеи: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении идеи: {str(e)}")

async def save_suggested_ideas_batch(payload, request: Request):
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # Преобразуем ID пользователя в целое число
    try:
        telegram_user_id = int(telegram_user_id)
    except (ValueError, TypeError):
        logger.error(f"Некорректный ID пользователя в заголовке: {telegram_user_id}")
        raise HTTPException(status_code=400, detail="Некорректный формат ID пользователя")
    if not supabase:
        logger.error("Supabase client not initialized")
        raise HTTPException(status_code=500, detail="Database not initialized")
        
    # Добавляем проверку лимита генерации идей
    subscription_service = SupabaseSubscriptionService(supabase)
    can_generate = await subscription_service.can_generate_idea(telegram_user_id)
    if not can_generate:
        usage = await subscription_service.get_user_usage(telegram_user_id)
        reset_at = usage.get("reset_at")
        raise HTTPException(
            status_code=403, 
            detail={
                "message": f"Достигнут лимит генерации идей для бесплатной подписки. Следующая попытка будет доступна после: {reset_at}.",
                "reset_at": reset_at,
                "limit_reached": True,
                "subscription_required": True
            }
        )
        
    saved_count = 0
    errors = []
    saved_ids = []
    ideas_to_save = payload.ideas
    channel_name = payload.channel_name
    logger.info(f"Получен запрос на сохранение {len(ideas_to_save)} идей для канала {channel_name}")
    # --- НАЧАЛО: Удаление старых идей для этого канала перед сохранением новых --- 
    if channel_name:
        try:
            delete_result = supabase.table("suggested_ideas")\
                .delete()\
                .eq("user_id", int(telegram_user_id))\
                .eq("channel_name", channel_name)\
                .execute()
            logger.info(f"Удалено {len(delete_result.data)} старых идей для канала {channel_name}")
        except Exception as del_err:
            logger.error(f"Ошибка при удалении старых идей для канала {channel_name}: {del_err}")
            errors.append(f"Ошибка удаления старых идей: {str(del_err)}")
    # --- КОНЕЦ: Удаление старых идей --- 
    # --- ДОБАВЛЕНО: Вызов fix_schema перед вставкой --- 
    try:
        logger.info("Вызов fix_schema непосредственно перед сохранением идей...")
        from backend.main import fix_schema
        fix_result = await fix_schema()
        if not fix_result.get("success"):
            logger.warning(f"Не удалось обновить/проверить схему перед сохранением идей: {fix_result}")
            errors.append("Предупреждение: не удалось проверить/обновить схему перед сохранением.")
        else:
            logger.info("Проверка/обновление схемы перед сохранением идей завершена успешно.")
    except Exception as pre_save_fix_err:
        logger.error(f"Ошибка при вызове fix_schema перед сохранением идей: {pre_save_fix_err}", exc_info=True)
        errors.append(f"Ошибка проверки схемы перед сохранением: {str(pre_save_fix_err)}")
    # --- КОНЕЦ ДОБАВЛЕНИЯ ---
    records_to_insert = []
    for idea_data in ideas_to_save:
        try:
            topic_idea = clean_text_formatting(idea_data.get("topic_idea", ""))
            format_style = clean_text_formatting(idea_data.get("format_style", ""))
            if not topic_idea or not format_style:
                continue
            idea_id = str(uuid.uuid4())
            # Корректно переносим day -> relative_day
            relative_day = idea_data.get("relative_day") or idea_data.get("day")
            # Заполняем все нужные поля
            record = {
                "id": idea_id,
                "user_id": int(telegram_user_id),
                "channel_name": idea_data.get("channel_name") or channel_name,
                "topic_idea": topic_idea,
                "format_style": format_style,
                "relative_day": relative_day,
                "created_at": datetime.now().isoformat(),
                "is_detailed": bool(idea_data.get("is_detailed", False)),
            }
            records_to_insert.append(record)
            saved_ids.append(idea_id)
        except Exception as e:
            errors.append(f"Ошибка подготовки идеи {idea_data.get('topic_idea')}: {str(e)}")
            logger.error(f"Ошибка подготовки идеи {idea_data.get('topic_idea')}: {str(e)}")
    if not records_to_insert:
        logger.warning("Нет идей для сохранения после обработки.")
        return {"message": "Нет корректных идей для сохранения.", "saved_count": 0, "errors": errors}
    try:
        result = supabase.table("suggested_ideas").insert(records_to_insert).execute()
        if hasattr(result, 'data') and result.data:
            saved_count = len(result.data)
            logger.info(f"Успешно сохранено {saved_count} идей батчем.")
            return {"message": f"Успешно сохранено {saved_count} идей.", "saved_count": saved_count, "saved_ids": saved_ids, "errors": errors}
        else:
            error_detail = getattr(result, 'error', 'Unknown error')
            logger.error(f"Ошибка при батч-сохранении идей: {error_detail}")
            errors.append(f"Ошибка при батч-сохранении: {error_detail}")
            logger.warning("Попытка сохранить идеи по одной...")
            saved_count_single = 0
            saved_ids_single = []
            for record in records_to_insert:
                try:
                    single_result = supabase.table("suggested_ideas").insert(record).execute()
                    if hasattr(single_result, 'data') and single_result.data:
                        saved_count_single += 1
                        saved_ids_single.append(record['id'])
                    else:
                        single_error = getattr(single_result, 'error', 'Unknown error')
                        errors.append(f"Ошибка сохранения идеи {record.get('topic_idea')}: {single_error}")
                        logger.error(f"Ошибка сохранения идеи {record.get('topic_idea')}: {single_error}")
                except Exception as single_e:
                    errors.append(f"Исключение при сохранении идеи {record.get('topic_idea')}: {str(single_e)}")
                    logger.error(f"Исключение при сохранении идеи {record.get('topic_idea')}: {str(single_e)}")
            logger.info(f"Сохранено {saved_count_single} идей по одной.")
            return {
                "message": f"Сохранено {saved_count_single} идей (остальные с ошибкой).",
                "saved_count": saved_count_single,
                "saved_ids": saved_ids_single,
                "errors": errors
            }
    except Exception as e:
        logger.error(f"Исключение при батч-сохранении идей: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Исключение при батч-сохранении: {str(e)}") 