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

interface TelegramAuthProps {
  onAuthSuccess: (userId: string) => void;
}

export const TelegramAuth: React.FC<TelegramAuthProps> = ({ onAuthSuccess }) => {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [debugInfo, setDebugInfo] = useState<string>('');

  useEffect(() => {
    console.log('TelegramAuth компонент загружен');
    
    const initAuth = async () => {
      try {
        console.log('Инициализация Telegram WebApp...');
        
        // Проверка наличия WebApp в window
        if (window.Telegram && window.Telegram.WebApp) {
          console.log('Telegram.WebApp найден в window');
          
          // Используем нативный объект Telegram.WebApp вместо SDK
          const nativeWebApp = window.Telegram.WebApp;
          console.log('Используем нативный Telegram.WebApp');
          console.log('WebApp имеет метод ready:', typeof nativeWebApp.ready === 'function');
          
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
            onAuthSuccess(user.id.toString());
            return;
          }
        } else {
          console.log('Telegram.WebApp не найден в window, используем @twa-dev/sdk');
        }
        
        // Запасной вариант - используем SDK от @twa-dev/sdk
        console.log('WebApp SDK тип:', typeof WebApp);
        console.log('WebApp SDK имеет метод ready:', typeof WebApp.ready === 'function');
        
        // Инициализируем SDK WebApp
        WebApp.ready();
        console.log('WebApp.ready() вызван');
        
        // Получаем данные пользователя из SDK
        const user = WebApp.initDataUnsafe?.user;
        console.log('Данные пользователя из SDK:', user);
        
        // Проверка содержимого данных
        if (!WebApp.initDataUnsafe) {
          console.warn('WebApp.initDataUnsafe отсутствует или null');
        } else {
          console.log('WebApp.initDataUnsafe имеет свойство user:', 'user' in WebApp.initDataUnsafe);
        }
        
        // Собираем отладочную информацию
        const debugData = {
          window_telegram_exists: Boolean(window.Telegram),
          window_telegram_webapp_exists: Boolean(window.Telegram?.WebApp),
          sdk_web_app_exists: Boolean(WebApp),
          initData: WebApp.initDataUnsafe,
          initDataRaw: WebApp.initData,
          platform: WebApp.platform,
          version: WebApp.version,
          colorScheme: WebApp.colorScheme,
        };
        
        setDebugInfo(JSON.stringify(debugData, null, 2));
        
        if (user?.id) {
          console.log('ID пользователя получен из SDK:', user.id);
          onAuthSuccess(user.id.toString());
        } else {
          console.warn('ID пользователя не найден в WebApp.initDataUnsafe.user');
          
          // Попробуем получить ID из query параметров
          const urlParams = new URLSearchParams(window.location.search);
          const userId = urlParams.get('user_id');
          
          if (userId) {
            console.log('ID пользователя найден в URL параметрах:', userId);
            onAuthSuccess(userId);
          } else {
            console.error('ID пользователя не найден ни в WebApp, ни в URL параметрах');
            // Предоставляем временный ID для тестирования (только для разработки!)
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
              console.warn('Используем тестовый ID пользователя для локальной разработки: 123456789');
              onAuthSuccess('123456789');
              return;
            }
            
            setError('Не удалось получить ID пользователя Telegram');
          }
        }
      } catch (err) {
        console.error('Ошибка при инициализации Telegram WebApp:', err);
        setError(`Ошибка при инициализации приложения: ${err instanceof Error ? err.message : String(err)}`);
        
        // Для тестирования в режиме разработки
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
          console.warn('Используем тестовый ID пользователя для локальной разработки после ошибки: 123456789');
          onAuthSuccess('123456789');
        }
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
          
          <button 
            className="auth-button"
            onClick={() => onAuthSuccess('123456789')}
          >
            Продолжить с тестовым ID
          </button>
          
          {debugInfo && (
            <div className="debug-info">
              <h3>Отладочная информация:</h3>
              <pre>{debugInfo}</pre>
            </div>
          )}
        </div>
      </div>
    );
  }

  return null;
}; 