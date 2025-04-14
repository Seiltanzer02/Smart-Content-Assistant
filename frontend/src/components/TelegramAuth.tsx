import React, { useState, useEffect } from 'react';
import axios from 'axios';
import WebApp from '@twa-dev/sdk';
import './TelegramAuth.css';

interface TelegramAuthProps {
  onAuthSuccess: (userId: string) => void;
}

export const TelegramAuth: React.FC<TelegramAuthProps> = ({ onAuthSuccess }) => {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      try {
        // Инициализируем Telegram WebApp
        WebApp.ready();
        
        // Получаем данные пользователя
        const user = WebApp.initDataUnsafe.user;
        
        if (user?.id) {
          // Если есть ID пользователя, вызываем успешную авторизацию
          onAuthSuccess(user.id.toString());
        } else {
          setError('Не удалось получить ID пользователя Telegram');
        }
      } catch (err) {
        console.error('Ошибка при инициализации Telegram WebApp:', err);
        setError('Ошибка при инициализации приложения');
      } finally {
        setLoading(false);
      }
    };

    initAuth();
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
        <div className="auth-card">
          <h1 className="auth-title">Ошибка авторизации</h1>
          <div className="auth-error">{error}</div>
          <p>Пожалуйста, попробуйте открыть приложение через Telegram</p>
        </div>
      </div>
    );
  }

  return null;
}; 