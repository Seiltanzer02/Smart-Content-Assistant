-- Эта миграция добавляет отсутствующие столбцы в таблицы:
-- 1. author_url в таблицу saved_images
-- 2. analyzed_posts_count в таблицу channel_analysis

DO $$
BEGIN
    -- Добавляем столбец author_url в таблицу saved_images, если он отсутствует
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'saved_images' AND column_name = 'author_url'
    ) THEN
        ALTER TABLE saved_images ADD COLUMN author_url text;
        RAISE NOTICE 'Столбец author_url добавлен в таблицу saved_images';
    ELSE
        RAISE NOTICE 'Столбец author_url уже существует в таблице saved_images';
    END IF;
    
    -- Добавляем индекс для столбца author_url, если он отсутствует
    IF NOT EXISTS (
        SELECT FROM pg_indexes 
        WHERE tablename = 'saved_images' AND indexname = 'idx_saved_images_author_url'
    ) THEN
        CREATE INDEX idx_saved_images_author_url ON saved_images (author_url);
        RAISE NOTICE 'Индекс idx_saved_images_author_url создан';
    ELSE
        RAISE NOTICE 'Индекс idx_saved_images_author_url уже существует';
    END IF;
    
    -- Добавляем столбец analyzed_posts_count в таблицу channel_analysis, если он отсутствует
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'channel_analysis' AND column_name = 'analyzed_posts_count'
    ) THEN
        ALTER TABLE channel_analysis ADD COLUMN analyzed_posts_count integer DEFAULT 0;
        RAISE NOTICE 'Столбец analyzed_posts_count добавлен в таблицу channel_analysis';
    ELSE
        RAISE NOTICE 'Столбец analyzed_posts_count уже существует в таблице channel_analysis';
    END IF;
    
    -- Добавляем индекс для столбца analyzed_posts_count, если он отсутствует
    IF NOT EXISTS (
        SELECT FROM pg_indexes 
        WHERE tablename = 'channel_analysis' AND indexname = 'idx_channel_analysis_posts_count'
    ) THEN
        CREATE INDEX idx_channel_analysis_posts_count ON channel_analysis (analyzed_posts_count);
        RAISE NOTICE 'Индекс idx_channel_analysis_posts_count создан';
    ELSE
        RAISE NOTICE 'Индекс idx_channel_analysis_posts_count уже существует';
    END IF;
END $$; 