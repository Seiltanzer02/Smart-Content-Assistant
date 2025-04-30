import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus, generateInvoice } from '../api/subscription';

interface SubscriptionWidgetProps {
  userId: string | null;
  isActive?: boolean;
}

// API_URL для относительных путей
const API_URL = '';

const SubscriptionWidget: React.FC<SubscriptionWidgetProps> = ({ userId, isActive }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<'active' | 'inactive' | 'loading'>('loading');
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  const SUBSCRIPTION_PRICE = 70; // в Stars
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [endDate, setEndDate] = useState<string | null>(null);
  
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
      const response = await fetch(`/subscription/status?user_id=${userId}`);
      const data = await response.json();
      if (data.is_active && data.end_date) {
        setStatus('active');
        setEndDate(data.end_date);
      } else {
        setStatus('inactive');
        setEndDate(null);
      }
      
      // Показываем/скрываем главную кнопку в зависимости от статуса подписки
      if (window.Telegram?.WebApp?.MainButton) {
        if (!data.has_subscription && !isActive) {
          window.Telegram.WebApp.MainButton.show();
        } else {
          window.Telegram.WebApp.MainButton.hide();
        }
      }
      
      return data.has_subscription;
    } catch (err: any) {
      console.error('Ошибка при получении статуса подписки:', err);
      setError(err.response?.data?.detail || err.message || 'Ошибка при загрузке статуса подписки');
      setStatus('inactive');
      setEndDate(null);
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
    if (typeof window === 'undefined' || !('Telegram' in window) || !window.Telegram) return;
    const telegramWebApp = window.Telegram;
    try {
      setIsSubscribing(true);
      const response = await fetch('/send-stars-invoice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, amount: 70 })
      });
      const data = await response.json();
      if (data.success) {
        if (telegramWebApp.WebApp?.showPopup) {
          telegramWebApp.WebApp.showPopup({
            title: 'Оплата',
            message: 'Инвойс отправлен в чат с ботом. После оплаты вернитесь и обновите статус.',
          });
        }
        if (telegramWebApp.WebApp?.close) {
          setTimeout(() => telegramWebApp.WebApp.close(), 1000);
        }
        setTimeout(fetchSubscriptionStatus, 5000);
      } else {
        alert(data.message || 'Ошибка при отправке инвойса');
      }
    } catch (e) {
      alert('Ошибка при отправке инвойса');
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
      await handleInvoiceGeneration(Number(userId));
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
      
      {status === 'loading' && <div>Загрузка статуса подписки...</div>}
      {status === 'active' && endDate && (
        <div style={{ color: 'green', marginBottom: 12 }}>
          Ваша подписка активна до {new Date(endDate).toLocaleString('ru-RU')}
        </div>
      )}
      {status === 'inactive' && userId != null && (
        <button onClick={() => handleInvoiceGeneration(Number(userId))} disabled={isSubscribing}>
          Подписаться за 70 Stars
        </button>
      )}
      {status === 'active' && (
        <button onClick={fetchSubscriptionStatus} style={{ marginTop: 8 }}>
          Обновить статус
        </button>
      )}
    </div>
  );
};

export default SubscriptionWidget; 