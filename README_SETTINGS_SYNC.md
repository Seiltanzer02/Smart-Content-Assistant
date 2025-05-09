# Синхронизация настроек пользователя между устройствами

## Введение

Данное решение позволяет синхронизировать настройки пользователя между различными устройствами в мини-приложении Telegram. 
Основная проблема заключалась в том, что ранее настройки хранились в локальном хранилище браузера (localStorage), 
которое не синхронизируется между устройствами.

## Что было реализовано

1. **Серверное хранение настроек**:
   - Создана таблица `user_settings` в базе данных для хранения настроек пользователей
   - Реализованы API-эндпоинты для получения и обновления настроек

2. **Клиентская часть**:
   - Добавлены новые API-запросы для работы с настройками
   - Модифицирован код для использования API вместо localStorage
   - Реализован механизм резервного копирования в localStorage при ошибках API

## Установка и настройка

### 1. Создание таблицы в базе данных

Выполните скрипт миграции:

```bash
cd backend
python apply_user_settings_migration.py
```

Или выполните SQL-запрос для создания таблицы напрямую через интерфейс Supabase:

```sql
CREATE TABLE IF NOT EXISTS user_settings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id INT8 NOT NULL,
  "channelName" TEXT,
  "selectedChannels" JSONB DEFAULT '[]'::jsonb,
  "allChannels" JSONB DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);
```

### 2. Обновление бэкенда

В файле `backend/main.py` были добавлены новые API-эндпоинты:
- `GET /user-settings` - для получения настроек пользователя
- `POST /user-settings` - для обновления настроек пользователя

### 3. Обновление фронтенда

1. Добавлен новый файл `frontend/src/api/userSettings.ts` с функциями для работы с API
2. Обновлен файл `frontend/src/App.tsx` для использования новых API

## Тестирование

1. Запустите приложение
2. Войдите в систему на первом устройстве
3. Выберите канал и добавьте его в фильтр
4. Войдите в систему на втором устройстве
5. Проверьте, что выбранный канал и фильтр синхронизировались

## Решение проблем

### Если настройки не синхронизируются:

1. Убедитесь, что API-эндпоинты доступны и работают корректно:
   ```bash
   curl -X GET "http://your-backend-url/user-settings" \
     -H "X-Telegram-User-Id: your_user_id"
   ```

2. Проверьте, что таблица `user_settings` создана в базе данных:
   ```sql
   SELECT * FROM user_settings;
   ```

3. Проверьте наличие ошибок в консоли браузера

## Техническая информация

### API-эндпоинты

#### GET /user-settings
- **Заголовки**:
  - `X-Telegram-User-Id`: ID пользователя Telegram
- **Ответ**:
  ```json
  {
    "channelName": "string",
    "selectedChannels": ["string"],
    "allChannels": ["string"]
  }
  ```

#### POST /user-settings
- **Заголовки**:
  - `X-Telegram-User-Id`: ID пользователя Telegram
- **Тело запроса**:
  ```json
  {
    "channelName": "string",
    "selectedChannels": ["string"],
    "allChannels": ["string"]
  }
  ```
- **Ответ**: Такой же, как и тело запроса

### База данных

Структура таблицы `user_settings`:

| Поле             | Тип          | Описание                               |
|------------------|--------------|----------------------------------------|
| id               | UUID         | Первичный ключ                         |
| user_id          | INT8         | ID пользователя Telegram               |
| channelName      | TEXT         | Текущий выбранный канал                |
| selectedChannels | JSONB        | Массив выбранных каналов для фильтров  |
| allChannels      | JSONB        | Список всех каналов пользователя       |
| created_at       | TIMESTAMPTZ  | Дата и время создания                  |
| updated_at       | TIMESTAMPTZ  | Дата и время последнего обновления     | 