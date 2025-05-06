import ast
import sys

def check_file_syntax(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            source = file.read()
        
        # Попытка парсинга файла
        ast.parse(source)
        print(f"Файл {filename} имеет правильный синтаксис Python.")
        return True
    except SyntaxError as e:
        print(f"Синтаксическая ошибка в {filename}:")
        print(f"  Строка {e.lineno}, позиция {e.offset}: {e.text}")
        print(f"  {e}")
        return False
    except Exception as e:
        print(f"Ошибка при чтении или парсинге {filename}:")
        print(f"  {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = "main.py"
    
    check_file_syntax(filename) 