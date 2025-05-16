import os
import re

# Путь к файлу posts_service.py
posts_service_path = os.path.join('services', 'posts_service.py')

# Чтение содержимого файла
with open(posts_service_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Определение проблемного блока кода
problem_block_pattern = r'# РЎРЅР°С‡Р°Р»Р° РїСЂРѕР±СѓРµРј OpenRouter API.*?if OPENROUTER_API_KEY:.*?try:'
problem_block_regex = re.compile(problem_block_pattern, re.DOTALL)

# Исправленный блок кода
fixed_block = """        # РЎРЅР°С‡Р°Р»Р° РїСЂРѕР±СѓРµРј OpenRouter API, РµСЃР»Рё РѕРЅ РґРѕСЃС‚СѓРїРµРЅ
        post_text = ""
        used_backup_api = False
        api_error_message = None
        found_images = []
        
        if OPENROUTER_API_KEY:
            try:"""

# Замена проблемного блока
fixed_content = problem_block_regex.sub(fixed_block, content)

# Запись исправленного содержимого обратно в файл
with open(posts_service_path, 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print(f"Файл {posts_service_path} успешно исправлен!") 