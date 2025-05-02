import React, { useState, useEffect, useRef, SetStateAction, Dispatch } from 'react';
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

  // Новый простой рендеринг
  const isPremium = subscriptionStatus.is_active && subscriptionStatus.has_subscription;
  console.log('[SubscriptionWidget] Рендеринг. isPremium:', isPremium, 'subscriptionStatus:', subscriptionStatus);

  // ======= ПОДРОБНОЕ ЛОГИРОВАНИЕ В РЕНДЕРЕ =======
  console.log('[SubscriptionWidget][RENDER] userId:', userId);
  console.log('[SubscriptionWidget][RENDER] subscriptionStatus:', subscriptionStatus);
  console.log('[SubscriptionWidget][RENDER] isPremium:', subscriptionStatus?.is_active && subscriptionStatus?.has_subscription);
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