import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '../styles/SubscriptionWidget.css';
import Loader from './Loader';
import styles from '../styles/SubscriptionWidget.module.css';
import { getUserSubscriptionStatus, SubscriptionStatus } from '../api/subscription';

interface SubscriptionWidgetProps {
  userId: string | null;
}

interface SubscriptionStatus {
  has_subscription: boolean;
  analysis_count: number;
  post_generation_count: number;
  subscription_end_date?: string;
}

// Добавляем константу API_URL
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

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
        window.Telegram.WebApp.MainButton.hide();
        
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
    try {
      const response = await axios.get('/subscription/status', {
        headers: { 'x-telegram-user-id': userId }
      });
      setStatus(response.data);
      
      // Показываем/скрываем главную кнопку в зависимости от статуса подписки
      if (window.Telegram?.WebApp?.MainButton) {
        if (!response.data.has_subscription) {
          window.Telegram.WebApp.MainButton.show();
        } else {
          window.Telegram.WebApp.MainButton.hide();
        }
      }
      
      return response.data.has_subscription;
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
  
  // Функция для генерации инвойса напрямую через Telegram Bot API
  const generateInvoice = async (userId: number) => {
    try {
      setIsSubscribing(true);
      
      // Делаем запрос к серверу для получения invoice_url
      const response = await fetch(`${API_URL}/generate-invoice`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          amount: 70 // Фиксированная сумма 70 Stars
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Не удалось создать инвойс');
      }
      
      const data = await response.json();
      console.log('Получены данные инвойса:', data);
      
      // Проверяем наличие URL инвойса
      if (data.invoice_url && window.Telegram?.WebApp?.openInvoice) {
        // Открываем инвойс прямо в Telegram WebApp
        window.Telegram.WebApp.openInvoice(data.invoice_url, (status) => {
          // Этот callback будет вызван после завершения платежа
          console.log('Статус платежа:', status);
          
          if (status === 'paid') {
            // Если платеж успешный, обновляем статус подписки
            fetchSubscriptionStatus();
            
            // Показываем сообщение об успешной оплате
            if (window.Telegram?.WebApp?.showPopup) {
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
        throw new Error('Не удалось получить URL инвойса или WebApp не поддерживает openInvoice');
      }
    } catch (error) {
      console.error('Ошибка при генерации инвойса:', error);
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
      await generateInvoice(userId);
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