import os
import logging
import re
import random
from collections import Counter
from openai import AsyncOpenAI, OpenAIError

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_KEY2 = os.getenv("OPENROUTER_API_KEY2")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Fallback-обёртка для запросов к OpenRouter ---
async def openrouter_with_fallback(request_func, *args, **kwargs):
    errors = []
    try:
        from openai import RateLimitError, APIStatusError, APIError
        openai_errors_imported = True
    except ImportError:
        openai_errors_imported = False
        logger.warning("Не удалось импортировать специфичные ошибки openai. Будет использована базовая проверка статуса/текста.")
    for api_key in [OPENROUTER_API_KEY, OPENROUTER_API_KEY2]:
        if not api_key:
            logger.warning("Пропуск попытки: API ключ отсутствует.")
            continue
        try:
            client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
            logger.info(f"Попытка вызова OpenRouter API с ключом {api_key[:6]}...")
            return await request_func(client, *args, **kwargs)
        except Exception as e:
            error_message = str(e)
            errors.append(f"Key {api_key[:6]}...: {error_message}")
            logger.warning(f"Ошибка при вызове OpenRouter API с ключом {api_key[:6]}...: {e}")
            should_retry = False
            if openai_errors_imported:
                if isinstance(e, RateLimitError):
                    logger.warning(f"Поймана ошибка RateLimitError с ключом {api_key[:6]}... Попытка следующего ключа.")
                    should_retry = True
                elif isinstance(e, APIStatusError):
                    if e.status_code == 429:
                        logger.warning(f"Поймана ошибка APIStatusError 429 (Rate Limit) с ключом {api_key[:6]}... Попытка следующего ключа.")
                        should_retry = True
                    elif e.status_code in [401, 403]:
                        logger.warning(f"Поймана ошибка APIStatusError {e.status_code} (Auth/Permission) с ключом {api_key[:6]}... Попытка следующего ключа.")
                        should_retry = True
                    elif e.status_code in [500, 502, 503, 504]:
                        logger.warning(f"Поймана ошибка APIStatusError {e.status_code} (Server Error) с ключом {api_key[:6]}... Попытка следующего ключа.")
                        should_retry = True
                    else:
                        logger.error(f"Поймана непредусмотренная ошибка APIStatusError {e.status_code} с ключом {api_key[:6]}... Прерывание попыток.")
                elif isinstance(e, APIError):
                    logger.warning(f"Поймана общая ошибка APIError с ключом {api_key[:6]}...: {e}. Попытка следующего ключа (на всякий случай).")
                    should_retry = True
                else:
                    logger.error(f"Поймана неожиданная ошибка (не APIError) с ключом {api_key[:6]}...: {e}. Прерывание попыток.")
            else:
                if hasattr(e, 'status_code') and e.status_code in [401, 403, 429, 500, 502, 503, 504]:
                    logger.warning(f"(Fallback logic) Ошибка со статус кодом {e.status_code} для ключа {api_key[:6]}... Попытка следующего.")
                    should_retry = True
                elif 'rate limit' in error_message.lower() or 'quota' in error_message.lower():
                    logger.warning(f"(Fallback logic) Ошибка содержит 'rate limit' или 'quota' для ключа {api_key[:6]}... Попытка следующего.")
                    should_retry = True
                else:
                    logger.error(f"(Fallback logic) Непредусмотренная ошибка для ключа {api_key[:6]}...: {e}. Прерывание попыток.")
            if should_retry:
                continue
            else:
                break
    if OPENAI_API_KEY:
        try:
            logger.info("Попытка вызова OpenAI GPT-3.5 turbo с запасным ключом...")
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            # --- Определяем тип запроса по request_func и аргументам ---
            func_name = getattr(request_func, '__name__', '')
            # Для генерации плана (generate_plan_llm)
            if func_name == "do_request" and len(args) >= 1 and isinstance(args[0], str):
                user_prompt = args[0]
                period_days = args[1] if len(args) > 1 and isinstance(args[1], int) else 7
                if not user_prompt or not isinstance(user_prompt, str):
                    raise Exception("GPT-3.5: user_prompt отсутствует или не строка!")
                return await client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.7,
                    max_tokens=150 * period_days,
                    timeout=120
                )
            # Для генерации поста (generate_post_llm)
            elif func_name == "do_request" and len(args) >= 2 and all(isinstance(a, str) for a in args[:2]):
                system_prompt, user_prompt = args[0], args[1]
                if not system_prompt or not isinstance(system_prompt, str):
                    raise Exception("GPT-3.5: system_prompt отсутствует или не строка!")
                if not user_prompt or not isinstance(user_prompt, str):
                    raise Exception("GPT-3.5: user_prompt отсутствует или не строка!")
                return await client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    temperature=0.7,
                    max_tokens=850,
                    timeout=60
                )
            # Для генерации ключевых слов (generate_keywords_llm)
            elif func_name == "do_request" and len(args) >= 2 and all(isinstance(a, str) for a in args[:2]):
                system_prompt, user_prompt = args[0], args[1]
                if not system_prompt or not isinstance(system_prompt, str):
                    raise Exception("GPT-3.5: system_prompt отсутствует или не строка!")
                if not user_prompt or not isinstance(user_prompt, str):
                    raise Exception("GPT-3.5: user_prompt отсутствует или не строка!")
                return await client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    temperature=0.7,
                    max_tokens=100,
                    timeout=15
                )
            # Для анализа (analyze_content_with_deepseek_fallback)
            elif func_name == "do_request" and len(args) >= 1 and isinstance(args[0], list):
                texts = args[0]
                if not texts or not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
                    raise Exception("GPT-3.5: texts отсутствует или не список строк!")
                user_prompt = "\n\n".join(texts)
                return await client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.7,
                    max_tokens=512,
                    timeout=60
                )
            else:
                raise Exception(f"GPT-3.5 fallback: не удалось определить тип запроса или аргументы некорректны: func_name={func_name}, args={args}")
        except Exception as e:
            error_message = str(e)
            errors.append(f"Key OPENAI_API_KEY: {error_message}")
            logger.error(f"Ошибка при вызове OpenAI GPT-3.5 turbo: {e}")
    else:
        logger.warning("OPENAI_API_KEY не задан, пропускаем попытку с OpenAI GPT-3.5 turbo.")
    logger.error(f"Ошибка OpenRouter/OpenAI API после попытки со всеми ключами. Собранные ошибки: {errors}")
    raise Exception(f"Ошибка OpenRouter/OpenAI API (все ключи не сработали). Последние ошибки: {' | '.join(errors)}")

