# Smart Content Assistant

Это бэкенд для Telegram Mini App "Smart Content Assistant".

## Установка

1.  Клонируйте репозиторий.
2.  Создайте и активируйте виртуальное окружение:
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```
3.  Установите зависимости:
    ```bash
    pip install -r requirements.txt
    ```
4.  Создайте файл `.env` на основе `.env.example` и заполните его вашими API-ключами и настройками.
5.  Запустите приложение:
    ```bash
    uvicorn main:app --reload
    ```

Приложение будет доступно по адресу `http://127.0.0.1:8000`.

## Устранение проблем с миграциями

При развертывании приложения могут возникать ошибки, связанные с недостающими столбцами в базе данных. Для их исправления предусмотрено несколько скриптов:

### 1. Стандартный процесс миграции

```bash
python migrate.py
```

Этот скрипт запускает стандартный процесс миграции, который пытается применить все миграции SQL из директории `migrations/`.

### 2. Принудительное добавление недостающих столбцов

```bash
python move_temp_files.py
```

Этот скрипт напрямую добавляет столбцы `author_url` в таблицу `saved_images` и `analyzed_posts_count` в таблицу `channel_analysis`, а также создает соответствующие индексы. Используйте его, если стандартная миграция завершается с ошибками о недостающих столбцах.

### 3. Принудительное выполнение всех миграций

```bash
python execute_migrations.py
```

Этот скрипт выполняет все миграции напрямую, обходя стандартный механизм миграций. Он:

1. Создает функцию `exec_sql` и связанные функции для работы с JSON
2. Добавляет недостающие столбцы и индексы
3. Применяет все миграции из папки `migrations/` по порядку

Используйте этот скрипт, если предыдущие методы не помогли.

### Для пользователей npm/pnpm

Также предусмотрены команды в package.json:

```bash
# Стандартная миграция
npm run migrate

# Добавление недостающих столбцов
npm run add-columns

# Принудительное выполнение всех миграций
npm run force-migrate
```

### Ручное выполнение SQL

Если ни один из скриптов не помогает, выполните следующие SQL-команды напрямую в SQL-редакторе Supabase:

```sql
-- Добавление столбца author_url в таблицу saved_images
ALTER TABLE IF EXISTS saved_images ADD COLUMN IF NOT EXISTS author_url TEXT;
CREATE INDEX IF NOT EXISTS idx_saved_images_author_url ON saved_images(author_url);

-- Добавление столбца analyzed_posts_count в таблицу channel_analysis
ALTER TABLE IF EXISTS channel_analysis ADD COLUMN IF NOT EXISTS analyzed_posts_count INTEGER DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_channel_analysis_analyzed_posts_count ON channel_analysis(analyzed_posts_count);
```

## Запуск приложения

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск сервера разработки
uvicorn main:app --reload

# Или через npm
npm start
``` 