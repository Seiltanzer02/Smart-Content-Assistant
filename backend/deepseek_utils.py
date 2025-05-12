import json
import re
import logging
from typing import List, Dict
from openai import AsyncOpenAI
import os

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_KEY2 = os.getenv("OPENROUTER_API_KEY2")

async def analyze_content_with_deepseek(texts: List[str], api_key: str = None) -> Dict[str, List[str]]:
    """Анализ контента с использованием модели DeepSeek через OpenRouter API с fallback на второй ключ."""
    keys_to_try = [api_key] if api_key else [OPENROUTER_API_KEY, OPENROUTER_API_KEY2]
    for key in keys_to_try:
        if not key:
            continue
        try:
            if not texts or not key:
                logger.error("Отсутствуют тексты или API ключ для анализа")
                return {"themes": [], "styles": []}
            combined_text = "\n\n".join([f"Пост {i+1}: {text}" for i, text in enumerate(texts)])
            logger.info(f"Подготовлено {len(texts)} текстов для анализа через DeepSeek")
            client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
            response = await client.chat.completions.create(
                model="deepseek/deepseek-chat-v3-0324:free",
                messages=[{"role": "user", "content": combined_text}],
                temperature=0.7,
                max_tokens=512,
                timeout=60,
                extra_headers={
                    "HTTP-Referer": "https://content-manager.onrender.com",
                    "X-Title": "Smart Content Assistant"
                }
            )
            # --- Строгая проверка структуры ответа и логирование ---
            if response and hasattr(response, 'choices') and response.choices:
                first_choice = response.choices[0]
                if hasattr(first_choice, 'message') and first_choice.message and hasattr(first_choice.message, 'content'):
                    content = first_choice.message.content.strip()
                    logger.info(f"Получен анализ (первые 100 символов): {content[:100]}...")
                    try:
                        # Попробуем найти JSON в тексте
                        json_match = re.search(r'(\{.*\})', content, re.DOTALL)
                        if json_match:
                            content_json = json.loads(json_match.group(1))
                        else:
                            content_json = json.loads(content)
                        themes = content_json.get("themes", [])
                        styles = content_json.get("styles", [])
                        logger.info(f"Извлечено тем: {len(themes)}, стилей: {len(styles)}")
                        return {"themes": themes, "styles": styles}
                    except Exception as e:
                        logger.error(f"Ошибка парсинга JSON из ответа OpenRouter: {e}, content: {content}")
                        return {"themes": [], "styles": []}
                else:
                    logger.error(f"Ответ OpenRouter не содержит message.content: {first_choice}")
                    logger.error(f"Полный ответ: {response}")
                    return {"themes": [], "styles": []}
            else:
                logger.error(f"Ответ OpenRouter не содержит choices: {response}")
                return {"themes": [], "styles": []}
        except Exception as e:
            logger.warning(f"Ошибка анализа через DeepSeek с ключом {key[:6]}...: {e}")
            logger.error(f"Исключение при анализе: {e}", exc_info=True)
            continue
    logger.error("Ошибка анализа через DeepSeek: оба ключа не сработали")
    return {"themes": [], "styles": []} 