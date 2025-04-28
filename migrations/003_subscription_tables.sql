-- Таблица для хранения статистики использования бесплатных функций
CREATE TABLE IF NOT EXISTS user_usage_stats (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    analysis_count INTEGER DEFAULT 0,
    post_generation_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Таблица для хранения данных о подписках пользователей
CREATE TABLE IF NOT EXISTS user_subscription (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    start_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_date TIMESTAMP WITH TIME ZONE NOT NULL,
    payment_id TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_user_subscription_user_id ON user_subscription(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscription_end_date ON user_subscription(end_date);
CREATE INDEX IF NOT EXISTS idx_user_usage_stats_user_id ON user_usage_stats(user_id); 