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

-- Таблица для хранения анализа каналов
CREATE TABLE IF NOT EXISTS channel_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    themes JSONB,
    styles JSONB,
    analyzed_posts_count INTEGER DEFAULT 0,
    sample_posts JSONB,
    best_posting_time TEXT,
    is_sample_data BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Таблица для хранения предложенных идей
CREATE TABLE IF NOT EXISTS suggested_ideas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    channel_name TEXT,
    topic_idea TEXT NOT NULL,
    format_style TEXT,
    relative_day INTEGER DEFAULT 0,
    is_detailed BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'new',
    cleaned_title TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Таблица для хранения постов
CREATE TABLE IF NOT EXISTS saved_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    channel_name TEXT,
    topic_idea TEXT NOT NULL,
    format_style TEXT,
    final_text TEXT,
    image_url TEXT,
    images_ids TEXT[],
    target_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Таблица для хранения изображений
CREATE TABLE IF NOT EXISTS saved_images (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    preview_url TEXT,
    alt TEXT,
    author TEXT,
    author_url TEXT,
    source TEXT DEFAULT 'unsplash',
    user_id TEXT NOT NULL,
    local_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Таблица для хранения связей между постами и изображениями
CREATE TABLE IF NOT EXISTS post_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID REFERENCES saved_posts(id) ON DELETE CASCADE,
    image_id TEXT REFERENCES saved_images(id) ON DELETE SET NULL,
    user_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(post_id, image_id)
);

-- Индексы для ускорения запросов
CREATE INDEX IF NOT EXISTS idx_channel_analysis_user_id ON channel_analysis(user_id);
CREATE INDEX IF NOT EXISTS idx_channel_analysis_channel_name ON channel_analysis(channel_name);
CREATE INDEX IF NOT EXISTS idx_suggested_ideas_user_id ON suggested_ideas(user_id);
CREATE INDEX IF NOT EXISTS idx_suggested_ideas_channel_name ON suggested_ideas(channel_name);
CREATE INDEX IF NOT EXISTS idx_saved_images_user_id ON saved_images(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_posts_user_id ON saved_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_posts_channel_name ON saved_posts(channel_name);
CREATE INDEX IF NOT EXISTS idx_saved_posts_target_date ON saved_posts(target_date);
CREATE INDEX IF NOT EXISTS idx_post_images_post_id ON post_images(post_id);
CREATE INDEX IF NOT EXISTS idx_post_images_image_id ON post_images(image_id);

-- Обновление saved_posts: добавляем функцию для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = now();
   RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггеры для автоматического обновления полей updated_at
CREATE TRIGGER update_saved_posts_updated_at
BEFORE UPDATE ON saved_posts
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_channel_analysis_updated_at
BEFORE UPDATE ON channel_analysis
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_suggested_ideas_updated_at
BEFORE UPDATE ON suggested_ideas
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column(); 