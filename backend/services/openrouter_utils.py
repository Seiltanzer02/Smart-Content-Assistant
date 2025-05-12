import os
import logging
from openai import AsyncOpenAI, OpenAIError

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_KEY2 = os.getenv("OPENROUTER_API_KEY2")
logger = logging.getLogger(__name__)

async def openrouter_with_fallback(request_func, *args, **kwargs):
    """Выполняет запрос к OpenRouter с fallback на второй ключ при ошибке."""
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
    logger.error(f"Ошибка OpenRouter API после попытки с обоими ключами. Собранные ошибки: {errors}")
    raise Exception(f"Ошибка OpenRouter API (оба ключа не сработали). Последние ошибки: {' | '.join(errors)}")

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
    response = await openrouter_with_fallback(do_request)
    if hasattr(response, "error") and response.error:
        raise Exception(f"OpenRouter API error (post-fallback): {response.error}")
    return response

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