# --- Анализ контента (fallback) ---
async def analyze_content_with_deepseek_fallback(texts, api_key=None):
    from backend.deepseek_utils import analyze_content_with_deepseek as orig_analyze_content_with_deepseek
    async def do_request(client):
        return await orig_analyze_content_with_deepseek(texts, api_key)
    try:
        return await openrouter_with_fallback(do_request, texts, api_key)
    except Exception as e:
        logger.error(f"Ошибка анализа через DeepSeek/OpenRouter: {e}. Пробуем fallback на GPT-3.5-turbo...")
        # --- Fallback на GPT-3.5-turbo ---
        if not OPENAI_API_KEY:
            logger.error("Нет OPENAI_API_KEY для fallback анализа!")
            return {
                "themes": [],
                "styles": [],
                "analyzed_posts_sample": [],
                "best_posting_time": "",
                "analyzed_posts_count": len(texts),
                "message": "LLM анализ недоступен (нет ключей)",
                "error": str(e)
            }
        try:
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            # Формируем строгий промпт для анализа
            user_prompt = (
                "Проанализируй следующие посты Telegram-канала и выдели основные темы (3-5), стили оформления (2-3), "
                "приведи 2-3 примера постов (коротко), и укажи лучшее время публикации (например, '18:00' или 'утро'). "
                "Ответ строго в формате JSON: {\"themes\": [...], \"styles\": [...], \"analyzed_posts_sample\": [...], \"best_posting_time\": \"...\"}. "
                "Посты для анализа:\n\n"
                + "\n---\n".join(texts[:5])
            )
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.3,
                max_tokens=512,
                timeout=60
            )
            content = response.choices[0].message.content.strip()
            import json
            # Пробуем найти JSON в ответе
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = content[json_start:json_end]
                try:
                    data = json.loads(json_str)
                    return {
                        "themes": data.get("themes", []),
                        "styles": data.get("styles", []),
                        "analyzed_posts_sample": data.get("analyzed_posts_sample", []),
                        "best_posting_time": data.get("best_posting_time", ""),
                        "analyzed_posts_count": len(texts),
                        "message": "Анализ выполнен через GPT-3.5-turbo",
                        "error": None
                    }
                except Exception as json_err:
                    logger.error(f"Ошибка парсинга JSON из ответа GPT-3.5-turbo: {json_err}")
            # Если не удалось — возвращаем базовый анализ
            logger.warning("GPT-3.5-turbo не вернул корректный JSON, возвращаем базовый анализ.")
            return {
                "themes": [],
                "styles": [],
                "analyzed_posts_sample": texts[:3],
                "best_posting_time": "",
                "analyzed_posts_count": len(texts),
                "message": "LLM анализ недоступен (ошибка формата)",
                "error": str(e)
            }
        except Exception as gpt_err:
            logger.error(f"Ошибка анализа через GPT-3.5-turbo: {gpt_err}")
            return {
                "themes": [],
                "styles": [],
                "analyzed_posts_sample": texts[:3],
                "best_posting_time": "",
                "analyzed_posts_count": len(texts),
                "message": "LLM анализ недоступен (ошибка GPT-3.5-turbo)",
                "error": str(gpt_err)
            }

