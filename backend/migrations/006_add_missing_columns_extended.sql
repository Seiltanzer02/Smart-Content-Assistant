-- Эта миграция добавляет дополнительные отсутствующие столбцы в таблицы

-- Добавление столбца preview_url в таблицу saved_images
ALTER TABLE saved_images 
ADD COLUMN IF NOT EXISTS preview_url TEXT;

-- Добавление столбца updated_at в таблицу channel_analysis
ALTER TABLE channel_analysis 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Обновление схемы кэша для таблиц
NOTIFY pgrst, 'reload schema'; 