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
        # Удаляем обёртку ```json ... ``` если есть
        if analysis_text.startswith('```json'):
            analysis_text = analysis_text[7:]
        if analysis_text.endswith('```'):
            analysis_text = analysis_text[:-3]
        # Удаляем шаблоны вида [ссылка], [контакт], [детали] и т.д.
        try:
            analysis_text = re.sub(r'\[[^\]]{2,40}\]', '', analysis_text)
        except Exception as re1:
            logger.error(f"Ошибка re.sub для квадратных скобок: {re1}")
        try:
            analysis_text = re.sub(r'\([сС]сылка( или контакт)?\)', '', analysis_text)
        except Exception as re2:
            logger.error(f"Ошибка re.sub для (ссылка): {re2}")
        try:
            analysis_text = re.sub(r'\((?:[кК]онтакт(?:ы)?|[дД]етали|[цЦ]ена|[нН]омер|[иИ]мя|[нН]азвание|[eE]mail|[тТ]елефон)\)', '', analysis_text)
        except Exception as re3:
            logger.error(f"Ошибка re.sub для (контакт/детали/и др.): {re3}")
        try:
            analysis_text = re.sub(r'\s{2,}', ' ', analysis_text)
        except Exception as re4:
            logger.error(f"Ошибка re.sub для пробелов: {re4}")
        analysis_text = analysis_text.strip()
        logger.info(f"Получен ответ от DeepSeek: {analysis_text[:100]}...")
        # Если невалидный JSON — пробуем обрезать до последней } или ] и парсить снова
        try:
            analysis_json = json.loads(analysis_text)
        except json.JSONDecodeError as e:
            last_curly = analysis_text.rfind('}')
            last_square = analysis_text.rfind(']')
            cut = max(last_curly, last_square)
            recovered = False
            if cut > 0:
                try:
                    analysis_json = json.loads(analysis_text[:cut+1])
                    recovered = True
                except Exception:
                    logger.error(f"Ошибка парсинга JSON даже после восстановления: {e}, текст: {analysis_text}")
            if not recovered:
                # Попытка удалить последнюю незакрытую строку из themes/styles
                def fix_array(text, key):
                    arr_match = re.search(rf'"{key}"\s*:\s*\[(.*?)\]', text, re.DOTALL)
                    if arr_match:
                        arr = arr_match.group(1)
                        items = re.findall(r'"(.*?)"', arr)
                        filtered = [s for s in items if len(s.strip()) > 2 and s.strip()[-1].isalnum()]
                        # Если ничего не найдено, но есть хотя бы одна открывающая кавычка — взять текст до неё
                        if not filtered and '"' in arr:
                            possible = arr.split('"')
                            if len(possible) > 1:
                                candidate = possible[1].split(',')[0].strip()
                                if len(candidate) > 2:
                                    filtered.append(candidate)
                        # Если всё ещё пусто — взять всё, что идёт после последней кавычки
                        if not filtered:
                            last_quote = arr.rfind('"')
                            if last_quote != -1:
                                tail = arr[last_quote+1:].split(']')[0].split(',')[0].strip()
                                if tail and len(tail) > 2:
                                    filtered.append(tail)
                        # Если всё ещё пусто — взять всё, что идёт после ключа до конца строки/массива
                        if not filtered:
                            key_pos = text.find(f'"{key}"')
                            if key_pos != -1:
                                arr_start = text.find('[', key_pos)
                                if arr_start != -1:
                                    arr_tail = text[arr_start+1:]
                                    # Берём до конца строки или до закрывающей скобки/конца текста
                                    arr_tail = arr_tail.split(']')[0].split('\n')[0]
                                    arr_tail = arr_tail.strip(' ,"\n')
                                    if len(arr_tail) > 2:
                                        filtered.append(arr_tail)
                        return filtered
                    return []
                themes = fix_array(analysis_text, 'themes')
                styles = fix_array(analysis_text, 'styles')
                analysis_json = {"themes": themes, "styles": styles}
                logger.warning(f"Восстановлен частичный JSON: themes={themes}, styles={styles}")
        themes = analysis_json.get("themes", [])
        styles = analysis_json.get("styles", analysis_json.get("style", [])) 
        if isinstance(themes, list) and isinstance(styles, list):
            analysis_result = {"themes": themes, "styles": styles}
            logger.info(f"Успешно извлечены темы ({len(themes)}) и стили ({len(styles)}) из JSON.")
        else:
            logger.warning(f"Некорректный тип данных для тем или стилей в JSON: {analysis_json}")
            analysis_result = {"themes": [], "styles": []}
    except Exception as e:
        logger.error(f"Ошибка при анализе контента через DeepSeek: {e}")
    return analysis_result 