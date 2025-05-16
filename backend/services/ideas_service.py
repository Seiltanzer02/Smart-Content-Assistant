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
                "message": f"Достигнут лимит в 3 генерации идей для бесплатной подписки. Следующая попытка будет доступна после: {reset_at}. Лимиты обновляются каждые 3 дня.",
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
        
        # Проверка наличия хотя бы одного API ключа
        if not OPENROUTER_API_KEY and not OPENAI_API_KEY:
            logger.warning("Генерация плана невозможна: отсутствуют OPENROUTER_API_KEY и OPENAI_API_KEY")
            # Создаем базовый план без использования API
            plan_items = []
            for day in range(1, period_days + 1):
                random_theme = random.choice(themes)
                random_style = random.choice(styles)
                plan_items.append({
                    "day": day,
                    "topic_idea": f"Пост о {random_theme}",
                    "format_style": random_style
                })
            logger.info(f"Создан базовый план из {len(plan_items)} идей (без использования API)")
            return {"plan": plan_items, "message": "План сгенерирован с базовыми идеями (API недоступен)"}
            
        system_prompt = f"""Ты - опытный контент-маркетолог. Твоя задача - сгенерировать план публикаций для Telegram-канала на {period_days} дней.\nИспользуй предоставленные темы и стили.\n\nТемы: {', '.join(themes)}\nСтили (используй ТОЛЬКО их): {', '.join(styles)}\n\nДля КАЖДОГО дня из {period_days} дней предложи ТОЛЬКО ОДНУ идею поста (конкретный заголовок/концепцию) и выбери ТОЛЬКО ОДИН стиль из списка выше.\n\nСТРОГО СЛЕДУЙ ФОРМАТУ ВЫВОДА:\nКаждая строка должна содержать только день, идею и стиль, разделенные ДВУМЯ двоеточиями (::).\nНЕ ДОБАВЛЯЙ НИКАКИХ ЗАГОЛОВКОВ, НОМЕРОВ ВЕРСИЙ, СПИСКОВ ФИЧ, КОММЕНТАРИЕВ ИЛИ ЛЮБОГО ДРУГОГО ЛИШНЕГО ТЕКСТА.\nТолько строки плана.\n\nПример НУЖНОГО формата:\nДень 1:: Запуск нового продукта X:: Анонс\nДень 2:: Советы по использованию Y:: Лайфхак\nДень 3:: Интервью с экспертом Z:: Интервью\n\nФормат КАЖДОЙ строки: День <номер_дня>:: <Идея поста>:: <Стиль из списка>"""
        
        user_prompt = f"""Сгенерируй план контента для Telegram-канала \"{channel_name}\" на {period_days} дней.\nТемы: {', '.join(themes)}\nСтили (используй ТОЛЬКО их): {', '.join(styles)}\n\nВыдай ровно {period_days} строк СТРОГО в формате:\nДень <номер_дня>:: <Идея поста>:: <Стиль из списка>\n\nНе включай ничего, кроме этих строк."""
        
        # Сначала пробуем OpenRouter API, если он доступен
        plan_text = ""
        used_backup_api = False
        
        if OPENROUTER_API_KEY:
            try:
                logger.info(f"Отправка запроса на генерацию плана через OpenRouter API для канала {channel_name}")
                client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=OPENROUTER_API_KEY
                )
                
                response = await client.chat.completions.create(
                    model="meta-llama/llama-4-maverick:free",
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=150 * period_days,
                    timeout=120,
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
                    logger.error(f"Некорректный или пустой ответ от OpenRouter API при генерации плана. Status: {response.response.status_code if hasattr(response, 'response') else 'N/A'}")
                    try:
                        raw_response_content = await response.response.text() if hasattr(response, 'response') and hasattr(response.response, 'text') else str(response)
                        logger.error(f"Полный ответ API (или его представление): {raw_response_content}")
                    except Exception as log_err:
                        logger.error(f"Не удалось залогировать тело ответа API: {log_err}")
                    # Ошибка OpenRouter API - пробуем запасной вариант
                    raise Exception("Некорректный или пустой ответ от OpenRouter API")
                
            except Exception as api_error:
                # В случае ошибки с OpenRouter API, проверяем наличие запасного ключа
                logger.error(f"Ошибка при запросе к OpenRouter API: {api_error}", exc_info=True)
                
                # Пробуем использовать OpenAI API как запасной вариант
                if OPENAI_API_KEY:
                    used_backup_api = True
                    logger.info(f"Попытка использования OpenAI API как запасного варианта для генерации плана канала {channel_name}")
                    try:
                        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
                        
                        openai_response = await openai_client.chat.completions.create(
                            model="gpt-3.5-turbo",  # Используем GPT-3.5 Turbo как запасной вариант
                            messages=[
                                {"role": "user", "content": user_prompt}
                            ],
                            temperature=0.7,
                            max_tokens=150 * period_days
                        )
                        
                        if openai_response and openai_response.choices and len(openai_response.choices) > 0 and openai_response.choices[0].message:
                            plan_text = openai_response.choices[0].message.content.strip()
                            logger.info(f"Получен план через запасной OpenAI API для канала {channel_name}")
                        else:
                            logger.error(f"Некорректный или пустой ответ от запасного OpenAI API")
                            plan_text = ""
                    except Exception as openai_error:
                        logger.error(f"Ошибка при использовании запасного OpenAI API: {openai_error}", exc_info=True)
                        plan_text = ""
                else:
                    logger.error("Запасной OPENAI_API_KEY не настроен, невозможно использовать альтернативный API")
                    plan_text = ""
        
        # Если нет OPENROUTER_API_KEY, но есть OPENAI_API_KEY, используем его напрямую
        elif OPENAI_API_KEY:
            used_backup_api = True
            logger.info(f"OPENROUTER_API_KEY отсутствует, используем OpenAI API напрямую для канала {channel_name}")
            try:
                openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
                
                openai_response = await openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",  # Используем GPT-3.5 Turbo 
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=150 * period_days
                )
                
                if openai_response and openai_response.choices and len(openai_response.choices) > 0 and openai_response.choices[0].message:
                    plan_text = openai_response.choices[0].message.content.strip()
                    logger.info(f"Получен план публикаций через OpenAI API для канала {channel_name}")
                else:
                    logger.error(f"Некорректный или пустой ответ от OpenAI API")
                    plan_text = ""
            except Exception as openai_error:
                logger.error(f"Ошибка при запросе к OpenAI API: {openai_error}", exc_info=True)
                plan_text = ""
                
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
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос пакетного сохранения идей без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для сохранения идей необходимо авторизоваться через Telegram")
        
        ideas = payload.ideas
        channel_name = payload.channel_name
        
        if not ideas or not isinstance(ideas, list):
            logger.warning(f"Некорректный запрос на сохранение идей. payload.ideas: {ideas}")
            raise HTTPException(status_code=400, detail="Необходимо предоставить непустой список идей")
        
        saved_ideas = []
        
        for idea in ideas:
            try:
                idea_to_save = {}
                
                # Обязательные поля для идеи
                if "topic_idea" not in idea or not idea["topic_idea"]:
                    logger.warning(f"Пропущена идея без topic_idea: {idea}")
                    continue
                
                idea_to_save["topic_idea"] = idea["topic_idea"]
                idea_to_save["format_style"] = idea.get("format_style", "")
                idea_to_save["user_id"] = int(telegram_user_id)
                idea_to_save["channel_name"] = channel_name if channel_name else idea.get("channel_name", "")
                idea_to_save["id"] = str(uuid.uuid4())
                
                # Опциональные поля
                if "day" in idea:
                    idea_to_save["relative_day"] = idea["day"]
                elif "relative_day" in idea:
                    idea_to_save["relative_day"] = idea["relative_day"]
                
                idea_to_save["is_detailed"] = idea.get("is_detailed", False)
                
                # Сохраняем идею в БД
                result = supabase.table("suggested_ideas").insert(idea_to_save).execute()
                
                if hasattr(result, 'data') and len(result.data) > 0:
                    saved_ideas.append({
                        "id": idea_to_save["id"],
                        "topic_idea": idea_to_save["topic_idea"],
                        "format_style": idea_to_save["format_style"]
                    })
                else:
                    logger.error(f"Ошибка при сохранении идеи в пакетном режиме: {result}")
            except Exception as idea_error:
                logger.error(f"Ошибка при обработке идеи в пакетном сохранении: {idea_error}")
                continue
        
        if saved_ideas:
            logger.info(f"Сохранено {len(saved_ideas)} идей для пользователя {telegram_user_id}")
            return {"success": True, "saved_count": len(saved_ideas), "saved_ideas": saved_ideas}
        else:
            logger.warning(f"Не удалось сохранить ни одной идеи для пользователя {telegram_user_id}")
            return {"success": False, "saved_count": 0, "message": "Не удалось сохранить ни одной идеи"}
    except Exception as e:
        logger.error(f"Ошибка при пакетном сохранении идей: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при пакетном сохранении идей: {str(e)}") 