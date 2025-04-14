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
    const initAuth = async () => {
      try {
        console.log('Инициализация Telegram WebApp...');
        
        // Проверяем, доступен ли WebApp
        if (!WebApp) {
          throw new Error('WebApp не доступен');
        }
        
        // Инициализируем Telegram WebApp
        WebApp.ready();
        console.log('WebApp.ready() вызван');
        
        // Получаем данные пользователя
        const user = WebApp.initDataUnsafe?.user;
        console.log('Данные пользователя:', user);
        
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
              setError('Не удалось получить ID пользователя Telegram');
            }
          }
        }
      } catch (err) {
        console.error('Ошибка при инициализации Telegram WebApp:', err);
        setError(`Ошибка при инициализации приложения: ${err instanceof Error ? err.message : String(err)}`);
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