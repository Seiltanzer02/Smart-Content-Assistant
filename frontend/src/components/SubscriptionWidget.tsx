import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getBotStylePremiumStatus, PremiumStatus, generateInvoice } from '../api/subscription';

// Добавляем объявление глобального объекта Telegram для TypeScript
declare global {
  interface Window {
    Telegram?: any;
  }
}

interface SubscriptionWidgetProps {
  userId: string | null;
  isActive?: boolean;
}

// API_URL для относительных путей
const API_URL = '';

// Ключ для хранения данных о премиум-статусе в localStorage
const PREMIUM_STATUS_KEY = 'premium_status_data';

// Функция для форматирования даты с часовым поясом
const formatDate = (isoDateString: string): string => {
  if (!isoDateString) return '';
  const date = new Date(isoDateString);
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const SubscriptionWidget: React.FC<SubscriptionWidgetProps> = ({ userId, isActive }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<PremiumStatus | null>(null);
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  const SUBSCRIPTION_PRICE = 1; // в Stars
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [validatedUserId, setValidatedUserId] = useState<string | null>(null);
  // localStorage только как fallback для даты окончания
  const [localEndDate, setLocalEndDate] = useState<string | null>(null);
  
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
  
  // localStorage только как fallback для даты окончания
  useEffect(() => {
    const savedData = localStorage.getItem(PREMIUM_STATUS_KEY);
    if (savedData) {
      try {
        const parsedData = JSON.parse(savedData);
        if (parsedData.userId === validatedUserId && parsedData.endDate) {
          setLocalEndDate(parsedData.endDate);
        }
      } catch {}
    }
  }, [validatedUserId]);
  
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
      fetchSubscriptionStatus();
      intervalId = window.setInterval(() => {
        fetchSubscriptionStatus();
      }, 15000);
    }
    return () => {
      if (intervalId !== null) window.clearInterval(intervalId);
    };
  }, [validatedUserId]);
  
  // Используем только прямой запрос к /bot-style-premium-check/{user_id}
  const fetchSubscriptionStatus = async (): Promise<boolean> => {
    const effectiveUserId = validatedUserId;
    if (!effectiveUserId) {
      setError('ID пользователя не определен. Пожалуйста, перезапустите приложение.');
      return false;
    }
    setLoading(true);
    try {
      const result = await getBotStylePremiumStatus(effectiveUserId);
      setStatus(result);
      setError(null);
      setLoading(false);
      return true;
    } catch (err) {
      setError('Не удалось получить статус подписки');
      setLoading(false);
      return false;
    }
  };
  
  const handleSubscribeViaMainButton = () => {
    try {
      // Получаем ID пользователя из Telegram WebApp
      const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
      
      if (!userId) {
        setError('Не удалось получить ID пользователя');
        return;
      }
      
      // Генерируем инвойс для оплаты
      handleInvoiceGeneration(Number(userId));
    } catch (error) {
      console.error('Ошибка при подписке через главную кнопку:', error);
      setError(`Ошибка: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`);
    }
  };
  
  const handleInvoiceGeneration = async (userId: number) => {
    setIsSubscribing(true);
    setError(null);
    
    try {
      // Используем Fetch API для генерации инвойса через Stars
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
  
  // Функция для обработки проверки через бота и сохранения результата
  const handleCheckPremiumViaBot = () => {
    // Пытаемся получить или сохранить информацию в localStorage
    if (validatedUserId) {
      // Предварительно сохраняем информацию в localStorage о том, что проверка была запущена
      const checkInitiated = {
        userId: validatedUserId,
        timestamp: new Date().getTime(),
        status: 'checking'
      };
      localStorage.setItem('premium_check_initiated', JSON.stringify(checkInitiated));
      
      // Открываем бота для проверки премиума
      getBotStylePremiumStatus(validatedUserId);
    }
  };
  
  // Функция для ручного сохранения премиум-статуса (после проверки через бота)
  const savePremiumStatusFromBot = (hasPremium: boolean, endDate?: string) => {
    if (validatedUserId) {
      const dataToSave = {
        userId: validatedUserId,
        hasPremium,
        endDate: endDate || null,
        timestamp: new Date().getTime()
      };
      localStorage.setItem(PREMIUM_STATUS_KEY, JSON.stringify(dataToSave));
      setLocalEndDate(endDate || null);
      // После проверки через бота — всегда обновляем основной статус через API
      fetchSubscriptionStatus();
    }
  };
  
  // После возвращения из бота — всегда обновляем статус через API
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchSubscriptionStatus();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [validatedUserId]);
  
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
  
  // Основной индикатор статуса подписки — только по API, localStorage как резерв
  const hasPremium = status?.has_premium || false;
  const endDate = status?.subscription_end_date || null;

  return (
    <div className="subscription-widget">
      <h3>Статус подписки</h3>
      {hasPremium ? (
        <div className="premium-block">
          <h4>Премиум активен</h4>
          <p>Вам доступны все функции!</p>
          {endDate && (
            <p className="end-date">Действует до: {formatDate(endDate)}</p>
          )}
        </div>
      ) : (
        <div className="free-block">
          <h4>Бесплатный доступ</h4>
          <p>Для доступа к премиум-функциям оформите подписку.</p>
          <div className="buy-section">
            <button
              className="subscribe-button"
              onClick={handleSubscribe}
              disabled={isSubscribing}
            >
              {isSubscribing ? 'Обработка...' : 'Подписаться за ' + SUBSCRIPTION_PRICE + ' Stars'}
            </button>
          </div>
        </div>
      )}
      <p className="user-id">User ID: {validatedUserId}</p>
    </div>
  );
};

export default SubscriptionWidget; 