import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus, generateInvoice } from '../api/subscription';
import axios from 'axios';

// API_URL для относительных путей
const API_URL = '';

const SubscriptionWidget: React.FC<{ isActive?: boolean }> = ({ isActive }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [showPaymentInfo, setShowPaymentInfo] = useState<boolean>(false);
  const SUBSCRIPTION_PRICE = 1; // временно 1 Star для теста
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  const [userIdReady, setUserIdReady] = useState(false);
  const [initDataString, setInitDataString] = useState<string>('N/A'); // Новый стейт для initData
  
  const fetchSubscriptionStatus = async (currentUserId: string | null): Promise<boolean> => {
    if (!currentUserId || !/^\d+$/.test(String(currentUserId))) {
      setError('Не удалось получить корректный ID пользователя (для запроса статуса)');
      console.error('[SubscriptionWidget] fetchSubscriptionStatus: userId невалиден:', currentUserId);
      setLoading(false); // Останавливаем загрузку, т.к. запроса не будет
      return false;
    }
    console.log('[SubscriptionWidget] Запрос статуса подписки для userId:', currentUserId);
    setLoading(true);
    setError(null); // Сбрасываем предыдущие ошибки перед запросом
    try {
      const subscriptionData = await getUserSubscriptionStatus(String(currentUserId));
      setStatus(subscriptionData);
      if (typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.MainButton) {
        if (!subscriptionData.has_subscription && !isActive) {
          window.Telegram.WebApp.MainButton.show();
        } else {
          window.Telegram.WebApp.MainButton.hide();
        }
      }
      console.log('[SubscriptionWidget] Получен статус подписки:', subscriptionData);
      return subscriptionData.has_subscription;
    } catch (e: any) {
      setError('Ошибка API при получении статуса подписки: ' + (e?.message || e));
      console.error('[SubscriptionWidget] Ошибка API при получении статуса подписки:', e);
      setStatus(null); // Сбрасываем статус при ошибке API
      return false;
    } finally {
      setLoading(false);
    }
  };
  
  useEffect(() => {
    async function initializeApp() {
      console.log('[SubscriptionWidget] Инициализация приложения...');
      let resolvedId: string | null = null;

      // 1. initDataUnsafe.user.id
      if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        const potentialId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
        if (/^\d+$/.test(potentialId)) {
          resolvedId = potentialId;
          localStorage.setItem('tg_user_id', resolvedId);
          console.log('[SubscriptionWidget] userId из Telegram:', resolvedId);
        }
      }

      // 2. initData (если не нашли в п.1)
      if (!resolvedId && window.Telegram?.WebApp?.initData) {
        try {
          const params = new URLSearchParams(window.Telegram.WebApp.initData);
          const userParam = params.get('user');
          if (userParam) {
            const userObj = JSON.parse(userParam);
            if (userObj && userObj.id && /^\d+$/.test(String(userObj.id))) {
              resolvedId = String(userObj.id);
              localStorage.setItem('tg_user_id', resolvedId);
              console.log('[SubscriptionWidget] userId из initData:', resolvedId);
            }
          }
        } catch (e) {
          console.error('[SubscriptionWidget] Ошибка декодирования initData:', e);
        }
      }

      // 3. localStorage (если не нашли в п.1 и п.2)
      if (!resolvedId) {
        const storedId = localStorage.getItem('tg_user_id');
        if (storedId && /^\d+$/.test(storedId)) {
          resolvedId = storedId;
          console.log('[SubscriptionWidget] userId из localStorage:', resolvedId);
        }
      }

      // 4. Бэкенд (если не нашли нигде выше и есть initData)
      if (!resolvedId && window.Telegram?.WebApp?.initData) {
        try {
          const resp = await axios.post('/resolve-user-id', { initData: window.Telegram.WebApp.initData });
          if (resp.data && resp.data.user_id && /^\d+$/.test(String(resp.data.user_id))) {
            resolvedId = String(resp.data.user_id);
            localStorage.setItem('tg_user_id', resolvedId);
            console.log('[SubscriptionWidget] userId с бэкенда:', resolvedId);
          }
        } catch (e) {
          console.error('[SubscriptionWidget] Ошибка при запросе userId с бэкенда:', e);
        }
      }

      // Сохраняем initData в стейт после проверки
      if (window.Telegram?.WebApp?.initData) {
        setInitDataString(window.Telegram.WebApp.initData);
      }

      // --- Устанавливаем стейт и ЗАПУСКАЕМ получение статуса --- 
      if (resolvedId) {
        setUserId(resolvedId); // Устанавливаем найденный ID
        setUserIdReady(true);
        await fetchSubscriptionStatus(resolvedId); // <- Сразу запрашиваем статус с этим ID
      } else {
        // Если ID не найден ни одним способом
        setUserId(null);
        setUserIdReady(true); // Готовность к отображению (с ошибкой)
        setError("Не удалось получить корректный ID пользователя ни одним из способов.");
        console.error('[SubscriptionWidget] userId не найден нигде!');
        setLoading(false); // Останавливаем загрузку, т.к. ничего не делаем
      }
    }

    initializeApp(); // Запускаем весь процесс инициализации

    // Настройка Telegram WebApp (MainButton и events)
    // Оставим это в отдельном useEffect, т.к. оно зависит от isActive

  }, []); // Запускается один раз при монтировании
  
  // --- useEffect для настройки кнопок и событий Telegram --- 
  useEffect(() => {
    console.log('Инициализация Telegram WebApp UI...');
    if (typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp) {
      console.log('window.Telegram.WebApp найден, настраиваем UI...');
      window.Telegram.WebApp.ready();
      
      if (typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.MainButton) {
        window.Telegram.WebApp.MainButton.setText('Подписаться за ' + SUBSCRIPTION_PRICE + ' Stars');
        window.Telegram.WebApp.MainButton.color = '#2481cc';
        window.Telegram.WebApp.MainButton.textColor = '#ffffff';
        // Показываем/скрываем кнопку в зависимости от статуса (полученного ранее)
        if (status?.has_subscription) {
           window.Telegram.WebApp.MainButton.hide();
        } else {
           window.Telegram.WebApp.MainButton.show();
        }
        window.Telegram.WebApp.MainButton.onClick(handleSubscribeViaMainButton);
      } else {
        console.warn('MainButton недоступен в Telegram WebApp');
      }
      
      const handleInvoiceClosed = () => {
        console.log('Событие invoiceClosed, обновляем статус подписки');
        fetchSubscriptionStatus(userId); // Используем userId из стейта
      };

      if (typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp && typeof window.Telegram.WebApp.onEvent === 'function') {
        // Убираем обработчик popup_closed, он может быть излишним
        // window.Telegram.WebApp.onEvent('popup_closed', handleInvoiceClosed); 
        window.Telegram.WebApp.onEvent('invoiceClosed', handleInvoiceClosed); 
      } else {
        console.warn('onEvent недоступен в Telegram WebApp');
      }

      // Функция очистки для useEffect
      return () => {
        if (typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.MainButton) {
          window.Telegram.WebApp.MainButton.offClick(handleSubscribeViaMainButton);
        }
        if (typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp && typeof window.Telegram.WebApp.offEvent === 'function') {
          // window.Telegram.WebApp.offEvent('popup_closed', handleInvoiceClosed);
          window.Telegram.WebApp.offEvent('invoiceClosed', handleInvoiceClosed);
        }
      };
    }
  }, [status]); // Перезапускаем настройку UI при изменении статуса подписки
  
  const handleSubscribeViaMainButton = () => {
    console.log('Нажата главная кнопка в Telegram WebApp');
    if (window.Telegram?.WebApp?.showConfirm) {
      window.Telegram.WebApp.showConfirm(
        'Вы хотите оформить подписку за ' + SUBSCRIPTION_PRICE + ' Stars?',
        (confirmed) => {
          if (confirmed) {
            handleSubscribe();
          }
        }
      );
    } else {
      handleSubscribe();
    }
  };
  
  const handleInvoiceGeneration = async (userId: string) => {
    try {
      setIsSubscribing(true);
      const response = await fetch('/generate-stars-invoice-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, amount: SUBSCRIPTION_PRICE }) // Используем константу
      });
      const data = await response.json();
      if (data.success && data.invoice_link) {
        if (window?.Telegram?.WebApp && typeof window?.Telegram?.WebApp.openInvoice === 'function') {
          window.Telegram.WebApp.openInvoice(data.invoice_link, async (invoiceStatus) => { // <- делаем async
            console.log('[SubscriptionWidget] openInvoice callback status:', invoiceStatus);
            if (invoiceStatus === 'paid') {
              // Форсируем обновление статуса после успешной оплаты
              await fetchSubscriptionStatus(userId); 
              if (window?.Telegram?.WebApp?.showPopup) {
                window.Telegram.WebApp.showPopup({
                  title: 'Успешная оплата',
                  message: 'Ваша подписка Premium активирована!',
                  buttons: [{ type: 'ok' }]
                });
              }
            } else if (invoiceStatus === 'failed') {
              setError('Оплата не удалась. Пожалуйста, попробуйте позже.');
            } else if (invoiceStatus === 'cancelled') {
              // Не устанавливаем ошибку, просто ничего не делаем
              console.log('[SubscriptionWidget] Платеж был отменен пользователем.');
            } else if (invoiceStatus === 'pending') {
              // Можно показать сообщение о ожидании
               console.log('[SubscriptionWidget] Платеж в обработке...');
            }
            setIsSubscribing(false);
          });
        } else {
          setError('Оплата через Stars недоступна в этом окружении.');
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
  
  const handleSubscribe = async () => {
    if (!userId) {
      setError('Не удалось получить корректный ID пользователя для инициации подписки');
      return;
    }
    await handleInvoiceGeneration(userId);
  };
  
  // --- Логика рендера --- 
  
  // Показываем начальную загрузку, пока не определен пользователь
  if (!userIdReady) {
    return <div className="subscription-widget loading">Определение пользователя Telegram...</div>;
  }
  
  // Показываем ошибку, если она есть
  if (error) {
    return (
      <div className="subscription-widget error">
        <p>Ошибка: {error}</p>
        {/* Показываем кнопку Повторить только если ошибка НЕ связана с отсутствием userId */}
        {error.startsWith('Ошибка API') && (
          <button onClick={() => fetchSubscriptionStatus(userId)}>Повторить запрос статуса</button>
        )}
        {error.startsWith('Не удалось получить') && (
          <button onClick={() => {
            if (typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp && typeof window.Telegram.WebApp.close === 'function') {
              window.Telegram.WebApp.close();
            }
          }}>Закрыть</button>
        )}
        <pre style={{textAlign: 'left', fontSize: '12px', marginTop: '16px', color: '#888', background: '#222', padding: '8px', borderRadius: '6px'}}>
          userId: {userId}
          {/* Добавляем вывод статуса для отладки */} 
          {status && `\nstatus: ${JSON.stringify(status)}`}
          {/* Выводим initData только если он есть */}
          {initDataString}
          {`\nlocalStorage.tg_user_id: ${localStorage.getItem('tg_user_id')}`}
        </pre>
      </div>
    );
  }
  
  // Показываем загрузку статуса подписки
  if (loading) {
    return <div className="subscription-widget loading">Загрузка статуса подписки...</div>;
  }
  
  // --- Новый блок отображения статуса подписки ---
  // Проверяем лимиты для бесплатного плана
  const freePostLimit = 2;
  const freeAnalysisLimit = 2;
  const postGenUsed = typeof status?.post_generation_count === 'number' ? status.post_generation_count : 0;
  const analysisUsed = typeof status?.analysis_count === 'number' ? status.analysis_count : 0;
  const postGenLeft = Math.max(0, freePostLimit - postGenUsed);
  const analysisLeft = Math.max(0, freeAnalysisLimit - analysisUsed);
  const freeLimitsExceeded = postGenLeft <= 0 && analysisLeft <= 0;

  return (
    <div className="subscription-widget">
      <h3>Статус подписки</h3>
      {status?.has_subscription ? (
        <div className="subscription-active">
          <div className="status-badge premium">Премиум-подписка</div>
          <p>Ваша подписка активна{status.subscription_end_date ? ` до ${new Date(status.subscription_end_date).toLocaleString('ru-RU')}` : ''}</p>
          <p>Все функции доступны без ограничений.</p>
        </div>
      ) : (
        <div className="subscription-free">
          <div className="status-badge free">Бесплатный план</div>
          <div style={{marginBottom: 8}}>
            <b>Осталось генераций постов:</b> {postGenLeft} / {freePostLimit}<br/>
            <b>Осталось анализов каналов:</b> {analysisLeft} / {freeAnalysisLimit}
          </div>
          <div className="subscription-offer">
            <h4>Получите безлимитный доступ</h4>
            <ul>
              <li>Неограниченный анализ каналов</li>
              <li>Неограниченная генерация постов</li>
              <li>Сохранение данных в облаке</li>
            </ul>
            {/* Кнопка подписки только здесь, если нет подписки */}
            {status && !status.has_subscription && !freeLimitsExceeded && (
              <button
                className="subscribe-button"
                onClick={handleSubscribe}
                disabled={isSubscribing}
              >
                {isSubscribing ? 'Создание платежа...' : `Подписаться за ${SUBSCRIPTION_PRICE} Stars`}
              </button>
            )}
            {/* Если лимиты исчерпаны, показываем предупреждение и дату сброса */}
            {freeLimitsExceeded && (
              <div style={{color: '#d32f2f', marginTop: 8}}>
                Бесплатные лимиты исчерпаны.<br/>
                {status?.next_free_limit_reset && (
                  <>
                    <span>Следующее бесплатное использование будет доступно: <b>{new Date(status.next_free_limit_reset).toLocaleString('ru-RU')}</b></span><br/>
                  </>
                )}
                <span>Приходите через две недели или оформите подписку для безлимитного доступа.</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default SubscriptionWidget; 