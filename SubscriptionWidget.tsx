import React, { useState, useEffect, useRef } from 'react';
import '../styles/SubscriptionWidget.css';
import { 
  getUserSubscriptionStatus, 
  SubscriptionStatus, 
  getSubscriptionStatusV2, 
  getPremiumStatus, 
  generateInvoice
} from './subscription';

// Определяем недостающие интерфейсы и функции локально
interface PremiumStatus {
  has_premium: boolean;
  user_id: string;
  error?: string | null;
  subscription_end_date?: string | null;
  analysis_count?: number;
  post_generation_count?: number;
}

// Добавляем отсутствующие функции для использования в компоненте
const getBotStylePremiumStatus = async (userId: string | null): Promise<PremiumStatus> => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }

  console.log(`[API] Запрос премиум-статуса через бот-стиль API для пользователя ID: ${userId}`);
  
  try {
    // Добавляем случайный параметр для предотвращения кэширования
    const nocache = `_nocache=${new Date().getTime()}`;
    
    // Используем прямой URL, который работает как в боте
    const response = await fetch(`/bot-style-premium-check/${userId}?${nocache}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache'
      },
      cache: 'no-store'
    });

    if (!response.ok) {
      throw new Error(`Ошибка API: ${response.status}`);
    }
    
    const data = await response.json();
    console.log(`[API] Получен ответ из бот-стиль API:`, data);
    
    // Приводим ответ к формату PremiumStatus
    return {
      has_premium: data.has_premium,
      user_id: userId,
      error: data.error || null,
      subscription_end_date: data.subscription_end_date || null,
      analysis_count: data.analysis_count,
      post_generation_count: data.post_generation_count
    };
  } catch (error) {
    console.error('[API] Ошибка при получении премиум-статуса через бот-стиль API:', error);
    
    // Возвращаем базовые данные при ошибке
    return {
      has_premium: false,
      user_id: userId,
      error: error instanceof Error ? error.message : 'Неизвестная ошибка'
    };
  }
};

const getDirectPremiumStatus = async (userId: string | null): Promise<PremiumStatus> => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }

  console.log(`[API] Запрос прямого премиум-статуса для пользователя ID: ${userId}`);
  
  try {
    // Добавляем случайный параметр для предотвращения кэширования
    const nocache = `_nocache=${new Date().getTime()}`;
    
    // Используем URL, который гарантированно не будет перехвачен SPA роутером
    const response = await fetch(`/direct_premium_check?user_id=${userId}&${nocache}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache'
      },
      cache: 'no-store'
    });

    if (!response.ok) {
      throw new Error(`Ошибка API: ${response.status}`);
    }
    
    const data = await response.json();
    console.log(`[API] Получен прямой ответ о премиуме:`, data);
    
    // Если подписка не активна, очищаем все данные о премиуме из localStorage
    if (!data.has_premium) {
      console.log('[API] Подписка неактивна, очищаем localStorage от премиум-данных');
      localStorage.removeItem('premium_status');
      localStorage.removeItem('premium_expiry');
      localStorage.removeItem('subscription_data');
      // Очищаем все ключи, содержащие "premium" или "subscription"
      Object.keys(localStorage).forEach(key => {
        if (key.includes('premium') || key.includes('subscription')) {
          localStorage.removeItem(key);
        }
      });
    }
    
    return data;
  } catch (error) {
    console.error('[API] Ошибка при получении прямого премиум-статуса:', error);
    
    // Возвращаем базовые данные при ошибке
    return {
      has_premium: false,
      user_id: userId,
      error: error instanceof Error ? error.message : 'Неизвестная ошибка'
    };
  }
};

const checkPremiumViaBot = (botName: string = 'SmartContentHelperBot'): void => {
  try {
    // Формируем URL для открытия чата с ботом и отправки команды
    const url = `https://t.me/${botName}?start=check_premium`;
    
    console.log(`[API] Открываем чат с ботом для проверки премиума: ${url}`);
    
    // Если мы внутри Telegram WebApp, используем специальный метод
    if (window.Telegram?.WebApp?.openTelegramLink) {
      window.Telegram.WebApp.openTelegramLink(url);
    } else {
      // Обычное открытие в новой вкладке
      window.open(url, '_blank');
    }
  } catch (e) {
    console.error('[API] Ошибка при открытии чата с ботом:', e);
  }
};

