# Прочитаем содержимое файла
with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.readlines()

# Исправляем проблемное место на строке 827
# Ищем строку с проблемой и окружающие строки
fixed_lines = []
in_ideas_section = False
skip_indentation_issue = False

for i, line in enumerate(content):
    if "# === ИЗМЕНЕНИЕ: Корректное формирование ответа ===" in line:
        in_ideas_section = True
        fixed_lines.append(line)
    elif "# === КОНЕЦ ИЗМЕНЕНИЯ ===" in line and in_ideas_section:
        in_ideas_section = False
        fixed_lines.append(line)
    elif in_ideas_section and "if idea[\"topic_idea\"]:" in line:
        # Пропускаем проблемную строку и следующий if/else блок
        skip_indentation_issue = True
        fixed_lines.append("            # Проверяем topic_idea перед добавлением в список\n")
        fixed_lines.append("            if idea.get(\"topic_idea\"):\n")
        fixed_lines.append("                ideas.append(idea)\n")
        fixed_lines.append("            else:\n")
        fixed_lines.append("                logger.warning(f\"Пропущена идея без topic_idea: ID={idea.get('id', 'N/A')}\")\n")
    elif skip_indentation_issue and ("ideas.append(idea)" in line or "logger.warning" in line):
        # Пропускаем эти строки, так как мы их уже добавили
        continue
    else:
        fixed_lines.append(line)

# Записываем исправленный файл
with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)
    
print("Файл исправлен!") 