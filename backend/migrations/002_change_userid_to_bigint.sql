-- Миграция для изменения типа поля user_id с TEXT на BIGINT
-- Файл: 002_change_userid_to_bigint.sql

-- Альтернативные колонки для хранения текущих значений
DO $$ 
BEGIN
    -- Добавляем колонку temp_user_id типа BIGINT в таблицу channel_analysis, если ее нет
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'channel_analysis') 
    AND EXISTS (SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'channel_analysis' AND column_name = 'user_id'
                AND data_type = 'text') THEN
        ALTER TABLE channel_analysis ADD COLUMN IF NOT EXISTS temp_user_id BIGINT;
        
        -- Обновляем временную колонку данными из текущей (конвертируя текст в число)
        UPDATE channel_analysis SET temp_user_id = user_id::BIGINT WHERE user_id ~ '^\d+$';
        
        -- Удаляем старую колонку и переименовываем временную
        ALTER TABLE channel_analysis DROP COLUMN user_id;
        ALTER TABLE channel_analysis RENAME COLUMN temp_user_id TO user_id;
        
        -- Делаем колонку NOT NULL
        ALTER TABLE channel_analysis ALTER COLUMN user_id SET NOT NULL;
        
        -- Воссоздаем индекс
        DROP INDEX IF EXISTS idx_channel_analysis_user_id;
        CREATE INDEX idx_channel_analysis_user_id ON channel_analysis(user_id);
    END IF;
    
    -- Изменяем тип user_id в таблице suggested_ideas
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'suggested_ideas') 
    AND EXISTS (SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'suggested_ideas' AND column_name = 'user_id'
                AND data_type = 'text') THEN
        ALTER TABLE suggested_ideas ADD COLUMN IF NOT EXISTS temp_user_id BIGINT;
        
        UPDATE suggested_ideas SET temp_user_id = user_id::BIGINT WHERE user_id ~ '^\d+$';
        
        ALTER TABLE suggested_ideas DROP COLUMN user_id;
        ALTER TABLE suggested_ideas RENAME COLUMN temp_user_id TO user_id;
        
        ALTER TABLE suggested_ideas ALTER COLUMN user_id SET NOT NULL;
        
        DROP INDEX IF EXISTS idx_suggested_ideas_user_id;
        CREATE INDEX idx_suggested_ideas_user_id ON suggested_ideas(user_id);
    END IF;
    
    -- Изменяем тип user_id в таблице saved_images
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'saved_images') 
    AND EXISTS (SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'saved_images' AND column_name = 'user_id'
                AND data_type = 'text') THEN
        ALTER TABLE saved_images ADD COLUMN IF NOT EXISTS temp_user_id BIGINT;
        
        UPDATE saved_images SET temp_user_id = user_id::BIGINT WHERE user_id ~ '^\d+$';
        
        ALTER TABLE saved_images DROP COLUMN user_id;
        ALTER TABLE saved_images RENAME COLUMN temp_user_id TO user_id;
        
        ALTER TABLE saved_images ALTER COLUMN user_id SET NOT NULL;
        
        DROP INDEX IF EXISTS idx_saved_images_user_id;
        CREATE INDEX idx_saved_images_user_id ON saved_images(user_id);
    END IF;
    
    -- Изменяем тип user_id в таблице saved_posts
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'saved_posts') 
    AND EXISTS (SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'saved_posts' AND column_name = 'user_id'
                AND data_type = 'text') THEN
        ALTER TABLE saved_posts ADD COLUMN IF NOT EXISTS temp_user_id BIGINT;
        
        UPDATE saved_posts SET temp_user_id = user_id::BIGINT WHERE user_id ~ '^\d+$';
        
        ALTER TABLE saved_posts DROP COLUMN user_id;
        ALTER TABLE saved_posts RENAME COLUMN temp_user_id TO user_id;
        
        ALTER TABLE saved_posts ALTER COLUMN user_id SET NOT NULL;
        
        DROP INDEX IF EXISTS idx_saved_posts_user_id;
        CREATE INDEX idx_saved_posts_user_id ON saved_posts(user_id);
    END IF;
    
    -- Изменяем тип user_id в таблице post_images
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'post_images') 
    AND EXISTS (SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'post_images' AND column_name = 'user_id'
                AND data_type = 'text') THEN
        ALTER TABLE post_images ADD COLUMN IF NOT EXISTS temp_user_id BIGINT;
        
        UPDATE post_images SET temp_user_id = user_id::BIGINT WHERE user_id ~ '^\d+$';
        
        ALTER TABLE post_images DROP COLUMN user_id;
        ALTER TABLE post_images RENAME COLUMN temp_user_id TO user_id;
        
        ALTER TABLE post_images ALTER COLUMN user_id SET NOT NULL;
    END IF;
END $$; 