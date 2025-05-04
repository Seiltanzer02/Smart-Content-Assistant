import React, { useState, useEffect, useRef } from 'react';
import './DirectPremiumStatus.css';
import { PremiumStatus, getPremiumStatus, getRawPremiumStatus, openPremiumStatusPage, forcePremiumStatus } from '../api/subscription';

interface DirectPremiumStatusProps {
  userId?: string | null;
  forcePremium?: boolean;
}

// API_URL для относительных путей
const API_URL = '';

/**
 * Компонент для прямого определения премиум-статуса пользователя
 * Использует выделенный эндпоинт API-V2 и надежное отображение статуса
 */
const DirectPremiumStatus: React.FC<DirectPremiumStatusProps> = ({ userId, forcePremium = false }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [premiumStatus, setPremiumStatus] = useState<PremiumStatus | null>(null);
  const [debugInfo, setDebugInfo] = useState<string | null>(null);
  const userIdRef = useRef<string | null>(null);
  const attempts = useRef<number>(0);
  const usingFallback = useRef<boolean>(false);

  // Проверка/получение userId из различных источников
  useEffect(() => {
    // Устанавливаем userId из пропсов, если он есть
    if (userId) {
      userIdRef.current = userId;
      console.log(`[DirectStatus] Получен userId из props: ${userId}`);
    } 
    // Иначе проверяем другие источники
    else {
      // Проверяем окно Telegram
      if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        userIdRef.current = window.Telegram.WebApp.initDataUnsafe.user.id.toString();
        console.log(`[DirectStatus] Получен userId из Telegram.WebApp: ${userIdRef.current}`);
      } 
      // Проверяем инжектированный ID
      else if (window.INJECTED_USER_ID) {
        userIdRef.current = window.INJECTED_USER_ID;
        console.log(`[DirectStatus] Получен userId из INJECTED_USER_ID: ${userIdRef.current}`);
      }
      // Проверяем localStorage
      else if (localStorage.getItem('contenthelper_user_id')) {
        userIdRef.current = localStorage.getItem('contenthelper_user_id');
        console.log(`[DirectStatus] Получен userId из localStorage: ${userIdRef.current}`);
      }
    }
    
    // Проверяем статус премиума, если userId известен
    if (userIdRef.current) {
      checkPremiumStatus();
    } else {
      setLoading(false);
      setError('ID пользователя не найден');
    }
  }, [userId]);

  // Основная функция проверки премиума
  const checkPremiumStatus = async () => {
    if (!userIdRef.current) {
      setLoading(false);
      setError('ID пользователя не найден');
      return;
    }

    setLoading(true);
    setError(null);
    attempts.current += 1;
    
    try {
      console.log(`[DirectStatus] Запрос статуса для ID: ${userIdRef.current}`);
      
      // Сначала пробуем получить статус через RAW API
      if (attempts.current <= 1 || !usingFallback.current) {
        try {
          const premiumData = await getRawPremiumStatus(userIdRef.current, `_nocache=${Date.now()}`);
          console.log(`[DirectStatus] Получен RAW ответ:`, premiumData);
          setPremiumStatus(premiumData);
          setDebugInfo(JSON.stringify(premiumData, null, 2));
          setLoading(false);
          return;
        } catch (rawError) {
          console.error('[DirectStatus] Ошибка при получении RAW статуса:', rawError);
          console.log('[DirectStatus] Переключение на обычный API...');
          usingFallback.current = true;
        }
      }
      
      // Если RAW API не сработал, используем обычный API
      const premiumData = await getPremiumStatus(userIdRef.current, `_nocache=${Date.now()}`);
      console.log(`[DirectStatus] Получен ответ:`, premiumData);
      
      // Проверяем, не получили ли мы HTML вместо JSON
      if (typeof premiumData === 'string' && 
          (premiumData.includes('<!doctype html>') || premiumData.includes('<html>'))) {
        console.error('[DirectStatus] Получен HTML вместо JSON');
        throw new Error('Получен HTML вместо данных (проблема маршрутизации API)');
      }
      
      setPremiumStatus(premiumData);
      setDebugInfo(JSON.stringify(premiumData, null, 2));
      
    } catch (err) {
      console.error('[DirectStatus] Ошибка:', err);
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка');
    } finally {
      setLoading(false);
    }
  };

  // Открытие отдельной страницы со статусом премиума
  const openStatusPage = () => {
    if (userIdRef.current) {
      openPremiumStatusPage(userIdRef.current, true);
    }
  };

  // Рендеринг компонента
  return (
    <div className="direct-premium-status">
      {loading ? (
        <div className="direct-status loading">Проверка статуса...</div>
      ) : error ? (
        <div className="direct-status error">
          {error}
          <div className="actions">
            <button 
              className="refresh-button"
              onClick={checkPremiumStatus}
            >
              Проверить снова
            </button>
            
            {/* Кнопка для открытия отдельной страницы */}
            {userIdRef.current && (
              <button 
                className="status-page-button"
                onClick={openStatusPage}
              >
                Открыть страницу
              </button>
            )}
            
            {/* Добавляем кнопку для диагностики */}
            {userIdRef.current && (
              <button 
                className="debug-button"
                onClick={() => {
                  // Открываем диагностический эндпоинт в новом окне
                  window.open(`/api/subscription/debug/${userIdRef.current}?create_test=true`, '_blank');
                }}
              >
                Диагностика
              </button>
            )}
          </div>
          
          {/* Форма для ручного ввода userId */}
          <div className="manual-userid-form">
            <input 
              type="text" 
              placeholder="Введите ваш ID вручную" 
              defaultValue={userIdRef.current || ''}
              onChange={(e) => {
                const value = e.target.value.trim();
                if (value && !isNaN(Number(value))) {
                  userIdRef.current = value;
                  localStorage.setItem('contenthelper_user_id', value);
                }
              }}
            />
            <button onClick={checkPremiumStatus}>Проверить</button>
            
            {/* Кнопка для принудительной установки премиум статуса */}
            <button 
              className="force-premium-button" 
              onClick={() => {
                if (!userIdRef.current) return;
                forcePremiumStatus(userIdRef.current, true, 30);
                // Обновим состояние компонента тоже
                setPremiumStatus({
                  has_premium: true,
                  user_id: userIdRef.current,
                  error: null,
                  subscription_end_date: new Date(Date.now() + 30*24*60*60*1000).toISOString(),
                  analysis_count: 9999,
                  post_generation_count: 9999
                });
                setError(null);
                setLoading(false);
              }}
            >
              Премиум 👑
            </button>
          </div>
        </div>
      ) : premiumStatus?.has_premium || forcePremium ? (
        <div className="direct-status premium">
          <div className="premium-badge">
            <span className="premium-icon">⭐</span>
            ПРЕМИУМ
          </div>
          
          {forcePremium && !premiumStatus?.has_premium && (
            <div className="forced-premium-badge">
              <span className="forced-note">Принудительно активирован</span>
            </div>
          )}
          
          {premiumStatus?.subscription_end_date && (
            <div className="expiry-date">
              Подписка активна до: {new Date(premiumStatus.subscription_end_date).toLocaleDateString()}
            </div>
          )}
          
          {/* Кнопка для открытия отдельной страницы */}
          <button 
            className="status-page-button"
            onClick={openStatusPage}
          >
            Подробнее
          </button>
          
          {debugInfo && (
            <div className="debug-data">
              <details>
                <summary>Данные для отладки</summary>
                <pre>{debugInfo}</pre>
              </details>
            </div>
          )}
        </div>
      ) : (
        <div className="direct-status free">
          <div className="free-badge">Бесплатный доступ</div>
          <p>Для получения расширенного функционала приобретите подписку</p>
          
          {/* Кнопка для открытия отдельной страницы */}
          <button 
            className="status-page-button"
            onClick={openStatusPage}
          >
            Подробнее
          </button>
          
          {debugInfo && (
            <div className="debug-data">
              <details>
                <summary>Данные для отладки</summary>
                <pre>{debugInfo}</pre>
              </details>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DirectPremiumStatus; 