import React, { useState, useEffect, useRef } from 'react';
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
  const [error, setError] = useState<string | null>(null);
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  const SUBSCRIPTION_PRICE = 1; // временно 1 Star для теста
  const [isSubscribing, setIsSubscribing] = useState(false);
  const pollIntervalRef = useRef<number | null>(null);
  const pollTimeoutRef = useRef<number | null>(null);

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
      console.log('Polling stopped');
    }
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
  };

  const handleSubscribeViaMainButton = () => {
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
          window.Telegram.WebApp.openInvoice(data.invoice_link, async (status) => {
            setIsSubscribing(false);
            if (status === 'paid') {
              console.log('Payment status: paid. Starting polling...');
              if (window?.Telegram?.WebApp?.showPopup) {
                window.Telegram.WebApp.showPopup({
                  title: 'Успешная оплата',
                  message: 'Подписка активирована! Обновляем статус...',
                  buttons: [{ type: 'ok' }]
                });
              }
              await onSubscriptionUpdate();

              stopPolling();
              pollIntervalRef.current = window.setInterval(() => {
                console.log('Polling for subscription status...');
                onSubscriptionUpdate();
              }, 2000);

              pollTimeoutRef.current = window.setTimeout(() => {
                console.log('Polling timeout reached. Stopping polling.');
                stopPolling();
              }, 15000);

            } else if (status === 'failed') {
              console.log('Payment status: failed');
              setError('Оплата не удалась. Пожалуйста, попробуйте позже.');
            } else if (status === 'cancelled') {
              console.log('Payment status: cancelled');
            }
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
      stopPolling();
    }
  };

  const handleSubscribe = async () => {
    if (!userId) {
      setError('Не удалось получить корректный ID пользователя');
      return;
    }
    await handleInvoiceGeneration(userId);
  };

  useEffect(() => {
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
      }
      if (typeof window.Telegram.WebApp.onEvent === 'function') {
        window.Telegram.WebApp.onEvent('popup_closed', () => {
          onSubscriptionUpdate();
        });
        window.Telegram.WebApp.onEvent('invoiceClosed', () => {
          onSubscriptionUpdate();
        });
      }
    }
    return () => {
      if (window.Telegram?.WebApp?.MainButton) {
        window.Telegram.WebApp.MainButton.offClick(handleSubscribeViaMainButton);
      }
      stopPolling();
    };
  }, [isActive, onSubscriptionUpdate]);

  useEffect(() => {
    if (subscriptionStatus?.has_subscription) {
      console.log('Subscription is active, stopping polling.');
      stopPolling();
    }
  }, [subscriptionStatus]);

  if (!userId) {
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
    return <div className="subscription-widget loading">Загрузка информации о подписке...</div>;
  }

  return (
    <div className="subscription-widget">
      <h3>Статус подписки</h3>
      {subscriptionStatus.has_subscription ? (
        <div className="subscription-active">
          <div className="status-badge premium">Premium</div>
          <p>У вас активная подписка{subscriptionStatus.subscription_end_date ? ` до ${new Date(subscriptionStatus.subscription_end_date).toLocaleDateString()}` : ''}</p>
          <p>Все функции доступны без ограничений</p>
        </div>
      ) : (
        <div className="subscription-free">
          <div className="status-badge free">Бесплатный план</div>
          <p>Использовано анализов: {subscriptionStatus.analysis_count || 0}/2</p>
          <p>Использовано генераций постов: {subscriptionStatus.post_generation_count || 0}/2</p>
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