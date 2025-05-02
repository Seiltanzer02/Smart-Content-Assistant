import React, { useState, useEffect, useRef, SetStateAction, Dispatch, useMemo } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus, generateInvoice } from '../api/subscription';
import axios from 'axios';

// API_URL для относительных путей
const API_URL = '';

const SubscriptionWidget: React.FC<{
  userId: string | null,
  subscriptionStatus: SubscriptionStatus | null,
  onSubscriptionUpdate: () => void,
  isActive?: boolean
}> = ({ userId, subscriptionStatus, onSubscriptionUpdate, isActive }) => {
  console.log('[SubscriptionWidget] 🔄 Монтирование компонента с пропсами:', 
    {userId, subscriptionStatus, isActive, 
     hasSubscription: subscriptionStatus?.has_subscription,
     isActiveFromStatus: subscriptionStatus?.is_active,
     endDate: subscriptionStatus?.subscription_end_date});
  
  const [error, setError] = useState<string | null>(null);
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  const SUBSCRIPTION_PRICE = 1; // временно 1 Star для теста
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshLog, setRefreshLog] = useState<string[]>([]);
  const [lastUpdateTime, setLastUpdateTime] = useState<string>(
    new Date().toLocaleTimeString()
  );
  
  // Возвращаем refs
  const pollIntervalRef = useRef<number | null>(null);
  const pollTimeoutRef = useRef<number | null>(null);
  const mountedRef = useRef(true); // Для проверки монтирования/размонтирования

  // Проверка end_date для отображения
  const isEndDateValid = useMemo(() => {
    if (subscriptionStatus?.subscription_end_date) {
      try {
        const endDate = new Date(subscriptionStatus.subscription_end_date);
        const now = new Date();
        // Проверка валидности даты и что она в будущем
        return !isNaN(endDate.getTime()) && endDate > now;
      } catch (e) {
        console.error('[SubscriptionWidget] ⚠️ Ошибка при проверке end_date:', e);
        return false;
      }
    }
    return false;
  }, [subscriptionStatus?.subscription_end_date]);

  // Вычисляем итоговый статус активности
  const calculatedIsActive = useMemo(() => {
    // Приоритизируем наши собственные проверки над данными API
    if (isEndDateValid) {
      console.log('[SubscriptionWidget] ✅ Подписка активна по end_date');
      return true;
    }
    
    // Затем проверяем is_active из API
    if (subscriptionStatus?.is_active === true) {
      console.log('[SubscriptionWidget] ✅ Подписка активна по is_active');
      return true;
    }
    
    // Затем has_subscription из API
    if (subscriptionStatus?.has_subscription === true) {
      console.log('[SubscriptionWidget] ✅ Подписка активна по has_subscription');
      return true;
    }
    
    console.log('[SubscriptionWidget] ❌ Подписка НЕ активна по всем проверкам');
    return false;
  }, [subscriptionStatus, isEndDateValid]);

  // При изменении статуса добавляем запись в лог
  useEffect(() => {
    const timestamp = new Date().toLocaleTimeString();
    setLastUpdateTime(timestamp);
    
    const statusLog = `[${timestamp}] Статус: has_subscription=${subscriptionStatus?.has_subscription}, is_active=${subscriptionStatus?.is_active}, end_date=${subscriptionStatus?.subscription_end_date?.substring(0, 10) || 'null'}`;
    setRefreshLog(prev => [statusLog, ...prev.slice(0, 4)]); // Храним последние 5 обновлений
    
    console.log(`[SubscriptionWidget] 🔄 Обновление статуса:`, 
      {hasSubscription: subscriptionStatus?.has_subscription,
       isActive: subscriptionStatus?.is_active,
       endDate: subscriptionStatus?.subscription_end_date,
       calculatedIsActive});
  }, [subscriptionStatus, calculatedIsActive]);

  // Возвращаем функцию stopPolling
  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
      console.log('[SubscriptionWidget] Polling stopped by stopPolling function');
    }
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
      console.log('[SubscriptionWidget] Polling timeout cleared');
    }
  };
  
  // Функция для обновления статуса подписки с индикацией загрузки
  const refreshSubscriptionStatus = async () => {
    if (!userId || isRefreshing) return;
    
    try {
      console.log('[SubscriptionWidget] 🔄 Запрос принудительного обновления статуса...');
      setIsRefreshing(true);
      
      await onSubscriptionUpdate();
      
      const successTimestamp = new Date().toLocaleTimeString();
      setRefreshLog(prev => [`[${successTimestamp}] ✅ Статус успешно обновлен`, ...prev.slice(0, 4)]);
      console.log('[SubscriptionWidget] ✅ Статус успешно обновлен');
    } catch (err) {
      console.error('[SubscriptionWidget] ❌ Ошибка при обновлении статуса:', err);
      setError('Не удалось обновить статус подписки. Пожалуйста, попробуйте позже.');
      
      const errorTimestamp = new Date().toLocaleTimeString();
      setRefreshLog(prev => [`[${errorTimestamp}] ❌ Ошибка обновления: ${err}`, ...prev.slice(0, 4)]);
    } finally {
      if (mountedRef.current) {
        setIsRefreshing(false);
      }
    }
  };

  // Принудительно обновляем статус подписки при монтировании
  useEffect(() => {
    console.log('[SubscriptionWidget] Инициализация компонента, обновляем статус подписки');
    refreshSubscriptionStatus();
    
    // Устанавливаем интервал для регулярного опроса статуса подписки
    const statusInterval = setInterval(() => {
      if (mountedRef.current) {
        console.log('[SubscriptionWidget] Плановая проверка статуса подписки (интервал)');
        onSubscriptionUpdate();
      }
    }, 30000); // Проверка каждые 30 секунд
    
    return () => {
      mountedRef.current = false;
      clearInterval(statusInterval);
      console.log('[SubscriptionWidget] Компонент размонтирован, очищаем интервалы');
    };
  }, [userId]);

  const handleSubscribeViaMainButton = () => {
    console.log('[SubscriptionWidget] Нажатие на MainButton для подписки');
    if (window.Telegram?.WebApp?.showConfirm) {
      window.Telegram.WebApp.showConfirm(
        'Вы хотите оформить подписку за ' + SUBSCRIPTION_PRICE + ' Stars?',
        (confirmed) => {
          console.log('[SubscriptionWidget] showConfirm ответ:', confirmed);
          if (confirmed) {
            handleSubscribe();
          }
        }
      );
    } else {
      handleSubscribe();
    }
  };

  const handleInvoiceGeneration = async (userId: string) => {
    console.log('[SubscriptionWidget] handleInvoiceGeneration вызван для userId:', userId);
    if (!window.Telegram?.WebApp) {
      console.error('[SubscriptionWidget] Telegram WebApp не инициализирован!');
      setError('Не удалось инициализировать Telegram WebApp для оплаты.');
      setIsSubscribing(false);
      return;
    }

    try {
      setIsSubscribing(true);
      const response = await fetch('/generate-stars-invoice-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, amount: 1 })
      });
      const data = await response.json();
      console.log('[SubscriptionWidget] Ответ от /generate-stars-invoice-link:', data);
      if (data.success && data.invoice_link) {
        if (typeof window.Telegram.WebApp?.openInvoice === 'function') {
          window.Telegram.WebApp.openInvoice(data.invoice_link, async (status) => {
            setIsSubscribing(false);
            const timestamp = new Date().toISOString();
            console.log(`[SubscriptionWidget] [${timestamp}] 💰 openInvoice callback статус: ${status}`);
            
            if (status === 'paid') {
              console.log(`[SubscriptionWidget] [${timestamp}] ✅ Payment status: paid. Обработка успешной оплаты...`);
              
              // --- Добавляем усиленный опрос статуса подписки ---
              // Функция для одного запроса с детальным логированием
              const checkSubscriptionStatus = async () => {
                const checkTimestamp = new Date().toISOString();
                console.log(`[SubscriptionWidget] [${checkTimestamp}] 🔄 Запрашиваем обновление статуса подписки...`);
                
                try {
                  // Вызываем обновление через родительский компонент
                  onSubscriptionUpdate();
                  console.log(`[SubscriptionWidget] [${checkTimestamp}] ✓ Запрос на обновление статуса отправлен`);
                  return true;
                } catch (err) {
                  console.error(`[SubscriptionWidget] [${checkTimestamp}] ❌ Ошибка при запросе обновления:`, err);
                  return false;
                }
              };

              // Запускаем первый запрос сразу после оплаты
              console.log(`[SubscriptionWidget] [${timestamp}] 🚀 Запускаем немедленное обновление статуса`);
              await checkSubscriptionStatus();
              
              // Запускаем серию дополнительных запросов с интервалами
              const intervals = [1000, 2000, 3000, 5000, 8000]; // интервалы в мс
              
              for (let i = 0; i < intervals.length; i++) {
                console.log(`[SubscriptionWidget] [${new Date().toISOString()}] ⏰ Планируем запрос #${i+1} через ${intervals[i]/1000} сек...`);
                
                // Ждем указанный интервал
                await new Promise(resolve => setTimeout(resolve, intervals[i]));
                
                // Выполняем запрос
                console.log(`[SubscriptionWidget] [${new Date().toISOString()}] 🔄 Выполняем запрос #${i+1}...`);
                await checkSubscriptionStatus();
              }
              
              console.log(`[SubscriptionWidget] [${new Date().toISOString()}] 🏁 Серия запросов статуса завершена`);
              // --- Конец усиленного опроса ---
              
              if (window?.Telegram?.WebApp?.showPopup) {
                window.Telegram.WebApp.showPopup({
                  title: 'Успешная оплата',
                  message: 'Подписка активирована! Обновляем статус...',
                  buttons: [{ type: 'ok' }]
                });
              }
              stopPolling();
              console.log(`[SubscriptionWidget] [${new Date().toISOString()}] 🔔 Оповещаем пользователя об успешной активации подписки`);
            } else {
              console.log(`[SubscriptionWidget] [${timestamp}] ❌ Payment status: ${status}. Оплата не произведена или отменена.`);
            }
          });
        } else {
          setError('Оплата через Stars недоступна в этом окружении.');
          setIsSubscribing(false);
          console.error('[SubscriptionWidget] openInvoice не поддерживается');
        }
      } else {
        setError(data.error || 'Ошибка генерации инвойса');
        setIsSubscribing(false);
        console.error('[SubscriptionWidget] Ошибка генерации инвойса:', data.error);
      }
    } catch (error) {
      setError(`Ошибка: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`);
      setIsSubscribing(false);
      console.error('[SubscriptionWidget] Ошибка в handleInvoiceGeneration:', error);
    }
  };

  const handleSubscribe = async () => {
    console.log('[SubscriptionWidget] handleSubscribe вызван. userId:', userId);
    if (!userId) {
      setError('Не удалось получить корректный ID пользователя');
      console.error('[SubscriptionWidget] Нет userId при попытке подписки');
      return;
    }
    await handleInvoiceGeneration(userId);
  };

  useEffect(() => {
    console.log('[SubscriptionWidget] useEffect инициализации Telegram WebApp. isActive:', isActive);
    if (window.Telegram?.WebApp) {
      window.Telegram.WebApp.ready();
      if (window.Telegram.WebApp.MainButton) {
        window.Telegram.WebApp.MainButton.setText('Подписаться за ' + SUBSCRIPTION_PRICE + ' Stars');
        window.Telegram.WebApp.MainButton.color = '#2481cc';
        window.Telegram.WebApp.MainButton.textColor = '#ffffff';
        if (isActive) {
          window.Telegram.WebApp.MainButton.hide();
        }
        window.Telegram.WebApp.MainButton.onClick(handleSubscribeViaMainButton);
        console.log('[SubscriptionWidget] MainButton настроен');
      }
      if (typeof window.Telegram.WebApp.onEvent === 'function') {
        window.Telegram.WebApp.onEvent('popup_closed', () => {
          console.log('[SubscriptionWidget] popup_closed event');
          onSubscriptionUpdate();
        });
        window.Telegram.WebApp.onEvent('invoiceClosed', () => {
          console.log('[SubscriptionWidget] invoiceClosed event');
          onSubscriptionUpdate();
        });
      }
    }
  }, [isActive, onSubscriptionUpdate]);

  // Добавляем useEffect для остановки polling при подтверждении Premium статуса
  useEffect(() => {
    console.log('[SubscriptionWidget] useEffect: изменение subscriptionStatus:', subscriptionStatus);
    if (subscriptionStatus?.has_subscription) {
      console.log('[SubscriptionWidget] Premium status confirmed. Stopping polling.');
      stopPolling();
    }
  }, [subscriptionStatus]); // Зависимость от статуса подписки

  // Возвращаем очистку таймеров при размонтировании
  useEffect(() => {
    return () => {
      console.log('[SubscriptionWidget] Размонтирование компонента. Очищаю MainButton и polling');
      if (window.Telegram?.WebApp?.MainButton && typeof window.Telegram.WebApp.MainButton.offClick === 'function') {
        window.Telegram.WebApp.MainButton.offClick(handleSubscribeViaMainButton);
      }
      stopPolling(); // Очищаем таймеры при размонтировании
    };
  }, [isActive, onSubscriptionUpdate]);

  if (!userId) {
    console.error('[SubscriptionWidget] Нет userId!');
    return (
      <div className="subscription-widget error">
        <p>Ошибка: Не удалось получить корректный ID пользователя из Telegram.<br/>Пожалуйста, перезапустите мини-приложение из Telegram.<br/>Если ошибка повторяется — попробуйте очистить кэш Telegram или обновить приложение.</p>
        <button onClick={() => window.Telegram?.WebApp?.close?.()}>Закрыть мини-приложение</button>
        <pre style={{textAlign: 'left', fontSize: '12px', marginTop: '16px', color: '#888', background: '#222', padding: '8px', borderRadius: '6px'}}>
          userId: {userId}
        </pre>
      </div>
    );
  }

  if (error) {
    console.error('[SubscriptionWidget] Ошибка:', error);
    return (
      <div className="subscription-widget error">
        <p>Ошибка: {error}</p>
        <button onClick={refreshSubscriptionStatus}>Попробовать снова</button>
        <pre style={{textAlign: 'left', fontSize: '12px', marginTop: '16px', color: '#888', background: '#222', padding: '8px', borderRadius: '6px'}}>
          userId: {userId}
        </pre>
      </div>
    );
  }

  if (!subscriptionStatus) {
    console.log('[SubscriptionWidget] subscriptionStatus отсутствует, показываю лоадер');
    return <div className="subscription-widget loading">Загрузка информации о подписке...</div>;
  }

  // Новый простой рендеринг
  console.log('[SubscriptionWidget] Рендеринг. isPremium:', calculatedIsActive, 'subscriptionStatus:', subscriptionStatus);

  // ======= ПОДРОБНОЕ ЛОГИРОВАНИЕ В РЕНДЕРЕ =======
  console.log('[SubscriptionWidget][RENDER] userId:', userId);
  console.log('[SubscriptionWidget][RENDER] subscriptionStatus:', subscriptionStatus);
  console.log('[SubscriptionWidget][RENDER] isPremium:', calculatedIsActive);
  console.log('[SubscriptionWidget][RENDER] error:', error);
  console.log('[SubscriptionWidget][RENDER] isSubscribing:', isSubscribing);
  console.log('[SubscriptionWidget][RENDER] showPaymentInfo:', showPaymentInfo);
  console.log('[SubscriptionWidget][RENDER] pollIntervalRef:', pollIntervalRef.current);
  console.log('[SubscriptionWidget][RENDER] pollTimeoutRef:', pollTimeoutRef.current);

  // ======= ЛОГИРУЕМ ВСЕ ПРОПСЫ И СОСТОЯНИЯ =======
  console.log('[SubscriptionWidget][RENDER] props:', { userId, subscriptionStatus, isActive });
  console.log('[SubscriptionWidget][RENDER] state:', { error, showPaymentInfo, isSubscribing });

  // ======= ОБЕРТКА ДЛЯ onSubscriptionUpdate С ЛОГАМИ =======
  const onSubscriptionUpdateWithLog = () => {
    console.log('[SubscriptionWidget] Вызов onSubscriptionUpdateWithLog');
    setIsRefreshing(true);
    onSubscriptionUpdate();
    
    // Сбрасываем состояние загрузки через некоторое время
    setTimeout(() => {
      if (mountedRef.current) {
        setIsRefreshing(false);
        setLastUpdateTime(new Date().toLocaleTimeString());
      }
    }, 1500);
  };

  // ======= ЛОГИРУЕМ useEffect'ы =======
  useEffect(() => {
    console.log('[SubscriptionWidget][useEffect] Монтирование/обновление компонента. userId:', userId, 'subscriptionStatus:', subscriptionStatus, 'isActive:', isActive);
  }, [userId, subscriptionStatus, isActive]);

  useEffect(() => {
    console.log('[SubscriptionWidget][useEffect] error изменился:', error);
  }, [error]);

  useEffect(() => {
    console.log('[SubscriptionWidget][useEffect] isSubscribing изменился:', isSubscribing);
  }, [isSubscribing]);

  useEffect(() => {
    console.log('[SubscriptionWidget][useEffect] showPaymentInfo изменился:', showPaymentInfo);
  }, [showPaymentInfo]);

  // Переключает отображение информации об оплате
  const togglePaymentInfo = () => setShowPaymentInfo(!showPaymentInfo);

  return (
    <div className="subscription-widget">
      <h3>Статус подписки</h3>
      
      {calculatedIsActive ? (
        <>
          <div className="status-badge premium">Премиум</div>
          <div className="subscription-active">
            <h4>Активная подписка</h4>
            <p>
              У вас активирована премиум-подписка, открывающая полный доступ к функциям:
            </p>
            <ul>
              <li>Неограниченный анализ каналов</li>
              <li>Расширенная генерация идей</li>
              <li>Доступ к базе изображений</li>
              <li>Планирование и автоматизация публикаций</li>
            </ul>
            
            {subscriptionStatus.subscription_end_date && (
              <p>
                <strong>Действует до:</strong> {new Date(subscriptionStatus.subscription_end_date).toLocaleDateString()}
              </p>
            )}
          </div>
        </>
      ) : (
        <>
          <div className="status-badge free">Бесплатный план</div>
          <div className="subscription-free">
            <h4>Ограниченный доступ</h4>
            <p>Используйте премиум-подписку для полного доступа ко всем функциям приложения.</p>
            
            <div className="subscription-offer">
              <h4>Премиум-подписка включает:</h4>
              <ul>
                <li>Неограниченный анализ каналов</li>
                <li>Расширенную генерацию идей</li>
                <li>Доступ к базе изображений</li>
                <li>Планирование и автоматизацию публикаций</li>
              </ul>
              <button 
                className="subscribe-button" 
                onClick={handleSubscribe}
                disabled={isSubscribing}
              >
                {isSubscribing ? 'Создание платежа...' : 'Получить премиум доступ'} 
              </button>
              
              <p style={{ marginTop: '10px', fontSize: '14px', color: '#666' }}>
                <a href="#" onClick={togglePaymentInfo}>
                  {showPaymentInfo ? 'Скрыть информацию об оплате' : 'Как оплатить?'}
                </a>
              </p>
              
              {showPaymentInfo && (
                <div className="payment-info">
                  <h4>Информация об оплате</h4>
                  <p>Оплата производится через Telegram Stars:</p>
                  <ol>
                    <li>Нажмите на кнопку "Получить премиум доступ"</li>
                    <li>Подтвердите платеж в Telegram</li>
                    <li>После успешной оплаты премиум-статус будет активирован</li>
                  </ol>
                  <p>
                    <small>
                      * Стоимость подписки: {SUBSCRIPTION_PRICE} Telegram Stars
                    </small>
                  </p>
                  <button className="cancel-button" onClick={togglePaymentInfo}>
                    Закрыть
                  </button>
                </div>
              )}
            </div>
          </div>
        </>
      )}
      
      {/* Блок для ручного обновления статуса */}
      <div className="refresh-status">
        <button
          className="refresh-button"
          onClick={refreshSubscriptionStatus}
          disabled={isRefreshing}
        >
          {isRefreshing ? 'Обновление...' : 'Обновить статус'}
        </button>
        <small>Последнее обновление: {lastUpdateTime}</small>
      </div>
      
      {/* Отладочная информация о подписке */}
      <div className="debug-info">
        <details>
          <summary>Информация о подписке (для отладки)</summary>
          <pre>
{JSON.stringify({
  userId: userId,
  subscriptionStatus: {
    has_subscription: subscriptionStatus.has_subscription,
    is_active: subscriptionStatus.is_active,
    subscription_end_date: subscriptionStatus.subscription_end_date
  },
  calculatedIsActive: calculatedIsActive,
  isEndDateValid: isEndDateValid,
  lastUpdateTime: lastUpdateTime
}, null, 2)}
          </pre>
          
          <h5>Журнал обновлений:</h5>
          <pre>
{refreshLog.join('\n')}
          </pre>
        </details>
      </div>
    </div>
  );
};

export default SubscriptionWidget; 