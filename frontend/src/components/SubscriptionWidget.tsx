import React, { useState, useEffect, useRef } from 'react';
import '../styles/SubscriptionWidget.css';
import { SubscriptionStatus } from '../api/subscription';
import { Button, Box, Typography, CircularProgress, Paper } from '@mui/material';
import moment from 'moment';

// Константы
const SUBSCRIPTION_PRICE = 1; // временно 1 Star для теста

// Вспомогательная функция для проверки валидности даты end_date
const isEndDateValid = (dateStr: string | null | undefined): boolean => {
  if (!dateStr) return false;
  
  try {
    const endDate = new Date(dateStr);
    const now = new Date();
    return !isNaN(endDate.getTime()) && endDate > now;
  } catch (e) {
    console.error(`[SubscriptionWidget] Ошибка при проверке даты: ${e}`);
    return false;
  }
};

const SubscriptionWidget: React.FC<{
  userId: string | null;
  subscriptionStatus: SubscriptionStatus | null;
  onSubscriptionUpdate: () => void;
  isActive?: boolean;
}> = ({ userId, subscriptionStatus, onSubscriptionUpdate }) => {
  // Основные состояния
  const [error, setError] = useState<string | null>(null);
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshLog, setRefreshLog] = useState<string[]>([]);
  const [lastUpdateTime, setLastUpdateTime] = useState<string>(
    new Date().toLocaleTimeString()
  );

  // Вычисленные состояния
  const [calculatedIsActive, setCalculatedIsActive] = useState<boolean>(false);
  const [validEndDate, setValidEndDate] = useState<boolean>(false);
  
  // Состояние UI
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  
  // Рефы для таймеров и монтирования
  const mountedRef = useRef(true);
  const statusIntervalRef = useRef<number | null>(null);

  // Добавление записи в лог обновлений
  const addToRefreshLog = (message: string) => {
    setRefreshLog(prev => {
      const newLog = [`[${new Date().toLocaleTimeString()}] ${message}`, ...prev];
      return newLog.slice(0, 10); // Храним только 10 последних записей
    });
    setLastUpdateTime(new Date().toLocaleTimeString());
  };

  // Обновление вычисленных состояний при изменении данных подписки
  useEffect(() => {
    try {
      if (subscriptionStatus) {
        console.log('[SubscriptionWidget] 🔄 Обработка новых данных subscriptionStatus:', subscriptionStatus);
        
        // Проверка валидности end_date
        const hasValidEndDate = isEndDateValid(subscriptionStatus.subscription_end_date);
        setValidEndDate(hasValidEndDate);
        
        // Расчет статуса активности по всем критериям
        const isActive = hasValidEndDate || (subscriptionStatus.is_active && subscriptionStatus.has_subscription);
        setCalculatedIsActive(isActive);
        
        // Логирование
        addToRefreshLog(`Статус: has_sub=${subscriptionStatus.has_subscription}, is_active=${subscriptionStatus.is_active}, end_date=${subscriptionStatus.subscription_end_date || 'null'}`);
        
        // Выявление несоответствий
        if (hasValidEndDate && (!subscriptionStatus.is_active || !subscriptionStatus.has_subscription)) {
          console.warn('[SubscriptionWidget] ⚠️ Несоответствие: end_date валидна, но статус неактивен');
          addToRefreshLog(`⚠️ Несоответствие: date_end валидна, но статус неактивен`);
        }
      } else {
        console.log('[SubscriptionWidget] subscriptionStatus отсутствует');
        setCalculatedIsActive(false);
        setValidEndDate(false);
      }
    } catch (err) {
      console.error('[SubscriptionWidget] Ошибка при обработке данных подписки:', err);
      setError('Ошибка при обработке данных о подписке');
    }
  }, [subscriptionStatus]);

  // Функция для обновления статуса подписки
  const refreshSubscriptionStatus = async () => {
    if (!userId || isRefreshing) return;
    
    try {
      console.log('[SubscriptionWidget] 🔄 Запрос принудительного обновления статуса...');
      setIsRefreshing(true);
      addToRefreshLog('Запрос обновления статуса...');
      
      await onSubscriptionUpdate();
      
      addToRefreshLog('✅ Статус успешно обновлен');
    } catch (err) {
      console.error('[SubscriptionWidget] ❌ Ошибка при обновлении статуса:', err);
      setError('Не удалось обновить статус подписки');
      addToRefreshLog(`❌ Ошибка обновления: ${err}`);
    } finally {
      if (mountedRef.current) {
        setIsRefreshing(false);
      }
    }
  };

  // Инициализация компонента и установка интервала для опроса статуса
  useEffect(() => {
    console.log('[SubscriptionWidget] Инициализация компонента');
    refreshSubscriptionStatus();
    
    // Установка интервала для регулярного опроса статуса
    statusIntervalRef.current = window.setInterval(() => {
      if (mountedRef.current) {
        console.log('[SubscriptionWidget] Плановая проверка статуса');
        onSubscriptionUpdate();
      }
    }, 30000); // Проверка каждые 30 секунд
    
    return () => {
      mountedRef.current = false;
      if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
      }
      console.log('[SubscriptionWidget] Компонент размонтирован');
    };
  }, [userId, onSubscriptionUpdate]);

  // Инициализация Telegram WebApp
  useEffect(() => {
    try {
      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.ready();
        
        if (window.Telegram.WebApp.MainButton) {
          window.Telegram.WebApp.MainButton.setText(`Подписаться за ${SUBSCRIPTION_PRICE} Stars`);
          window.Telegram.WebApp.MainButton.color = '#2481cc';
          window.Telegram.WebApp.MainButton.textColor = '#ffffff';
          
          if (calculatedIsActive) {
            window.Telegram.WebApp.MainButton.hide();
          } else {
            window.Telegram.WebApp.MainButton.show();
            window.Telegram.WebApp.MainButton.onClick(handleSubscribeViaMainButton);
          }
        }
        
        if (typeof window.Telegram.WebApp.onEvent === 'function') {
          window.Telegram.WebApp.onEvent('popup_closed', () => {
            console.log('[SubscriptionWidget] popup_closed event');
            onSubscriptionUpdate();
          });
          
          window.Telegram.WebApp.onEvent('invoiceClosed', () => {
            console.log('[SubscriptionWidget] invoiceClosed event');
            onSubscriptionUpdate();
          });
        }
      }
    } catch (e) {
      console.error('[SubscriptionWidget] Ошибка при инициализации Telegram WebApp:', e);
    }
  }, [calculatedIsActive, onSubscriptionUpdate]);

  // Очистка MainButton при размонтировании
  useEffect(() => {
    return () => {
      try {
        if (window.Telegram?.WebApp?.MainButton && typeof window.Telegram.WebApp.MainButton.offClick === 'function') {
          window.Telegram.WebApp.MainButton.offClick(handleSubscribeViaMainButton);
        }
      } catch (e) {
        console.error('[SubscriptionWidget] Ошибка при очистке MainButton:', e);
      }
    };
  }, []);

  // Обработчик клика на MainButton
  const handleSubscribeViaMainButton = () => {
    try {
      console.log('[SubscriptionWidget] Нажатие на MainButton для подписки');
      if (window.Telegram?.WebApp?.showConfirm) {
        window.Telegram.WebApp.showConfirm(
          `Вы хотите оформить подписку за ${SUBSCRIPTION_PRICE} Stars?`,
          (confirmed) => {
            if (confirmed) {
              handleSubscribe();
            }
          }
        );
      } else {
        handleSubscribe();
      }
    } catch (e) {
      console.error('[SubscriptionWidget] Ошибка при обработке MainButton:', e);
      setError('Ошибка при обработке кнопки');
    }
  };

  // Обработчик подписки
  const handleSubscribe = async () => {
    if (!userId) {
      setError('Не удалось получить ID пользователя');
      return;
    }
    
    await handleInvoiceGeneration(userId);
  };

  // Функция генерации и открытия инвойса для оплаты Stars
  const handleInvoiceGeneration = async (userId: string) => {
    if (!window.Telegram?.WebApp) {
      setError('Не удалось инициализировать Telegram WebApp для оплаты');
      return;
    }

    try {
      setIsSubscribing(true);
      
      const response = await fetch('/generate-stars-invoice-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, amount: SUBSCRIPTION_PRICE })
      });
      
      const data = await response.json();
      console.log('[SubscriptionWidget] Ответ от /generate-stars-invoice-link:', data);
      
      if (data.success && data.invoice_link) {
        if (typeof window.Telegram.WebApp.openInvoice === 'function') {
          window.Telegram.WebApp.openInvoice(data.invoice_link, async (status) => {
            setIsSubscribing(false);
            console.log(`[SubscriptionWidget] openInvoice callback статус: ${status}`);
            
            if (status === 'paid') {
              console.log('[SubscriptionWidget] Платеж успешен, обновляем статус...');
              
              // Серия запросов статуса с интервалами
              const intervals = [1000, 2000, 3000, 5000, 10000];
              
              await onSubscriptionUpdate();
              
              for (const interval of intervals) {
                await new Promise(resolve => setTimeout(resolve, interval));
                await onSubscriptionUpdate();
              }
              
              if (window.Telegram.WebApp.showPopup) {
                window.Telegram.WebApp.showPopup({
                  title: 'Успешная оплата',
                  message: 'Подписка активирована! Обновляем статус...',
                  buttons: [{ type: 'ok' }]
                });
              }
            }
          });
        } else {
          setError('Оплата через Stars недоступна в этом окружении');
          setIsSubscribing(false);
        }
      } else {
        setError(data.error || 'Ошибка генерации инвойса');
        setIsSubscribing(false);
      }
    } catch (error) {
      setError(`Ошибка: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`);
      setIsSubscribing(false);
    }
  };

  // Переключатель отображения информации об оплате
  const togglePaymentInfo = () => setShowPaymentInfo(!showPaymentInfo);

  // Обработка отсутствия userId
  if (!userId) {
    return (
      <Paper elevation={3} sx={{ p: 3, mb: 3, borderRadius: 2 }}>
        <Typography variant="h6" align="center" color="error" gutterBottom>
          Ошибка идентификации пользователя
        </Typography>
        <Typography>
          Не удалось получить корректный ID пользователя. Пожалуйста, перезапустите приложение.
        </Typography>
      </Paper>
    );
  }

  // Обработка ошибок
  if (error) {
    return (
      <Paper elevation={3} sx={{ p: 3, mb: 3, borderRadius: 2 }}>
        <Typography variant="h6" align="center" color="error" gutterBottom>
          Ошибка
        </Typography>
        <Typography paragraph>{error}</Typography>
        <Button 
          variant="contained" 
          onClick={refreshSubscriptionStatus} 
          disabled={isRefreshing}
        >
          {isRefreshing ? 'Обновление...' : 'Попробовать снова'}
        </Button>
      </Paper>
    );
  }

  // Отображение загрузки
  if (!subscriptionStatus) {
    return (
      <Paper elevation={3} sx={{ p: 3, mb: 3, borderRadius: 2, textAlign: 'center' }}>
        <CircularProgress size={40} />
        <Typography variant="body1" sx={{ mt: 2 }}>
          Загрузка информации о подписке...
        </Typography>
      </Paper>
    );
  }

  // Основной рендеринг
  return (
    <Paper elevation={3} sx={{ p: 3, mb: 3, borderRadius: 2 }}>
      <Typography variant="h5" align="center" gutterBottom>
        Статус подписки
      </Typography>
      
      {calculatedIsActive ? (
        // Отображение для активной подписки
        <>
          <div className="status-badge premium">Премиум</div>
          <Box sx={{ mt: 2, mb: 2 }}>
            <Typography variant="h6" align="center" color="success.main" gutterBottom>
              Премиум активен
            </Typography>
            
            {subscriptionStatus.subscription_end_date && (
              <Typography variant="body2" align="center" color="text.secondary">
                Активен до: {moment(subscriptionStatus.subscription_end_date).format('DD.MM.YYYY')}
              </Typography>
            )}
          </Box>
          
          <div className="subscription-active">
            <Typography variant="body1" paragraph>
              У вас активирована премиум-подписка, открывающая полный доступ к функциям:
            </Typography>
            <ul>
              <li>Неограниченный анализ каналов</li>
              <li>Расширенная генерация идей</li>
              <li>Доступ к базе изображений</li>
              <li>Планирование и автоматизация публикаций</li>
            </ul>
          </div>
        </>
      ) : (
        // Отображение для неактивной подписки
        <>
          <div className="status-badge free">Бесплатный план</div>
          <Box sx={{ mt: 2, mb: 2 }}>
            <Typography variant="h6" align="center" gutterBottom>
              Бесплатный план
            </Typography>
          </Box>
          
          <div className="subscription-free">
            <Typography variant="body1" paragraph>
              Используйте премиум-подписку для полного доступа ко всем функциям приложения.
            </Typography>
            
            <div className="subscription-offer">
              <Typography variant="h6" gutterBottom>
                Премиум-подписка включает:
              </Typography>
              <ul>
                <li>Неограниченный анализ каналов</li>
                <li>Расширенную генерацию идей</li>
                <li>Доступ к базе изображений</li>
                <li>Планирование и автоматизацию публикаций</li>
              </ul>
              
              <Button 
                variant="contained" 
                color="primary"
                onClick={handleSubscribe}
                disabled={isSubscribing}
                fullWidth
                sx={{ mt: 2, mb: 1 }}
              >
                {isSubscribing ? 'Создание платежа...' : 'Получить премиум доступ'} 
              </Button>
              
              <Typography 
                variant="body2" 
                sx={{ mt: 1, textAlign: 'center', cursor: 'pointer', color: 'primary.main' }}
                onClick={togglePaymentInfo}
              >
                {showPaymentInfo ? 'Скрыть информацию об оплате' : 'Как оплатить?'}
              </Typography>
              
              {showPaymentInfo && (
                <Box sx={{ mt: 2, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
                  <Typography variant="h6" gutterBottom>
                    Информация об оплате
                  </Typography>
                  <Typography variant="body2" paragraph>
                    Оплата производится через Telegram Stars:
                  </Typography>
                  <ol>
                    <li>Нажмите на кнопку "Получить премиум доступ"</li>
                    <li>Подтвердите платеж в Telegram</li>
                    <li>После успешной оплаты премиум-статус будет активирован</li>
                  </ol>
                  <Typography variant="caption" display="block">
                    * Стоимость подписки: {SUBSCRIPTION_PRICE} Telegram Stars
                  </Typography>
                  <Button 
                    variant="outlined" 
                    size="small" 
                    onClick={togglePaymentInfo} 
                    sx={{ mt: 1 }}
                  >
                    Закрыть
                  </Button>
                </Box>
              )}
            </div>
          </div>
        </>
      )}
      
      {/* Блок для ручного обновления статуса */}
      <Box sx={{ mt: 3, textAlign: 'center' }}>
        <Button
          variant="outlined"
          size="small"
          onClick={refreshSubscriptionStatus}
          disabled={isRefreshing}
          startIcon={isRefreshing ? <CircularProgress size={16} /> : null}
        >
          {isRefreshing ? 'Обновление...' : 'Обновить статус'}
        </Button>
        <Typography variant="caption" display="block" sx={{ mt: 1 }}>
          Последнее обновление: {lastUpdateTime}
        </Typography>
      </Box>
      
      {/* Отладочная информация о подписке */}
      <Box sx={{ mt: 3 }}>
        <details>
          <summary style={{ cursor: 'pointer' }}>
            <Typography variant="caption">Информация о подписке (для отладки)</Typography>
          </summary>
          <Box component="pre" sx={{ 
            mt: 2, 
            p: 1, 
            fontSize: '0.7rem',
            bgcolor: '#f5f5f5',
            borderRadius: 1,
            overflowX: 'auto'
          }}>
            {JSON.stringify({
              userId,
              subscriptionStatus: {
                has_subscription: subscriptionStatus.has_subscription,
                is_active: subscriptionStatus.is_active,
                subscription_end_date: subscriptionStatus.subscription_end_date
              },
              calculatedIsActive,
              validEndDate,
              lastUpdateTime
            }, null, 2)}
          </Box>
          
          <Typography variant="caption" sx={{ mt: 2, display: 'block' }}>
            Журнал обновлений:
          </Typography>
          <Box component="pre" sx={{ 
            mt: 1, 
            p: 1, 
            fontSize: '0.7rem',
            bgcolor: '#f5f5f5',
            borderRadius: 1,
            maxHeight: '150px',
            overflowY: 'auto'
          }}>
            {refreshLog.join('\n')}
          </Box>
        </details>
      </Box>
    </Paper>
  );
};

export default SubscriptionWidget; 