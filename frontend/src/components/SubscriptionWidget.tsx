import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus, generateInvoice } from '../api/subscription';
// Убираем axios, так как генерация инвойса теперь через API
// import axios from 'axios';
import { toast } from 'react-hot-toast';

// API_URL для относительных путей
const API_URL = '';

// Ожидаем userId как обязательный проп
interface SubscriptionWidgetProps {
  userId: string | null;
  // Убираем isActive, так как статус будем получать сами
  // isActive?: boolean;
}

const SubscriptionWidget: React.FC<SubscriptionWidgetProps> = ({ userId }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  // const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false); // Не используется
  const SUBSCRIPTION_PRICE = 1; // временно 1 Star для теста
  const [isSubscribing, setIsSubscribing] = useState(false);
  // Убираем локальное состояние userId и userIdReady
  // const [userId, setUserId] = useState<string | null>(null);
  // const [userIdReady, setUserIdReady] = useState(false);

  // Убираем useEffect для получения userId
  // useEffect(() => { ... resolveUserId ... }, []);

  // useEffect для инициализации Telegram UI и подписки на события
  useEffect(() => {
    console.log('SubscriptionWidget: Инициализация Telegram WebApp UI...');

    if (window.Telegram?.WebApp) {
      console.log('SubscriptionWidget: window.Telegram.WebApp найден, настраиваем...');

      window.Telegram.WebApp.ready(); // Вызываем ready здесь

      // Управление MainButton переносим в fetchSubscriptionStatus/handleSubscribe
      // if (window.Telegram.WebApp.MainButton) { ... }

      // Добавляем обработчики событий один раз при монтировании
      const handleInvoiceClosed = (eventData?: { slug?: string; status?: 'paid' | 'cancelled' | 'failed' | 'pending' }) => {
        console.log('SubscriptionWidget: Событие invoiceClosed', eventData);
        // Добавляем небольшую задержку перед обновлением статуса
        setTimeout(() => {
          console.log('SubscriptionWidget: Обновляем статус подписки после invoiceClosed');
          fetchSubscriptionStatus();
        }, 1500); // Задержка 1.5 секунды
      };

      const handlePopupClosed = (eventData?: { button_id?: string }) => {
        console.log('SubscriptionWidget: Popup закрыт', eventData);
        // Обновляем статус, если это было окно подтверждения оплаты
        if (eventData?.button_id === 'ok') {
          console.log('SubscriptionWidget: Обновляем статус подписки после popup_closed (ok)');
          fetchSubscriptionStatus();
        }
      };

      // Используем API SDK если доступно
      const TWA = window.Telegram.WebApp;
      if (typeof TWA.onEvent === 'function') {
        TWA.onEvent('invoiceClosed', handleInvoiceClosed);
        TWA.onEvent('popupClosed', handlePopupClosed); // Используем popupClosed вместо popup_closed
      } else {
        console.warn('SubscriptionWidget: TWA.onEvent не найден!');
      }

      // Функция очистки при размонтировании
      return () => {
        console.log('SubscriptionWidget: Очистка обработчиков событий...');
        if (typeof TWA.offEvent === 'function') {
          TWA.offEvent('invoiceClosed', handleInvoiceClosed);
          TWA.offEvent('popupClosed', handlePopupClosed);
        }
        // Скрываем MainButton при уходе со страницы подписки
        if (TWA.MainButton?.isVisible) {
          TWA.MainButton.offClick(handleSubscribeViaMainButton); // Отписываемся от клика
          TWA.MainButton.hide();
        }
      };
    } else {
      console.warn('SubscriptionWidget: window.Telegram.WebApp не найден!');
      setError("Telegram WebApp не инициализирован. Пожалуйста, перезапустите приложение.")
      setLoading(false);
      return; // Выходим, если TWA недоступен
    }
  }, []); // Пустой массив зависимостей - выполняем один раз

  // useEffect для получения статуса при изменении userId (из пропсов)
  useEffect(() => {
    // Сбрасываем ошибку и статус при смене пользователя (если он стал null)
    setError(null);
    setStatus(null);
    setLoading(true); // Устанавливаем загрузку при смене пользователя или его появлении

    if (userId && /^\\d+$/.test(userId)) {
      console.log(`SubscriptionWidget: userId (${userId}) валиден, запрашиваем статус.`);
      setError(null); // сбрасываем ошибку, если userId валиден
      fetchSubscriptionStatus();
    } else if (userId === null || userId === undefined) {
       console.warn('[SubscriptionWidget] userId еще не получен или null.');
       // Не устанавливаем ошибку сразу, даем время App.tsx передать userId
       setLoading(true); // Остаемся в состоянии загрузки
    } else {
      console.error('[SubscriptionWidget] Получен невалидный userId:', userId);
      setError('Не удалось получить корректный ID пользователя');
      setLoading(false); // Завершаем загрузку с ошибкой
    }
    // Зависимость только от userId
  }, [userId]);

  const fetchSubscriptionStatus = async (): Promise<boolean> => {
    // Проверяем userId прямо перед запросом
    if (!userId || !/^\\d+$/.test(String(userId))) {
       console.error('[SubscriptionWidget] fetchSubscriptionStatus: userId невалиден или отсутствует:', userId);
      // Не устанавливаем глобальную ошибку, просто выходим
      // setError('Не удалось получить корректный ID пользователя');
      setLoading(false); // Завершаем загрузку, если ID нет
      return false;
    }

    console.log(`[SubscriptionWidget] Запрос статуса подписки для userId: ${userId}`);
    setLoading(true); // Начинаем загрузку
    try {
      const subscriptionData = await getUserSubscriptionStatus(userId); // Передаем userId из пропса
      console.log('[SubscriptionWidget] Получен статус подписки:', subscriptionData);

      if (typeof subscriptionData === 'object' && 'error' in subscriptionData && subscriptionData.error) {
        setError('Ошибка при получении статуса подписки: ' + subscriptionData.error);
        setStatus(null);
        // Скрываем кнопку, если была ошибка
        if (window.Telegram?.WebApp?.MainButton?.isVisible) {
           window.Telegram.WebApp.MainButton.hide();
        }
        return false;
      }

      setStatus(subscriptionData);
      setError(null); // Сбрасываем предыдущие ошибки если запрос успешен

      // Управление MainButton после получения статуса
      const TWA = window.Telegram?.WebApp;
      if (TWA?.MainButton) {
        if (!subscriptionData.has_subscription) {
          TWA.MainButton.setText(`Подписаться за ${SUBSCRIPTION_PRICE} Stars`);
          TWA.MainButton.color = '#2481cc'; // Синий цвет для подписки
          TWA.MainButton.textColor = '#ffffff';
          TWA.MainButton.enable(); // Убедимся, что кнопка активна
          // Удаляем старый обработчик перед добавлением нового
          TWA.MainButton.offClick(handleSubscribeViaMainButton);
          TWA.MainButton.onClick(handleSubscribeViaMainButton);
          TWA.MainButton.show();
          console.log('[SubscriptionWidget] MainButton показана для подписки');
        } else {
          // Если подписка активна, просто скрываем кнопку
          if (TWA.MainButton.isVisible) {
            TWA.MainButton.offClick(handleSubscribeViaMainButton);
            TWA.MainButton.hide();
            console.log('[SubscriptionWidget] MainButton скрыта (подписка активна)');
          }
        }
      } else {
        console.warn('[SubscriptionWidget] MainButton не доступна для настройки');
      }

      return subscriptionData.has_subscription;
    } catch (e: any) {
      setError('Ошибка при получении статуса подписки: ' + (e?.message || e));
      setStatus(null);
      console.error('[SubscriptionWidget] Ошибка при получении статуса подписки:', e);
       // Скрываем кнопку при ошибке
      if (window.Telegram?.WebApp?.MainButton?.isVisible) {
         window.Telegram.WebApp.MainButton.hide();
      }
      return false;
    } finally {
      setLoading(false); // Завершаем загрузку в любом случае
    }
  };

  const handleSubscribeViaMainButton = () => {
    console.log('[SubscriptionWidget] Нажата главная кнопка Telegram');
    // Убедимся что userId есть перед показом подтверждения
     if (!userId || !/^\\d+$/.test(userId)) {
      console.error('[SubscriptionWidget] Попытка подписки без валидного userId:', userId);
      setError('Не удалось получить ID пользователя для начала подписки.');
      return;
     }

    if (window.Telegram?.WebApp?.showConfirm) {
      window.Telegram.WebApp.showConfirm(
        `Вы хотите оформить подписку за ${SUBSCRIPTION_PRICE} Stars?`,
        (confirmed) => {
          if (confirmed) {
             console.log('[SubscriptionWidget] Подписка подтверждена пользователем');
            handleSubscribe();
          } else {
             console.log('[SubscriptionWidget] Подписка отменена пользователем');
          }
        }
      );
    } else {
      // Если showConfirm недоступен, сразу инициируем подписку
      console.warn('[SubscriptionWidget] showConfirm недоступен, подписываем сразу');
      handleSubscribe();
    }
  };

  // Используем generateInvoice из api/subscription
  const handleInvoiceGeneration = async (currentUserId: string) => {
     if (!currentUserId) {
       console.error('[SubscriptionWidget] handleInvoiceGeneration вызван без userId');
       setError('ID пользователя не найден для генерации инвойса.');
       return;
     }
     console.log(`[SubscriptionWidget] Генерация инвойса для userId: ${currentUserId}`);
     setIsSubscribing(true);
     setError(null); // Сбрасываем предыдущие ошибки
    try {
      // Генерируем инвойс через API бэкенда
      const response = await fetch('/generate-stars-invoice-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // Передаем user_id как число
        body: JSON.stringify({ user_id: parseInt(currentUserId, 10), amount: SUBSCRIPTION_PRICE })
      });

      if (!response.ok) {
          const errorData = await response.json().catch(() => ({ error: 'Network or JSON parse error' }));
          throw new Error(errorData.error || `HTTP error ${response.status}`);
      }

      const data = await response.json();

      if (data.success && data.invoice_link) {
         console.log('[SubscriptionWidget] Инвойс успешно сгенерирован:', data.invoice_link);
        const TWA = window?.Telegram?.WebApp;
        if (TWA && typeof TWA.openInvoice === 'function') {
           console.log('[SubscriptionWidget] Открываем инвойс через TWA.openInvoice');
          TWA.openInvoice(data.invoice_link, (invoiceStatus) => {
             console.log(`[SubscriptionWidget] Статус инвойса из openInvoice callback: ${invoiceStatus}`);
            if (invoiceStatus === 'paid') {
               console.log('[SubscriptionWidget] Инвойс оплачен (событие openInvoice)');
               // Не показываем popup здесь, ждем webhook и событие invoiceClosed/popupClosed
              // fetchSubscriptionStatus(); // Не вызываем здесь, ждем invoiceClosed
              // TWA.showPopup({...});
              toast.success('Оплата прошла успешно! Статус подписки скоро обновится.', { duration: 4000 });

            } else if (invoiceStatus === 'failed') {
               console.error('[SubscriptionWidget] Оплата не удалась (событие openInvoice)');
              setError('Оплата не удалась. Пожалуйста, попробуйте позже.');
              toast.error('Оплата не удалась. Пожалуйста, попробуйте позже.');
            } else if (invoiceStatus === 'cancelled') {
               console.log('[SubscriptionWidget] Платеж был отменен (событие openInvoice)');
              // Не показываем ошибку, если пользователь сам отменил
              // setError('Платеж был отменен.');
              toast('Оформление подписки отменено.');
            } else if (invoiceStatus === 'pending') {
                console.log('[SubscriptionWidget] Платеж в обработке (событие openInvoice)');
                toast.loading('Платеж обрабатывается...'); // Показываем индикатор
            }
            // Убираем isSubscribing только если статус не pending
            if (invoiceStatus !== 'pending') {
                setIsSubscribing(false);
                // Обновляем состояние кнопки после завершения платежа (успех/неудача/отмена)
                if (TWA.MainButton && !status?.has_subscription) {
                    TWA.MainButton.enable(); // Включаем кнопку снова
                }
            }
          });
           // Блокируем кнопку пока инвойс открыт
           if (TWA.MainButton) {
               TWA.MainButton.disable();
           }
        } else {
           console.error('[SubscriptionWidget] TWA.openInvoice не доступна');
          setError('Оплата через Stars недоступна в этом окружении.');
          setIsSubscribing(false);
        }
      } else {
         console.error('[SubscriptionWidget] Ошибка генерации инвойса (ответ API):', data.error);
        setError(data.error || 'Ошибка генерации инвойса');
        setIsSubscribing(false);
      }
    } catch (error) {
       console.error('[SubscriptionWidget] Критическая ошибка при генерации/открытии инвойса:', error);
      setError(`Ошибка: ${error instanceof Error ? error.message : 'Неизвестная ошибка при оплате'}`);
      setIsSubscribing(false);
       // Включаем кнопку при ошибке
       if (window.Telegram?.WebApp?.MainButton) {
           window.Telegram.WebApp.MainButton.enable();
       }
    }
  };

  const handleSubscribe = async () => {
     // Еще раз проверяем userId перед генерацией инвойса
    if (!userId) {
      console.error('[SubscriptionWidget] handleSubscribe: userId отсутствует');
      setError('Не удалось получить корректный ID пользователя');
      return;
    }
    console.log(`[SubscriptionWidget] Инициируем подписку для userId: ${userId}`);
    await handleInvoiceGeneration(userId); // Передаем текущий userId
  };

  // Отображение загрузки
  if (loading && !status && !error) { // Показываем только если нет статуса и ошибки
    return <div className="subscription-widget loading">Загрузка информации о подписке...</div>;
  }

  // Отображение ошибки (приоритетнее статуса)
  if (error) {
    return (
      <div className="subscription-widget error">
        <p><strong>Ошибка</strong><br/>{error}</p>
        {/* Показываем кнопку Повторить только если есть userId для повтора */}
        {userId && <button onClick={fetchSubscriptionStatus} disabled={loading}>Повторить</button>}
        {/* Убираем отладочную информацию
        <pre style={{...}}>
          userId: {userId}
          ...
        </pre>
        */}
      </div>
    );
  }

   // Сообщение если userId все еще не получен после начальной загрузки
  if (!userId && !loading) {
      return (
          <div className="subscription-widget error">
              <p><strong>Ошибка</strong><br/>Не удалось определить пользователя Telegram. Пожалуйста, перезапустите приложение.</p>
          </div>
      );
  }


  // Отображение статуса подписки
  return (
    <div className="subscription-widget">
      <h3>Статус подписки</h3>

      {status?.has_subscription ? (
        <div className="status active">
          <p>✅ Ваша подписка <strong>Premium</strong> активна.</p>
          {status.subscription_end_date && (
            <p>Действительна до: {new Date(status.subscription_end_date).toLocaleString('ru-RU')}</p>
          )}
          <p>Доступно анализов: {status.analysis_count}</p>
          <p>Доступно генераций постов: {status.post_generation_count}</p>
        </div>
      ) : (
        <div className="status inactive">
          <p>❌ У вас нет активной подписки Premium.</p>
          <p>Подписка дает неограниченное количество анализов каналов и генераций постов.</p>
          {/* Основная кнопка подписки теперь Telegram MainButton */}
          {/* <button onClick={handleSubscribe} disabled={isSubscribing || loading}>
            {isSubscribing ? 'Обработка...' : `Оформить подписку за ${SUBSCRIPTION_PRICE} Stars`}
          </button> */}
          {isSubscribing && <p><i>Инициируем процесс оплаты...</i></p>}
        </div>
      )}
    </div>
  );
};

export default SubscriptionWidget; 