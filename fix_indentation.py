import re

# Читаем файл
with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Исправляем блок идей в get_saved_ideas
ideas_pattern = r'(# === ИЗМЕНЕНИЕ: Корректное формирование ответа ===\n\s+ideas = \[\]\n\s+for item in result\.data:.*?)(if idea\["topic_idea"\]:)(.*?)(# === КОНЕЦ ИЗМЕНЕНИЯ ===)'
fixed_ideas_block = """        # === ИЗМЕНЕНИЕ: Корректное формирование ответа ===
        ideas = []
        for item in result.data:
            # Проверяем наличие topic_idea
            topic_idea = item.get("topic_idea", "")
            if not topic_idea:
                logger.warning(f"Пропущена идея без topic_idea: ID={item.get('id', 'N/A')}")
                continue
                
            # Создаем объект идеи
            idea = {
                "id": item.get("id"),
                "channel_name": item.get("channel_name"),
                "topic_idea": topic_idea,
                "format_style": item.get("format_style"),
                "relative_day": item.get("relative_day"),
                "is_detailed": item.get("is_detailed"),
                "created_at": item.get("created_at")
            }
            ideas.append(idea)
        # === КОНЕЦ ИЗМЕНЕНИЯ ==="""

content_modified = re.sub(ideas_pattern, fixed_ideas_block, content, flags=re.DOTALL)

# Исправляем повторяющиеся строки в generate_post_details
api_pattern = r'(post_text = ""\n\s+try:.*?response = await client\.chat\.completions\.create\(.*?\)\n\s+)(# Проверка ответа и извлечение текста.*?post_text = \"\[Текст не сгенерирован из-за ошибки API\]\"\n\s+)(# === КОНЕЦ ИЗМЕНЕНИЯ ===)'
fixed_api_block = """        # === ИЗМЕНЕНО: Добавлена обработка ошибок API ===
        post_text = ""
        try:
            # Запрос к API
            logger.info(f"Отправка запроса на генерацию поста по идее: {topic_idea}")
            response = await client.chat.completions.create(
                model="deepseek/deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.75,
                max_tokens=500, # <--- УМЕНЬШЕНО ЗНАЧЕНИЕ до 500
                timeout=120,
                extra_headers={
                    "HTTP-Referer": "https://content-manager.onrender.com",
                    "X-Title": "Smart Content Assistant"
                }
            )
            
            # Обработка ответа от API
            if response and hasattr(response, 'choices') and response.choices and response.choices[0].message:
                post_text = response.choices[0].message.content.strip()
                logger.info(f"Получен текст поста ({len(post_text)} символов)")
            elif response and hasattr(response, 'error') and response.error:
                # Явная обработка ошибки в ответе
                err_details = response.error
                api_error_message = getattr(err_details, 'message', str(err_details))
                logger.error(f"OpenRouter API вернул ошибку: {api_error_message}")
                post_text = "[Текст не сгенерирован из-за ошибки API]"
            else:
                # Общий случай некорректного ответа
                api_error_message = "API вернул некорректный или пустой ответ"
                logger.error(f"Некорректный или пустой ответ от OpenRouter API. Ответ: {response}")
                post_text = "[Текст не сгенерирован из-за ошибки API]"
                
        except Exception as api_error:
            # Ловим ошибки HTTP запроса или другие исключения
            api_error_message = f"Ошибка соединения с API: {str(api_error)}"
            logger.error(f"Ошибка при запросе к OpenRouter API: {api_error}", exc_info=True)
            post_text = "[Текст не сгенерирован из-за ошибки API]"
        # === КОНЕЦ ИЗМЕНЕНИЯ ==="""

# Заменяем дублирующиеся строки
content_modified = re.sub(r'post_text = response\.choices\[0\]\.message\.content\.strip\(\)\s+logger\.info\(f"Получен текст поста \(\{len\(post_text\)\} символов\)"\)\s+post_text = response\.choices\[0\]\.message\.content\.strip\(\)', 'post_text = response.choices[0].message.content.strip()', content_modified)

# Сохраняем исправленный файл
with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content_modified)

print("Файл исправлен!") 