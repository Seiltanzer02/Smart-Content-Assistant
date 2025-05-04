import React, { useState, useEffect, useRef } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus, getSubscriptionStatusV2, getPremiumStatus } from '../api/subscription';

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
  
  // Сохраняем userId в ref для предотвращения нежелательных перерисовок
  const userIdRef = useRef<string | null>(null);
  
  // Ссылка для хранения таймера обновления статуса
  const updateTimerRef = useRef<number | null>(null);
  
  // При монтировании получаем userId из URL-параметров, если он не передан через props
  useEffect(() => {
    console.log('[SubscriptionWidget] Инициализация компонента');
    
    const getUserIdFromUrl = (): string | null => {
      try {
        // Извлекаем userId из параметров URL
        const urlParams = new URLSearchParams(window.location.search);
        const urlUserId = urlParams.get('user_id');
        
        if (urlUserId) {
          console.log(`[SubscriptionWidget] Получен userId из URL: ${urlUserId}`);
          return urlUserId;
        }
        
        // Извлекаем userId из hash данных Telegram WebApp
        const hash = window.location.hash;
        if (hash && hash.includes("user")) {
          const decodedHash = decodeURIComponent(hash);
          const userMatch = decodedHash.match(/"id":(\d+)/);
          if (userMatch && userMatch[1]) {
            console.log(`[SubscriptionWidget] Получен userId из hash Telegram WebApp: ${userMatch[1]}`);
            return userMatch[1];
          }
        }
        
        return null;
      } catch (e) {
        console.error('[SubscriptionWidget] Ошибка при извлечении userId из URL:', e);
        return null;
      }
    };
    
    const validateUserId = () => {
      // Приоритет 1: userId из props
      if (userId) {
        console.log(`[SubscriptionWidget] Используем userId из props: ${userId}`);
        userIdRef.current = userId;
        return;
      }
      
      // Приоритет 2: userId из Telegram WebApp
      if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        const telegramUserId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
        console.log(`[SubscriptionWidget] Используем userId из Telegram WebApp: ${telegramUserId}`);
        userIdRef.current = telegramUserId;
        return;
      }
      
      // Приоритет 3: userId из URL-параметров
      const urlUserId = getUserIdFromUrl();
      if (urlUserId) {
        userIdRef.current = urlUserId;
        return;
      }
      
      // Если userId не определен, логируем ошибку
      console.error('[SubscriptionWidget] Не удалось определить userId');
      setError('Не удалось определить ID пользователя. Пожалуйста, обратитесь в поддержку.');
    };
    
    validateUserId();
    
    // Очистка таймера при размонтировании компонента
    return () => {
      if (updateTimerRef.current !== null) {
        clearInterval(updateTimerRef.current);
        updateTimerRef.current = null;
      }
    };
  }, [userId]);
  
  // Инициализация Telegram WebApp при монтировании компонента
  useEffect(() => {
    console.log('[SubscriptionWidget] Инициализация Telegram WebApp...');
    
    if (window.Telegram?.WebApp) {
      console.log('[SubscriptionWidget] window.Telegram.WebApp найден, настраиваем...');
      try {
        // Сообщаем Telegram WebApp, что мы готовы
        window.Telegram.WebApp.ready();
        console.log('[SubscriptionWidget] Telegram WebApp.ready() вызван успешно');
        
        // Если инит-данные содержат информацию о пользователе, обновляем userId
        if (window.Telegram.WebApp.initDataUnsafe?.user?.id && !userIdRef.current) {
          const telegramUserId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
          console.log(`[SubscriptionWidget] Обновляем userId из Telegram WebApp: ${telegramUserId}`);
          userIdRef.current = telegramUserId;
        }
      } catch (e) {
        console.error('[SubscriptionWidget] Ошибка при инициализации Telegram WebApp:', e);
      }
    }
  }, []);
  
  // Получение статуса подписки при изменении userId
  useEffect(() => {
    const fetchSubscriptionStatus = async () => {
      if (!userIdRef.current) {
        console.error('[SubscriptionWidget] Попытка запроса статуса подписки без валидного userId');
        setLoading(false);
        setError('ID пользователя не определен');
        return;
      }
      
      try {
        setLoading(true);
        setError(null);
        
        console.log(`[SubscriptionWidget] Запрос статуса подписки для ID: ${userIdRef.current}`);
        
        // Получаем статус подписки через новую функцию с каскадной проверкой
        const subscriptionData = await getUserSubscriptionStatus(userIdRef.current);
        
        console.log(`[SubscriptionWidget] Получен статус подписки:`, subscriptionData);
        
        setStatus(subscriptionData);
        setLoading(false);
        
        // Если есть ошибка в данных подписки, отображаем ее
        if (subscriptionData.error) {
          console.warn(`[SubscriptionWidget] Ошибка в данных подписки: ${subscriptionData.error}`);
          setError(`Ошибка получения данных: ${subscriptionData.error}`);
        }
      } catch (e) {
        console.error('[SubscriptionWidget] Ошибка при получении статуса подписки:', e);
        
        setError('Не удалось получить статус подписки');
        setLoading(false);
        
        // Устанавливаем базовый статус при ошибке
        setStatus({
          has_subscription: false,
          analysis_count: 1,
          post_generation_count: 1,
          error: e instanceof Error ? e.message : 'Неизвестная ошибка'
        });
      }
    };
    
    // Вызываем функцию сразу при монтировании и при изменении userId
    if (userIdRef.current) {
      fetchSubscriptionStatus();
      
      // Устанавливаем интервал для регулярного обновления статуса
      const updateInterval = 30000; // 30 секунд
      updateTimerRef.current = window.setInterval(() => {
        console.log('[SubscriptionWidget] Регулярное обновление статуса подписки...');
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
  }, []);
  
  // Запуск процесса подписки
  const handleSubscribe = () => {
    setIsSubscribing(true);
    setShowPaymentInfo(true);
  };
  
  // Проверка премиум-статуса напрямую через API
  const checkPremiumDirectly = async () => {
    if (!userIdRef.current) return;
    
    try {
      setLoading(true);
      const premiumStatus = await getPremiumStatus(userIdRef.current);
      
      if (premiumStatus.has_premium) {
        setStatus({
          has_subscription: true,
          analysis_count: premiumStatus.analysis_count || 9999,
          post_generation_count: premiumStatus.post_generation_count || 9999,
          subscription_end_date: premiumStatus.subscription_end_date
        });
        setError(null);
      } else {
        // Если премиум не обнаружен, проверяем подробный статус
        const detailedStatus = await getSubscriptionStatusV2(userIdRef.current);
        setStatus(detailedStatus);
      }
    } catch (e) {
      console.error('[SubscriptionWidget] Ошибка при прямой проверке премиума:', e);
      setError('Ошибка проверки статуса премиума');
    } finally {
      setLoading(false);
    }
  };
  
  // Рендеринг виджета подписки
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
          <button 
            className="retry-button" 
            onClick={checkPremiumDirectly}
          >
            Проверить снова
          </button>
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
          
          {/* Отладочная информация для диагностики проблем */}
          <div className="debug-info">
            <details>
              <summary>Диагностическая информация</summary>
              <div className="debug-data">
                <p>ID пользователя: {userIdRef.current || 'не определен'}</p>
                <p>Статус подписки: {status.has_subscription ? 'Активна' : 'Неактивна'}</p>
                <p>Telegram WebApp доступен: {window.Telegram?.WebApp ? 'Да' : 'Нет'}</p>
                {window.Telegram?.WebApp?.initDataUnsafe?.user?.id && (
                  <p>ID из Telegram WebApp: {window.Telegram.WebApp.initDataUnsafe.user.id}</p>
                )}
                <button 
                  className="debug-button"
                  onClick={checkPremiumDirectly}
                >
                  Принудительно проверить статус
                </button>
              </div>
            </details>
          </div>
        </div>
      ) : (
        <div className="subscription-status not-found">
          <span>Информация о подписке не найдена</span>
          <button 
            className="retry-button" 
            onClick={checkPremiumDirectly}
          >
            Проверить снова
          </button>
        </div>
      )}
      
      {userIdRef.current && (
        <div className="user-id-display">
          ID пользователя: {userIdRef.current}
        </div>
      )}
    </div>
  );
};

export default SubscriptionWidget; 