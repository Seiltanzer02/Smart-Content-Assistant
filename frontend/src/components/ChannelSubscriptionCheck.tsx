import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { getTelegramUserId } from '../utils/telegramAuth';
import './ChannelSubscriptionCheck.css';

interface SubscriptionStatus {
  success: boolean;
  is_subscribed: boolean;
  channel_username: string;
  channel_link: string;
  message: string;
  access_granted?: boolean;
  error?: string;
  instructions?: string[];
}

const ChannelSubscriptionCheck: React.FC = () => {
  const [loading, setLoading] = useState<boolean>(true);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [checkingSubscription, setCheckingSubscription] = useState<boolean>(false);
  const navigate = useNavigate();
  const userId = getTelegramUserId();

  useEffect(() => {
    checkSubscription();
  }, []);

  const checkSubscription = async () => {
    if (!userId) {
      setStatus({
        success: false,
        is_subscribed: false,
        channel_username: '',
        channel_link: '',
        message: 'Не удалось определить ID пользователя Telegram'
      });
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      // Добавляем nocache параметр для предотвращения кэширования
      const nocache = `nocache=${new Date().getTime()}`;
      const response = await axios.get(`/channel/subscription-required?${nocache}`, {
        headers: {
          'X-Telegram-User-Id': userId,
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      });

      setStatus(response.data);
      
      // Если пользователь подписан, можно перенаправить на главную страницу
      if (response.data.is_subscribed || response.data.access_granted) {
        // Перенаправление после небольшой задержки, чтобы пользователь увидел позитивное сообщение
        setTimeout(() => {
          navigate('/');
        }, 1500);
      }
    } catch (error) {
      console.error('Ошибка при проверке подписки:', error);
      setStatus({
        success: false,
        is_subscribed: false,
        channel_username: '',
        channel_link: '',
        message: 'Произошла ошибка при проверке подписки на канал'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCheckSubscriptionClick = () => {
    setCheckingSubscription(true);
    checkSubscription().finally(() => {
      setCheckingSubscription(false);
    });
  };

  const goToChannel = () => {
    if (status?.channel_link) {
      window.open(status.channel_link, '_blank');
    }
  };

  if (loading) {
    return (
      <div className="subscription-check-container loading">
        <div className="loader"></div>
        <p>Проверка подписки на канал...</p>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="subscription-check-container error">
        <p>Не удалось получить информацию о подписке</p>
        <button onClick={checkSubscription}>Попробовать снова</button>
      </div>
    );
  }

  if (status.is_subscribed || status.access_granted) {
    return (
      <div className="subscription-check-container subscribed">
        <div className="success-icon">✅</div>
        <h1>Подписка подтверждена!</h1>
        <p>{status.message}</p>
        <button onClick={() => navigate('/')}>Перейти к приложению</button>
      </div>
    );
  }

  return (
    <div className="subscription-check-container">
      <h1>Требуется подписка на канал</h1>
      <p>{status.message}</p>
      
      {status.instructions && (
        <div className="instructions">
          {status.instructions.map((instruction, index) => (
            <p key={index}>{instruction}</p>
          ))}
        </div>
      )}
      
      <div className="subscription-actions">
        <button 
          className="primary-btn" 
          onClick={goToChannel}
        >
          Подписаться на канал
        </button>
        
        <button 
          className={`check-btn ${checkingSubscription ? 'checking' : ''}`} 
          onClick={handleCheckSubscriptionClick}
          disabled={checkingSubscription}
        >
          {checkingSubscription ? 'Проверка...' : 'Проверить подписку'}
        </button>
      </div>
      
      {status.error && (
        <div className="error-message">
          <p>Ошибка: {status.error}</p>
        </div>
      )}
    </div>
  );
};

export default ChannelSubscriptionCheck; 