# --- Генерация плана ---
async def generate_plan_llm(user_prompt, period_days, styles, channel_name):
    async def do_request(client):
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.7,
            max_tokens=150 * period_days,
            timeout=120,
            extra_headers={
                "HTTP-Referer": "https://content-manager.onrender.com",
                "X-Title": "Smart Content Assistant"
            }
        )
        if hasattr(response, "error") and response.error:
            raise Exception(f"OpenRouter API error: {response.error}")
        return response
    try:
        response = await openrouter_with_fallback(do_request, user_prompt, period_days, styles, channel_name)
    except Exception as e:
        logger.error(f"Ошибка при генерации плана через OpenRouter с fallback: {e}")
        # Возвращаем базовый план, если всё сломалось
        plan_items = []
        for day in range(1, period_days + 1):
            random_theme = styles[0] if styles else "Общая тема"
            random_style = styles[0] if styles else "Общий стиль"
            plan_items.append({
                "day": day,
                "topic_idea": f"Пост о {random_theme}",
                "format_style": random_style
            })
        return plan_items
    # --- Парсим ответ ---
    plan_text = ""
    if response and hasattr(response, 'choices') and response.choices and response.choices[0].message and response.choices[0].message.content:
        plan_text = response.choices[0].message.content.strip()
    else:
        logger.error(f"Некорректный или пустой ответ от LLM при генерации плана. Status: {getattr(response, 'response', None)}")
        plan_text = ""
    # --- Пробуем извлечь идеи регуляркой ---
    plan_items = []
    pattern = re.compile(r"День\s*(\d+)::\s*(.+?)::\s*(.+)")
    for match in pattern.finditer(plan_text):
        try:
            day = int(match.group(1))
            topic_idea = match.group(2).strip()
            format_style = match.group(3).strip()
            plan_items.append({
                "day": day,
                "topic_idea": topic_idea,
                "format_style": format_style
            })
        except Exception as e:
            logger.warning(f"Ошибка парсинга строки плана: {e}")
    # Если не удалось — fallback к старому разбору
    if not plan_items:
        lines = plan_text.split('\n') if plan_text else []
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
                    topic_idea = parts[1].strip()
                    format_style = parts[2].strip()
                    if format_style.lower() not in expected_style_set:
                        format_style = styles[0] if styles else "Без указания стиля"
                    if topic_idea:
                        plan_items.append({
                            "day": day,
                            "topic_idea": topic_idea,
                            "format_style": format_style
                        })
                except Exception as parse_err:
                    logger.warning(f"Ошибка парсинга строки плана '{line}': {parse_err}")
    # Если всё равно пусто — возвращаем базовый план
    if not plan_items:
        logger.warning("Не удалось извлечь идеи из ответа LLM или все строки были некорректными, генерируем базовый план.")
        for day in range(1, period_days + 1):
            random_theme = styles[0] if styles else "Общая тема"
            random_style = styles[0] if styles else "Общий стиль"
            plan_items.append({
                "day": day,
                "topic_idea": f"Пост о {random_theme}",
                "format_style": random_style
            })
    plan_items.sort(key=lambda x: x["day"])
    plan_items = plan_items[:period_days]
    return plan_items

