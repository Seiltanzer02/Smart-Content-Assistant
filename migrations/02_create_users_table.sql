-- Миграция для создания таблицы пользователей с информацией о подписке и лимитах

-- Создаем таблицу app_users, если она еще не существует
CREATE TABLE IF NOT EXISTS app_users (
    user_id TEXT PRIMARY KEY,                     -- ID пользователя Telegram (текстовый, т.к. может быть большим)
    subscription_expires_at TIMESTAMP WITH TIME ZONE NULL, -- Дата и время окончания подписки (NULL, если нет активной подписки)
    free_analysis_count INTEGER NOT NULL DEFAULT 2,  -- Счетчик оставшихся бесплатных анализов
    free_post_details_count INTEGER NOT NULL DEFAULT 2, -- Счетчик оставшихся бесплатных генераций деталей поста
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), -- Время создания записи пользователя
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()  -- Время последнего обновления записи
);

-- Индекс для быстрого поиска по user_id (хотя он и PRIMARY KEY)
CREATE INDEX IF NOT EXISTS idx_app_users_user_id ON app_users(user_id);

-- Индекс для возможного поиска по дате окончания подписки
CREATE INDEX IF NOT EXISTS idx_app_users_subscription_expires_at ON app_users(subscription_expires_at);

-- Триггер для автоматического обновления поля updated_at
-- Используем существующую функцию update_updated_at_column(), созданную в предыдущих миграциях
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM pg_proc WHERE proname = 'update_updated_at_column') THEN
        -- Удаляем старый триггер, если он вдруг был на этой таблице с другим именем
        DROP TRIGGER IF EXISTS update_app_users_updated_at ON app_users;
        -- Создаем триггер
        CREATE TRIGGER update_app_users_updated_at
        BEFORE UPDATE ON app_users
        FOR EACH ROW
        EXECUTE PROCEDURE update_updated_at_column();
        RAISE NOTICE 'Триггер update_app_users_updated_at создан или уже существует.';
    ELSE
        RAISE WARNING 'Функция update_updated_at_column() не найдена. Триггер для app_users.updated_at не создан.';
    END IF;
END $$;

COMMENT ON TABLE app_users IS 'Хранит информацию о пользователях приложения, их подписках и лимитах бесплатных действий.';
COMMENT ON COLUMN app_users.user_id IS 'Уникальный идентификатор пользователя Telegram.';
COMMENT ON COLUMN app_users.subscription_expires_at IS 'Дата и время окончания активной подписки.';
COMMENT ON COLUMN app_users.free_analysis_count IS 'Количество оставшихся бесплатных анализов каналов.';
COMMENT ON COLUMN app_users.free_post_details_count IS 'Количество оставшихся бесплатных генераций деталей поста.'; 