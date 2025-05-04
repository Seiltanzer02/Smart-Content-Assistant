import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus, generateInvoice } from '../api/subscription';

interface SubscriptionWidgetProps {
  userId: string | null;
  isActive?: boolean;
}

// API_URL для относительных путей
const API_URL = '';

const SubscriptionWidget: React.FC<SubscriptionWidgetProps> = ({ userId, isActive }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  const SUBSCRIPTION_PRICE = 1; // в Stars
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [validatedUserId, setValidatedUserId] = useState<string | null>(null);
  
  // Проверка и валидация ID пользователя
  useEffect(() => {
    const validateUserId = () => {
      // Проверяем userId из props
      if (userId) {
        console.log(`Получен userId из props: ${userId}`);
        setValidatedUserId(userId);
        return;
      }
      
      // Если userId из props отсутствует, проверяем Telegram WebApp
      if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        const telegramUserId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
        console.log(`Получен userId из Telegram WebApp: ${telegramUserId}`);
        setValidatedUserId(telegramUserId);
        return;
      }
      
      // Если не удалось получить userId
      console.error('Не удалось получить ID пользователя ни из props, ни из Telegram WebApp');
      setError('Не удалось определить ID пользователя. Попробуйте перезагрузить страницу.');
      setValidatedUserId(null);
    };
    
    validateUserId();
  }, [userId]);
  
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
    <div className={`subscription-widget ${status?.has_subscription ? 'premium-active' : 'free-tier'}`}>
      <h3>Управление подпиской</h3>
      {!validatedUserId ? (
        <p className="error-message">Не удалось определить пользователя. Пожалуйста, перезагрузите страницу.</p>
      ) : loading ? (
        <p>Загрузка статуса подписки...</p>
      ) : error ? (
        <div>
          <p className="error-message">{error}</p>
          <button onClick={fetchSubscriptionStatus}>Повторить</button>
        </div>
      ) : status ? (
        <div className={status.has_subscription ? "subscription-active" : "subscription-free"}>
          {status.has_subscription ? (
            <>
              <span className="status-badge premium">Premium</span>
              <p>Ваша подписка активна до: {new Date(status.subscription_end_date!).toLocaleDateString()}</p>
              <p>Спасибо за поддержку!</p>
              <p className="user-info">ID пользователя: {validatedUserId}</p>
            </>
          ) : (
            <>
              <span className="status-badge free">Бесплатный доступ</span>
              <p>У вас осталось:</p>
              <ul>
                <li>Анализов каналов: {status.analysis_count}</li>
                <li>Генераций постов: {status.post_generation_count}</li>
              </ul>
              <div className="subscription-offer">
                <h4>Получите Premium</h4>
                <p>Снимите все ограничения, получив Premium-подписку всего за 1 Star в месяц!</p>
                <button 
                  className="subscribe-button"
                  onClick={() => validatedUserId && handleInvoiceGeneration(Number(validatedUserId))}
                  disabled={isSubscribing}
                >
                  {isSubscribing ? 'Создание платежа...' : 'Подписаться за 1 Star'}
                </button>
              </div>
              <p className="user-info">ID пользователя: {validatedUserId}</p>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
};

export default SubscriptionWidget; 