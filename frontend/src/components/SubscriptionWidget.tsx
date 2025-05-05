import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus, generateInvoice, checkPremiumViaBot, getBotStylePremiumStatus } from '../api/subscription';

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
  // Состояние для отслеживания, когда пользователь проверил статус через бота
  const [checkedViaBot, setCheckedViaBot] = useState(false);
  // Состояние для отображения локально сохраненного статуса подписки
  const [localPremiumStatus, setLocalPremiumStatus] = useState<boolean | null>(null);
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
  
  // Проверяем localStorage при загрузке и после проверки через бота
  useEffect(() => {
    const checkLocalStorage = () => {
      const savedData = localStorage.getItem(PREMIUM_STATUS_KEY);
      if (savedData) {
        try {
          const parsedData = JSON.parse(savedData);
          console.log('[SubscriptionWidget] Найдены сохраненные данные о подписке:', parsedData);

          if (parsedData.userId === validatedUserId && parsedData.timestamp) {
            // Проверяем, что данные не устарели (24 часа)
            const now = new Date().getTime();
            const timestamp = parsedData.timestamp;
            const isValid = now - timestamp < 24 * 60 * 60 * 1000;
            
            if (isValid) {
              console.log('[SubscriptionWidget] Данные актуальны, используем их');
              setLocalPremiumStatus(parsedData.hasPremium);
              setLocalEndDate(parsedData.endDate);
              // Если мы только что проверили через бота и статус премиум, устанавливаем эти данные и в основной статус
              if (checkedViaBot && parsedData.hasPremium) {
                setStatus({
                  has_subscription: true,
                  analysis_count: 9999,
                  post_generation_count: 9999,
                  subscription_end_date: parsedData.endDate
                });
              }
            } else {
              console.log('[SubscriptionWidget] Данные устарели, удаляем');
              localStorage.removeItem(PREMIUM_STATUS_KEY);
              setLocalPremiumStatus(null);
              setLocalEndDate(null);
            }
          }
        } catch (e) {
          console.error('[SubscriptionWidget] Ошибка при разборе данных из localStorage:', e);
          localStorage.removeItem(PREMIUM_STATUS_KEY);
        }
      }
    };

    checkLocalStorage();
  }, [validatedUserId, checkedViaBot]);
  
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
    // Дополнительная проверка и получение userId из всех доступных источников
    let effectiveUserId = validatedUserId;
    
    if (!effectiveUserId) {
      console.log('[SubscriptionWidget] ValidatedUserId отсутствует, пробуем альтернативные источники...');
      
      // Попробуем получить из localStorage
      const storedUserId = localStorage.getItem('contenthelper_user_id');
      if (storedUserId) {
        console.log(`[SubscriptionWidget] Найден userId в localStorage: ${storedUserId}`);
        effectiveUserId = storedUserId;
      }
      
      // Попробуем получить из URL (если страница содержит user_id в параметрах)
      if (!effectiveUserId) {
        const urlParams = new URLSearchParams(window.location.search);
        const urlUserId = urlParams.get('user_id');
        if (urlUserId) {
          console.log(`[SubscriptionWidget] Найден userId в параметрах URL: ${urlUserId}`);
          effectiveUserId = urlUserId;
        }
      }
      
      // Попробуем получить из Telegram WebApp если доступен
      if (!effectiveUserId && window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        const webAppUserId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
        console.log(`[SubscriptionWidget] Найден userId в Telegram WebApp: ${webAppUserId}`);
        effectiveUserId = webAppUserId;
      }
    }

    if (!effectiveUserId) {
      console.error('[SubscriptionWidget] Попытка запроса статуса подписки без валидного userId после всех проверок');
      setError('ID пользователя не определен. Пожалуйста, перезапустите приложение.');
      return false;
    }
    
    setLoading(true);
    
    try {
      // Проверяем, есть ли локальные данные о премиум-статусе
      if (localPremiumStatus === true) {
        console.log('[SubscriptionWidget] Используем локальный премиум-статус');
        const result: SubscriptionStatus = {
          has_subscription: true,
          analysis_count: 9999,
          post_generation_count: 9999,
          subscription_end_date: localEndDate || undefined
        };
        setStatus(result);
        setError(null);
        setLoading(false);
        return true;
      }
      
      const result = await getUserSubscriptionStatus(effectiveUserId);
      console.log('[SubscriptionWidget] Получен статус подписки:', result);
      setStatus(result);
      setError(null);
      
      // Обновляем видимость MainButton в зависимости от статуса подписки
      if (window.Telegram?.WebApp?.MainButton) {
        if (result.has_subscription) {
          window.Telegram.WebApp.MainButton.hide();
        } else if (!isActive) {
          window.Telegram.WebApp.MainButton.show();
        }
      }
      
      setLoading(false);
      return true;
    } catch (err) {
      console.error('Ошибка при получении статуса подписки:', err);
      const errorMessage = err instanceof Error ? err.message : 'Неизвестная ошибка';
      
      setError(`Не удалось получить статус подписки: ${errorMessage}`);
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
  
  // Функция для обработки проверки через бота и сохранения результата
  const handleCheckPremiumViaBot = () => {
    // Устанавливаем флаг, что пользователь проверил статус через бота
    setCheckedViaBot(true);
    
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
      checkPremiumViaBot();
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
      console.log('[SubscriptionWidget] Сохранен премиум-статус в localStorage:', dataToSave);
      
      // Обновляем состояния компонента
      setLocalPremiumStatus(hasPremium);
      setLocalEndDate(endDate || null);
      
      // Обновляем основной статус
      if (hasPremium) {
        setStatus({
          has_subscription: true,
          analysis_count: 9999,
          post_generation_count: 9999,
          subscription_end_date: endDate
        });
      }
    }
  };
  
  // Обработчик события фокуса, чтобы проверить статус после возвращения из бота
  useEffect(() => {
    const handleVisibilityChange = () => {
      // Если страница становится видимой и был установлен флаг проверки через бота
      if (document.visibilityState === 'visible' && checkedViaBot) {
        console.log('[SubscriptionWidget] Страница снова активна после проверки через бота, обновляем статус');
        
        // Проверяем, был ли запрос на проверку через бота
        const checkInitiatedRaw = localStorage.getItem('premium_check_initiated');
        if (checkInitiatedRaw) {
          try {
            const checkInitiated = JSON.parse(checkInitiatedRaw);
            const now = new Date().getTime();
            
            // Если проверка была запущена не более 5 минут назад
            if (now - checkInitiated.timestamp < 5 * 60 * 1000) {
              console.log('[SubscriptionWidget] Обнаружена недавняя проверка через бота, запрашиваем актуальный статус');
              
              // Устанавливаем временно статус обновления
              setLoading(true);
              setError(null);
              
              // Делаем попытку получить статус напрямую через API в стиле бота
              if (validatedUserId) {
                getBotStylePremiumStatus(validatedUserId)
                  .then(botData => {
                    console.log('[SubscriptionWidget] Получен ответ от бот-стиль API после возвращения из бота:', botData);
                    
                    // Если получили премиум-статус, сохраняем его
                    if (botData.has_premium) {
                      savePremiumStatusFromBot(true, botData.subscription_end_date || undefined);
                    }
                    
                    // В любом случае обновляем обычный статус
                    fetchSubscriptionStatus();
                  })
                  .catch(error => {
                    console.error('[SubscriptionWidget] Ошибка при получении статуса через бот-стиль API после возвращения из бота:', error);
                    // Пробуем обычный метод
                    fetchSubscriptionStatus();
                  });
                
                // Очищаем флаг инициированной проверки
                localStorage.removeItem('premium_check_initiated');
              }
            }
          } catch (e) {
            console.error('[SubscriptionWidget] Ошибка при разборе данных о проверке через бота:', e);
            localStorage.removeItem('premium_check_initiated');
          }
        }
      }
    };
    
    // Добавляем обработчик события изменения видимости страницы
    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    // Очистка при размонтировании
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [checkedViaBot, validatedUserId]);
  
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
  
  // Отображаем локальный премиум-статус, если он доступен и мы проверяли через бота
  if (checkedViaBot && localPremiumStatus === true) {
    return (
      <div className="subscription-widget">
        <h3>Статус подписки</h3>
        <div className="subscription-details">
          <div className="premium-status">
            <p className="status-label">Премиум (подтверждено ботом)</p>
            {localEndDate && (
              <p className="end-date">
                Действует до: {formatDate(localEndDate)}
              </p>
            )}
            <p className="limits">
              Доступно анализов: Неограниченно
              <br />
              Доступно генераций постов: Неограниченно
            </p>
          </div>
        </div>
        
        {/* Секция "Прямая проверка" */}
        <div className="direct-check-section">
          <h4>Статус подписки (Прямая проверка)</h4>
          <p className="direct-check-status">Прямая проверка: Статус Premium</p>
          <p className="user-id">User ID: {validatedUserId}</p>
        </div>
        
        <div className="bot-check-section">
          <button 
            className="check-via-bot-button"
            onClick={handleCheckPremiumViaBot}
          >
            Проверить через бота
          </button>
        </div>
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
          </div>
        </div>
      ) : (
        <div className="subscription-details">
          {status?.has_subscription ? (
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
              </div>
            </div>
          )}
        </div>
      )}

      {/* Секция "Прямая проверка" */}
      <div className="direct-check-section">
        <h4>Статус подписки (Прямая проверка)</h4>
        <p className="direct-check-status">
          Прямая проверка: Статус {localPremiumStatus === true ? 'Premium' : 'Free'}
        </p>
        <p className="user-id">User ID: {validatedUserId}</p>
      </div>

      {/* Секция для ручного ввода результата проверки через бота (для тестирования) */}
      <div className="manual-set-section">
        <button 
          className="manual-set-button"
          onClick={() => savePremiumStatusFromBot(true, '2025-06-03T12:10:56.203118+00:00')}
        >
          Установить Premium (тест)
        </button>
        <button 
          className="manual-set-button"
          onClick={() => savePremiumStatusFromBot(false)}
        >
          Установить Free (тест)
        </button>
      </div>

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