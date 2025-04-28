with open('main_fixed.py', 'r', encoding='utf-8') as file:
    lines = file.readlines()

# Найдем все строки, содержащие определение эндпоинта
endpoints = []
for i, line in enumerate(lines):
    if '@app.post("/generate-invoice"' in line:
        endpoints.append(i)
        print(f"Найдено определение на строке {i+1}: {line.strip()}")

if len(endpoints) >= 2:
    # Найдем начало и конец второго блока
    start_line = endpoints[1]
    print(f"Начало второго блока: строка {start_line+1}")
    
    # Ищем конец второго блока
    end_line = len(lines)
    for i in range(start_line + 1, len(lines)):
        if i < len(lines) - 1 and 'if __name__ == "__main__"' in lines[i]:
            end_line = i
            print(f"Конец второго блока: строка {end_line+1} (if __name__)")
            break
        elif '@app.post(' in lines[i] or '@app.get(' in lines[i]:
            end_line = i
            print(f"Конец второго блока: строка {end_line+1} (новый декоратор)")
            break
    
    print(f"Удаляем строки с {start_line+1} по {end_line} (всего {end_line - start_line} строк)")
    
    # Создаем новый список строк без второго блока
    new_lines = lines[:start_line]
    new_lines.append("\n# Дублирующийся блок эндпоинта /generate-invoice удален\n\n")
    new_lines.extend(lines[end_line:])
    
    # Записываем в новый файл для безопасности
    with open('main_fixed.py.new', 'w', encoding='utf-8') as file:
        file.writelines(new_lines)
        print("Изменения сохранены в файл main_fixed.py.new")
    
    # Проверим, что блок удален
    count = 0
    for line in new_lines:
        if '@app.post("/generate-invoice"' in line:
            count += 1
    print(f"После изменений найдено {count} определений эндпоинта /generate-invoice")
    
    # Обновляем исходный файл
    with open('main_fixed.py', 'w', encoding='utf-8') as file:
        file.writelines(new_lines)
        print("Изменения сохранены в исходный файл main_fixed.py")
    
    print("Готово! Дублирующийся блок удален.")
else:
    print(f"Найдено только {len(endpoints)} определений. Нет дублирующегося блока для удаления.") 