import React, { useState, useEffect, useRef, useCallback } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus } from '../api/subscription'; // Убираем generateInvoice, если он не используется здесь напрямую
import { toast } from 'react-hot-toast';

// Дефолтный статус, чтобы избежать undefined
const defaultStatus: SubscriptionStatus = {
  has_subscription: false,
  analysis_count: 0,
  post_generation_count: 0,
  subscription_end_date: undefined,
};

interface SubscriptionWidgetProps {
  userId: string | null;
}

// Определяем возможные состояния виджета для большей ясности
type WidgetState = 'loading' | 'error' | 'subscribed' | 'not_subscribed';

const SubscriptionWidget: React.FC<SubscriptionWidgetProps> = ({ userId }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // Инициализируем status дефолтным объектом
  const [status, setStatus] = useState<SubscriptionStatus>(defaultStatus);
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);
  const isFetching = useRef(false); // Флаг для предотвращения гонок запросов

  const SUBSCRIPTION_PRICE = 1; // в Stars

  // Используем useCallback для стабильности функции fetch
  const fetchSubscriptionStatus = useCallback(async () => {
    // Предотвращаем одновременные запросы
    if (isFetching.current) {
        console.log('[fetchSubscriptionStatus] Пропуск вызова: предыдущий запрос еще выполняется.');
        return;
    }
    isFetching.current = true;
    setLoading(true);
    setError(null);

    if (!userId) {
      console.warn('[fetchSubscriptionStatus] userId отсутствует.');
      setError('Ошибка: ID пользователя не определен.');
      setStatus(defaultStatus); // Сбрасываем к дефолту при отсутствии ID
      if (window.Telegram?.WebApp?.MainButton) {
          window.Telegram.WebApp.MainButton.hide();
      }
      setLoading(false);
      isFetching.current = false;
      return;
    }

    try {
      console.log(`[fetchSubscriptionStatus] Запрос статуса для userId: ${userId}`);
      const data = await getUserSubscriptionStatus(userId);
      console.log('[fetchSubscriptionStatus] Данные получены:', data);

      // Проверяем, что данные получены и имеют поле has_subscription
      if (data && typeof data.has_subscription === 'boolean') {
        setStatus(data); // Устанавливаем полученные данные
        if (data.has_subscription) {
           if (window.Telegram?.WebApp?.MainButton) window.Telegram.WebApp.MainButton.hide();
        } else {
           if (window.Telegram?.WebApp?.MainButton) window.Telegram.WebApp.MainButton.show();
        }
      } else {
         console.warn('[fetchSubscriptionStatus] Получены некорректные данные или отсутствует has_subscription:', data);
         setError('Ошибка: Некорректные данные статуса.');
         setStatus(defaultStatus); // Сбрасываем к дефолту при некорректных данных
         if (window.Telegram?.WebApp?.MainButton) window.Telegram.WebApp.MainButton.hide();
      }

    } catch (err: any) {
      console.error('[fetchSubscriptionStatus] Ошибка:', err);
      setError(err.response?.data?.detail || err.message || 'Ошибка при загрузке статуса');
      setStatus(defaultStatus); // Сбрасываем к дефолту при ошибке
      if (window.Telegram?.WebApp?.MainButton) window.Telegram.WebApp.MainButton.hide();
    } finally {
      setLoading(false);
      isFetching.current = false; // Сбрасываем флаг
    }
  // Включаем userId в зависимости useCallback
  }, [userId]);

  // --- Эффекты ---
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg) {
        console.warn('window.Telegram.WebApp не найден!');
        return;
    }

    console.log('Инициализация и настройка Telegram WebApp...');
    tg.ready();

    // Обработчик изменения видимости
    const handleViewportChanged = (eventPayload: { isStateStable: boolean }) => {
        console.log('Viewport changed:', eventPayload);
        if (eventPayload.isStateStable) {
            console.log('Viewport стабилен, обновляем статус подписки...');
            fetchSubscriptionStatus(); // Используем useCallback-версию
        }
    };
    
    // Обработчик закрытия попапа оплаты
    const handlePopupClosed = () => {
        console.log('Popup оплаты закрыт, обновляем статус...');
        fetchSubscriptionStatus(); // Используем useCallback-версию
    };

    // Настройка кнопок и событий
    if (tg.MainButton) {
        tg.MainButton.setText(`Подписаться за ${SUBSCRIPTION_PRICE} Stars`);
        tg.MainButton.color = '#2481cc';
        tg.MainButton.textColor = '#ffffff';
        tg.MainButton.hide(); // Прячем по умолчанию, пока статус не загружен
        tg.MainButton.onClick(handleSubscribeViaMainButton);
    }
    if (typeof tg.onEvent === 'function') {
        tg.onEvent('popup_closed', handlePopupClosed); 
        tg.onEvent('viewportChanged', handleViewportChanged);
    }

    // Функция очистки
    return () => {
        console.log('Очистка обработчиков SubscriptionWidget...');
        if (tg?.MainButton) {
            tg.MainButton.offClick(handleSubscribeViaMainButton);
            tg.MainButton.hide();
        }
        if (typeof tg?.offEvent === 'function') {
            tg.offEvent('popup_closed', handlePopupClosed);
            tg.offEvent('viewportChanged', handleViewportChanged);
        }
    };
  // fetchSubscriptionStatus теперь в useCallback и зависит от userId, поэтому его можно убрать отсюда
  // userId как зависимость для основного useEffect не нужен, так как есть отдельный useEffect ниже
  }, [fetchSubscriptionStatus]); // Добавляем fetchSubscriptionStatus в зависимости

  // Эффект для первоначальной загрузки и при смене userId
  useEffect(() => {
    console.log(`[useEffect userId] userId изменился: ${userId}. Вызов fetchSubscriptionStatus.`);
    fetchSubscriptionStatus();
  }, [userId, fetchSubscriptionStatus]); // fetchSubscriptionStatus добавлен как зависимость

  // --- Обработчики ---
  const handleSubscribeViaMainButton = () => {
    console.log('Нажата главная кнопка в Telegram WebApp');
    if (window.Telegram?.WebApp?.showConfirm) {
        window.Telegram.WebApp.showConfirm(
          `Вы хотите оформить подписку за ${SUBSCRIPTION_PRICE} Stars?`,
          (confirmed) => {
            if (confirmed) {
              initiatePaymentFlow();
            }
          }
        );
    } else {
        initiatePaymentFlow();
    }
  };

  const initiatePaymentFlow = async () => {
     if (!userId) {
        setError("Не удалось получить ID пользователя для оплаты.");
        return;
     }

     setIsProcessingPayment(true);
     setError(null);

    try {
       const numericUserId = parseInt(userId, 10);
       if (isNaN(numericUserId)){
           throw new Error("Некорректный формат ID пользователя");
       }

      const response = await fetch('/generate-stars-invoice-link', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: numericUserId, amount: SUBSCRIPTION_PRICE })
      });

      if (!response.ok) {
          let errorDetail = `HTTP ошибка ${response.status}`;
          try {
              const errorData = await response.json();
              errorDetail = errorData.detail || errorData.error || errorDetail;
          } catch (jsonError) { /* ignore */ }
          throw new Error(errorDetail);
      }
      const data = await response.json();
      if (data.success && data.invoice_link) {
          if (window?.Telegram?.WebApp?.openInvoice) {
              window.Telegram.WebApp.openInvoice(data.invoice_link, (invoiceStatus) => {
                  console.log(`Статус инвойса: ${invoiceStatus}`);
                  if (invoiceStatus === 'paid') {
                      toast.success('Оплата прошла успешно! Обновляем статус...');
                      setTimeout(fetchSubscriptionStatus, 2500); // Небольшая задержка перед обновлением
                  } else if (invoiceStatus === 'failed') {
                      setError('Оплата не удалась.');
                  } else if (invoiceStatus === 'cancelled') {
                      setError('Платеж был отменен.');
                  } else {
                      setError(`Статус платежа: ${invoiceStatus}.`);
                  }
                  setIsProcessingPayment(false);
              });
          } else { throw new Error('Метод openInvoice не доступен.'); }
      } else { throw new Error(data.error || 'Ошибка генерации ссылки.'); }
    } catch (error) {
      console.error('Ошибка в процессе инициирования оплаты:', error);
      setError(`Ошибка оплаты: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`);
      setIsProcessingPayment(false);
    }
  };

  // --- Рендеринг ---

  // Показываем загрузку, пока loading=true ИЛИ если статус еще дефолтный (на случай быстрой первой загрузки)
  if (loading && status === defaultStatus) {
    return <div className="subscription-widget loading">Загрузка информации о подписке...</div>;
  }

  // Показываем ошибку, если она есть
  if (error) {
    return (
      <div className="subscription-widget error">
        <p>Ошибка: {error}</p>
        {userId && <button onClick={fetchSubscriptionStatus} disabled={loading}>Повторить</button>}
      </div>
    );
  }

  // Основной рендеринг на основе status.has_subscription
  return (
    <div className="subscription-widget">
      <h3>Статус подписки</h3>

      {status.has_subscription ? (
        // Состояние "Подписан"
        <div className="subscription-active">
          <div className="status-badge premium">Premium</div>
          <p>
            У вас активная подписка
            {status.subscription_end_date
              ? ` до ${new Date(status.subscription_end_date).toLocaleDateString()}`
              : ''}
          </p>
          <p>Все функции доступны без ограничений</p>
          {/* Отладка */}
          <p>
             Отладка: has_subscription = {String(status.has_subscription)}, тип: {typeof status.has_subscription}
          </p>
        </div>
      ) : (
        // Состояние "Не подписан"
        <div className="subscription-free">
          <div className="status-badge free">Бесплатный план</div>
          <p>Использовано анализов: {status.analysis_count}/2</p>
          <p>Использовано генераций постов: {status.post_generation_count}/2</p>
          {/* Отладка */}
           <p>
             Отладка: has_subscription = {String(status.has_subscription)}, тип: {typeof status.has_subscription}
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
              onClick={initiatePaymentFlow}
              disabled={isProcessingPayment || loading} // Блокируем во время обработки/загрузки
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