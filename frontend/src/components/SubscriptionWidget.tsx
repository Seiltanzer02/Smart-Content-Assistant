import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus } from '../api/subscription';

interface SubscriptionWidgetProps {
  userId: string | null;
  isActive?: boolean;
}

// API_URL для относительных путей
const API_URL = '';

const SubscriptionWidget: React.FC<SubscriptionWidgetProps> = ({ userId, isActive }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  const SUBSCRIPTION_PRICE = 1;
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
        window.Telegram.WebApp.MainButton.setText('Подписаться за ' + SUBSCRIPTION_PRICE + ' Star');
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
    try {
      // Используем функцию из API вместо прямого запроса
      const subscriptionData = await getUserSubscriptionStatus(userId);
      setStatus(subscriptionData);
      
      // Показываем/скрываем главную кнопку в зависимости от статуса подписки
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
  
  // Функция для запуска платежа через MainButton
  const handleSubscribeViaMainButton = () => {
    console.log('Нажата главная кнопка в Telegram WebApp');
    
    // Показываем подтверждение через Telegram WebApp
    if (window.Telegram?.WebApp?.showConfirm) {
      window.Telegram.WebApp.showConfirm(
        'Вы хотите оформить подписку за ' + SUBSCRIPTION_PRICE + ' Star?',
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
  
  const handleInvoiceGeneration = async () => {
    if (!userId) {
      setError("Не удалось определить ID пользователя");
      return;
    }
    try {
      setIsSubscribing(true);
      if (window?.Telegram?.WebApp && typeof window?.Telegram?.WebApp.openInvoice === 'function') {
        window.Telegram.WebApp.openInvoice(
          { slug: 'stars', amount: SUBSCRIPTION_PRICE },
          (paymentStatus) => {
            if (paymentStatus === 'paid') {
              fetchSubscriptionStatus();
              if (window?.Telegram?.WebApp?.showPopup) {
                window.Telegram.WebApp.showPopup({
                  title: 'Успешная оплата',
                  message: 'Ваша подписка Premium активирована!',
                  buttons: [{ type: 'ok' }]
                });
              }
            } else if (paymentStatus === 'failed' || paymentStatus === 'cancelled') {
              if (window?.Telegram?.WebApp?.showPopup) {
                window.Telegram.WebApp.showPopup({
                  title: 'Ошибка оплаты',
                  message: 'Не удалось завершить оплату. Пожалуйста, попробуйте снова.',
                  buttons: [{ type: 'ok' }]
                });
              }
            }
          });
      } else {
        console.error('Telegram WebApp или openInvoice недоступен.');
        setError('Не удалось инициировать оплату через Telegram.');
      }
    } catch (err: any) {
      console.error('Ошибка при генерации инвойса:', err);
      setError(err.message || 'Не удалось начать процесс оплаты.');
    } finally {
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
      await handleInvoiceGeneration();
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
          <p>Доступно бесплатных анализов: {status?.analysis_count === null ? 'Неограниченно' : (2 - (status?.analysis_count || 0))}</p>
          <p>Доступно бесплатных генераций постов: {status?.post_generation_count === null ? 'Неограниченно' : (2 - (status?.post_generation_count || 0))}</p>
          
          {showPaymentInfo ? (
            <div className="payment-info">
              <h4>Процесс оплаты</h4>
              <p>Для оплаты подписки выполните следующие шаги:</p>
              <ol>
                <li>Нажмите кнопку "Оплатить" выше</li>
                <li>Откроется чат с нашим ботом</li>
                <li>Нажмите кнопку "Оплатить {SUBSCRIPTION_PRICE} Star" в боте</li>
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
              <h4>Получите Premium</h4>
              <p>Снимите все ограничения и получите полный доступ ко всем функциям.</p>
              <button
                className="subscribe-button"
                onClick={handleInvoiceGeneration}
                disabled={isSubscribing}
              >
                {isSubscribing ? 'Обработка...' : `Подписаться за ${SUBSCRIPTION_PRICE} Star`}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SubscriptionWidget; 