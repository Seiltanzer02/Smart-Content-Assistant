import os

try:
    posts_service_path = os.path.join('services', 'posts_service.py')
    print(f"Чтение файла {posts_service_path}...")
    
    with open(posts_service_path, 'r', encoding='utf-8') as f:
        source_code = f.read()
    
    print("Проверка синтаксиса...")
    
    # Компилируем код - при синтаксической ошибке будет выброшено исключение
    compiled_code = compile(source_code, posts_service_path, 'exec')
    
    print("Синтаксис файла корректен!")
except SyntaxError as e:
    print(f"Ошибка синтаксиса: {e}")
    print(f"Строка {e.lineno}, позиция {e.offset}: {e.text}")
except Exception as e:
    print(f"Ошибка: {e}") 