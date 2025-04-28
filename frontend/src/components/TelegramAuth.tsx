import React, { useState, useEffect } from 'react';
import './TelegramAuth.css';

interface TelegramAuthProps {
  onAuthSuccess: (userId: string) => void;
}

interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
}

export const TelegramAuth: React.FC<TelegramAuthProps> = ({ onAuthSuccess }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    console.log('TelegramAuth компонент загружен');
    
    // Проверяем наличие Telegram WebApp API
    if (typeof window !== 'undefined') {
      // Проверяем доступность Telegram WebApp API
      const tgWebApp = (window as any).Telegram?.WebApp || (window as any).WebApp;
      
      if (tgWebApp) {
        try {
          console.log('TelegramAuth: WebApp API обнаружен');
          
          // Инициализация WebApp
          tgWebApp.ready();
          
          // Получаем данные пользователя
          const initData = tgWebApp.initData || '';
          const initDataUnsafe = tgWebApp.initDataUnsafe || {};
          
          if (initDataUnsafe && initDataUnsafe.user) {
            // Получаем данные пользователя из initDataUnsafe
            const user = initDataUnsafe.user as TelegramUser;
            console.log('TelegramAuth: Пользователь получен из initDataUnsafe', user);
            
            // Сохраняем ID пользователя
            const userId = String(user.id);
            localStorage.setItem('telegramUserId', userId);
            
            // Вызываем колбэк успешной аутентификации
            setLoading(false);
            onAuthSuccess(userId);
          } else if (initData) {
            // Если есть initData, но нет initDataUnsafe, пробуем получить данные из неё
            console.log('TelegramAuth: Пробуем получить пользователя из initData');
            
            try {
              // initData имеет формат query string - нужно распарсить
              const params = new URLSearchParams(initData);
              const userStr = params.get('user');
              
              if (userStr) {
                const user = JSON.parse(decodeURIComponent(userStr)) as TelegramUser;
                const userId = String(user.id);
                localStorage.setItem('telegramUserId', userId);
                
                setLoading(false);
                onAuthSuccess(userId);
              } else {
                throw new Error('Не удалось получить данные пользователя из initData');
              }
            } catch (e) {
              console.error('Ошибка при извлечении данных пользователя из initData:', e);
              useTestUserIfNeeded();
            }
          } else {
            console.warn('TelegramAuth: WebApp API найден, но нет данных пользователя');
            useTestUserIfNeeded();
          }
        } catch (e) {
          console.error('Ошибка при получении данных пользователя из Telegram:', e);
          useTestUserIfNeeded();
        }
      } else {
        console.warn('TelegramAuth: WebApp API не найден');
        useTestUserIfNeeded();
      }
    } else {
      console.error('TelegramAuth: window не определено');
      useTestUserIfNeeded();
    }
    
    // Использование тестового пользователя в разработке или при ошибке
    function useTestUserIfNeeded() {
      // Пробуем получить сохраненный ID из localStorage
      const savedUserId = localStorage.getItem('telegramUserId');
      
      if (savedUserId) {
        console.log('TelegramAuth: Использую сохраненный ID пользователя:', savedUserId);
        setLoading(false);
        onAuthSuccess(savedUserId);
      } else {
        // В продакшене можно показать ошибку или редирект
        // Для отладки генерируем уникальный ID на основе случайного числа
        const isDevelopment = window.location.hostname === 'localhost' || 
                            window.location.hostname === '127.0.0.1';
        
        if (isDevelopment) {
          // Для отладки используем уникальный ID, чтобы не мешать данным реальных пользователей
          const randomUserId = 'dev_' + Math.floor(Math.random() * 1000000);
          console.log('TelegramAuth (DEV MODE): Использую тестовый ID пользователя:', randomUserId);
          localStorage.setItem('telegramUserId', randomUserId);
          setLoading(false);
          onAuthSuccess(randomUserId);
        } else {
          // В продакшене показываем ошибку
          setError('Не удалось авторизоваться через Telegram. Пожалуйста, убедитесь, что вы открываете приложение в Telegram.');
          setLoading(false);
        }
      }
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
        <div className="auth-card auth-error">
          <p>{error}</p>
          <button 
            className="action-button" 
            onClick={() => window.location.reload()}
          >
            Попробовать снова
          </button>
        </div>
      </div>
    );
  }

  // После успешной аутентификации ничего не отображаем
  return null;
}; 