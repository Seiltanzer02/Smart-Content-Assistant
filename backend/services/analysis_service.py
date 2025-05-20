from fastapi import Request, HTTPException
from typing import List, Dict, Any, Optional
from backend.telegram_utils import get_telegram_posts_via_http, get_telegram_posts_via_telethon, get_sample_posts
from backend.deepseek_utils import analyze_content_with_deepseek
from backend.main import supabase, logger, OPENROUTER_API_KEY, OPENAI_API_KEY
from backend.services.supabase_subscription_service import SupabaseSubscriptionService
from datetime import datetime
from pydantic import BaseModel

class AnalyzeRequest(BaseModel):
    username: str

class AnalyzeResponse(BaseModel):
    themes: List[str]
    styles: List[str]
    analyzed_posts_sample: List[str]
    best_posting_time: str
    analyzed_posts_count: int
    message: Optional[str] = None
    error: Optional[str] = None

async def analyze_channel(request: Request, req: AnalyzeRequest):
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    logger.info(f"Начинаем анализ канала от пользователя: {telegram_user_id}")
    if not telegram_user_id or not telegram_user_id.isdigit():
        raise HTTPException(status_code=401, detail="Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram.")
    try:
        subscription_service = SupabaseSubscriptionService(supabase)
        can_analyze = await subscription_service.can_analyze_channel(int(telegram_user_id))
        if not can_analyze:
            usage = await subscription_service.get_user_usage(int(telegram_user_id))
            reset_at = usage.get("reset_at")
            raise HTTPException(status_code=403, detail=f"Достигнут лимит в 5 анализов каналов для бесплатной подписки. Следующая попытка будет доступна после: {reset_at}. Лимиты обновляются каждые 3 дня. Оформите подписку для снятия ограничений.")
        username = req.username.replace("@", "").strip()
        posts = []
        errors_list = []
        error_message = None
        # 1. HTTP парсер
        try:
            logger.info(f"Пытаемся получить посты канала @{username} через HTTP парсинг")
            http_posts = await get_telegram_posts_via_http(username)
            if http_posts and len(http_posts) > 0:
                posts = [{"text": post} for post in http_posts]
                logger.info(f"Успешно получено {len(posts)} постов через HTTP парсинг")
            else:
                logger.warning(f"HTTP парсинг не вернул постов для канала @{username}, пробуем Telethon")
                errors_list.append("HTTP: Не получены посты, пробуем Telethon")
        except Exception as http_error:
            logger.error(f"Ошибка при HTTP парсинге для канала @{username}: {http_error}")
            errors_list.append(f"HTTP: {str(http_error)}")
        # 2. Telethon
        if not posts:
            try:
                logger.info(f"Пытаемся получить посты канала @{username} через Telethon")
                telethon_posts, telethon_error = await get_telegram_posts_via_telethon(username)
                if telethon_error:
                    logger.warning(f"Ошибка Telethon для канала @{username}: {telethon_error}")
                    errors_list.append(f"Telethon: {telethon_error}")
                else:
                    posts = telethon_posts
                    logger.info(f"Успешно получено {len(posts)} постов через Telethon")
            except Exception as e:
                logger.error(f"Непредвиденная ошибка при получении постов канала @{username} через Telethon: {e}")
                errors_list.append(f"Ошибка Telethon: {str(e)}")
        # 3. Примеры
        sample_data_used = False
        if not posts:
            logger.warning(f"Не удалось получить посты канала {username}")
            
            # Проверяем наличие явных ошибок доступа, чтобы определить тип проблемы
            channel_not_exists = False
            channel_is_private = False
            
            for error in errors_list:
                if "No user has" in error or "not found" in error.lower() or "does not exist" in error.lower():
                    channel_not_exists = True
                    break
                if "private" in error.lower() or "not accessible" in error.lower() or "access" in error.lower():
                    channel_is_private = True
                    break
            
            if channel_not_exists:
                return AnalyzeResponse(
                    themes=[],
                    styles=[],
                    analyzed_posts_sample=[],
                    best_posting_time="",
                    analyzed_posts_count=0,
                    error=f"Канал @{username} не существует или закрытый. Пожалуйста, проверьте правильность написания имени канала."
                )
            elif channel_is_private:
                return AnalyzeResponse(
                    themes=[],
                    styles=[],
                    analyzed_posts_sample=[],
                    best_posting_time="",
                    analyzed_posts_count=0,
                    error=f"Канал @{username} является закрытым и недоступен для анализа. Выберите публичный канал."
                )
            else:
                return AnalyzeResponse(
                    themes=[],
                    styles=[],
                    analyzed_posts_sample=[],
                    best_posting_time="",
                    analyzed_posts_count=0,
                    error=f"Не удалось получить доступ к каналу @{username}. Возможно, канал не существует, является закрытым или превышен лимит запросов."
                )
                
        # 4. Анализируем первые 20 постов
        posts = posts[:20]
        logger.info(f"Анализируем {len(posts)} постов")
        texts = [post.get("text", "") for post in posts if post.get("text")]
        
        # Проверяем наличие API ключей и выбираем стратегию анализа
        used_backup_api = False
        
        if OPENROUTER_API_KEY:
            # Пробуем сначала использовать OpenRouter API
            try:
                logger.info(f"Анализируем посты канала @{username} с использованием OpenRouter API")
                try:
                    analysis_result = await analyze_content_with_deepseek(texts, OPENROUTER_API_KEY)
                except Exception as e:
                    logger.error(f"Ошибка анализа: {e}")
                    analysis_result = {"themes": [], "styles": []}
                
                themes = analysis_result.get("themes", [])
                styles = analysis_result.get("styles", [])
                
                if not themes and not styles:
                    # Если не получены результаты, пробуем запасной API
                    logger.warning(f"OpenRouter API не вернул результатов анализа для канала @{username}, пробуем использовать запасной API")
                    raise Exception("OpenRouter API не вернул результатов анализа")
            except Exception as api_error:
                logger.error(f"Ошибка при анализе через OpenRouter API: {api_error}")
                
                # Пробуем использовать OpenAI API как запасной вариант
                if OPENAI_API_KEY:
                    used_backup_api = True
                    try:
                        logger.info(f"Пробуем анализировать посты канала @{username} с использованием запасного OpenAI API")
                        
                        # Импортируем локально, чтобы избежать циклических импортов
                        from openai import AsyncOpenAI
                        
                        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
                        
                        # Подготавливаем короткую выборку текстов для GPT
                        sample_texts = [text[:2000] for text in texts[:10]]  # Ограничиваем размер и количество текстов
                        combined_texts = "\n\n---\n\n".join(sample_texts)
                        
                        prompt = f"""Проанализируй следующие посты из Telegram-канала и определи:
1. Основные темы канала (5-7 тем)
2. Стили/форматы постов (5-7 стилей)

Выдай ответ в JSON-формате:
{{
  "themes": ["тема1", "тема2", ...],
  "styles": ["стиль1", "стиль2", ...]
}}

Тексты постов:
{combined_texts}"""
                        
                        response = await openai_client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "Ты - аналитик контента для Telegram-каналов."},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.7,
                            max_tokens=500
                        )
                        
                        analysis_text = response.choices[0].message.content.strip()
                        
                        # Извлекаем JSON из ответа
                        import json
                        import re
                        
                        json_match = re.search(r'(\{.*\})', analysis_text, re.DOTALL)
                        if json_match:
                            analysis_text = json_match.group(1)
                        
                        try:
                            backup_analysis = json.loads(analysis_text)
                            themes = backup_analysis.get("themes", [])
                            styles = backup_analysis.get("styles", [])
                            logger.info(f"Успешно получены результаты анализа через запасной OpenAI API: темы:{len(themes)}, стили:{len(styles)}")
                            
                            if error_message:
                                error_message += " Использован запасной API для анализа."
                            else:
                                error_message = "Использован запасной API для анализа."
                                
                        except json.JSONDecodeError as json_err:
                            logger.error(f"Не удалось распарсить JSON из ответа OpenAI: {json_err}, ответ: {analysis_text}")
                            themes = []
                            styles = []
                            error_message = "Ошибка при анализе контента (ошибка парсинга JSON)."
                            
                    except Exception as openai_err:
                        logger.error(f"Ошибка при использовании запасного OpenAI API: {openai_err}")
                        themes = []
                        styles = []
                        error_message = "Ошибка при анализе контента через оба API."
                else:
                    # Нет запасного API
                    logger.error("Запасной API (OPENAI_API_KEY) не настроен, невозможно продолжить анализ")
                    themes = []
                    styles = []
                    error_message = "Ошибка при анализе контента (запасной API не настроен)."
        
        elif OPENAI_API_KEY:
            # Если нет OPENROUTER_API_KEY, но есть OPENAI_API_KEY, используем его напрямую
            used_backup_api = True
            try:
                logger.info(f"OPENROUTER_API_KEY отсутствует, используем OpenAI API напрямую для анализа канала @{username}")
                
                # Импортируем локально, чтобы избежать циклических импортов
                from openai import AsyncOpenAI
                
                openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
                
                # Подготавливаем короткую выборку текстов для GPT
                sample_texts = [text[:2000] for text in texts[:10]]  # Ограничиваем размер и количество текстов
                combined_texts = "\n\n---\n\n".join(sample_texts)
                
                prompt = f"""Проанализируй следующие посты из Telegram-канала и определи:
1. Основные темы канала (5-7 тем)
2. Стили/форматы постов (5-7 стилей)

Выдай ответ в JSON-формате:
{{
  "themes": ["тема1", "тема2", ...],
  "styles": ["стиль1", "стиль2", ...]
}}

Тексты постов:
{combined_texts}"""
                
                response = await openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Ты - аналитик контента для Telegram-каналов."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                
                analysis_text = response.choices[0].message.content.strip()
                
                # Извлекаем JSON из ответа
                import json
                import re
                
                json_match = re.search(r'(\{.*\})', analysis_text, re.DOTALL)
                if json_match:
                    analysis_text = json_match.group(1)
                
                try:
                    backup_analysis = json.loads(analysis_text)
                    themes = backup_analysis.get("themes", [])
                    styles = backup_analysis.get("styles", [])
                    logger.info(f"Успешно получены результаты анализа через OpenAI API: темы:{len(themes)}, стили:{len(styles)}")
                    
                    if error_message:
                        error_message += " Использован запасной API для анализа."
                    else:
                        error_message = "Использован запасной API для анализа."
                        
                except json.JSONDecodeError as json_err:
                    logger.error(f"Не удалось распарсить JSON из ответа OpenAI: {json_err}, ответ: {analysis_text}")
                    themes = []
                    styles = []
                    error_message = "Ошибка при анализе контента (ошибка парсинга JSON)."
                    
            except Exception as openai_err:
                logger.error(f"Ошибка при использовании OpenAI API: {openai_err}")
                themes = []
                styles = []
                error_message = "Ошибка при анализе контента через API."
                
        else:
            # Нет ни одного API ключа
            logger.error("Отсутствуют API ключи для анализа (OPENROUTER_API_KEY и OPENAI_API_KEY)")
            themes = ["Технологии", "Маркетинг", "Бизнес", "Аналитика", "Новости"]
            styles = ["Обзор", "Лайфхак", "Анонс", "Интервью", "Туториал"]
            error_message = "API для анализа контента недоступны. Использованы темы и стили по умолчанию."
        
        # 5. Сохраняем результат анализа в БД
        try:
            analysis_data = {
                "user_id": int(telegram_user_id),
                "channel_name": username,
                "themes": themes,
                "styles": styles,
                "analyzed_posts_count": len(posts),
                "sample_posts": [p.get("text", "") for p in posts[:10]],
                "best_posting_time": "18:00-20:00",  # Можно доработать
                "is_sample_data": sample_data_used,
                "used_backup_api": used_backup_api,  # Добавляем информацию об использовании запасного API
                "updated_at": datetime.now().isoformat()
            }
            analysis_check = supabase.table("channel_analysis").select("id").eq("user_id", telegram_user_id).eq("channel_name", username).execute()
            if hasattr(analysis_check, 'data') and len(analysis_check.data) > 0:
                supabase.table("channel_analysis").update(analysis_data).eq("user_id", telegram_user_id).eq("channel_name", username).execute()
            else:
                supabase.table("channel_analysis").insert(analysis_data).execute()
            # --- Обновляем allChannels в user_settings ---
            user_settings_result = supabase.table("user_settings").select("allChannels").eq("user_id", telegram_user_id).maybe_single().execute()
            all_channels = []
            if hasattr(user_settings_result, 'data') and user_settings_result.data and user_settings_result.data.get("allChannels"):
                all_channels = user_settings_result.data["allChannels"]
            if username not in all_channels:
                all_channels.append(username)
                supabase.table("user_settings").update({"allChannels": all_channels, "updated_at": datetime.now().isoformat()}).eq("user_id", telegram_user_id).execute()
        except Exception as db_error:
            logger.error(f"Ошибка при сохранении результатов анализа в БД: {db_error}")
        # 6. Увеличиваем счетчик использования
        try:
            await subscription_service.increment_analysis_usage(int(telegram_user_id))
        except Exception as counter_error:
            logger.error(f"Ошибка при увеличении счетчика анализа: {counter_error}")
        # 7. Возвращаем результат
        return AnalyzeResponse(
            themes=themes,
            styles=styles,
            analyzed_posts_sample=[post.get("text", "") for post in posts[:10]],
            best_posting_time="18:00-20:00",
            analyzed_posts_count=len(posts),
            message=error_message
        )
    except Exception as e:
        logger.error(f"Ошибка при анализе канала для пользователя {telegram_user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}") 