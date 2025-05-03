import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus, generateInvoice } from '../api/subscription';

interface SubscriptionWidgetProps {
  userId: string | null;
}

// API_URL для относительных путей
const API_URL = '';

const SubscriptionWidget: React.FC<SubscriptionWidgetProps> = ({ userId }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  const SUBSCRIPTION_PRICE = 70; // в Stars
  const [isSubscribing, setIsSubscribing] = useState(false);
  
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
  }, []);
  
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
  
  const fetchSubscriptionStatus = async (): Promise<boolean> => {
    setLoading(true);
    setError(null);
    let hasPremium = false;
    try {
      const subscriptionData = await getUserSubscriptionStatus(userId);
      console.log('(fetchSubscriptionStatus) Получен ответ о статусе подписки:', subscriptionData);
      
      setStatus(subscriptionData);
      hasPremium = subscriptionData?.has_subscription || false;
      
      if (window.Telegram?.WebApp?.MainButton) {
        if (!hasPremium) {
          window.Telegram.WebApp.MainButton.show();
          console.log('(fetchSubscriptionStatus) MainButton показана (нет подписки)');
        } else {
          window.Telegram.WebApp.MainButton.hide();
          console.log('(fetchSubscriptionStatus) MainButton скрыта (есть подписка)');
        }
      }
      
      return hasPremium;
    } catch (err: any) {
      console.error('Ошибка при получении статуса подписки в fetchSubscriptionStatus:', err);
      setError(err.response?.data?.detail || err.message || 'Ошибка при загрузке статуса подписки');
      setStatus(null);
      if (window.Telegram?.WebApp?.MainButton) {
        window.Telegram.WebApp.MainButton.hide();
        console.log('(fetchSubscriptionStatus) MainButton скрыта (ошибка)');
      }
      return false;
    } finally {
      setLoading(false);
    }
  };
  
  // Функция для запуска платежа через MainButton
  const handleSubscribeViaMainButton = () => {
    console.log('Нажата главная кнопка в Telegram WebApp');
    
    // Показываем подтверждение через Telegram WebApp
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
      // Если метод showConfirm недоступен, просто продолжаем
      handleSubscribe();
    }
  };
  
  const handleInvoiceGeneration = async (userId: number) => {
    try {
      setIsSubscribing(true);
      setError(null);
      
      // Получаем invoice_url с backend
      const response = await fetch('/generate-stars-invoice-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, amount: SUBSCRIPTION_PRICE })
      });
      
      if (!response.ok) {
        // Обработка ошибок HTTP
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData?.detail || `Ошибка сервера: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.success && data.invoice_link) {
        if (window?.Telegram?.WebApp && typeof window?.Telegram?.WebApp.openInvoice === 'function') {
          window.Telegram.WebApp.openInvoice(data.invoice_link, (invoiceStatus) => {
            console.log('Статус инвойса:', invoiceStatus);
            if (invoiceStatus === 'paid') {
              fetchSubscriptionStatus().then(() => {
                if (window?.Telegram?.WebApp?.showPopup) {
                  window.Telegram.WebApp.showPopup({
                    title: 'Успешная оплата',
                    message: 'Ваша подписка Premium активирована!',
                    buttons: [{ type: 'ok' }]
                  });
                }
              });
            } else if (invoiceStatus === 'failed') {
              setError('Оплата не удалась. Пожалуйста, попробуйте позже.');
            } else if (invoiceStatus === 'cancelled') {
              console.log('Платеж отменен пользователем.');
            } else {
              console.log('Статус платежа:', invoiceStatus);
            }
            setIsSubscribing(false);
          });
        } else {
          setError('Оплата через Stars недоступна в этом окружении.');
          setIsSubscribing(false);
        }
      } else {
        setError(data.error?.detail || data.error || 'Ошибка генерации ссылки на оплату');
        setIsSubscribing(false);
      }
    } catch (error) {
      console.error('Ошибка при генерации/открытии Stars invoice:', error);
      setError(`Ошибка платежа: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`);
      setIsSubscribing(false);
    }
  };
  
  const handleSubscribe = async () => {
    try {
      // Получаем ID пользователя из Telegram WebApp
      const tgUserId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
      
      if (!tgUserId) {
        setError('Не удалось получить ID пользователя Telegram для оплаты.');
        return;
      }
      
      // Генерируем и открываем инвойс для оплаты
      await handleInvoiceGeneration(tgUserId);
    } catch (error) {
      console.error('Общая ошибка в handleSubscribe:', error);
    }
  };
  
  if (loading) {
    return <div className="subscription-widget loading">Загрузка информации о подписке...</div>;
  }
  
  if (error && !isSubscribing) {
    return (
      <div className="subscription-widget error">
        <p>Ошибка: {error}</p>
        <button className="action-button small" onClick={fetchSubscriptionStatus}>Повторить</button>
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
              {isSubscribing ? 'Создание платежа...' : `Подписаться за ${SUBSCRIPTION_PRICE} Stars`}
            </button>
            {error && isSubscribing && <p className="error-message small">{error}</p>}
          </div>
        </div>
      )}
    </div>
  );
};

export default SubscriptionWidget; 