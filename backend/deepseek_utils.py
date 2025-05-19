import json
import re
import logging
from typing import List, Dict
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

async def analyze_content_with_deepseek(texts: List[str], api_key: str) -> Dict[str, List[str]]:
    """Анализ контента с использованием нескольких моделей OpenRouter API с fallback на OpenAI."""
    if not api_key:
        logger.warning("Анализ контента с DeepSeek невозможен: отсутствует OPENROUTER_API_KEY")
        return {
            "themes": ["Тема 1", "Тема 2", "Тема 3", "Тема 4", "Тема 5"],
            "styles": ["Формат 1", "Формат 2", "Формат 3", "Формат 4", "Формат 5"]
        }
    if not texts or not api_key:
        logger.error("Отсутствуют тексты или API ключ для анализа")
        return {"themes": [], "styles": []}
    combined_text = "\n\n".join([f"Пост {i+1}: {text}" for i, text in enumerate(texts)])
    logger.info(f"Подготовлено {len(texts)} текстов для анализа через DeepSeek")
    system_prompt = """Ты - эксперт по анализу контента Telegram-каналов. \nТвоя задача - глубоко проанализировать предоставленные посты и выявить САМЫЕ ХАРАКТЕРНЫЕ, ДОМИНИРУЮЩИЕ темы и стили/форматы, отражающие СУТЬ и УНИКАЛЬНОСТЬ канала. \nИзбегай слишком общих формулировок, если они не являются ключевыми. Сосредоточься на качестве, а не на количестве.\n\nВыдай результат СТРОГО в формате JSON с двумя ключами: \"themes\" и \"styles\". Каждый ключ должен содержать массив из 3-5 наиболее РЕЛЕВАНТНЫХ строк."""
    user_prompt = f"""Проанализируй СТРОГО следующие посты из Telegram-канала:\n{combined_text}\n\nОпредели 3-5 САМЫХ ХАРАКТЕРНЫХ тем и 3-5 САМЫХ РАСПРОСТРАНЕННЫХ стилей/форматов подачи контента, которые наилучшим образом отражают специфику ИМЕННО ЭТОГО канала. \nОсновывайся ТОЛЬКО на предоставленных текстах. \n\nПредставь результат ТОЛЬКО в виде JSON объекта с ключами \"themes\" и \"styles\". Никакого другого текста. \n\nОтветь только JSON-объектом, без пояснений, markdown и текста вокруг."""
    analysis_result = {"themes": [], "styles": []}
    openrouter_models = [
        "meta-llama/llama-4-maverick:free",
        "meta-llama/llama-4-scout:free",
        "google/gemini-2.0-flash-exp:free"
    ]
    for model_name in openrouter_models:
        try:
            client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key
            )
            response = await client.chat.completions.create(
                model=model_name,
                messages=build_messages(system_prompt, user_prompt, True),
                temperature=0.1,
                max_tokens=600,
                timeout=60,
                extra_headers={
                    "HTTP-Referer": "https://content-manager.onrender.com",
                    "X-Title": "Smart Content Assistant"
                }
            )
            analysis_text = response.choices[0].message.content.strip()
            logger.info(f"Получен ответ от {model_name}: {analysis_text[:100]}...")
            analysis_text = extract_json_from_llm_response(analysis_text)
            import re
            json_match = re.search(r'(\{.*\})', analysis_text, re.DOTALL)
            if json_match:
                analysis_text = json_match.group(1)
            import json
            analysis_json = json.loads(analysis_text)
            themes = analysis_json.get("themes", [])
            styles = analysis_json.get("styles", analysis_json.get("style", []))
            if isinstance(themes, list) and isinstance(styles, list) and themes and styles:
                analysis_result = {"themes": themes, "styles": styles}
                logger.info(f"Успешно извлечены темы ({len(themes)}) и стили ({len(styles)}) из JSON c {model_name}.")
                return analysis_result
            else:
                logger.warning(f"Некорректный тип данных для тем или стилей в JSON: {analysis_json} (модель: {model_name})")
        except Exception as e:
            logger.error(f"Ошибка при анализе через модель {model_name}: {e}")
    # Если все OpenRouter модели не дали результата — возвращаем пустой результат, чтобы сработал fallback на OpenAI
    return analysis_result

def build_messages(system_prompt, user_prompt, is_openrouter):
    if is_openrouter:
        return [
            {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}
        ]
    else:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ] 

def extract_json_from_llm_response(text):
    text = text.strip()
    if text.startswith('```json'):
        text = text[len('```json'):].lstrip('\n')
    elif text.startswith('```'):
        text = text[len('```'):].lstrip('\n')
    if text.endswith('```'):
        text = text[:-3].rstrip()
    import re
    json_match = re.search(r'(\{.*\})', text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    return text 