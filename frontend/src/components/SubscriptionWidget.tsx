import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus } from '../api/subscription'; // Убираем generateInvoice, если он не используется здесь напрямую
import { toast } from 'react-hot-toast';

interface SubscriptionWidgetProps {
  userId: string | null;
}

// Определяем возможные состояния виджета для большей ясности
type WidgetState = 'loading' | 'error' | 'subscribed' | 'not_subscribed';

const SubscriptionWidget: React.FC<SubscriptionWidgetProps> = ({ userId }) => {
  // Используем одно состояние для отслеживания текущего этапа
  const [widgetState, setWidgetState] = useState<WidgetState>('loading');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // Состояние для хранения данных подписки (может быть null)
  const [subscriptionDetails, setSubscriptionDetails] = useState<SubscriptionStatus | null>(null);

  const SUBSCRIPTION_PRICE = 1; // в Stars
  const [isProcessingPayment, setIsProcessingPayment] = useState(false); // Переименовано для ясности

  // --- Функция получения статуса ---
  const fetchSubscriptionStatus = async () => {
    // Сразу переводим в состояние загрузки при каждом вызове
    setWidgetState('loading');
    setErrorMsg(null);
    setSubscriptionDetails(null); // Сбрасываем детали перед запросом

    if (!userId) {
      console.warn('[fetchSubscriptionStatus] userId отсутствует.');
      setErrorMsg('Ошибка: ID пользователя не определен.');
      setWidgetState('error');
      // Скрываем кнопку подписки, если ID нет
      if (window.Telegram?.WebApp?.MainButton) {
        window.Telegram.WebApp.MainButton.hide();
      }
      return; // Прерываем выполнение
    }

    try {
      console.log(`[fetchSubscriptionStatus] Запрос статуса для userId: ${userId}`);
      const data = await getUserSubscriptionStatus(userId);
      console.log('[fetchSubscriptionStatus] Данные получены:', data);

      setSubscriptionDetails(data); // Сохраняем полученные детали

      // Определяем следующее состояние виджета на основе данных
      if (data && data.has_subscription) {
        setWidgetState('subscribed');
        // Скрываем кнопку ТГ
        if (window.Telegram?.WebApp?.MainButton) {
          window.Telegram.WebApp.MainButton.hide();
        }
      } else {
        setWidgetState('not_subscribed');
         // Показываем кнопку ТГ
         if (window.Telegram?.WebApp?.MainButton) {
           window.Telegram.WebApp.MainButton.show();
         }
      }
    } catch (err: any) {
      console.error('[fetchSubscriptionStatus] Ошибка:', err);
      setErrorMsg(err.response?.data?.detail || err.message || 'Ошибка при загрузке статуса');
      setWidgetState('error');
      // Скрываем кнопку ТГ при ошибке
      if (window.Telegram?.WebApp?.MainButton) {
         window.Telegram.WebApp.MainButton.hide();
      }
    }
  };

  // --- Эффекты ---
  useEffect(() => {
    // Настройка Telegram WebApp (выполняется один раз)
    console.log('Инициализация и настройка Telegram WebApp...');
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();

      if (tg.MainButton) {
        tg.MainButton.setText(`Подписаться за ${SUBSCRIPTION_PRICE} Stars`);
        tg.MainButton.color = '#2481cc';
        tg.MainButton.textColor = '#ffffff';
        tg.MainButton.hide(); // Начинаем со скрытой кнопки
        tg.MainButton.onClick(handleSubscribeViaMainButton);
      } else {
        console.warn('MainButton недоступен в Telegram WebApp');
      }

      // Обработчик закрытия окна оплаты
      if (typeof tg.onEvent === 'function') {
        tg.onEvent('popup_closed', handlePopupClosed);
      }
      
      // --- ДОБАВЛЕНО: Обработчик изменения видимости --- 
      if (typeof tg.onEvent === 'function') {
        tg.onEvent('viewportChanged', handleViewportChanged);
      }
      // --- КОНЕЦ ДОБАВЛЕНИЯ ---
      
    } else {
      console.warn('window.Telegram.WebApp не найден!');
    }

    // Функция очистки
    return () => {
      if (tg?.MainButton) {
        tg.MainButton.offClick(handleSubscribeViaMainButton);
        tg.MainButton.hide();
      }
      if (typeof tg?.offEvent === 'function'){
         tg.offEvent('popup_closed', handlePopupClosed);
         // --- ДОБАВЛЕНО: Удаление обработчика изменения видимости --- 
         tg.offEvent('viewportChanged', handleViewportChanged);
         // --- КОНЕЦ ДОБАВЛЕНИЯ ---
      }
    };
  }, []); // Пустой массив зависимостей - выполняется один раз

  // Эффект для загрузки статуса при изменении userId
  useEffect(() => {
    console.log(`[useEffect userId] userId изменился на: ${userId}, вызываем fetchSubscriptionStatus`);
    fetchSubscriptionStatus();
  }, [userId]);


  // --- Обработчики ---
  
  // --- ДОБАВЛЕНО: Выносим обработчики событий в отдельные функции --- 
  const handlePopupClosed = () => {
    console.log('Popup оплаты закрыт, обновляем статус...');
    fetchSubscriptionStatus(); // Перезапрашиваем статус
  };
  
  const handleViewportChanged = async (eventPayload: { isStateStable: boolean }) => {
    console.log('Viewport changed:', eventPayload);
    // Перезапрашиваем статус, только если viewport стабилен и приложение стало видимым
    // (проверка на видимость может быть неточной, но isStateStable полезна)
    if (eventPayload.isStateStable) {
       console.log('Viewport стабилен, обновляем статус подписки...');
       await fetchSubscriptionStatus(); 
    }
  };
  // --- КОНЕЦ ДОБАВЛЕНИЯ ---
  
  const handleSubscribeViaMainButton = () => {
    console.log('Нажата главная кнопка в Telegram WebApp');
    if (window.Telegram?.WebApp?.showConfirm) {
      window.Telegram.WebApp.showConfirm(
        `Вы хотите оформить подписку за ${SUBSCRIPTION_PRICE} Stars?`,
        (confirmed) => {
          if (confirmed) {
            initiatePaymentFlow(); // Запускаем процесс оплаты
          }
        }
      );
    } else {
      initiatePaymentFlow();
    }
  };

  // Переименованная функция для ясности
  const initiatePaymentFlow = async () => {
     if (!userId) {
        setErrorMsg("Не удалось получить ID пользователя для оплаты.");
        setWidgetState('error');
        return;
     }

     setIsProcessingPayment(true);
     setErrorMsg(null); // Сбрасываем предыдущие ошибки

    try {
       const numericUserId = parseInt(userId, 10); // ID для API инвойса - число
       if (isNaN(numericUserId)){
           throw new Error("Некорректный формат ID пользователя");
       }

      // Запрос ссылки на инвойс с бэкенда
      // Используем fetch, т.к. не импортировали generateInvoice из api/subscription
      const response = await fetch('/generate-stars-invoice-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: numericUserId, amount: SUBSCRIPTION_PRICE })
      });

      if (!response.ok) {
          // Пытаемся получить детали ошибки из ответа
          let errorDetail = `HTTP ошибка ${response.status}`;
          try {
              const errorData = await response.json();
              errorDetail = errorData.detail || errorData.error || errorDetail;
          } catch (jsonError) {
              // Ошибка парсинга JSON, используем статус
          }
          throw new Error(errorDetail);
      }

      const data = await response.json();

      if (data.success && data.invoice_link) {
        if (window?.Telegram?.WebApp?.openInvoice) {
          window.Telegram.WebApp.openInvoice(data.invoice_link, (status) => {
             console.log(`Статус инвойса: ${status}`);
            if (status === 'paid') {
              // Даем время на обработку webhook и обновляем статус
               toast.success('Оплата прошла успешно! Обновляем статус...');
              setTimeout(fetchSubscriptionStatus, 2000); // Обновляем через 2 сек
              // Можно добавить повторные попытки, как было раньше, если 2 сек мало
            } else if (status === 'failed') {
               setErrorMsg('Оплата не удалась. Пожалуйста, попробуйте позже.');
               setWidgetState('not_subscribed'); // Возвращаем в состояние без подписки
            } else if (status === 'cancelled') {
               setErrorMsg('Платеж был отменен.');
                setWidgetState('not_subscribed');
            } else { // pending и др.
                setErrorMsg(`Статус платежа: ${status}. Обновите статус вручную позже.`);
                setWidgetState('not_subscribed');
            }
            setIsProcessingPayment(false); // Завершаем процесс в любом случае
          });
        } else {
          throw new Error('Метод openInvoice не доступен в Telegram WebApp.');
        }
      } else {
        throw new Error(data.error || 'Ошибка генерации ссылки на инвойс.');
      }
    } catch (error) {
      console.error('Ошибка в процессе инициирования оплаты:', error);
      setErrorMsg(`Ошибка оплаты: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`);
      setWidgetState('error'); // Переводим в состояние ошибки
      setIsProcessingPayment(false);
    }
  };

  // --- Рендеринг ---

  // 1. Состояние загрузки
  if (widgetState === 'loading') {
    return <div className="subscription-widget loading">Загрузка информации о подписке...</div>;
  }

  // 2. Состояние ошибки
  if (widgetState === 'error') {
    return (
      <div className="subscription-widget error">
        <p>Ошибка: {errorMsg || 'Неизвестная ошибка'}</p>
        {/* Позволяем повторить попытку, если есть userId */}
        {userId && <button onClick={fetchSubscriptionStatus} >Повторить</button>}
      </div>
    );
  }

  // 3. Состояния подписки (subscribed / not_subscribed)
  // Детали берем из subscriptionDetails
  const details = subscriptionDetails; // Может быть null, если была ошибка, но widgetState не 'error'

  return (
    <div className="subscription-widget">
      <h3>Статус подписки</h3>

      {widgetState === 'subscribed' ? (
        // Состояние "Подписан"
        <div className="subscription-active">
          <div className="status-badge premium">Premium</div>
          <p>
            У вас активная подписка
            {details?.subscription_end_date
              ? ` до ${new Date(details.subscription_end_date).toLocaleDateString()}`
              : ''}
          </p>
          <p>Все функции доступны без ограничений</p>
          {/* Отладка */}
          <p>
             Отладка: State='subscribed', has_subscription = {String(details?.has_subscription)}, тип: {typeof details?.has_subscription}
          </p>
        </div>
      ) : (
        // Состояние "Не подписан" (widgetState === 'not_subscribed')
        <div className="subscription-free">
          <div className="status-badge free">Бесплатный план</div>
          <p>Использовано анализов: {details?.analysis_count ?? 0}/2</p>
          <p>Использовано генераций постов: {details?.post_generation_count ?? 0}/2</p>
          {/* Отладка */}
           <p>
             Отладка: State='not_subscribed', has_subscription = {String(details?.has_subscription)}, тип: {typeof details?.has_subscription}
          </p>

          {/* Кнопка подписки */}
          <div className="subscription-offer">
             <h4>Получите безлимитный доступ</h4>
              <ul>
                <li>Неограниченный анализ каналов</li>
                <li>Неограниченная генерация постов</li>
                <li>Сохранение данных в облаке</li>
              </ul>
            <button
              className="subscribe-button"
              onClick={initiatePaymentFlow} // Используем новую функцию
              disabled={isProcessingPayment}
            >
              {isProcessingPayment ? 'Обработка...' : `Подписаться за ${SUBSCRIPTION_PRICE} Star`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SubscriptionWidget; 