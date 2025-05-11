# Сервис для работы с идеями и генерацией плана
from fastapi import Request, HTTPException
from typing import Dict, Any, List, Optional
from backend.main import supabase, logger, OPENROUTER_API_KEY
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
            return {"message": "Достигнут лимит генерации идей для бесплатной подписки. Оформите подписку для снятия ограничений.", "plan": []}
            
        themes = req.themes
        styles = req.styles
        period_days = req.period_days
        channel_name = req.channel_name
        if not themes or not styles:
            logger.warning(f"Запрос с пустыми темами или стилями: themes={themes}, styles={styles}")
            return {"message": "Необходимо указать темы и стили для генерации плана", "plan": []}
        if not OPENROUTER_API_KEY:
            logger.warning("Генерация плана невозможна: отсутствует OPENROUTER_API_KEY")
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
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free",
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
        plan_text = ""
        if response and response.choices and len(response.choices) > 0 and response.choices[0].message and response.choices[0].message.content:
            plan_text = response.choices[0].message.content.strip()
            logger.info(f"Получен ответ с планом публикаций (первые 100 символов): {plan_text[:100]}...")
        else:
            logger.error(f"Некорректный или пустой ответ от OpenRouter API при генерации плана. Status: {response.response.status_code if hasattr(response, 'response') else 'N/A'}")
            try:
                raw_response_content = await response.response.text() if hasattr(response, 'response') and hasattr(response.response, 'text') else str(response)
                logger.error(f"Полный ответ API (или его представление): {raw_response_content}")
            except Exception as log_err:
                logger.error(f"Не удалось залогировать тело ответа API: {log_err}")
            return {"plan": [], "message": "Ошибка: API не вернул ожидаемый результат для генерации плана."}
        plan_items = []
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
                        continue
                    plan_items.append({
                        "day": day,
                        "topic_idea": topic_idea,
                        "format_style": format_style
                    })
                except Exception as parse_err:
                    logger.error(f"Ошибка при парсинге строки плана: {line} — {parse_err}")
                    continue
        logger.info(f"Сгенерировано {len(plan_items)} пунктов плана")
        
        # После успешной генерации идей увеличиваем счетчик использования
        has_subscription = await subscription_service.has_active_subscription(int(telegram_user_id))
        if not has_subscription:
            await subscription_service.increment_idea_usage(int(telegram_user_id))
            
        return {"plan": plan_items}
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
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        try:
            telegram_user_id = int(telegram_user_id)
        except (ValueError, TypeError):
            logger.error(f"Некорректный ID пользователя в заголовке: {telegram_user_id}")
            raise HTTPException(status_code=400, detail="Некорректный формат ID пользователя")
        ideas_to_save = payload.ideas
        channel_name = payload.channel_name
        logger.info(f"Получен запрос на сохранение {len(ideas_to_save)} идей для канала {channel_name}")
        errors = []
        saved_ids = []
        # Удаляем старые идеи для этого канала
        if channel_name:
            try:
                delete_result = supabase.table("suggested_ideas")\
                    .delete()\
                    .eq("user_id", telegram_user_id)\
                    .eq("channel_name", channel_name)\
                    .execute()
                logger.info(f"Удалено {len(delete_result.data) if hasattr(delete_result, 'data') else 0} старых идей для канала {channel_name}")
            except Exception as del_err:
                logger.error(f"Ошибка при удалении старых идей для канала {channel_name}: {del_err}")
                errors.append(f"Ошибка удаления старых идей: {str(del_err)}")
        records_to_insert = []
        for idea_data in ideas_to_save:
            try:
                topic_idea = clean_text_formatting(idea_data.get("topic_idea", ""))
                format_style = clean_text_formatting(idea_data.get("format_style", ""))
                if not topic_idea:
                    continue
                idea_id = str(uuid.uuid4())
                record = {
                    "id": idea_id,
                    "user_id": telegram_user_id,
                    "channel_name": idea_data.get("channel_name") or channel_name,
                    "topic_idea": topic_idea,
                    "format_style": format_style,
                    "relative_day": idea_data.get("day") or idea_data.get("relative_day"),
                    "created_at": datetime.now().isoformat(),
                    "is_detailed": idea_data.get("is_detailed", False),
                }
                records_to_insert.append(record)
                saved_ids.append(idea_id)
            except Exception as e:
                errors.append(f"Ошибка подготовки идеи {idea_data.get('topic_idea')}: {str(e)}")
                logger.error(f"Ошибка подготовки идеи {idea_data.get('topic_idea')}: {str(e)}")
        if not records_to_insert:
            logger.warning("Нет идей для сохранения после обработки.")
            raise HTTPException(status_code=400, detail="Нет корректных идей для сохранения.")
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
                # Пытаемся сохранить по одной, если батч не удался
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
    except Exception as e:
        logger.error(f"Ошибка при пакетном сохранении идей: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при пакетном сохранении идей: {str(e)}") 