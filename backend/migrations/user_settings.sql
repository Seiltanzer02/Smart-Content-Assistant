-- Создаем миграцию для таблицы user_settings
CREATE TABLE IF NOT EXISTS user_settings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id INT8 NOT NULL,
  "channelName" TEXT,
  "selectedChannels" JSONB DEFAULT '[]'::jsonb,
  "allChannels" JSONB DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Создаем индекс для быстрого поиска по user_id
CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);

-- Добавляем комментарии к таблице и полям
COMMENT ON TABLE user_settings IS 'Таблица для хранения пользовательских настроек приложения';
COMMENT ON COLUMN user_settings.id IS 'Уникальный идентификатор записи';
COMMENT ON COLUMN user_settings.user_id IS 'ID пользователя Telegram';
COMMENT ON COLUMN user_settings."channelName" IS 'Текущий выбранный канал пользователя';
COMMENT ON COLUMN user_settings."selectedChannels" IS 'Массив выбранных каналов для фильтрации';
COMMENT ON COLUMN user_settings."allChannels" IS 'Список всех каналов пользователя';
COMMENT ON COLUMN user_settings.created_at IS 'Дата и время создания записи';
COMMENT ON COLUMN user_settings.updated_at IS 'Дата и время последнего обновления'; 