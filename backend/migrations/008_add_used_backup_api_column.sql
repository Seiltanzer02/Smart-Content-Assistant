-- Миграция для добавления поля used_backup_api в таблицы posts и channel_analysis

-- Добавление столбца used_backup_api в таблицу posts, если его ещё нет
ALTER TABLE posts 
ADD COLUMN IF NOT EXISTS used_backup_api BOOLEAN DEFAULT FALSE;

-- Добавление столбца used_backup_api в таблицу channel_analysis, если его ещё нет
ALTER TABLE channel_analysis 
ADD COLUMN IF NOT EXISTS used_backup_api BOOLEAN DEFAULT FALSE;

-- Создание индекса для поля used_backup_api в таблице posts
CREATE INDEX IF NOT EXISTS idx_posts_used_backup_api
ON posts (used_backup_api);

-- Создание индекса для поля used_backup_api в таблице channel_analysis
CREATE INDEX IF NOT EXISTS idx_channel_analysis_used_backup_api
ON channel_analysis (used_backup_api);

-- Обновление схемы кэша для таблиц
NOTIFY pgrst, 'reload schema'; 