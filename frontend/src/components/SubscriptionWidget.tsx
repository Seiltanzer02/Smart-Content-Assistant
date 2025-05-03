import React, { useState, useEffect, useCallback, useRef, SetStateAction, Dispatch } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, generateInvoice } from '../api/subscription';
import axios from 'axios';

// API_URL для относительных путей
const API_URL = '';

// Тип для статуса подписки
type SubscriptionStatus = {
  has_subscription: boolean;
  is_active: boolean;
  subscription_end_date?: string;
  debug?: any; // Добавляем поле debug
};

const SubscriptionWidget: React.FC<{
  userId: string | null,
  subscriptionStatus: SubscriptionStatus | null,
  onSubscriptionUpdate: () => void,
  setSubscriptionStatus: Dispatch<SetStateAction<SubscriptionStatus | null>>;
  isActive?: boolean
}> = ({ userId, subscriptionStatus, onSubscriptionUpdate, setSubscriptionStatus, isActive }) => {
  console.log('[SubscriptionWidget] Монтирование компонента. userId:', userId, 'subscriptionStatus:', subscriptionStatus, 'isActive:', isActive);
  const [error, setError] = useState<string | null>(null);
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  const SUBSCRIPTION_PRICE = 1; // временно 1 Star для теста
  const [isSubscribing, setIsSubscribing] = useState(false);
  // Возвращаем refs
  const pollIntervalRef = useRef<number | null>(null);
  const pollTimeoutRef = useRef<number | null>(null);

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
        if (window?.Telegram?.WebApp && typeof window?.Telegram?.WebApp.openInvoice === 'function') {
          window.Telegram.WebApp.openInvoice(data.invoice_link, async (status) => {
            setIsSubscribing(false);
            console.log('[SubscriptionWidget] openInvoice callback статус:', status);
            if (status === 'paid') {
              console.log('[SubscriptionWidget] Payment status: paid. Optimistically updating UI...');
              if (userId) {
                  const timestampKey = `premiumConfirmed_${userId}`;
                  localStorage.setItem(timestampKey, Date.now().toString());
                  console.log(`[SubscriptionWidget] Saved premium confirmation timestamp to localStorage: ${timestampKey}`);
              }
              if (window?.Telegram?.WebApp?.showPopup) {
                window.Telegram.WebApp.showPopup({
                  title: 'Успешная оплата',
                  message: 'Подписка активирована!',
                  buttons: [{ type: 'ok' }]
                });
              }
              const optimisticStatus: SubscriptionStatus = {
                has_subscription: true,
                is_active: true,
                subscription_end_date: undefined
              };
              setSubscriptionStatus(optimisticStatus);
              stopPolling();
              console.log('[SubscriptionWidget] Starting aggressive polling for status confirmation...');
              pollIntervalRef.current = window.setInterval(() => {
                console.log('[SubscriptionWidget] Polling for subscription status...');
                onSubscriptionUpdate();
              }, 2000);
              pollTimeoutRef.current = window.setTimeout(() => {
                console.warn('[SubscriptionWidget] Polling timeout reached. Stopping polling. Status might not be up-to-date.');
                stopPolling();
              }, 15000);
            } else if (status === 'failed') {
              console.log('[SubscriptionWidget] Payment status: failed');
              setError('Оплата не удалась. Пожалуйста, попробуйте позже.');
            } else if (status === 'cancelled') {
              console.log('[SubscriptionWidget] Payment status: cancelled');
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
    if (subscriptionStatus && subscriptionStatus.is_active) {
      console.log('[SubscriptionWidget] Premium статус подтвержден, останавливаем polling');
      stopPolling();
    }
    
    if (subscriptionStatus && subscriptionStatus.debug && subscriptionStatus.debug.selected_sub) {
      const debugSub = subscriptionStatus.debug.selected_sub;
      if (debugSub.is_active) {
        console.log('[SubscriptionWidget] ВАЖНО! В debug данных найдена активная подписка, останавливаем polling');
        stopPolling();
      }
    }
  }, [subscriptionStatus, stopPolling]);

  // Возвращаем очистку таймеров при размонтировании
  useEffect(() => {
    return () => {
      console.log('[SubscriptionWidget] Размонтирование компонента. Очищаю MainButton и polling');
      if (window.Telegram?.WebApp?.MainButton) {
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
        <button onClick={onSubscriptionUpdate}>Повторить</button>
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

  // ИЗМЕНЕНО: теперь проверяем ТОЛЬКО is_active, а не оба флага (has_subscription и is_active)
  // Так как в базе у нас может быть запись с is_active = true, даже если старые проверки не сработали
  let isPremium = subscriptionStatus.is_active;
  
  // НОВОЕ: Принудительная проверка из debug данных, если они есть
  if (!isPremium && subscriptionStatus.debug && subscriptionStatus.debug.selected_sub) {
    const debugSub = subscriptionStatus.debug.selected_sub;
    if (debugSub.is_active) {
      console.log('[SubscriptionWidget] ВАЖНО! В debug данных найдена активная подписка, устанавливаем isPremium = true');
      isPremium = true;
    }
  }
  
  console.log('[SubscriptionWidget] Рендеринг. isPremium:', isPremium, 'subscriptionStatus:', subscriptionStatus);

  // ======= ПОДРОБНОЕ ЛОГИРОВАНИЕ В РЕНДЕРЕ =======
  console.log('[SubscriptionWidget][RENDER] userId:', userId);
  console.log('[SubscriptionWidget][RENDER] subscriptionStatus:', subscriptionStatus);
  console.log('[SubscriptionWidget][RENDER] is_active:', subscriptionStatus.is_active);
  console.log('[SubscriptionWidget][RENDER] has_subscription:', subscriptionStatus.has_subscription);
  console.log('[SubscriptionWidget][RENDER] Определен premium статус:', isPremium);
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
    try {
      console.log('[SubscriptionWidget][onSubscriptionUpdate] Вызван onSubscriptionUpdate');
      onSubscriptionUpdate();
    } catch (e) {
      console.error('[SubscriptionWidget][onSubscriptionUpdate] Ошибка:', e);
    }
  };

  // ======= ОБЕРТКА ДЛЯ setSubscriptionStatus С ЛОГАМИ =======
  const setSubscriptionStatusWithLog = (status: SubscriptionStatus) => {
    console.log('[SubscriptionWidget][setSubscriptionStatus] Устанавливаю статус:', status);
    setSubscriptionStatus(status);
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
  
  return (
    <div className="subscription-widget">
      <h3>Статус подписки</h3>
      {isPremium ? (
        <div className="subscription-active">
          <div className="status-badge premium">Premium</div>
          <p>У вас активная подписка{subscriptionStatus.subscription_end_date ? ` до ${new Date(subscriptionStatus.subscription_end_date).toLocaleDateString()}` : ''}</p>
          <p>Все функции доступны без ограничений</p>
        </div>
      ) : (
        <div className="subscription-free">
          <div className="status-badge free">Бесплатный план</div>
          <p>Доступ ограничен. Для безлимитного доступа оформите подписку.</p>
          {showPaymentInfo ? (
            <div className="payment-info">
              <h4>Процесс оплаты</h4>
              <p>Для оплаты подписки выполните следующие шаги:</p>
              <ol>
                <li>Нажмите кнопку "Оплатить" выше</li>
                <li>Откроется чат с нашим ботом</li>
                <li>Нажмите кнопку "Оплатить {SUBSCRIPTION_PRICE} Stars" в боте</li>
                <li>Подтвердите платеж</li>
                <li>Вернитесь в это приложение</li>
              </ol>
              <p>После успешной оплаты ваша подписка активируется автоматически!</p>
              <button 
                className="cancel-button"
                onClick={() => {
                  setShowPaymentInfo(false);
                  console.log('[SubscriptionWidget] Пользователь отменил просмотр paymentInfo');
                }}
              >
                Отменить
              </button>
            </div>
          ) : (
            <div className="subscription-offer">
              <h4>Получите безлимитный доступ</h4>
              <ul>
                <li>Неограниченный анализ каналов</li>
                <li>Неограниченная генерация постов</li>
                <li>Сохранение данных в облаке</li>
              </ul>
              <button 
                className="subscribe-button"
                onClick={() => {
                  console.log('[SubscriptionWidget] Клик по кнопке подписки');
                  handleSubscribe();
                }}
                disabled={isSubscribing}
              >
                {isSubscribing ? 'Создание платежа...' : 'Подписаться за 70 Stars'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SubscriptionWidget; 