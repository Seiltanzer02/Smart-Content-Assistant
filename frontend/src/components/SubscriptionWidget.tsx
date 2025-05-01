import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus, generateInvoice } from '../api/subscription';

// API_URL для относительных путей
const API_URL = '';

const SubscriptionWidget: React.FC<{ isActive?: boolean }> = ({ isActive }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  const SUBSCRIPTION_PRICE = 1; // временно 1 Star для теста
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [userId, setUserId] = useState<number | null>(null);
  
  useEffect(() => {
    console.log('[SubscriptionWidget] Монтирование компонента');
    console.log('[SubscriptionWidget] window.Telegram:', window.Telegram);
    console.log('[SubscriptionWidget] window.Telegram?.WebApp:', window.Telegram?.WebApp);
    console.log('[SubscriptionWidget] window.Telegram?.WebApp?.initDataUnsafe:', window.Telegram?.WebApp?.initDataUnsafe);
    let tgUserId: string | undefined;
    if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
      tgUserId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
      if (/^\d+$/.test(tgUserId)) {
        localStorage.setItem('tg_user_id', tgUserId);
        console.log('[SubscriptionWidget] userId получен из Telegram:', tgUserId);
      } else {
        console.error('[SubscriptionWidget] userId из Telegram невалиден:', tgUserId);
        tgUserId = undefined;
      }
    } else {
      const storedId = localStorage.getItem('tg_user_id');
      if (storedId && /^\d+$/.test(storedId)) {
        tgUserId = storedId;
        console.log('[SubscriptionWidget] userId получен из localStorage:', tgUserId);
      } else {
        console.warn('[SubscriptionWidget] userId не найден или невалиден в localStorage:', storedId);
        tgUserId = undefined;
      }
    }
    setUserId(tgUserId ? Number(tgUserId) : null);
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
    if (userId && !isNaN(userId)) {
      console.log('[SubscriptionWidget] useEffect: userId найден:', userId, typeof userId);
      fetchSubscriptionStatus();
    } else {
      console.warn('[SubscriptionWidget] useEffect: userId отсутствует или невалиден!', userId);
    }
    console.log('SubscriptionWidget загружен, проверка Telegram.WebApp:');
    console.log('window.Telegram существует:', !!window.Telegram);
    console.log('window.Telegram?.WebApp существует:', !!window.Telegram?.WebApp);
    if (window.Telegram?.WebApp) {
      console.log('window.Telegram.WebApp методы:', Object.keys(window.Telegram.WebApp));
    }
  }, [userId]);
  
  const fetchSubscriptionStatus = async (): Promise<boolean> => {
    if (!userId || isNaN(userId)) {
      setError('Не удалось получить корректный ID пользователя');
      setLoading(false);
      console.error('[SubscriptionWidget] fetchSubscriptionStatus: userId отсутствует или невалиден!', userId);
      return false;
    }
    setLoading(true);
    try {
      console.log('[SubscriptionWidget] fetchSubscriptionStatus: userId =', userId, typeof userId);
      const subscriptionData = await getUserSubscriptionStatus(String(userId));
      setStatus(subscriptionData);
      
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
  
  const handleInvoiceGeneration = async (userId: number) => {
    try {
      setIsSubscribing(true);
      if (!userId || isNaN(userId)) {
        setError('Некорректный userId для оплаты');
        setIsSubscribing(false);
        console.error('[SubscriptionWidget] handleInvoiceGeneration: userId невалиден!', userId);
        return;
      }
      console.log('[SubscriptionWidget] handleInvoiceGeneration: userId =', userId, typeof userId);
      const response = await fetch('/generate-stars-invoice-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: String(userId), amount: 1 }) // временно 1 Star
      });
      const data = await response.json();
      if (data.success && data.invoice_link) {
        if (window?.Telegram?.WebApp && typeof window?.Telegram?.WebApp.openInvoice === 'function') {
          window.Telegram.WebApp.openInvoice(data.invoice_link, (status) => {
            console.log('[SubscriptionWidget] openInvoice callback status:', status);
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
      if (!userId || isNaN(userId)) {
        setError('Не удалось получить корректный ID пользователя');
        console.error('[SubscriptionWidget] handleSubscribe: userId невалиден!', userId);
        return;
      }
      await handleInvoiceGeneration(userId);
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
  
  if (!userId || isNaN(userId)) {
    return (
      <div className="subscription-widget error">
        <p>Ошибка: Не удалось получить корректный ID пользователя из Telegram.<br/>Пожалуйста, перезапустите мини-приложение из Telegram.<br/>Если ошибка повторяется — попробуйте очистить кэш Telegram или обновить приложение.</p>
        <button onClick={() => window.Telegram?.WebApp?.close?.()}>Закрыть мини-приложение</button>
        <pre style={{textAlign: 'left', fontSize: '12px', marginTop: '16px', color: '#888', background: '#222', padding: '8px', borderRadius: '6px'}}>
          window.Telegram: {JSON.stringify(window.Telegram, null, 2)}
          {'\n'}localStorage.tg_user_id: {localStorage.getItem('tg_user_id')}
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