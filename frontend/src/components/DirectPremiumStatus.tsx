import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface DirectPremiumStatusProps {
  userId: string | null;
}

interface PremiumStatusData {
  is_premium: boolean;
  end_date?: string;
  error?: string;
}

// Функция форматирования даты (можно вынести в utils)
const formatDate = (isoDateString?: string): string => {
  if (!isoDateString) return 'не указана';
  try {
    const date = new Date(isoDateString);
    const options: Intl.DateTimeFormatOptions = {
      year: 'numeric', month: 'long', day: 'numeric',
      hour: '2-digit', minute: '2-digit', timeZoneName: 'short'
    };
    return date.toLocaleDateString('ru-RU', options);
  } catch (e) {
    return 'некорректная дата';
  }
};

const DirectPremiumStatus: React.FC<DirectPremiumStatusProps> = ({ userId }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [status, setStatus] = useState<PremiumStatusData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDirectStatus = async () => {
      if (!userId) {
        setError('ID пользователя не передан в компонент');
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      setStatus(null);
      
      try {
        console.log(`[DirectStatus] Запрос статуса для ID: ${userId}`);
        const nocache = new Date().getTime();
        const telegramInitData = window.Telegram?.WebApp?.initData || '';
        
        const response = await axios.get<PremiumStatusData>(`/direct_premium_check?nocache=${nocache}`, {
          headers: {
            'x-telegram-user-id': userId,
            'x-telegram-init-data': telegramInitData,
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Expires': '0'
          }
        });
        
        console.log('[DirectStatus] Получен ответ:', response.data);
        if (response.data.error) {
            setError(`Ошибка от сервера: ${response.data.error}`);
            setStatus({ is_premium: false });
        } else {
            setStatus(response.data);
        }

      } catch (err: any) {
        console.error('[DirectStatus] Ошибка при запросе:', err);
        const errorMessage = err.response?.data?.detail || err.response?.data?.error || err.message || 'Неизвестная ошибка сети';
        setError(errorMessage);
        setStatus({ is_premium: false }); // По умолчанию считаем не премиум при ошибке
      } finally {
        setLoading(false);
      }
    };

    fetchDirectStatus();
    
    // Устанавливаем интервал для периодической проверки (не обязательно, но полезно для отладки)
    const intervalId = setInterval(fetchDirectStatus, 30000); // Каждые 30 секунд
    
    return () => clearInterval(intervalId); // Очистка при размонтировании

  }, [userId]);

  const renderStatus = () => {
    if (loading) {
      return <p>Загрузка статуса (прямая проверка)...</p>;
    }
    if (error) {
      return <p style={{ color: 'orange' }}>Прямая проверка: Ошибка: {error}</p>;
    }
    if (status) {
      if (status.is_premium) {
        return (
          <p style={{ color: 'green', fontWeight: 'bold' }}>
            Прямая проверка: Premium активен до {formatDate(status.end_date)}
          </p>
        );
      } else {
        return <p style={{ color: 'gray' }}>Прямая проверка: Статус Free</p>;
      }
    }
    return null;
  };

  return (
    <div style={{ border: '1px dashed blue', padding: '10px', margin: '10px 0' }}>
      <h4>Статус подписки (Прямая проверка)</h4>
      {renderStatus()}
      {userId && <small>User ID: {userId}</small>}
    </div>
  );
};

export default DirectPremiumStatus; 