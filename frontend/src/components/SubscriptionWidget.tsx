import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus, generateInvoice, checkPremiumViaBot, forcePremiumStatus, hasLocalPremium } from '../api/subscription';

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
  const [hasLocalPremiumStatus, setHasLocalPremiumStatus] = useState<boolean>(false);
  
  // Проверка и валидация ID пользователя
  useEffect(() => {
    let intervalId: number | null = null; // Используем number вместо NodeJS.Timeout
    
    const validateUserId = () => {
      console.log('[ValidateUserID] Starting validation...');
      // Проверяем userId из props
      if (userId) {
        console.log(`[ValidateUserID] Got userId from props: ${userId}`);
        setValidatedUserId(userId);
        setError(null); // Очищаем предыдущие ошибки
        if(intervalId !== null) clearInterval(intervalId); // Очищаем интервал, если он был запущен
        intervalId = null;
        return;
      }
      
      // Если userId из props отсутствует, проверяем Telegram WebApp
      if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        const telegramUserId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
        console.log(`[ValidateUserID] Got userId from Telegram WebApp immediately: ${telegramUserId}`);
        setValidatedUserId(telegramUserId);
        setError(null); // Очищаем предыдущие ошибки
        if(intervalId !== null) clearInterval(intervalId); // Очищаем интервал
        intervalId = null;
        return;
      }
      
      // Если не удалось получить сразу, пробуем подождать
      if (window.Telegram?.WebApp) {
        console.log('[ValidateUserID] userId not found yet, waiting for Telegram WebApp.ready() and initData...');
        window.Telegram.WebApp.ready(); // Убедимся, что ready() вызван
        
        // Если интервал уже запущен, не создаем новый
        if (intervalId !== null) return;
        
        // Запускаем интервал для проверки initData
        let attempts = 0;
        // Используем window.setInterval для ясности, что это браузерный API
        intervalId = window.setInterval(() => {
          attempts++;
          console.log(`[ValidateUserID] Polling for initData... Attempt: ${attempts}`);
          if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
            if(intervalId !== null) clearInterval(intervalId);
            intervalId = null; // Сбрасываем ID интервала
            const telegramUserId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
            console.log(`[ValidateUserID] Got userId from Telegram WebApp after waiting: ${telegramUserId}`);
            setValidatedUserId(telegramUserId);
            setError(null); // Очищаем ошибку, если она была установлена ранее
          } else if (attempts >= 10) { // Останавливаемся после ~5 секунд
            if(intervalId !== null) clearInterval(intervalId);
            intervalId = null; // Сбрасываем ID интервала
            // Проверяем еще раз, чтобы избежать гонки состояний
            if (!validatedUserId) { // Проверяем validatedUserId, чтобы не перезаписать ошибку, если ID уже получен
              console.error('[ValidateUserID] Failed to get userId from Telegram WebApp after multiple attempts.');
              setError('Не удалось определить ID пользователя. Попробуйте перезагрузить страницу.');
              setValidatedUserId(null);
            }
          }
        }, 500); // Проверяем каждые 500мс
      } else {
        // Если Telegram WebApp вообще недоступен
        console.error('[ValidateUserID] window.Telegram.WebApp not found.');
        setError('Ошибка: Приложение не запущено в среде Telegram.');
        setValidatedUserId(null);
      }
    };
    
    validateUserId();
    
    // Функция очистки для useEffect
    return () => {
      if (intervalId !== null) { // Используем number
        console.log('[ValidateUserID] Cleaning up interval on unmount or prop change.');
        clearInterval(intervalId);
      }
    };
  }, [userId, validatedUserId]); // Добавляем validatedUserId в зависимости, чтобы остановить поллинг, если ID получен
  
  // Проверяем локальный премиум-статус при каждом изменении userId
  useEffect(() => {
    if (validatedUserId) {
      const localPremium = hasLocalPremium(validatedUserId);
      setHasLocalPremiumStatus(localPremium);
      console.log(`[SubscriptionWidget] Локальный премиум-статус для ${validatedUserId}: ${localPremium}`);
    }
  }, [validatedUserId]);
  
  // Инициализация и настройка Telegram WebApp
  useEffect(() => {
    console.log('Инициализация Telegram WebApp...');
    
    // Проверяем наличие Telegram WebApp
    if (window.Telegram?.WebApp) {
      console.log('window.Telegram.WebApp найден, настраиваем...');
      
      // Инициализируем Telegram WebApp
      window.Telegram.WebApp.ready();
      
      // Настраиваем главную кнопку
      if (window.Telegram.WebApp.MainButton) {
        window.Telegram.WebApp.MainButton.setText('Подписаться за ' + SUBSCRIPTION_PRICE + ' Stars');
        window.Telegram.WebApp.MainButton.color = '#2481cc';
        window.Telegram.WebApp.MainButton.textColor = '#ffffff';
        if (isActive) {
          window.Telegram.WebApp.MainButton.hide();
        }
        
        // Добавляем обработчик нажатия на главную кнопку
        window.Telegram.WebApp.MainButton.onClick(handleSubscribeViaMainButton);
      } else {
        console.warn('MainButton недоступен в Telegram WebApp');
      }
      
      // Добавляем обработчик onEvent для события 'popup_closed'
      if (typeof window.Telegram.WebApp.onEvent === 'function') {
        window.Telegram.WebApp.onEvent('popup_closed', () => {
          console.log('Popup закрыт, обновляем статус подписки');
          fetchSubscriptionStatus();
        });
      }
    } else {
      console.warn('window.Telegram.WebApp не найден!');
    }
    
    // Функция очистки при размонтировании компонента
    return () => {
      if (window.Telegram?.WebApp?.MainButton) {
        window.Telegram.WebApp.MainButton.offClick(handleSubscribeViaMainButton);
      }
    };
  }, [isActive]);
  
  useEffect(() => {
    if (userId) {
      fetchSubscriptionStatus();
    }
    
    // Добавляем логирование статуса Telegram WebApp при загрузке компонента
    console.log('SubscriptionWidget загружен, проверка Telegram.WebApp:');
    console.log('window.Telegram существует:', !!window.Telegram);
    console.log('window.Telegram?.WebApp существует:', !!window.Telegram?.WebApp);
    if (window.Telegram?.WebApp) {
      console.log('window.Telegram.WebApp методы:', Object.keys(window.Telegram.WebApp));
    }
  }, [userId]);
  
  // Периодическое обновление статуса подписки
  useEffect(() => {
    let intervalId: number | null = null;
    
    if (validatedUserId) {
      // Сразу запрашиваем статус
      fetchSubscriptionStatus();
      
      // Устанавливаем интервал обновления - каждые 15 секунд
      intervalId = window.setInterval(() => {
        console.log('Регулярное обновление статуса подписки...');
        fetchSubscriptionStatus();
      }, 15000);
    }
    
    // Очистка при размонтировании
    return () => {
      if (intervalId !== null) {
        window.clearInterval(intervalId);
      }
    };
  }, [validatedUserId]);
  
  const fetchSubscriptionStatus = async (): Promise<boolean> => {
    if (!validatedUserId) {
      console.error('Попытка запроса статуса подписки без валидного userId');
      setError('ID пользователя не определен');
      return false;
    }
    
    setLoading(true);
    try {
      console.log(`Запрос статуса подписки для ID: ${validatedUserId}`);
      // Используем функцию из API вместо прямого запроса
      const subscriptionData = await getUserSubscriptionStatus(validatedUserId);
      console.log('Получен статус подписки:', subscriptionData);
      setStatus(subscriptionData);
      
      // Показываем/скрываем главную кнопку в зависимости от статуса подписки
      if (window.Telegram?.WebApp?.MainButton) {
        if (!subscriptionData.has_subscription && !isActive) {
          window.Telegram.WebApp.MainButton.show();
        } else {
          window.Telegram.WebApp.MainButton.hide();
        }
      }
      
      return subscriptionData.has_subscription;
    } catch (err: any) {
      console.error('Ошибка при получении статуса подписки:', err);
      setError(err.response?.data?.detail || err.message || 'Ошибка при загрузке статуса подписки');
      return false;
    } finally {
      setLoading(false);
    }
  };
  
  // Функция для запуска платежа через MainButton
  const handleSubscribeViaMainButton = () => {
    console.log('Нажата главная кнопка в Telegram WebApp');
    
    // Показываем подтверждение через Telegram WebApp
    if (window.Telegram?.WebApp?.showConfirm) {
      window.Telegram.WebApp.showConfirm(
        'Вы хотите оформить подписку за ' + SUBSCRIPTION_PRICE + ' Stars?',
        (confirmed) => {
          if (confirmed) {
            handleSubscribe();
          }
        }
      );
    } else {
      // Если метод showConfirm недоступен, просто продолжаем
      handleSubscribe();
    }
  };
  
  const handleInvoiceGeneration = async (userId: number) => {
    try {
      if (!validatedUserId) {
        setError('Не удалось определить ID пользователя');
        return;
      }
      
      setIsSubscribing(true);
      // Получаем invoice_link с backend
      const response = await fetch('/generate-stars-invoice-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, amount: 1 })
      });
      const data = await response.json();
      if (data.success && data.invoice_link) {
        if (window?.Telegram?.WebApp && typeof window?.Telegram?.WebApp.openInvoice === 'function') {
          window.Telegram.WebApp.openInvoice(data.invoice_link, (status) => {
            if (status === 'paid') {
              fetchSubscriptionStatus();
              if (window?.Telegram?.WebApp?.showPopup) {
                window.Telegram.WebApp.showPopup({
                  title: 'Успешная оплата',
                  message: 'Ваша подписка Premium активирована!',
                  buttons: [{ type: 'ok' }]
                });
              }
              setTimeout(() => {
                if (window?.Telegram?.WebApp?.close) {
                  window.Telegram.WebApp.close();
                }
              }, 300);
            } else if (status === 'failed') {
              setError('Оплата не удалась. Пожалуйста, попробуйте позже.');
            } else if (status === 'cancelled') {
              setError('Платеж был отменен.');
            }
            setIsSubscribing(false);
          });
        } else {
          setError('Оплата через Stars недоступна в этом окружении.');
          setIsSubscribing(false);
        }
      } else {
        setError(data.error || 'Ошибка генерации инвойса');
        setIsSubscribing(false);
      }
    } catch (error) {
      console.error('Ошибка при генерации Stars invoice link:', error);
      setError(`Ошибка: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`);
      setIsSubscribing(false);
    }
  };
  
  const handleSubscribe = async () => {
    try {
      // Получаем ID пользователя из Telegram WebApp
      const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
      
      if (!userId) {
        setError('Не удалось получить ID пользователя');
        return;
      }
      
      // Генерируем инвойс для оплаты
      await handleInvoiceGeneration(Number(userId));
    } catch (error) {
      console.error('Ошибка при подписке:', error);
      setError(`Ошибка: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`);
    }
  };
  
  // Добавляем функцию для форсирования премиум-статуса локально
  const handleForceLocalPremium = () => {
    if (validatedUserId) {
      forcePremiumStatus(validatedUserId, true, 30);
      setHasLocalPremiumStatus(true);
      alert('Премиум-статус активирован локально на 30 дней!');
    } else {
      alert('Ошибка: не удалось определить ID пользователя');
    }
  };
  
  // Добавляем функцию для проверки премиума через бота
  const handleCheckPremiumViaBot = () => {
    checkPremiumViaBot();
  };
  
  if (loading) {
    return <div className="subscription-widget loading">Загрузка информации о подписке...</div>;
  }
  
  if (error) {
    return (
      <div className="subscription-widget error">
        <p>Ошибка: {error}</p>
        <button onClick={fetchSubscriptionStatus}>Повторить</button>
      </div>
    );
  }
  
  return (
    <div className="subscription-widget">
      <h3>Статус подписки</h3>
      
      {loading ? (
        <p className="loading-indicator">Загрузка статуса подписки...</p>
      ) : error ? (
        <div className="error-section">
          <p className="error-message">{error}</p>
          
          {/* Добавляем альтернативные действия при ошибке */}
          <div className="error-actions">
            <p>Возможные действия:</p>
            <button 
              className="alternative-action-button"
              onClick={handleCheckPremiumViaBot}
            >
              Проверить через бота
            </button>
            
            <button 
              className="alternative-action-button"
              onClick={() => fetchSubscriptionStatus()}
            >
              Повторить проверку
            </button>
            
            {validatedUserId && (
              <button 
                className="alternative-action-button" 
                onClick={handleForceLocalPremium}
              >
                Активировать премиум локально
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="subscription-details">
          {status?.has_subscription || hasLocalPremiumStatus ? (
            <div className="premium-status">
              <p className="status-label">Премиум</p>
              {status?.subscription_end_date && (
                <p className="end-date">
                  Действует до: {formatDate(status.subscription_end_date)}
                </p>
              )}
              <p className="limits">
                Доступно анализов: {status?.analysis_count || 'Неограниченно'}
                <br />
                Доступно генераций постов: {status?.post_generation_count || 'Неограниченно'}
              </p>
              
              {/* Добавляем примечание о статусе */}
              {!status?.has_subscription && hasLocalPremiumStatus && (
                <p className="note">Примечание: премиум активирован локально</p>
              )}
            </div>
          ) : (
            <div className="free-status">
              <p className="status-label">Бесплатный доступ</p>
              <p className="limits">
                Доступно анализов: {status?.analysis_count || 3}
                <br />
                Доступно генераций постов: {status?.post_generation_count || 1}
              </p>
              {!isActive && (
                <button 
                  className="subscribe-button"
                  onClick={handleSubscribe}
                  disabled={isSubscribing}
                >
                  {isSubscribing ? 'Обработка...' : 'Подписаться за ' + SUBSCRIPTION_PRICE + ' Stars'}
                </button>
              )}
              
              {/* Альтернативные способы проверки */}
              <div className="alternative-actions">
                <button 
                  className="alternative-action-button"
                  onClick={handleCheckPremiumViaBot}
                >
                  Проверить через бота
                </button>
                
                {validatedUserId && (
                  <button 
                    className="alternative-action-button" 
                    onClick={handleForceLocalPremium}
                  >
                    Активировать премиум (тест)
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {showPaymentInfo && (
        <div className="payment-info">
          <p>Для оплаты используется Telegram Stars.</p>
          {/* ... existing payment info ... */}
        </div>
      )}
    </div>
  );
};

export default SubscriptionWidget; 