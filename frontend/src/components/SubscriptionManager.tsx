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
      const response = await fetch(`/subscription/create-invoice?user_id=${userId}`, {
        method: 'POST',
      });
      
      if (!response.ok) {
        throw new Error(`Ошибка создания счета: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (data.success && data.invoice_url) {
        // Открываем страницу оплаты в Telegram WebApp
        if (window.Telegram && window.Telegram.WebApp) {
          window.Telegram.WebApp.openInvoice(data.invoice_url, (status) => {
            if (status === 'paid') {
              // После успешной оплаты обновляем статус подписки
              fetchSubscriptionStatus();
            }
          });
        } else {
          // Если нет доступа к Telegram WebApp, открываем в новой вкладке
          window.open(data.invoice_url, '_blank');
        }
      } else {
        throw new Error('Не удалось получить ссылку для оплаты');
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