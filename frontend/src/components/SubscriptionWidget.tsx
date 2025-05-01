import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus, generateInvoice } from '../api/subscription';
import axios from 'axios';

// API_URL для относительных путей
const API_URL = '';

const SubscriptionWidget: React.FC<{ isActive?: boolean }> = ({ isActive }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  const SUBSCRIPTION_PRICE = 1; // временно 1 Star для теста
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  const [userIdReady, setUserIdReady] = useState(false);
  
  useEffect(() => {
    async function resolveUserId() {
      let tgUserId: string | undefined;
      // 1. initDataUnsafe.user.id
      if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        tgUserId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
        if (/^\d+$/.test(tgUserId)) {
          setUserId(tgUserId);
          setUserIdReady(true);
          console.log('[SubscriptionWidget] userId из Telegram:', tgUserId);
          return;
        }
      }
      // 2. initData
      if (window.Telegram?.WebApp?.initData) {
        try {
          const params = new URLSearchParams(window.Telegram.WebApp.initData);
          const userParam = params.get('user');
          if (userParam) {
            const userObj = JSON.parse(userParam);
            if (userObj && userObj.id && /^\d+$/.test(String(userObj.id))) {
              tgUserId = String(userObj.id);
              setUserId(tgUserId);
              setUserIdReady(true);
              console.log('[SubscriptionWidget] userId из initData:', tgUserId);
              return;
            }
          }
        } catch (e) {
          console.error('[SubscriptionWidget] Ошибка декодирования initData:', e);
        }
      }
      // 3. НЕ используем localStorage!
      setUserId(null);
      setUserIdReady(true);
      console.error('[SubscriptionWidget] userId не найден!');
    }
    resolveUserId();
  }, []);
  
  useEffect(() => {
    console.log('Инициализация Telegram WebApp...');
    
    if (window.Telegram?.WebApp) {
      console.log('window.Telegram.WebApp найден, настраиваем...');
      
      window.Telegram.WebApp.ready();
      
      if (window.Telegram.WebApp.MainButton) {
        window.Telegram.WebApp.MainButton.setText('Подписаться за ' + SUBSCRIPTION_PRICE + ' Stars');
        window.Telegram.WebApp.MainButton.color = '#2481cc';
        window.Telegram.WebApp.MainButton.textColor = '#ffffff';
        if (isActive) {
          window.Telegram.WebApp.MainButton.hide();
        }
        
        window.Telegram.WebApp.MainButton.onClick(handleSubscribeViaMainButton);
      } else {
        console.warn('MainButton недоступен в Telegram WebApp');
      }
      
      if (typeof window.Telegram.WebApp.onEvent === 'function') {
        window.Telegram.WebApp.onEvent('popup_closed', () => {
          console.log('Popup закрыт, обновляем статус подписки');
          fetchSubscriptionStatus();
        });
        window.Telegram.WebApp.onEvent('invoiceClosed', () => {
          console.log('Событие invoiceClosed, обновляем статус подписки');
          fetchSubscriptionStatus();
        });
      }
    } else {
      console.warn('window.Telegram.WebApp не найден!');
    }
    
    return () => {
      if (window.Telegram?.WebApp?.MainButton) {
        window.Telegram.WebApp.MainButton.offClick(handleSubscribeViaMainButton);
      }
    };
  }, [isActive]);
  
  useEffect(() => {
    if (userId === null || userId === undefined || !/^\d+$/.test(String(userId))) {
      setError('Не удалось получить корректный ID пользователя');
      console.error('[SubscriptionWidget] userId невалиден:', userId);
      return;
    }
    setError(null); // сбрасываем ошибку, если userId валиден
    fetchSubscriptionStatus();
  }, [userId]);
  
  const fetchSubscriptionStatus = async (): Promise<boolean> => {
    if (!userId || !/^\d+$/.test(String(userId))) {
      setError('Не удалось получить корректный ID пользователя');
      console.error('[SubscriptionWidget] fetchSubscriptionStatus: userId невалиден:', userId);
      return false;
    }
    setLoading(true);
    try {
      const subscriptionData = await getUserSubscriptionStatus(String(userId));
      setStatus(subscriptionData);
      if (window.Telegram?.WebApp?.MainButton) {
        if (!subscriptionData.has_subscription && !isActive) {
          window.Telegram.WebApp.MainButton.show();
        } else {
          window.Telegram.WebApp.MainButton.hide();
        }
      }
      console.log('[SubscriptionWidget] Получен статус подписки:', subscriptionData);
      return subscriptionData.has_subscription;
    } catch (e: any) {
      setError('Ошибка при получении статуса подписки: ' + (e?.message || e));
      console.error('[SubscriptionWidget] Ошибка при получении статуса подписки:', e);
      return false;
    } finally {
      setLoading(false);
    }
  };
  
  const handleSubscribeViaMainButton = () => {
    console.log('Нажата главная кнопка в Telegram WebApp');
    
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
      handleSubscribe();
    }
  };
  
  const handleInvoiceGeneration = async (userId: string) => {
    try {
      setIsSubscribing(true);
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
      setError(`Ошибка: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`);
      setIsSubscribing(false);
    }
  };
  
  const handleSubscribe = async () => {
    if (!userId) {
      setError('Не удалось получить корректный ID пользователя');
      return;
    }
    await handleInvoiceGeneration(userId);
  };
  
  if (loading) {
    return <div className="subscription-widget loading">Загрузка информации о подписке...</div>;
  }
  
  if (error) {
    return (
      <div className="subscription-widget error">
        <p>Ошибка: {error}</p>
        <button onClick={fetchSubscriptionStatus}>Повторить</button>
        <pre style={{textAlign: 'left', fontSize: '12px', marginTop: '16px', color: '#888', background: '#222', padding: '8px', borderRadius: '6px'}}>
          userId: {userId}
          {'\n'}initData: {window.Telegram?.WebApp?.initData}
        </pre>
      </div>
    );
  }
  
  if (!userIdReady) {
    return <div className="subscription-widget loading">Определение пользователя Telegram...</div>;
  }
  
  if (!userId) {
    return (
      <div className="subscription-widget error">
        <p>Ошибка: Не удалось получить корректный ID пользователя из Telegram.<br/>Пожалуйста, перезапустите мини-приложение из Telegram.<br/>Если ошибка повторяется — попробуйте очистить кэш Telegram или обновить приложение.</p>
        <button onClick={() => window.Telegram?.WebApp?.close?.()}>Закрыть мини-приложение</button>
        <pre style={{textAlign: 'left', fontSize: '12px', marginTop: '16px', color: '#888', background: '#222', padding: '8px', borderRadius: '6px'}}>
          userId: {userId}
          {'\n'}initData: {window.Telegram?.WebApp?.initData}
        </pre>
      </div>
    );
  }
  
  return (
    <div className="subscription-widget">
      <h3>Статус подписки</h3>
      
      {status?.has_subscription ? (
        <div className="subscription-active">
          <div className="status-badge premium">Premium</div>
          <p>У вас активная подписка{status.subscription_end_date ? ` до ${new Date(status.subscription_end_date).toLocaleDateString()}` : ''}</p>
          <p>Все функции доступны без ограничений</p>
        </div>
      ) : (
        <div className="subscription-free">
          <div className="status-badge free">Бесплатный план</div>
          <p>Использовано анализов: {status?.analysis_count || 0}/2</p>
          <p>Использовано генераций постов: {status?.post_generation_count || 0}/2</p>
          
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
                onClick={() => setShowPaymentInfo(false)}
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
                onClick={handleSubscribe}
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