-- Создаем таблицу платежей, если она еще не существует
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    currency TEXT NOT NULL,
    invoice_payload TEXT NOT NULL,
    telegram_payment_charge_id TEXT,
    provider_payment_charge_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_user
      FOREIGN KEY(user_id) 
      REFERENCES auth.users(id)
      ON DELETE CASCADE
);

-- Создаем индекс для ускорения поиска по user_id
CREATE INDEX IF NOT EXISTS payments_user_id_idx ON payments (user_id);

-- Добавляем комментарии к таблице
COMMENT ON TABLE payments IS 'Таблица для хранения информации о платежах пользователей';
COMMENT ON COLUMN payments.user_id IS 'ID пользователя, совершившего платеж';
COMMENT ON COLUMN payments.amount IS 'Сумма платежа в наименьших единицах валюты (например, копейки)';
COMMENT ON COLUMN payments.currency IS 'Код валюты платежа';
COMMENT ON COLUMN payments.invoice_payload IS 'Payload инвойса';
COMMENT ON COLUMN payments.telegram_payment_charge_id IS 'ID платежа в системе Telegram';
COMMENT ON COLUMN payments.provider_payment_charge_id IS 'ID платежа в платежной системе';
COMMENT ON COLUMN payments.created_at IS 'Дата и время создания записи о платеже'; 