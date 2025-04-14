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
  const [debugInfo, setDebugInfo] = useState<string>('');

  useEffect(() => {
    console.log('TelegramAuth компонент загружен');
    
    const initAuth = async () => {
      try {
        console.log('Инициализация Telegram WebApp...');
        console.log('WebApp до инициализации:', WebApp);
        
        // Проверяем, доступен ли WebApp
        if (!WebApp) {
          console.error('WebApp не доступен, объект не существует');
          throw new Error('WebApp не доступен');
        }
        
        // Более подробная информация о WebApp
        console.log('WebApp тип:', typeof WebApp);
        console.log('WebApp имеет метод ready:', typeof WebApp.ready === 'function');
        console.log('WebApp имеет initDataUnsafe:', typeof WebApp.initDataUnsafe);
        
        // Инициализируем Telegram WebApp
        WebApp.ready();
        console.log('WebApp.ready() вызван');
        
        // Получаем данные пользователя
        const user = WebApp.initDataUnsafe?.user;
        console.log('Данные пользователя:', user);
        
        // Проверка содержимого данных
        if (!WebApp.initDataUnsafe) {
          console.warn('WebApp.initDataUnsafe отсутствует или null');
        } else {
          console.log('WebApp.initDataUnsafe имеет свойство user:', 'user' in WebApp.initDataUnsafe);
        }
        
        // Проверяем данные запуска
        console.log('WebApp.initData:', WebApp.initData);
        console.log('Пытаемся распарсить initData');
        try {
          if (WebApp.initData) {
            const parsedData = JSON.parse(decodeURIComponent(WebApp.initData));
            console.log('Распарсенные данные:', parsedData);
          }
        } catch (parseError) {
          console.error('Ошибка при парсинге initData:', parseError);
        }
        
        // Собираем отладочную информацию
        const debugData = {
          initData: WebApp.initDataUnsafe,
          initDataRaw: WebApp.initData,
          platform: WebApp.platform,
          version: WebApp.version,
          colorScheme: WebApp.colorScheme,
          themeParams: WebApp.themeParams,
          isExpanded: WebApp.isExpanded,
          viewportHeight: WebApp.viewportHeight,
          viewportStableHeight: WebApp.viewportStableHeight,
          headerColor: WebApp.headerColor,
          backgroundColor: WebApp.backgroundColor,
          isClosingConfirmationEnabled: WebApp.isClosingConfirmationEnabled,
          BackButton: WebApp.BackButton,
          MainButton: WebApp.MainButton,
          HapticFeedback: WebApp.HapticFeedback,
          close: WebApp.close,
          expand: WebApp.expand,
          showPopup: WebApp.showPopup,
          showAlert: WebApp.showAlert,
          showConfirm: WebApp.showConfirm,
          ready: WebApp.ready,
          initDataUnsafe: WebApp.initDataUnsafe,
        };
        
        setDebugInfo(JSON.stringify(debugData, null, 2));
        
        if (user?.id) {
          console.log('ID пользователя получен:', user.id);
          // Если есть ID пользователя, вызываем успешную авторизацию
          onAuthSuccess(user.id.toString());
        } else {
          console.warn('ID пользователя не найден в WebApp.initDataUnsafe.user');
          
          // Попробуем получить ID из initData
          const initData = WebApp.initDataUnsafe;
          if (initData?.user?.id) {
            console.log('ID пользователя найден в initData:', initData.user.id);
            onAuthSuccess(initData.user.id.toString());
          } else {
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