import json
import re
import logging
from typing import List, Dict
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

async def analyze_content_with_deepseek(texts: List[str], api_key: str) -> Dict[str, List[str]]:
    """Анализ контента с использованием модели DeepSeek через OpenRouter API."""
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
    user_prompt = f"""Проанализируй СТРОГО следующие посты из Telegram-канала:\n{combined_text}\n\nОпредели 3-5 САМЫХ ХАРАКТЕРНЫХ тем и 3-5 САМЫХ РАСПРОСТРАНЕННЫХ стилей/форматов подачи контента, которые наилучшим образом отражают специфику ИМЕННО ЭТОГО канала. \nОсновывайся ТОЛЬКО на предоставленных текстах. \n\nПредставь результат ТОЛЬКО в виде JSON объекта с ключами \"themes\" и \"styles\". Никакого другого текста."""
    analysis_result = {"themes": [], "styles": []}
    try:
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        # --- Новый блок: расчет средней длины постов ---
        avg_length = 0
        if texts:
            avg_length = int(sum(len(t) for t in texts) / len(texts))
            # Примерная оценка: 1 токен ≈ 4 символа (англ.), 1 токен ≈ 2-3 символа (рус.)
            avg_tokens = max(100, min(1200, avg_length // 3))  # Ограничим диапазон
        else:
            avg_tokens = 600
        response = await client.chat.completions.create(
            model="google/gemini-2.5-flash-preview",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=avg_tokens,
            timeout=60,
            extra_headers={
                "HTTP-Referer": "https://content-manager.onrender.com",
                "X-Title": "Smart Content Assistant"
            }
        )
        analysis_text = response.choices[0].message.content.strip()
        logger.info(f"Получен ответ от DeepSeek: {analysis_text[:100]}...")
        json_match = re.search(r'(\{.*\})', analysis_text, re.DOTALL)
        if json_match:
            analysis_text = json_match.group(1)
        analysis_json = json.loads(analysis_text)
        themes = analysis_json.get("themes", [])
        styles = analysis_json.get("styles", analysis_json.get("style", [])) 
        if isinstance(themes, list) and isinstance(styles, list):
            analysis_result = {"themes": themes, "styles": styles}
            logger.info(f"Успешно извлечены темы ({len(themes)}) и стили ({len(styles)}) из JSON.")
        else:
            logger.warning(f"Некорректный тип данных для тем или стилей в JSON: {analysis_json}")
            analysis_result = {"themes": [], "styles": []}
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}, текст: {analysis_text}")
        themes_match = re.findall(r'"themes":\s*\[(.*?)\]', analysis_text, re.DOTALL)
        if themes_match:
            theme_items = re.findall(r'"([^"]+)"', themes_match[0])
            analysis_result["themes"] = theme_items
        styles_match = re.findall(r'"styles":\s*\[(.*?)\]', analysis_text, re.DOTALL)
        if styles_match:
            style_items = re.findall(r'"([^"]+)"', styles_match[0])
            analysis_result["styles"] = style_items
    except Exception as e:
        logger.error(f"Ошибка при анализе контента через DeepSeek: {e}")
    return analysis_result 