import React, { useEffect } from 'react';

interface TelegramAuthProps {
  onAuthSuccess: (userId: string) => void;
}

const TelegramAuth: React.FC<TelegramAuthProps> = ({ onAuthSuccess }) => {
  useEffect(() => {
    console.log('TelegramAuth компонент загружен');
    
    // Сохраняем ссылку на оригинальный fetch
    const originalFetch = window.fetch;
    
    const initTelegramAuth = () => {
      try {
        // WebApp уже должен быть инициализирован в этот момент
        if (window.Telegram?.WebApp?.initDataUnsafe?.user) {
          const userData = window.Telegram.WebApp.initDataUnsafe.user;
          console.log('Получены данные пользователя:', userData);
          
          // Используем ID пользователя из Telegram WebApp
          const userId = userData.id?.toString();
          
          if (userId) {
            console.log('Используем реальный Telegram ID пользователя:', userId);
            
            // Устанавливаем заголовок для всех будущих fetch запросов
            window.fetch = function(input, init) {
              init = init || {};
              init.headers = init.headers || {};
              
              // Добавляем пользовательские заголовки
              const customHeaders = {
                'X-Telegram-User-Id': userId.toString()
              };
              
              // Объединяем заголовки
              init.headers = {
                ...customHeaders,
                ...init.headers
              };
              
              return originalFetch.call(this, input, init);
            };
            
            // Передаем ID пользователя родительскому компоненту
            onAuthSuccess(userId);
          } else {
            console.error('ID пользователя отсутствует в данных Telegram WebApp');
            
            // Используем резервный метод для получения userId из URL (если возможно)
            const urlParams = new URLSearchParams(window.location.search);
            const userId = urlParams.get('userId') || '';
            
            if (userId) {
              console.log('Используем userId из URL параметров:', userId);
              onAuthSuccess(userId);
            } else {
              console.error('Не удалось получить ID пользователя ни из WebApp, ни из URL');
              // Используем тестовый ID в качестве крайней меры
              onAuthSuccess('427032240');
            }
          }
        } else {
          console.error('Данные пользователя Telegram WebApp отсутствуют');
          
          // Используем резервный метод для получения userId из URL (если возможно)
          const urlParams = new URLSearchParams(window.location.search);
          const userId = urlParams.get('userId') || '';
          
          if (userId) {
            console.log('Используем userId из URL параметров:', userId);
            onAuthSuccess(userId);
          } else {
            console.error('Не удалось получить ID пользователя ни из WebApp, ни из URL');
            // Используем тестовый ID в качестве крайней меры
            onAuthSuccess('427032240');
          }
        }
      } catch (error) {
        console.error('Ошибка при инициализации Telegram Auth:', error);
        
        // Используем тестовый ID в качестве крайней меры
        onAuthSuccess('427032240');
      }
    };
    
    // Запускаем инициализацию с небольшой задержкой, чтобы убедиться, что Telegram WebApp загружен
    setTimeout(initTelegramAuth, 500);
    
    // Добавляем слушателя события для обновления авторизации при необходимости
    window.addEventListener('telegram-auth-update', initTelegramAuth);
    
    return () => {
      window.removeEventListener('telegram-auth-update', initTelegramAuth);
      
      // Восстанавливаем оригинальный fetch, если он был изменен
      if (window.fetch !== originalFetch) {
        window.fetch = originalFetch;
      }
    };
  }, [onAuthSuccess]);
  
  return null; // Этот компонент не отображает никакого UI
};

export default TelegramAuth; 