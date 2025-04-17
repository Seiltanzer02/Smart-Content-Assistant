-- Эта миграция выполняет дополнительную проверку и добавление недостающих столбцов
-- Если столбцы уже существуют, никаких изменений не будет

-- Проверка и добавление столбца author_url в таблицу saved_images
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'saved_images' 
        AND column_name = 'author_url'
    ) THEN
        ALTER TABLE saved_images ADD COLUMN author_url TEXT;
    END IF;
END $$;

-- Проверка и добавление столбца analyzed_posts_count в таблицу channel_analysis
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'channel_analysis' 
        AND column_name = 'analyzed_posts_count'
    ) THEN
        ALTER TABLE channel_analysis ADD COLUMN analyzed_posts_count INTEGER DEFAULT 0;
    END IF;
END $$; 