# --- Генерация поста ---
async def generate_post_llm(system_prompt, user_prompt):
    async def do_request(client):
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.7,
            max_tokens=850,
            timeout=60,
            extra_headers={
                "HTTP-Referer": "https://content-manager.onrender.com",
                "X-Title": "Smart Content Assistant"
            }
        )
        if hasattr(response, "error") and response.error:
            raise Exception(f"OpenRouter API error: {response.error}")
        return response
    response = await openrouter_with_fallback(do_request)
    if hasattr(response, "error") and response.error:
        raise Exception(f"OpenRouter API error (post-fallback): {response.error}")
    return response

# --- Генерация ключевых слов (LLM) ---
async def generate_keywords_llm(system_prompt, user_prompt):
    async def do_request(client):
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.7,
            max_tokens=100,
            timeout=15,
            extra_headers={
                "HTTP-Referer": "https://content-manager.onrender.com",
                "X-Title": "Smart Content Assistant"
            }
        )
        if hasattr(response, "error") and response.error:
            raise Exception(f"OpenRouter API error: {response.error}")
        return response
    response = await openrouter_with_fallback(do_request)
    if hasattr(response, "error") and response.error:
        raise Exception(f"OpenRouter API error (post-fallback): {response.error}")
    return response

# --- Генерация ключевых слов для поиска изображений ---
async def generate_image_keywords(text: str, topic: str, format_style: str) -> list:
    try:
        if not OPENROUTER_API_KEY and not OPENROUTER_API_KEY2 and not OPENAI_API_KEY:
            words = re.findall(r'\b[а-яА-Яa-zA-Z]{4,}\b', text.lower())
            stop_words = ["и", "в", "на", "с", "по", "для", "а", "но", "что", "как", "так", "это"]
            filtered_words = [w for w in words if w not in stop_words]
            result = []
            if topic:
                result.append(topic)
            if format_style:
                result.append(format_style)
            word_counts = Counter(filtered_words)
            common_words = [word for word, _ in word_counts.most_common(3)]
            result.extend(common_words)
            context_words = ["business", "abstract", "professional", "technology", "creative", "modern"]
            result.extend(random.sample(context_words, 2))
            return result
        system_prompt = """Твоя задача - сгенерировать 2-3 эффективных ключевых слова для поиска изображений.\nКлючевые слова должны точно отражать тематику текста и быть универсальными для поиска стоковых изображений.\nВыбирай короткие конкретные существительные на английском языке, даже если текст на русском.\nФормат ответа: список ключевых слов через запятую."""
        user_prompt = f"""Текст поста: {text[:300]}...\n\nТематика поста: {topic}\nФормат поста: {format_style}\n\nВыдай 2-3 лучших ключевых слова на английском языке для поиска подходящих изображений. Только ключевые слова, без объяснений."""
        response = await generate_keywords_llm(system_prompt, user_prompt)
        keywords_text = response.choices[0].message.content.strip()
        keywords_list = re.split(r'[,;\n]', keywords_text)
        keywords = [k.strip() for k in keywords_list if k.strip()]
        if not keywords:
            logger.warning("Не удалось получить ключевые слова от API, используем запасной вариант")
            return [topic, format_style] + random.sample(["business", "abstract", "professional"], 2)
        logger.info(f"Сгенерированы ключевые слова для поиска изображений: {keywords}")
        return keywords
    except Exception as e:
        logger.error(f"Ошибка при генерации ключевых слов для поиска изображений: {e}")
        return [topic, format_style, "concept", "idea"] 