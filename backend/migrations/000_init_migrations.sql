-- Создание таблицы для отслеживания выполненных миграций
CREATE TABLE IF NOT EXISTS _migrations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    executed_at BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Создание функции для выполнения произвольных SQL запросов
CREATE OR REPLACE FUNCTION exec_sql(query text) RETURNS void AS $$
BEGIN
    EXECUTE query;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Создание индекса для ускорения поиска по имени миграции
CREATE INDEX IF NOT EXISTS idx_migrations_name ON _migrations(name);

-- Добавление комментария к таблице
COMMENT ON TABLE _migrations IS 'Таблица для отслеживания выполненных миграций SQL'; 