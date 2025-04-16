-- Создание таблицы для хранения предложенных идей
CREATE TABLE IF NOT EXISTS "suggested_ideas" (
    "id" uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    "telegram_user_id" text NOT NULL,
    "channel_name" text NOT NULL,
    "topic_idea" text NOT NULL,
    "format_style" text,
    "created_at" timestamp with time zone DEFAULT now(),
    "updated_at" timestamp with time zone DEFAULT now()
);

-- Создание таблицы для хранения сохраненных постов
CREATE TABLE IF NOT EXISTS "saved_posts" (
    "id" uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    "telegram_user_id" text NOT NULL,
    "channel_name" text NOT NULL,
    "topic_idea" text NOT NULL,
    "format_style" text,
    "post_text" text NOT NULL,
    "target_date" date,
    "created_at" timestamp with time zone DEFAULT now(),
    "updated_at" timestamp with time zone DEFAULT now()
);

-- Создание таблицы для хранения сохраненных изображений
CREATE TABLE IF NOT EXISTS "saved_images" (
    "id" uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    "telegram_user_id" text NOT NULL,
    "post_id" uuid REFERENCES "saved_posts"("id") ON DELETE CASCADE,
    "image_url" text NOT NULL,
    "image_data" bytea,
    "original_filename" text,
    "mime_type" text,
    "created_at" timestamp with time zone DEFAULT now()
);

-- Создание индексов для улучшения производительности запросов
CREATE INDEX IF NOT EXISTS "idx_suggested_ideas_telegram_user_id" ON "suggested_ideas" ("telegram_user_id");
CREATE INDEX IF NOT EXISTS "idx_saved_posts_telegram_user_id" ON "saved_posts" ("telegram_user_id");
CREATE INDEX IF NOT EXISTS "idx_saved_images_post_id" ON "saved_images" ("post_id");
CREATE INDEX IF NOT EXISTS "idx_saved_images_telegram_user_id" ON "saved_images" ("telegram_user_id");

-- Добавление функций для автоматического обновления временных меток
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Добавление триггеров для автоматического обновления временных меток
CREATE TRIGGER update_suggested_ideas_updated_at
BEFORE UPDATE ON "suggested_ideas"
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_saved_posts_updated_at
BEFORE UPDATE ON "saved_posts"
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column(); 