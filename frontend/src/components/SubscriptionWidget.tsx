import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '../styles/SubscriptionWidget.css';

interface SubscriptionWidgetProps {
  userId: string | null;
}

interface SubscriptionStatus {
  has_subscription: boolean;
  analysis_count: number;
  post_generation_count: number;
  subscription_end_date?: string;
}

const SubscriptionWidget: React.FC<SubscriptionWidgetProps> = ({ userId }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const SUBSCRIPTION_PRICE = 70; // в Stars
  
  useEffect(() => {
    if (userId) {
      fetchSubscriptionStatus();
    }
  }, [userId]);
  
  const fetchSubscriptionStatus = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/subscription/status', {
        headers: { 'x-telegram-user-id': userId }
      });
      setStatus(response.data);
    } catch (err: any) {
      console.error('Ошибка при получении статуса подписки:', err);
      setError(err.response?.data?.detail || err.message || 'Ошибка при загрузке статуса подписки');
    } finally {
      setLoading(false);
    }
  };
  
  const handleSubscribe = () => {
    // Проверяем наличие Telegram WebApp
    console.log('handleSubscribe: Проверка наличия Telegram WebApp...');
    if (window.Telegram?.WebApp) {
      console.log('handleSubscribe: Telegram WebApp найден. Отправка данных...');
      // Отправляем данные о подписке в Telegram
      window.Telegram.WebApp.sendData(JSON.stringify({
        type: "subscribe",
        tier: "premium_monthly",
        price: SUBSCRIPTION_PRICE
      }));
      console.log('handleSubscribe: Данные отправлены.');
    } else {
      console.error('handleSubscribe: Telegram WebApp не доступен!');
      setError('Telegram WebApp не доступен. Убедитесь, что вы открыли приложение в Telegram.');
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
              disabled={!window.Telegram?.WebApp}
            >
              Подписаться за {SUBSCRIPTION_PRICE} Stars
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SubscriptionWidget; 