// Расширение интерфейса Window для поддержки Telegram WebApp
declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initDataUnsafe?: {
          user?: {
            id?: number;
          };
        };
        ready?: () => void;
        initData?: string;
        openTelegramLink?: (url: string) => void;
      };
    };
    INJECTED_USER_ID?: string;
  }
}

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
  const [showBotCheckButton, setShowBotCheckButton] = useState(false);
  
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
      // Синхронно проверяем наличие userId
      // Проверяем все возможные источники
      if (!userIdRef.current) {
        // Проверяем window.INJECTED_USER_ID
        if (window.INJECTED_USER_ID) {
          console.log(`[SubscriptionWidget] Используем INJECTED_USER_ID: ${window.INJECTED_USER_ID}`);
          userIdRef.current = window.INJECTED_USER_ID;
        } 
        // Проверяем localStorage
        else if (localStorage.getItem('contenthelper_user_id')) {
          userIdRef.current = localStorage.getItem('contenthelper_user_id');
          console.log(`[SubscriptionWidget] Используем userId из localStorage: ${userIdRef.current}`);
        }
        // Проверяем Telegram WebApp
        else if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
          userIdRef.current = String(window.Telegram.WebApp.initDataUnsafe.user.id);
          console.log(`[SubscriptionWidget] Используем userId из Telegram WebApp: ${userIdRef.current}`);
        }
        // Извлекаем userId из URL
        else {
          try {
            const urlParams = new URLSearchParams(window.location.search);
            const urlUserId = urlParams.get('user_id');
            if (urlUserId) {
              userIdRef.current = urlUserId;
              console.log(`[SubscriptionWidget] Используем userId из URL: ${userIdRef.current}`);
            }
          } catch (e) {
            console.error('[SubscriptionWidget] Ошибка при извлечении userId из URL:', e);
          }
        }
      }
      
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
        
        // Если подписка не активна, очищаем все данные о премиуме из localStorage
        if (!subscriptionData.has_subscription) {
          console.log('[SubscriptionWidget] Подписка неактивна, очищаем localStorage от премиум-данных');
          localStorage.removeItem('premium_status');
          localStorage.removeItem('premium_expiry');
          localStorage.removeItem('subscription_data');
          // Очищаем все ключи, содержащие "premium" или "subscription"
          Object.keys(localStorage).forEach(key => {
            if (key.includes('premium') || key.includes('subscription')) {
              localStorage.removeItem(key);
            }
          });
        }
        
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
    
    // Вызываем функцию сразу при монтировании компонента
    fetchSubscriptionStatus();
    
    // Устанавливаем интервал для регулярного обновления статуса
    const updateInterval = 30000; // 30 секунд
    updateTimerRef.current = window.setInterval(() => {
      console.log('[SubscriptionWidget] Регулярное обновление статуса подписки...');
      fetchSubscriptionStatus();
    }, updateInterval);
    
    // Очистка интервала при размонтировании компонента
    return () => {
      if (updateTimerRef.current !== null) {
        clearInterval(updateTimerRef.current);
        updateTimerRef.current = null;
      }
    };
  }, []);
  
  // Запрос статуса подписки
  const checkPremiumDirectly = async () => {
    if (!userIdRef.current) {
      console.error('Попытка запроса статуса подписки без валидного userId');
      setError('ID пользователя не определен');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    console.log(`Запрос статуса подписки для ID: ${userIdRef.current}`);
    
    try {
      // Используем каскадную проверку через несколько методов
      // НОВЫЙ ПРИОРИТЕТНЫЙ МЕТОД: пробуем бот-стиль метод для прямого доступа к БД
      try {
        console.log('[SubscriptionWidget] Пробуем бот-стиль метод проверки...');
        const botStyleStatus = await getBotStylePremiumStatus(userIdRef.current);
        
        if (botStyleStatus) {
          console.log('[SubscriptionWidget] Получен статус через бот-стиль метод:', botStyleStatus);
          setStatus({
            has_subscription: botStyleStatus.has_premium,
            analysis_count: botStyleStatus.analysis_count || 3,
            post_generation_count: botStyleStatus.post_generation_count || 1,
            subscription_end_date: botStyleStatus.subscription_end_date
          });
          setError(null);
          setLoading(false);
          return;
        }
      } catch (botStyleError) {
        console.error('[SubscriptionWidget] Ошибка бот-стиль метода:', botStyleError);
      }
      
      // Затем пробуем прямой метод
      try {
        console.log('[SubscriptionWidget] Пробуем прямой метод проверки...');
        const directStatus = await getDirectPremiumStatus(userIdRef.current);
        
        if (directStatus) {
          console.log('[SubscriptionWidget] Получен статус через прямой метод:', directStatus);
          setStatus({
            has_subscription: directStatus.has_premium,
            analysis_count: directStatus.analysis_count || 3,
            post_generation_count: directStatus.post_generation_count || 1,
            subscription_end_date: directStatus.subscription_end_date
          });
          setError(null);
          setLoading(false);
          return;
        }
      } catch (directError) {
        console.error('[SubscriptionWidget] Ошибка прямого метода:', directError);
      }
      
      // Затем пробуем RAW метод
      try {
        console.log('[SubscriptionWidget] Пробуем RAW метод проверки...');
        const rawStatus = await getRawPremiumStatus(userIdRef.current, `_nocache=${Date.now()}`);
        
        if (rawStatus) {
          console.log('[SubscriptionWidget] Получен RAW статус подписки:', rawStatus);
          setStatus({
            has_subscription: rawStatus.has_premium,
            analysis_count: rawStatus.analysis_count || 3,
            post_generation_count: rawStatus.post_generation_count || 1,
            subscription_end_date: rawStatus.subscription_end_date
          });
          setError(null);
          setLoading(false);
          return;
        }
      } catch (rawError) {
        console.error('[SubscriptionWidget] Ошибка RAW метода:', rawError);
      }
      
      // Если предыдущие методы не сработали, используем универсальный метод
      try {
        console.log('[SubscriptionWidget] Пробуем универсальный метод проверки...');
        const status = await getUserSubscriptionStatus(userIdRef.current);
        console.log('[SubscriptionWidget] Получен статус через универсальный метод:', status);
        setStatus(status);
      } catch (apiError) {
        console.error('[SubscriptionWidget] Ошибка универсального метода:', apiError);
        throw apiError;
      }
    } catch (err) {
      console.error('[SubscriptionWidget] Все методы проверки не сработали:', err);
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Не удалось получить информацию о подписке');
      }
      
      // Fallback для пользователя: открыть чат с ботом
      console.log('[SubscriptionWidget] Предлагаем проверку через бота...');
      setShowBotCheckButton(true);
    } finally {
      setLoading(false);
    }
  };
  
  // Запуск процесса подписки
  const handleSubscribe = () => {
    setIsSubscribing(true);
    setShowPaymentInfo(true);
  };
  
  // Добавляем слушатель событий для получения userId из инъекции
  useEffect(() => {
    // Функция-обработчик события инъекции userId
    const handleUserIdInjection = (event: CustomEvent) => {
      const injectedUserId = event.detail?.userId;
      if (injectedUserId) {
        console.log(`[SubscriptionWidget] Получен инъектированный userId: ${injectedUserId}`);
        userIdRef.current = injectedUserId;
        
        // Перезапускаем проверку подписки
        checkPremiumDirectly();
      }
    };
    
    // Функция-обработчик загруженного статуса премиума
    const handlePremiumStatus = (event: CustomEvent) => {
      const statusData = event.detail?.premiumStatus;
      const injectedUserId = event.detail?.userId;
      
      if (statusData && injectedUserId) {
        console.log(`[SubscriptionWidget] Получен статус премиума из инъекции:`, statusData);
        
        // Преобразуем формат премиум-статуса в формат подписки
        setStatus({
          has_subscription: statusData.has_premium,
          analysis_count: statusData.analysis_count || 1,
          post_generation_count: statusData.post_generation_count || 1,
          subscription_end_date: statusData.subscription_end_date
        });
        
        setLoading(false);
        setError(null);
        
        // Обновляем userId, если он еще не установлен
        if (!userIdRef.current) {
          userIdRef.current = injectedUserId;
        }
      }
    };
    
    // Проверяем, есть ли userId уже в window
    if (window.INJECTED_USER_ID && !userIdRef.current) {
      console.log(`[SubscriptionWidget] Найден INJECTED_USER_ID: ${window.INJECTED_USER_ID}`);
      userIdRef.current = window.INJECTED_USER_ID;
      checkPremiumDirectly();
    }
    
    // Проверяем, есть ли userId в localStorage
    try {
      const storedUserId = localStorage.getItem('contenthelper_user_id');
      if (storedUserId && !userIdRef.current) {
        console.log(`[SubscriptionWidget] Найден userId в localStorage: ${storedUserId}`);
        userIdRef.current = storedUserId;
        checkPremiumDirectly();
      }
    } catch (e) {
      console.warn('[SubscriptionWidget] Ошибка чтения из localStorage:', e);
    }
    
    // Регистрируем слушателей событий
    document.addEventListener('userIdInjected', handleUserIdInjection as EventListener);
    document.addEventListener('premiumStatusLoaded', handlePremiumStatus as EventListener);
    
    // Очистка при размонтировании
    return () => {
      document.removeEventListener('userIdInjected', handleUserIdInjection as EventListener);
      document.removeEventListener('premiumStatusLoaded', handlePremiumStatus as EventListener);
    };
  }, []);
  
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
          
          {/* Добавляем кнопку диагностики */}
          {userIdRef.current && (
            <button 
              className="debug-button"
              onClick={() => {
                // Открываем диагностическую страницу в новом окне
                window.open(`/api/subscription/debug/${userIdRef.current}?create_test=true`, '_blank');
              }}
            >
              Диагностика и создание тестовой подписки
            </button>
          )}
          
          {/* Форма для ручного ввода userId если он не определен */}
          {!userIdRef.current && (
            <div className="manual-userid-form">
              <input 
                type="text" 
                placeholder="Введите Telegram ID пользователя" 
                id="manual-userid-input"
              />
              <button 
                onClick={() => {
                  const input = document.getElementById('manual-userid-input') as HTMLInputElement;
                  if (input && input.value) {
                    userIdRef.current = input.value;
                    console.log(`[SubscriptionWidget] Установлен userId вручную: ${userIdRef.current}`);
                    
                    // Сохраняем в localStorage
                    try {
                      localStorage.setItem('contenthelper_user_id', userIdRef.current);
                    } catch (e) {
                      console.error('[SubscriptionWidget] Ошибка сохранения в localStorage:', e);
                    }
                    
                    // Перезапускаем проверку
                    checkPremiumDirectly();
                  }
                }}
              >
                Установить ID и проверить
              </button>
            </div>
          )}
          
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