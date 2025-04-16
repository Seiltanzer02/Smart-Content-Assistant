-- Создание таблицы для хранения предложенных идей постов
CREATE TABLE IF NOT EXISTS suggested_ideas (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    content JSONB NOT NULL,
    is_used BOOLEAN DEFAULT FALSE
);

-- Создание таблицы для хранения созданных постов
CREATE TABLE IF NOT EXISTS saved_posts (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    topic_idea TEXT,
    format_style TEXT,
    post_text TEXT NOT NULL,
    target_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблицы для хранения сохраненных изображений
CREATE TABLE IF NOT EXISTS saved_images (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    post_id INTEGER REFERENCES saved_posts(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    content_type TEXT,
    original_filename TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для повышения производительности запросов
CREATE INDEX IF NOT EXISTS idx_suggested_ideas_user_id ON suggested_ideas(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_posts_user_id ON saved_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_images_user_id ON saved_images(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_images_post_id ON saved_images(post_id);

-- Функция для автоматического обновления поля updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггер для обновления поля updated_at при обновлении записи в таблице saved_posts
CREATE TRIGGER update_saved_posts_updated_at
BEFORE UPDATE ON saved_posts
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column(); 