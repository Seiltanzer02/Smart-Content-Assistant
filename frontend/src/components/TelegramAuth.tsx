import React, { useState, useEffect } from 'react';
import WebApp from '@twa-dev/sdk';
import './TelegramAuth.css';

// Упрощенный компонент без использования локального хранилища
interface TelegramAuthProps {
  onAuthSuccess: (userId: string) => void;
}

export const TelegramAuth: React.FC<TelegramAuthProps> = ({ onAuthSuccess }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    console.log('TelegramAuth компонент загружен');
    try {
      // Пытаемся получить данные пользователя из Telegram WebApp SDK
      if (WebApp.initDataUnsafe?.user) {
        const userData = WebApp.initDataUnsafe.user;
        console.log('Получены данные пользователя:', userData);
        const userId = String(userData.id);
        console.log('Используем реальный Telegram ID пользователя:', userId);

        // Задержка для стабильности
        setTimeout(() => {
          setLoading(false);
          onAuthSuccess(userId);
        }, 100);

      } else {
        console.error('Данные пользователя Telegram не найдены. Приложение должно быть запущено внутри Telegram.');
        setError('Не удалось получить данные пользователя. Пожалуйста, убедитесь, что приложение запущено в Telegram.');
        setLoading(false);
      }
    } catch (e) {
      console.error('Ошибка при инициализации Telegram SDK или получении данных:', e);
      setError('Произошла ошибка при инициализации приложения.');
      setLoading(false);
    }
  }, [onAuthSuccess]);

  if (loading) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <div className="auth-loading" />
          <p>Инициализация...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="auth-container">
        <div className="auth-card error">
          <p>Ошибка аутентификации:</p>
          <p className="error-details">{error}</p>
          <p>Попробуйте перезапустить приложение.</p>
        </div>
      </div>
    );
  }

  return null;
}; 