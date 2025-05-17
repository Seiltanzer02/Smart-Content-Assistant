import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus, generateInvoice, checkPremiumViaBot, getBotStylePremiumStatus, PremiumStatus } from '../api/subscription';
import { checkChannelSubscription } from '../channelSubscriptionCheck';

// Добавляем объявление глобального объекта Telegram для TypeScript
declare global {
  interface Window {
    Telegram?: any;
  }
}

declare global {
  interface ImportMetaEnv {
    readonly VITE_TARGET_CHANNEL_USERNAME: string;
  }
  interface ImportMeta {
    readonly env: ImportMetaEnv;
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

const TARGET_CHANNEL_USERNAME = import.meta.env.VITE_TARGET_CHANNEL_USERNAME || '';
const channelUrl = 'https://t.me/' + TARGET_CHANNEL_USERNAME;

const SubscriptionWidget: React.FC<SubscriptionWidgetProps> = ({ userId, isActive }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [premiumStatus, setPremiumStatus] = useState<PremiumStatus | null>(null);  // Добавляем состояние для прямого статуса премиума
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  const SUBSCRIPTION_PRICE = 1; // в Stars
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [validatedUserId, setValidatedUserId] = useState<string | null>(null);
  // localStorage только как fallback для даты окончания
  const [localEndDate, setLocalEndDate] = useState<string | null>(null);
  const [channelCheck, setChannelCheck] = useState<{ loading: boolean, subscribed: boolean, message: string }>({ loading: true, subscribed: false, message: '' });
  const [checking, setChecking] = useState(false);
  
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
    if (validatedUserId) {
      fetchSubscriptionStatus();
      // Также запускаем прямую проверку через новый эндпоинт
      fetchDirectPremiumStatus();
    }
    
    // Добавляем логирование статуса Telegram WebApp при загрузке компонента
    console.log('SubscriptionWidget загружен, проверка Telegram.WebApp:');
    console.log('window.Telegram существует:', !!window.Telegram);
    console.log('window.Telegram?.WebApp существует:', !!window.Telegram?.WebApp);
    if (window.Telegram?.WebApp) {
      console.log('window.Telegram.WebApp методы:', Object.keys(window.Telegram.WebApp));
    }
  }, [validatedUserId]);
  
  // Периодическое обновление статуса подписки
  useEffect(() => {
    let intervalId: number | null = null;
    if (validatedUserId) {
      fetchSubscriptionStatus();
      fetchDirectPremiumStatus(); // Также обновляем прямой статус премиума
      intervalId = window.setInterval(() => {
        fetchSubscriptionStatus();
        fetchDirectPremiumStatus(); // Также обновляем прямой статус премиума
      }, 15000);
    }
    return () => {
      if (intervalId !== null) window.clearInterval(intervalId);
    };
  }, [validatedUserId]);
  
  // Основная функция получения статуса
  const fetchSubscriptionStatus = async (): Promise<boolean> => {
    let effectiveUserId = validatedUserId;
    if (!effectiveUserId) {
      setError('ID пользователя не определен. Пожалуйста, перезапустите приложение.');
      return false;
    }
    setLoading(true);
    try {
      let result: SubscriptionStatus | null = null;
      try {
        result = await getUserSubscriptionStatus(effectiveUserId);
      } catch (apiError) {
        // fallback: пробуем взять из localStorage
        const savedData = localStorage.getItem('premium_status_data');
        if (savedData) {
          const parsed = JSON.parse(savedData);
          if (parsed.userId === effectiveUserId && parsed.hasPremium) {
            result = {
              has_subscription: true,
              is_active: true,
              analysis_count: 9999,
              post_generation_count: 9999,
              subscription_end_date: parsed.endDate || undefined
            };
          }
        }
      }
      if (!result) {
        result = {
          has_subscription: false,
          is_active: false,
          analysis_count: 3,
          post_generation_count: 1
        };
      }
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

  // Новая функция для прямой проверки премиум-статуса через API
  const fetchDirectPremiumStatus = async (): Promise<boolean> => {
    let effectiveUserId = validatedUserId;
    if (!effectiveUserId) {
      console.error('[fetchDirectPremiumStatus] ID пользователя не определен.');
      return false;
    }
    
    try {
      // Используем новую функцию из API
      const result = await getBotStylePremiumStatus(effectiveUserId);
      console.log('[fetchDirectPremiumStatus] Получен результат:', result);
      setPremiumStatus(result);

      // Если получили положительный ответ, сохраняем в localStorage для резервного доступа
      if (result.has_premium) {
        localStorage.setItem(PREMIUM_STATUS_KEY, JSON.stringify({
          userId: effectiveUserId,
          hasPremium: true,
          endDate: result.subscription_end_date,
          timestamp: new Date().getTime()
        }));
      }
      
      return true;
    } catch (err) {
      console.error('[fetchDirectPremiumStatus] Ошибка:', err);
      
      // Пробуем взять из localStorage в случае ошибки
      try {
        const savedData = localStorage.getItem(PREMIUM_STATUS_KEY);
        if (savedData) {
          const parsed = JSON.parse(savedData);
          if (parsed.userId === effectiveUserId && parsed.hasPremium) {
            // Создаем объект премиум-статуса из сохраненных данных
            const fallbackStatus: PremiumStatus = {
              has_premium: true,
              user_id: effectiveUserId,
              subscription_end_date: parsed.endDate,
              analysis_count: 9999,
              post_generation_count: 9999
            };
            console.log('[fetchDirectPremiumStatus] Использую сохраненные данные:', fallbackStatus);
            setPremiumStatus(fallbackStatus);
            return true;
          }
        }
      } catch (localStorageError) {
        console.error('[fetchDirectPremiumStatus] Ошибка при чтении из localStorage:', localStorageError);
      }
      
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
              fetchDirectPremiumStatus(); // Также обновляем прямой статус премиума
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
  
  // Проверка через бота и сохранение статуса в localStorage
  const handleCheckPremiumViaBot = () => {
    if (validatedUserId) {
      checkPremiumViaBot();
      // Сохраняем флаг, что была ручная проверка
      localStorage.setItem('premium_check_initiated', JSON.stringify({
        userId: validatedUserId,
        timestamp: new Date().getTime(),
        status: 'checking'
      }));
    }
  };
  
  // Автообновление после возврата из бота
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchSubscriptionStatus();
        fetchDirectPremiumStatus(); // Также обновляем прямой статус премиума
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [validatedUserId]);

  // Функция повторной проверки
  const handleRecheck = async () => {
    if (!validatedUserId) return;
    setChecking(true);
    try {
      const res = await checkChannelSubscription(Number(validatedUserId));
      setChannelCheck({ loading: false, subscribed: res.subscribed, message: res.message });
    } catch (e: any) {
      setChannelCheck({ loading: false, subscribed: false, message: e.message || 'Ошибка проверки подписки' });
    }
    setChecking(false);
  };

  // Проверка подписки на канал при появлении validatedUserId
  useEffect(() => {
    if (!validatedUserId) return;
    setChannelCheck({ loading: true, subscribed: false, message: '' });
    checkChannelSubscription(Number(validatedUserId))
      .then(res => {
        setChannelCheck({ loading: false, subscribed: res.subscribed, message: res.message });
      })
      .catch(e => {
        setChannelCheck({ loading: false, subscribed: false, message: e.message || 'Ошибка проверки подписки' });
      });
  }, [validatedUserId]);

  // Если не подписан — показываем экран с кнопкой перехода и повторной проверкой
  if (!channelCheck.loading && !channelCheck.subscribed) {
    return (
      <div className="subscription-required">
        <h2>Подпишитесь на наш канал</h2>
        <p>{channelCheck.message || 'Чтобы пользоваться приложением, подпишитесь на канал.'}</p>
        <a href={channelUrl} target="_blank" rel="noopener noreferrer" className="subscription-button">Перейти в канал</a>
        <button className="action-button" onClick={handleRecheck} disabled={checking}>{checking ? 'Проверяем...' : 'Проверить подписку'}</button>
      </div>
    );
  }

  // Используем комбинацию всех доступных проверок премиума
  // Приоритет: 1) Прямая проверка через bot-style API, 2) Стандартная проверка через subscription/status, 3) localStorage
  const hasPremium = 
    // Проверка через прямой API
    (premiumStatus?.has_premium === true) || 
    // Проверка через subscription API
    (status?.has_subscription === true && status?.is_active === true);
  
  // Выбираем дату окончания из всех доступных источников
  const endDate = 
    premiumStatus?.subscription_end_date || // Приоритет 1: из прямой проверки
    status?.subscription_end_date || // Приоритет 2: из стандартной проверки
    localEndDate; // Приоритет 3: из localStorage

  if (loading && !premiumStatus && !status) {
    return <div className="subscription-widget loading">Загрузка информации о подписке...</div>;
  }
  
  if (error && !hasPremium) {
    return (
      <div className="subscription-widget error">
        <p>Ошибка: {error}</p>
        <button onClick={() => {
          fetchSubscriptionStatus();
          fetchDirectPremiumStatus();
        }}>Повторить</button>
        <button onClick={handleCheckPremiumViaBot}>Проверить через бот</button>
      </div>
    );
  }

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
          <button 
            className="refresh-button"
            onClick={() => {
              fetchSubscriptionStatus();
              fetchDirectPremiumStatus();
            }}
          >
            Обновить статус
          </button>
        </div>
      ) : (
        <div className="free-block">
          <h4>Базовый доступ</h4>
          <p>Для Премиум доступа без ограничений оформите подписку.</p>
          <div className="buy-section">
            <button
              className="subscribe-button"
              onClick={handleSubscribe}
              disabled={isSubscribing}
            >
              {isSubscribing ? 'Обработка...' : 'Подписаться за ' + SUBSCRIPTION_PRICE + ' Stars'}
            </button>
            <button 
              className="check-button"
              onClick={handleCheckPremiumViaBot}
            >
              Проверить подписку через бот
            </button>
          </div>
        </div>
      )}
      <p className="user-id">User ID: {validatedUserId}</p>
    </div>
  );
};

export default SubscriptionWidget; 