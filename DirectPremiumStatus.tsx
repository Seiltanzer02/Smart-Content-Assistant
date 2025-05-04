import React, { useState, useEffect, useRef } from 'react';
import './DirectPremiumStatus.css';
import { getPremiumStatus, PremiumStatus } from '../api/subscription';

interface DirectPremiumStatusProps {
  userId: string | null;
  showDebug?: boolean;
}

// API_URL для относительных путей
const API_URL = '';

/**
 * Компонент для прямого определения премиум-статуса пользователя
 * Использует выделенный эндпоинт API-V2 и надежное отображение статуса
 */
const DirectPremiumStatus: React.FC<DirectPremiumStatusProps> = ({ userId, showDebug = false }) => {
  const [hasPremium, setHasPremium] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [endDate, setEndDate] = useState<string | null>(null);
  const [responseData, setResponseData] = useState<PremiumStatus | null>(null);
  
  // Сохраняем userId в ref для предотвращения лишних перерисовок
  const userIdRef = useRef<string | null>(null);
  
  // Таймер автообновления
  const updateTimerRef = useRef<number | null>(null);

  // Получаем и сохраняем userId из разных источников
  useEffect(() => {
    console.log('[DirectPremiumStatus] Инициализация компонента');
    
    const validateUserId = () => {
      // Приоритет 1: userId из props
      if (userId) {
        console.log(`[DirectPremiumStatus] Используем userId из props: ${userId}`);
        userIdRef.current = userId;
        return;
      }
      
      // Приоритет 2: userId из Telegram WebApp
      if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        const telegramUserId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
        console.log(`[DirectPremiumStatus] Используем userId из Telegram WebApp: ${telegramUserId}`);
        userIdRef.current = telegramUserId;
        return;
      }
      
      // Приоритет 3: userId из URL-параметров
      try {
        // Извлекаем userId из параметров URL
        const urlParams = new URLSearchParams(window.location.search);
        const urlUserId = urlParams.get('user_id');
        
        if (urlUserId) {
          console.log(`[DirectPremiumStatus] Получен userId из URL: ${urlUserId}`);
          userIdRef.current = urlUserId;
          return;
        }
        
        // Извлекаем userId из hash данных Telegram WebApp
        const hash = window.location.hash;
        if (hash && hash.includes("user")) {
          const decodedHash = decodeURIComponent(hash);
          const userMatch = decodedHash.match(/"id":(\d+)/);
          if (userMatch && userMatch[1]) {
            console.log(`[DirectPremiumStatus] Получен userId из hash Telegram WebApp: ${userMatch[1]}`);
            userIdRef.current = userMatch[1];
            return;
          }
        }
      } catch (e) {
        console.error('[DirectPremiumStatus] Ошибка при извлечении userId из URL:', e);
      }
      
      // Если userId не определен, логируем ошибку
      console.error('[DirectPremiumStatus] Не удалось определить userId');
      setError('ID пользователя не определен');
    };
    
    validateUserId();
    
    // Очистка таймера при размонтировании
    return () => {
      if (updateTimerRef.current !== null) {
        clearInterval(updateTimerRef.current);
        updateTimerRef.current = null;
      }
    };
  }, [userId]);

  // Добавляем слушатель событий для получения userId и статуса из инъекции
  useEffect(() => {
    // Функция-обработчик события инъекции userId
    const handleUserIdInjection = (event: CustomEvent) => {
      const injectedUserId = event.detail?.userId;
      if (injectedUserId) {
        console.log(`[DirectPremiumStatus] Получен инъектированный userId: ${injectedUserId}`);
        userIdRef.current = injectedUserId;
        
        // Перезапускаем проверку статуса
        checkPremiumStatus();
      }
    };
    
    // Функция-обработчик загруженного статуса премиума
    const handlePremiumStatus = (event: CustomEvent) => {
      const statusData = event.detail?.premiumStatus;
      const injectedUserId = event.detail?.userId;
      
      if (statusData && injectedUserId) {
        console.log(`[DirectPremiumStatus] Получен статус премиума из инъекции:`, statusData);
        
        // Обновляем состояние компонента
        setHasPremium(statusData.has_premium);
        setEndDate(statusData.subscription_end_date || null);
        setResponseData(statusData);
        setError(statusData.error || null);
        setLoading(false);
        
        // Обновляем userId, если он еще не установлен
        if (!userIdRef.current) {
          userIdRef.current = injectedUserId;
        }
      }
    };
    
    // Объявление глобальной переменной для TypeScript
    interface WindowWithInjection extends Window {
      INJECTED_USER_ID?: string;
    }
    
    // Проверяем, есть ли userId уже в window
    const windowWithInjection = window as WindowWithInjection;
    if (windowWithInjection.INJECTED_USER_ID && !userIdRef.current) {
      console.log(`[DirectPremiumStatus] Найден INJECTED_USER_ID: ${windowWithInjection.INJECTED_USER_ID}`);
      userIdRef.current = windowWithInjection.INJECTED_USER_ID;
      checkPremiumStatus();
    }
    
    // Проверяем, есть ли userId в localStorage
    try {
      const storedUserId = localStorage.getItem('contenthelper_user_id');
      if (storedUserId && !userIdRef.current) {
        console.log(`[DirectPremiumStatus] Найден userId в localStorage: ${storedUserId}`);
        userIdRef.current = storedUserId;
        checkPremiumStatus();
      }
    } catch (e) {
      console.warn('[DirectPremiumStatus] Ошибка чтения из localStorage:', e);
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

  // Функция для получения премиум-статуса
  const checkPremiumStatus = async () => {
    if (!userIdRef.current) {
      setError('ID пользователя не определен');
      setLoading(false);
      return;
    }
    
    try {
      setLoading(true);
      
      console.log(`[DirectPremiumStatus] Запрос статуса для ID: ${userIdRef.current}`);
      
      // Используем новый API для проверки премиума с защитой от кэширования
      const premiumData = await getPremiumStatus(userIdRef.current, `_nocache=${Date.now()}`);
      
      console.log(`[DirectPremiumStatus] Получен ответ:`, premiumData);
      
      // Обновляем состояние компонента
      setHasPremium(premiumData.has_premium);
      setEndDate(premiumData.subscription_end_date || null);
      setResponseData(premiumData);
      setError(premiumData.error || null);
      
    } catch (e) {
      console.error(`[DirectPremiumStatus] Ошибка запроса:`, e);
      setError(`Ошибка запроса: ${e instanceof Error ? e.message : 'Неизвестная ошибка'}`);
    } finally {
      setLoading(false);
    }
  };

  // Проверка статуса при монтировании компонента и при изменении userId
  useEffect(() => {
    if (userIdRef.current) {
      checkPremiumStatus();
      
      // Устанавливаем таймер для регулярного обновления
      const updateInterval = 30000; // 30 секунд
      updateTimerRef.current = window.setInterval(checkPremiumStatus, updateInterval);
    }
    
    return () => {
      if (updateTimerRef.current !== null) {
        clearInterval(updateTimerRef.current);
        updateTimerRef.current = null;
      }
    };
  }, []);

  // Функция для форматирования даты с часовым поясом
  const formatDate = (isoDateString: string): string => {
    try {
      const date = new Date(isoDateString);
      
      // Форматируем дату с временем и часовым поясом
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
      return 'Неизвестная дата';
    }
  };

  // Рендеринг компонента
  return (
    <div className="direct-premium-status">
      {loading ? (
        <div className="direct-status loading">Проверка статуса...</div>
      ) : error ? (
        <div className="direct-status error">
          {error}
          <button 
            className="refresh-button"
            onClick={checkPremiumStatus}
          >
            Проверить снова
          </button>
          
          {/* Добавляем кнопку для диагностики */}
          <button 
            className="debug-button"
            onClick={() => {
              if (!userIdRef.current) return;
              
              // Открываем диагностический эндпоинт в новом окне
              window.open(`/api/subscription/debug/${userIdRef.current}?create_test=true`, '_blank');
            }}
          >
            Диагностика и создание тестовой подписки
          </button>
        </div>
      ) : (
        <div className={`direct-status ${hasPremium ? 'premium' : 'free'}`}>
          {hasPremium ? (
            <>
              <div className="premium-badge">
                <span className="premium-icon">⭐</span>
                <span>ПРЕМИУМ</span>
              </div>
              {endDate && (
                <div className="expiry-date">
                  до {formatDate(endDate)}
                </div>
              )}
            </>
          ) : (
            <div className="free-badge">Бесплатный доступ</div>
          )}
          
          {showDebug && responseData && (
            <div className="debug-data">
              <details>
                <summary>Отладочная информация</summary>
                <pre>{JSON.stringify(responseData, null, 2)}</pre>
                <p>
                  ID: {userIdRef.current || 'не определен'}<br/>
                  Telegram WebApp: {window.Telegram?.WebApp ? 'Доступен' : 'Не доступен'}<br/>
                  {window.Telegram?.WebApp?.initDataUnsafe?.user?.id && 
                    `Telegram ID: ${window.Telegram.WebApp.initDataUnsafe.user.id}`
                  }
                </p>
              </details>
              <button onClick={checkPremiumStatus} className="refresh-button">
                Обновить статус
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DirectPremiumStatus; 