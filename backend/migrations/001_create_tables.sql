-- Создание таблицы для сохранения изображений
CREATE TABLE IF NOT EXISTS saved_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
    local_path TEXT
);

-- Обновление таблицы posts для поддержки нескольких изображений
ALTER TABLE IF EXISTS posts ADD COLUMN IF NOT EXISTS images JSONB DEFAULT '[]'::jsonb;

-- Обновление таблицы suggested_ideas для корректного форматирования
ALTER TABLE IF EXISTS suggested_ideas ADD COLUMN IF NOT EXISTS cleaned_title TEXT; 