import React, { useState, useEffect } from 'react';
import './DirectPremiumStatus.css';

interface DirectPremiumStatusProps {
  userId: string | null;
  showDebug?: boolean;
}

// Константы
const API_URL = '';

/**
 * Компонент для прямого определения премиум-статуса пользователя
 * Использует выделенный эндпоинт для проверки статуса подписки
 */
const DirectPremiumStatus: React.FC<DirectPremiumStatusProps> = ({ userId, showDebug = false }) => {
  const [hasPremium, setHasPremium] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [endDate, setEndDate] = useState<string | null>(null);
  const [responseData, setResponseData] = useState<any>(null);

  // Функция для получения премиум-статуса
  const checkPremiumStatus = async () => {
    if (!userId) {
      console.log('[DirectStatus] Отсутствует userId, статус не может быть проверен');
      setLoading(false);
      setError('ID пользователя не предоставлен');
      return;
    }
    
    try {
      setLoading(true);
      setError(null);
      
      console.log(`[DirectStatus] Запрос статуса для ID: ${userId}`);
      
      // URL с предотвращением кэширования
      const nocache = new Date().getTime();
      const url = `${API_URL}/force-premium-status/${userId}?nocache=${nocache}`;
      
      // Запрос к API с дополнительными заголовками против кэширования
      const response = await fetch(url, {
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log(`[DirectStatus] Получен ответ:`, data);
        
        setHasPremium(data.has_premium || false);
        setEndDate(data.subscription_end_date || null);
        setResponseData(data);
      } else {
        // В случае ошибки API
        console.error(`[DirectStatus] Ошибка API: ${response.status}`);
        setError(`Ошибка API: ${response.status}`);
        setHasPremium(false);
      }
    } catch (e) {
      console.error(`[DirectStatus] Ошибка запроса:`, e);
      setError(`Ошибка запроса: ${e}`);
      setHasPremium(false);
    } finally {
      setLoading(false);
    }
  };

  // Проверка статуса при монтировании компонента или изменении userId
  useEffect(() => {
    if (userId) {
      checkPremiumStatus();
      
      // Регулярное обновление статуса
      const interval = setInterval(checkPremiumStatus, 15000); // каждые 15 секунд
      
      return () => {
        clearInterval(interval);
      };
    }
  }, [userId]);

  // Функция для форматирования даты с часовым поясом
  const formatDate = (isoDateString: string): string => {
    try {
      const date = new Date(isoDateString);
      
      // Форматируем дату с временем и часовым поясом
      const options: Intl.DateTimeFormatOptions = {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short'
      };
      
      return date.toLocaleDateString('ru-RU', options);
    } catch (e) {
      console.error('Ошибка при форматировании даты:', e);
      return 'Неизвестная дата';
    }
  };

  // Рендеринг компонента
  return (
    <div className="direct-premium-status">
      {loading ? (
        <div className="direct-status loading">Проверка статуса...</div>
      ) : error ? (
        <div className="direct-status error">
          {error}
        </div>
      ) : (
        <div className={`direct-status ${hasPremium ? 'premium' : 'free'}`}>
          {hasPremium ? (
            <>
              <div className="premium-badge">
                <span className="premium-icon">⭐</span>
                <span>ПРЕМИУМ</span>
              </div>
              {endDate && (
                <div className="expiry-date">
                  до {formatDate(endDate)}
                </div>
              )}
            </>
          ) : (
            <div className="free-badge">Бесплатный доступ</div>
          )}
          
          {showDebug && responseData && (
            <div className="debug-data">
              <details>
                <summary>Отладочная информация</summary>
                <pre>{JSON.stringify(responseData, null, 2)}</pre>
              </details>
              <button onClick={checkPremiumStatus} className="refresh-button">
                Обновить статус
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DirectPremiumStatus; 