-- Создание таблицы для отслеживания выполненных миграций
CREATE TABLE IF NOT EXISTS _migrations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Создание индекса для быстрого поиска по имени миграции
CREATE INDEX IF NOT EXISTS idx_migrations_name ON _migrations(name);

-- Добавление комментария к таблице
COMMENT ON TABLE _migrations IS 'Таблица для отслеживания выполненных миграций';

-- Включаем расширение для генерации UUID, если его еще нет
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_extension WHERE extname = 'uuid-ossp'
    ) THEN
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    END IF;
END $$; 