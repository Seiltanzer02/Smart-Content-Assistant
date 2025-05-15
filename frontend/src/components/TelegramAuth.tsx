import React, { useEffect } from 'react';

// Типы данных для Telegram WebApp
declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        ready: () => void;
        initData: string;
        initDataUnsafe: {
          user?: {
            id?: number;
            first_name?: string;
            last_name?: string;
            username?: string;
          };
          query_id?: string;
        };
      };
    };
  }
}

// Интерфейс для props компонента
interface TelegramAuthProps {
  onAuthSuccess: (userId: string) => void;
  onAuthError?: (error: string) => void;
}

export const TelegramAuth: React.FC<TelegramAuthProps> = ({ onAuthSuccess, onAuthError }) => {
  console.log('Рендер компонента TelegramAuth');

  useEffect(() => {
    console.log('TelegramAuth useEffect запущен');
    const initTelegramAuth = () => {
      console.log('initTelegramAuth запущен');
      
      // Проверяем наличие объекта Telegram
      if (typeof window.Telegram === 'undefined') {
        console.error('window.Telegram не определен! Возможно, не загружен Telegram WebApp JS');
        if (onAuthError) onAuthError('Telegram WebApp not available');
        return;
      }
      
      console.log('window.Telegram определен:', window.Telegram);
      console.log('window.Telegram.WebApp определен:', window.Telegram.WebApp);
      
      // Инициализируем Telegram WebApp
      try {
        window.Telegram.WebApp.ready();
        console.log('window.Telegram.WebApp.ready() вызван успешно');
      } catch (e) {
        console.error('Ошибка при вызове window.Telegram.WebApp.ready():', e);
      }
      
      // Проверяем наличие данных пользователя
      console.log('initDataUnsafe:', window.Telegram.WebApp.initDataUnsafe);
      if (!window.Telegram.WebApp.initDataUnsafe || !window.Telegram.WebApp.initDataUnsafe.user) {
        console.error('User data not found in Telegram WebApp!');
        if (onAuthError) onAuthError('User data not found');
        return;
      }
      
      // Получаем ID пользователя
      const user = window.Telegram.WebApp.initDataUnsafe.user;
      console.log('Получены данные пользователя:', user);
      
      if (!user.id) {
        console.error('User ID not found in Telegram WebApp!');
        if (onAuthError) onAuthError('User ID not found');
        return;
      }
      
      // Успешная авторизация - вызываем колбэк
      const userId = String(user.id);
      console.log('Успешно получен User ID:', userId);
      onAuthSuccess(userId);
    };

    // Вызываем функцию инициализации с небольшой задержкой,
    // чтобы убедиться, что Telegram WebApp полностью загружен
    const timerId = setTimeout(() => {
      console.log('Вызываем initTelegramAuth после задержки');
      initTelegramAuth();
    }, 500);

    return () => {
      clearTimeout(timerId);
    };
  }, [onAuthSuccess, onAuthError]);

  // Отображаем экран загрузки, пока идет авторизация
  return (
    <div className="telegram-auth-container">
      <div className="loading-spinner"></div>
      <p>Авторизация в Telegram...</p>
    </div>
  );
};

export default TelegramAuth; 