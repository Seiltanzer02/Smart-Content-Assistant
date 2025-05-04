import React, { useEffect } from 'react';
import axios from 'axios';

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
              
              console.log(`TelegramAuth: Отправка запроса к ${typeof input === 'string' ? input : 'объекту Request'} с заголовками:`, init.headers);
              
              return originalFetch.call(this, input, init);
            };
            
            // Также устанавливаем заголовки по умолчанию для axios, если он используется
            try {
              if (axios && axios.defaults) {
                axios.defaults.headers.common['X-Telegram-User-Id'] = userId;
                console.log('TelegramAuth: Заголовки Axios настроены');
                
                // Добавляем интерцептор для логирования запросов axios
                axios.interceptors.request.use(
                  (config) => {
                    console.log(`TelegramAuth: Axios запрос к ${config.url} с заголовками:`, config.headers);
                    return config;
                  },
                  (error) => {
                    console.error('TelegramAuth: Ошибка запроса Axios:', error);
                    return Promise.reject(error);
                  }
                );
              }
            } catch (axiosError) {
              console.log('TelegramAuth: Axios не удалось настроить заголовки', axiosError);
            }
            
            // Передаем ID пользователя родительскому компоненту
            onAuthSuccess(userId);
            
            // Устанавливаем локальное хранилище для сохранения ID между сессиями
            try {
              localStorage.setItem('telegram_user_id', userId);
              console.log('TelegramAuth: ID пользователя сохранен в localStorage');
            } catch (storageError) {
              console.warn('TelegramAuth: Не удалось сохранить ID в localStorage:', storageError);
            }
            
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
              
              // Проверяем localStorage как последнее средство
              const savedUserId = localStorage.getItem('telegram_user_id');
              if (savedUserId) {
                console.log('Используем сохраненный userId из localStorage:', savedUserId);
                onAuthSuccess(savedUserId);
              } else {
                // Используем тестовый ID в качестве крайней меры
                const defaultUserId = '427032240';
                console.warn(`Используем тестовый ID в качестве крайней меры: ${defaultUserId}`);
                onAuthSuccess(defaultUserId);
              }
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
            
            // Проверяем localStorage как последнее средство
            const savedUserId = localStorage.getItem('telegram_user_id');
            if (savedUserId) {
              console.log('Используем сохраненный userId из localStorage:', savedUserId);
              onAuthSuccess(savedUserId);
            } else {
              // Используем тестовый ID в качестве крайней меры
              const defaultUserId = '427032240';
              console.warn(`Используем тестовый ID в качестве крайней меры: ${defaultUserId}`);
              onAuthSuccess(defaultUserId);
            }
          }
        }
      } catch (error) {
        console.error('Ошибка при инициализации Telegram Auth:', error);
        
        // Проверяем localStorage как последнее средство при ошибке
        try {
          const savedUserId = localStorage.getItem('telegram_user_id');
          if (savedUserId) {
            console.log('При ошибке используем сохраненный userId из localStorage:', savedUserId);
            onAuthSuccess(savedUserId);
            return;
          }
        } catch (storageError) {
          console.warn('Не удалось получить ID из localStorage при ошибке:', storageError);
        }
        
        // Используем тестовый ID в качестве крайней меры
        const defaultUserId = '427032240';
        console.warn(`При ошибке используем тестовый ID: ${defaultUserId}`);
        onAuthSuccess(defaultUserId);
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