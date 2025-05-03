-- Добавляем поле reset_at в таблицу user_usage_stats
ALTER TABLE user_usage_stats ADD COLUMN IF NOT EXISTS reset_at TIMESTAMP WITH TIME ZONE;

-- Обновляем существующие записи, устанавливая reset_at на первое число следующего месяца
UPDATE user_usage_stats 
SET reset_at = (date_trunc('month', CURRENT_DATE) + INTERVAL '1 month')::timestamp 
WHERE reset_at IS NULL;

-- Комментарий для уточнения назначения колонки
COMMENT ON COLUMN user_usage_stats.reset_at IS 'Дата следующего сброса счетчиков использования'; 