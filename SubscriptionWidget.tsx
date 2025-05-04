import React, { useState, useEffect, useRef } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus } from '../api/subscription';

interface SubscriptionWidgetProps {
  userId: string | null;
  isActive?: boolean;
}

// API_URL для относительных путей
const API_URL = '';

// Функция для форматирования даты с часовым поясом
const formatDate = (isoDateString: string): string => {
  try {
    const date = new Date(isoDateString);
    
    // Форматируем дату с временем и часовым поясом для консистентного отображения
    const options: Intl.DateTimeFormatOptions = {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short'
    };
    
    return date.toLocaleDateString('ru-RU', options);
  } catch (e) {
    console.error('Ошибка при форматировании даты:', e);
    return 'Дата неизвестна';
  }
};

const SubscriptionWidget: React.FC<SubscriptionWidgetProps> = ({ userId, isActive }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  const SUBSCRIPTION_PRICE = 1; // в Stars
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [validatedUserId, setValidatedUserId] = useState<string | null>(null);
  
  // Ссылка для хранения таймера обновления статуса
  const updateTimerRef = useRef<number | null>(null);
  
  // Проверка и валидация ID пользователя
  useEffect(() => {
    console.log('[ValidateUserID] Starting validation...');
    
    const clearUpdateTimer = () => {
      if (updateTimerRef.current !== null) {
        clearInterval(updateTimerRef.current);
        updateTimerRef.current = null;
      }
    };
    
    const validateUserId = () => {
      // Проверяем userId из props
      if (userId) {
        console.log(`[ValidateUserID] Got userId from props: ${userId}`);
        setValidatedUserId(userId);
        setError(null);
        clearUpdateTimer();
        return;
      }
      
      // Если userId из props отсутствует, проверяем Telegram WebApp
      if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        const telegramUserId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
        console.log(`[ValidateUserID] Got userId from Telegram WebApp immediately: ${telegramUserId}`);
        setValidatedUserId(telegramUserId);
        setError(null);
        clearUpdateTimer();
        return;
      }
      
      console.log('[ValidateUserID] Failed to get userId from props or Telegram WebApp');
      setError('ID пользователя не найден');
      setLoading(false);
    };
    
    // Вызываем функцию валидации при монтировании компонента
    validateUserId();
    
    // Очистка таймера при размонтировании компонента
    return () => {
      clearUpdateTimer();
    };
  }, [userId]);
  
  // Инициализация Telegram WebApp при монтировании компонента
  useEffect(() => {
    console.log('Инициализация Telegram WebApp...');
    
    if (window.Telegram?.WebApp) {
      console.log('window.Telegram.WebApp найден, настраиваем...');
      try {
        // Сообщаем Telegram WebApp, что мы готовы
        window.Telegram.WebApp.ready();
      } catch (e) {
        console.error('Ошибка при инициализации Telegram WebApp:', e);
      }
    }
  }, []);
  
  // Получение статуса подписки при изменении validatedUserId
  useEffect(() => {
    const fetchSubscriptionStatus = async () => {
      if (!validatedUserId) {
        console.log('Невозможно запросить статус подписки без валидного userId');
        return;
      }
      
      try {
        setLoading(true);
        setError(null);
        
        console.log(`Запрос статуса подписки для ID: ${validatedUserId}`);
        
        // Получение статуса подписки
        const subscriptionData = await getUserSubscriptionStatus(validatedUserId);
        console.log(`Получен статус подписки:`, subscriptionData);
        
        setStatus(subscriptionData);
        setLoading(false);
      } catch (e) {
        console.error('Ошибка при получении статуса подписки:', e);
        setError('Не удалось получить статус подписки');
        setLoading(false);
      }
    };
    
    // Вызываем функцию при монтировании компонента и при изменении validatedUserId
    if (validatedUserId) {
      fetchSubscriptionStatus();
    
      // Устанавливаем интервал для регулярного обновления статуса
      const updateInterval = 15000; // 15 секунд
      updateTimerRef.current = window.setInterval(() => {
        console.log('Регулярное обновление статуса подписки...');
        fetchSubscriptionStatus();
      }, updateInterval);
    }
    
    // Очистка интервала при размонтировании компонента
    return () => {
      if (updateTimerRef.current !== null) {
        clearInterval(updateTimerRef.current);
        updateTimerRef.current = null;
      }
    };
  }, [validatedUserId]);
  
  // Диагностическая информация
  useEffect(() => {
    console.log('SubscriptionWidget загружен, проверка Telegram.WebApp:');
    console.log('window.Telegram существует:', !!window.Telegram);
    console.log('window.Telegram?.WebApp существует:', !!window.Telegram?.WebApp);
    
    if (window.Telegram?.WebApp) {
      console.log('window.Telegram.WebApp методы:', Object.getOwnPropertyNames(window.Telegram.WebApp));
    }
  }, []);
  
  // Запуск процесса подписки
  const handleSubscribe = () => {
    setIsSubscribing(true);
    setShowPaymentInfo(true);
  };
  
  // Рендер виджета подписки
  return (
    <div className="subscription-widget">
      <h2>Управление подпиской</h2>
      
      {loading ? (
        <div className="subscription-status loading">
          <span>Загрузка данных подписки...</span>
        </div>
      ) : error ? (
        <div className="subscription-status error">
          <span>{error}</span>
        </div>
      ) : status ? (
        <div className="subscription-container">
          <div className={`subscription-status ${status.has_subscription ? 'premium' : 'free'}`}>
            {status.has_subscription ? (
              <div className="premium-status">
                <div className="premium-badge">ПРЕМИУМ</div>
                {status.subscription_end_date && (
                  <span className="expiry-date">
                    Действует до: {formatDate(status.subscription_end_date)}
                  </span>
                )}
              </div>
            ) : (
              <span className="free-status">Бесплатный доступ</span>
            )}
          </div>
          
          <div className="usage-limits">
            <h3>У вас осталось:</h3>
            <div className="limit-item">
              <span className="limit-label">Анализов каналов:</span>
              <span className="limit-value">{status.analysis_count === 9999 ? '∞' : status.analysis_count}</span>
            </div>
            <div className="limit-item">
              <span className="limit-label">Генераций постов:</span>
              <span className="limit-value">{status.post_generation_count === 9999 ? '∞' : status.post_generation_count}</span>
            </div>
          </div>
          
          {!status.has_subscription && (
            <div className="subscription-action">
              <button 
                className="premium-button"
                onClick={handleSubscribe}
                disabled={isSubscribing}
              >
                {isSubscribing ? 'Оформление подписки...' : 'Получите Premium'}
              </button>
              <div className="subscription-price">
                Снимите все ограничения, получив Premium-подписку всего за 1 Star в месяц!
              </div>
            </div>
          )}
          
          {showPaymentInfo && (
            <div className="payment-info">
              <h3>Подписаться за 1 Star</h3>
              <button 
                className="payment-button"
                onClick={() => {
                  // Здесь будет инициироваться платеж
                  setIsSubscribing(false);
                  setShowPaymentInfo(false);
                }}
              >
                Подписаться за 1 Star
              </button>
              <button 
                className="cancel-button"
                onClick={() => {
                  setIsSubscribing(false);
                  setShowPaymentInfo(false);
                }}
              >
                Отмена
              </button>
            </div>
          )}
          
          {/* Отладочная информация */}
          <div className="debug-info">
            <h4>Отладочная информация:</h4>
            <pre>{JSON.stringify(status, null, 2)}</pre>
            <button 
              className="debug-button"
              onClick={async () => {
                try {
                  const refreshedStatus = await getUserSubscriptionStatus(validatedUserId);
                  setStatus(refreshedStatus);
                  alert('Обновление выполнено');
                } catch (e) {
                  console.error('Ошибка обновления:', e);
                  alert(`Ошибка: ${e}`);
                }
              }}
            >
              Обновить статус
            </button>
          </div>
        </div>
      ) : (
        <div className="subscription-status not-found">
          <span>Информация о подписке не найдена</span>
        </div>
      )}
      
      {validatedUserId && (
        <div className="user-id-display">
          ID пользователя: {validatedUserId}
        </div>
      )}
    </div>
  );
};

export default SubscriptionWidget; 