import React, { useState, useEffect } from 'react';
import axios from 'axios';
import WebApp from '@twa-dev/sdk';
import './TelegramAuth.css';

// Добавляем определение типов для Telegram
declare global {
  interface Window {
    Telegram?: {
      WebApp?: any;
    };
  }
}

// Безопасная работа с хранилищем
const safeStorageOperation = (operation: () => any): any => {
  try {
    return operation();
  } catch (e) {
    console.warn('Ошибка при работе с хранилищем:', e);
    return null;
  }
};

// Генерация временного ID для демо-режима
const generateTempUserId = () => {
  return '123456789'; // Стандартный тестовый ID
};

interface TelegramAuthProps {
  onAuthSuccess: (userId: string) => void;
}

export const TelegramAuth: React.FC<TelegramAuthProps> = ({ onAuthSuccess }) => {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [debugInfo, setDebugInfo] = useState<string>('');

  // Функция для гарантированного получения ID пользователя
  const ensureUserId = () => {
    // В реальном приложении в Telegram всегда должен быть testUserId:
    const testUserId = generateTempUserId();
    console.log('Используем тестовый ID пользователя:', testUserId);
    safeStorageOperation(() => sessionStorage.setItem('telegram_user_id', testUserId));
    onAuthSuccess(testUserId);
  };

  useEffect(() => {
    console.log('TelegramAuth компонент загружен');
    
    const initAuth = async () => {
      try {
        console.log('Инициализация Telegram WebApp...');
        
        // Попытка восстановить sessionStorage данные, если есть
        const cachedUserId = safeStorageOperation(() => sessionStorage.getItem('telegram_user_id'));
        if (cachedUserId) {
          console.log('ID пользователя восстановлен из sessionStorage:', cachedUserId);
          onAuthSuccess(cachedUserId);
          return;
        }
        
        // Проверка наличия WebApp в window
        if (window.Telegram && window.Telegram.WebApp) {
          console.log('Telegram.WebApp найден в window');
          
          // Используем нативный объект Telegram.WebApp вместо SDK
          const nativeWebApp = window.Telegram.WebApp;
          console.log('Используем нативный Telegram.WebApp');
          
          // Инициализируем нативный WebApp
          if (typeof nativeWebApp.ready === 'function') {
            nativeWebApp.ready();
            console.log('nativeWebApp.ready() вызван');
          }
          
          // Получаем данные пользователя из нативного WebApp
          const user = nativeWebApp.initDataUnsafe?.user;
          console.log('Данные пользователя из нативного WebApp:', user);
          
          if (user?.id) {
            console.log('ID пользователя получен из нативного WebApp:', user.id);
            safeStorageOperation(() => sessionStorage.setItem('telegram_user_id', user.id.toString()));
            onAuthSuccess(user.id.toString());
            return;
          } else {
            console.log('ID пользователя не найден в нативном WebApp, продолжаем с SDK');
          }
        } else {
          console.log('Telegram.WebApp не найден в window, используем @twa-dev/sdk');
        }
        
        // Запасной вариант - используем SDK от @twa-dev/sdk
        console.log('WebApp SDK тип:', typeof WebApp);
        
        // Инициализируем SDK WebApp
        if (typeof WebApp.ready === 'function') {
          WebApp.ready();
          console.log('WebApp.ready() вызван');
        }
        
        // Получаем данные пользователя из SDK
        const user = WebApp.initDataUnsafe?.user;
        console.log('Данные пользователя из SDK:', user);
        
        if (user?.id) {
          console.log('ID пользователя получен из SDK:', user.id);
          safeStorageOperation(() => sessionStorage.setItem('telegram_user_id', user.id.toString()));
          onAuthSuccess(user.id.toString());
          return;
        }
        
        // Попробуем получить ID из query параметров
        const urlParams = new URLSearchParams(window.location.search);
        const userId = urlParams.get('user_id');
        
        if (userId) {
          console.log('ID пользователя найден в URL параметрах:', userId);
          safeStorageOperation(() => sessionStorage.setItem('telegram_user_id', userId));
          onAuthSuccess(userId);
          return;
        }
        
        console.log('Не удалось получить ID пользователя стандартными способами, используем тестовый ID');
        // В Telegram это всегда должно сработать
        ensureUserId();
        
      } catch (err) {
        console.error('Ошибка при инициализации Telegram WebApp:', err);
        setError(`Ошибка при инициализации приложения: ${err instanceof Error ? err.message : String(err)}`);
        // Даже при ошибке продолжаем с тестовым ID
        ensureUserId();
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
          <h1 className="auth-title">Внимание</h1>
          <div className="auth-error">{error}</div>
          <p>Нажмите на кнопку ниже, чтобы продолжить с тестовым ID</p>
          
          <button 
            className="auth-button"
            onClick={() => ensureUserId()}
          >
            Продолжить с тестовым ID
          </button>
        </div>
      </div>
    );
  }

  return null;
}; 