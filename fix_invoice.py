import re
import sys

try:
    # Открываем исходный файл
    with open('main_fixed.py', 'r', encoding='utf-8') as f:
        content = f.read()
        print(f"Успешно прочитан файл main_fixed.py размером {len(content)} байт")

    # Находим все вхождения определения эндпоинта generate-invoice
    pattern = r'@app\.post\("\/generate-invoice".*?response_model=Dict\[str,\s*Any\]\)'
    matches = list(re.finditer(pattern, content))
    
    print(f"Найдено {len(matches)} определений эндпоинта /generate-invoice")
    
    for i, match in enumerate(matches):
        print(f"Совпадение #{i+1} на позиции {match.start()}: {match.group()}")

    if len(matches) >= 2:
        # Берем первое и последнее вхождение (в случае, если есть больше двух)
        first_start = matches[0].start()
        last_start = matches[-1].start()
        
        print(f"Обрабатываем первое совпадение на позиции {first_start} и последнее на позиции {last_start}")
        
        # Ищем конец последнего блока - ищем до "if __name__"
        if_main_match = re.search(r'if\s+__name__\s*==\s*"__main__":', content[last_start:])
        
        if if_main_match:
            last_end = last_start + if_main_match.start()
            print(f"Найден 'if __name__' на позиции {last_end} относительно начала последнего блока")
        else:
            # Если не нашли if __name__, ищем следующий декоратор @app
            next_app_match = re.search(r'@app\.', content[last_start+1:])
            if next_app_match:
                last_end = last_start + 1 + next_app_match.start()
                print(f"Найден следующий декоратор @app на позиции {last_end}")
            else:
                # Если ничего не нашли, то удаляем до конца файла
                last_end = len(content)
                print(f"Не найдено следующего блока, удаляем до конца файла до позиции {last_end}")
        
        # Показываем текст, который будет удален
        text_to_remove = content[last_start:last_end]
        print(f"Будет удален следующий блок кода длиной {len(text_to_remove)} символов:")
        print("=" * 40)
        print(text_to_remove[:500] + "..." if len(text_to_remove) > 500 else text_to_remove)
        print("=" * 40)
        
        # Создаем новое содержимое файла
        new_content = content[:last_start] + "\n# Дублирующийся блок эндпоинта /generate-invoice удален\n\n" + content[last_end:]
        
        # Проверяем, что второй блок удален
        new_matches = list(re.finditer(pattern, new_content))
        print(f"После изменений найдено {len(new_matches)} определений эндпоинта /generate-invoice")
        
        # Записываем изменения в новый файл для безопасности
        with open('main_fixed.py.new', 'w', encoding='utf-8') as f:
            f.write(new_content)
            print("Изменения сохранены в файл main_fixed.py.new")
        
        # Заменяем оригинальный файл
        with open('main_fixed.py', 'w', encoding='utf-8') as f:
            f.write(new_content)
            print("Изменения сохранены в оригинальный файл main_fixed.py")
            
        print("Дублирующийся блок успешно удален!")
    else:
        print("Не найдено дублирующихся определений эндпоинта /generate-invoice.")
except Exception as e:
    print(f"Произошла ошибка: {e}", file=sys.stderr) 