-- Миграция для добавления столбца used_backup_api в таблицу channel_analysis

-- Добавление столбца used_backup_api в таблицу channel_analysis
ALTER TABLE channel_analysis 
ADD COLUMN IF NOT EXISTS used_backup_api BOOLEAN DEFAULT FALSE;

-- Создание индекса для столбца used_backup_api
CREATE INDEX IF NOT EXISTS idx_channel_analysis_used_backup_api 
ON channel_analysis (used_backup_api);

-- Обновление схемы кэша для таблиц
NOTIFY pgrst, 'reload schema'; 