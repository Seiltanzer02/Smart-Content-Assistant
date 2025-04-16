-- Создание таблицы для отслеживания выполненных миграций
CREATE TABLE IF NOT EXISTS _migrations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    executed_at BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Включаем расширение для генерации UUID, если его еще нет
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_extension WHERE extname = 'uuid-ossp'
    ) THEN
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    END IF;
END $$;

-- Создаем функцию для выполнения SQL динамически (если её нет)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_proc 
        WHERE proname = 'exec_sql' 
        AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
    ) THEN
        CREATE OR REPLACE FUNCTION exec_sql(query text) RETURNS void AS $$
        BEGIN
            EXECUTE query;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
    END IF;
END $$;

-- Создание индекса для ускорения поиска по имени миграции
CREATE INDEX IF NOT EXISTS idx_migrations_name ON _migrations(name);

-- Добавление комментария к таблице
COMMENT ON TABLE _migrations IS 'Таблица для отслеживания выполненных миграций SQL'; 