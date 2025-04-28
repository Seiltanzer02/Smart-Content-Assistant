import React, { useState, useEffect } from 'react';
import './SubscriptionManager.css';

interface SubscriptionStatus {
  has_subscription: boolean;
  free_analysis_count: number;
  free_post_details_count: number;
  subscription_expires_at: string | null;
  days_left: number;
}

interface SubscriptionManagerProps {
  userId: string;
  onStatusChange?: (status: SubscriptionStatus) => void;
}

const SubscriptionManager: React.FC<SubscriptionManagerProps> = ({ userId, onStatusChange }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [subscriptionStatus, setSubscriptionStatus] = useState<SubscriptionStatus>({
    has_subscription: false,
    free_analysis_count: 0,
    free_post_details_count: 0,
    subscription_expires_at: null,
    days_left: 0
  });
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fetchSubscriptionStatus = async () => {
    if (!userId) {
      setError('ID пользователя не указан');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(`/subscription/status?user_id=${userId}`);
      
      if (!response.ok) {
        throw new Error(`Ошибка получения статуса подписки: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (data.success && data.status) {
        setSubscriptionStatus(data.status);
        if (onStatusChange) {
          onStatusChange(data.status);
        }
      } else {
        throw new Error('Неверный формат данных о подписке');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка');
    } finally {
      setLoading(false);
    }
  };

  const handleSubscribe = async () => {
    try {
      setLoading(true);
      
      // Открываем бота для оформления подписки через Stars донат
      const botUsername = "ваш_бот_username"; // Замените на имя вашего бота
      
      if (window.Telegram && window.Telegram.WebApp) {
        // Используем Telegram WebApp для открытия ссылки на бота
        window.Telegram.WebApp.openTelegramLink(`https://t.me/${botUsername}?start=subscribe`);
        
        // Показываем сообщение пользователю о необходимости завершить подписку в боте
        setError(null);
        setSuccessMessage("Пожалуйста, завершите оформление подписки в боте Telegram. После оплаты вернитесь сюда и нажмите 'Обновить статус'.");
      } else {
        // Резервный вариант: открываем ссылку в новой вкладке
        window.open(`https://t.me/${botUsername}?start=subscribe`, '_blank');
        setSuccessMessage("Пожалуйста, завершите оформление подписки в боте Telegram. После оплаты вернитесь сюда и нажмите 'Обновить статус'.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubscriptionStatus();
  }, [userId]);

  if (loading && !subscriptionStatus.has_subscription) {
    return <div className="subscription-loading">Загрузка информации о подписке...</div>;
  }

  if (error) {
    return <div className="subscription-error">Ошибка: {error}</div>;
  }

  return (
    <div className="subscription-manager">
      {successMessage && (
        <div className="subscription-message success">
          {successMessage}
          <button 
            className="close-message-button" 
            onClick={() => setSuccessMessage(null)}
          >
            ×
          </button>
        </div>
      )}
      
      <div className="subscription-status">
        <h3>Статус подписки</h3>
        
        {subscriptionStatus.has_subscription ? (
          <div className="active-subscription">
            <div className="status-badge active">Активна</div>
            <p>Ваша подписка действует еще {subscriptionStatus.days_left} дней</p>
            <p className="expiry-date">
              Дата окончания: {subscriptionStatus.subscription_expires_at 
                ? new Date(subscriptionStatus.subscription_expires_at).toLocaleDateString('ru-RU') 
                : 'Неизвестно'}
            </p>
          </div>
        ) : (
          <div className="inactive-subscription">
            <div className="status-badge inactive">Неактивна</div>
            <p>У вас нет активной подписки</p>
            
            <div className="free-counters">
              <p>Бесплатные анализы: <span className="counter">{subscriptionStatus.free_analysis_count}</span></p>
              <p>Бесплатные детали постов: <span className="counter">{subscriptionStatus.free_post_details_count}</span></p>
            </div>
            
            <button 
              className="subscribe-button" 
              onClick={handleSubscribe}
              disabled={loading}
            >
              {loading ? 'Загрузка...' : 'Оформить подписку (70 Stars)'}
            </button>
          </div>
        )}
      </div>
      
      <div className="subscription-info">
        <h4>О подписке</h4>
        <ul>
          <li>Стоимость - 70 Stars в месяц</li>
          <li>Неограниченный доступ к анализу каналов</li>
          <li>Неограниченная генерация деталей постов</li>
          <li>Приоритетная поддержка</li>
        </ul>
      </div>
      
      <button 
        className="refresh-button" 
        onClick={fetchSubscriptionStatus}
        disabled={loading}
      >
        Обновить статус
      </button>
    </div>
  );
};

export default SubscriptionManager; 