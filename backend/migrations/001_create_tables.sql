-- Проверяем и создаем функцию для выполнения SQL динамически
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

-- Таблица для хранения изображений
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'saved_images') THEN
        CREATE TABLE IF NOT EXISTS saved_images (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            url TEXT NOT NULL,
            preview_url TEXT,
            alt TEXT,
            author TEXT,
            author_url TEXT,
            source TEXT DEFAULT 'unsplash',
            local_path TEXT,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    END IF;
END $$;

-- Проверяем существование таблицы posts и добавляем колонку если таблица существует
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'posts') THEN
        IF NOT EXISTS (SELECT FROM information_schema.columns 
                      WHERE table_schema = 'public' AND table_name = 'posts' AND column_name = 'images') THEN
            ALTER TABLE IF EXISTS posts ADD COLUMN IF NOT EXISTS images JSONB DEFAULT '[]'::jsonb;
        END IF;
    END IF;
END $$;

-- Проверяем существование таблицы suggested_ideas и добавляем колонку если таблица существует
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'suggested_ideas') THEN
        IF NOT EXISTS (SELECT FROM information_schema.columns 
                      WHERE table_schema = 'public' AND table_name = 'suggested_ideas' AND column_name = 'cleaned_title') THEN
            ALTER TABLE IF EXISTS suggested_ideas ADD COLUMN IF NOT EXISTS cleaned_title TEXT;
        END IF;
    END IF;
END $$;

-- Таблица для хранения анализа каналов
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'channel_analysis') THEN
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
    END IF;
END $$;

-- Таблица для хранения предложенных идей
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'suggested_ideas') THEN
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
    END IF;
END $$;

-- Таблица для хранения постов
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'saved_posts') THEN
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
    END IF;
END $$;

-- Таблица для хранения связей между постами и изображениями
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'post_images') THEN
        CREATE TABLE IF NOT EXISTS post_images (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            post_id UUID REFERENCES saved_posts(id) ON DELETE CASCADE,
            image_id TEXT REFERENCES saved_images(id) ON DELETE SET NULL,
            user_id TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            UNIQUE(post_id, image_id)
        );
    END IF;
END $$;

-- Индексы для ускорения запросов (добавляем только если таблицы существуют и индексы отсутствуют)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'channel_analysis') THEN
        IF NOT EXISTS (SELECT FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'channel_analysis' AND indexname = 'idx_channel_analysis_user_id') THEN
            CREATE INDEX IF NOT EXISTS idx_channel_analysis_user_id ON channel_analysis(user_id);
        END IF;
        IF NOT EXISTS (SELECT FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'channel_analysis' AND indexname = 'idx_channel_analysis_channel_name') THEN
            CREATE INDEX IF NOT EXISTS idx_channel_analysis_channel_name ON channel_analysis(channel_name);
        END IF;
    END IF;
    
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'suggested_ideas') THEN
        IF NOT EXISTS (SELECT FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'suggested_ideas' AND indexname = 'idx_suggested_ideas_user_id') THEN
            CREATE INDEX IF NOT EXISTS idx_suggested_ideas_user_id ON suggested_ideas(user_id);
        END IF;
        IF NOT EXISTS (SELECT FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'suggested_ideas' AND indexname = 'idx_suggested_ideas_channel_name') THEN
            CREATE INDEX IF NOT EXISTS idx_suggested_ideas_channel_name ON suggested_ideas(channel_name);
        END IF;
    END IF;
    
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'saved_images') THEN
        IF NOT EXISTS (SELECT FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'saved_images' AND indexname = 'idx_saved_images_user_id') THEN
            CREATE INDEX IF NOT EXISTS idx_saved_images_user_id ON saved_images(user_id);
        END IF;
    END IF;
    
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'saved_posts') THEN
        IF NOT EXISTS (SELECT FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'saved_posts' AND indexname = 'idx_saved_posts_user_id') THEN
            CREATE INDEX IF NOT EXISTS idx_saved_posts_user_id ON saved_posts(user_id);
        END IF;
        IF NOT EXISTS (SELECT FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'saved_posts' AND indexname = 'idx_saved_posts_channel_name') THEN
            CREATE INDEX IF NOT EXISTS idx_saved_posts_channel_name ON saved_posts(channel_name);
        END IF;
        IF NOT EXISTS (SELECT FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'saved_posts' AND indexname = 'idx_saved_posts_target_date') THEN
            CREATE INDEX IF NOT EXISTS idx_saved_posts_target_date ON saved_posts(target_date);
        END IF;
    END IF;
    
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'post_images') THEN
        IF NOT EXISTS (SELECT FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'post_images' AND indexname = 'idx_post_images_post_id') THEN
            CREATE INDEX IF NOT EXISTS idx_post_images_post_id ON post_images(post_id);
        END IF;
        IF NOT EXISTS (SELECT FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'post_images' AND indexname = 'idx_post_images_image_id') THEN
            CREATE INDEX IF NOT EXISTS idx_post_images_image_id ON post_images(image_id);
        END IF;
    END IF;
END $$;

-- Функция для автоматического обновления updated_at
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_proc 
        WHERE proname = 'update_updated_at_column' 
        AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
    ) THEN
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    END IF;
END $$;

-- Триггеры для автоматического обновления полей updated_at
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'saved_posts') 
    AND NOT EXISTS (SELECT FROM pg_trigger WHERE tgname = 'update_saved_posts_updated_at') THEN
        CREATE TRIGGER update_saved_posts_updated_at
        BEFORE UPDATE ON saved_posts
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'channel_analysis') 
    AND NOT EXISTS (SELECT FROM pg_trigger WHERE tgname = 'update_channel_analysis_updated_at') THEN
        CREATE TRIGGER update_channel_analysis_updated_at
        BEFORE UPDATE ON channel_analysis
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'suggested_ideas') 
    AND NOT EXISTS (SELECT FROM pg_trigger WHERE tgname = 'update_suggested_ideas_updated_at') THEN
        CREATE TRIGGER update_suggested_ideas_updated_at
        BEFORE UPDATE ON suggested_ideas
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$; 