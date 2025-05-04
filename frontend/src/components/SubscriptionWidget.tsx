import React, { useState, useEffect } from 'react';
import '../styles/SubscriptionWidget.css';
import { getUserSubscriptionStatus, SubscriptionStatus } from '../api/subscription';

interface SubscriptionWidgetProps {
  userId: string | null;
  isActive?: boolean;
}

const SubscriptionWidget: React.FC<SubscriptionWidgetProps> = ({ userId, isActive }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [isSubscribing, setIsSubscribing] = useState(false);
  const SUBSCRIPTION_PRICE = 1; // Цена подписки

  const fetchSubscriptionStatus = async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const fetchedStatus = await getUserSubscriptionStatus(userId);
      setStatus(fetchedStatus);
    } catch (err: any) {
      setError(err.message || 'Ошибка при получении статуса подписки');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubscriptionStatus();
    // Настраиваем MainButton только если компонент активен (на своей вкладке)
    if (isActive && window?.Telegram?.WebApp && window?.Telegram?.WebApp.MainButton) {
        window.Telegram.WebApp.MainButton.show();
        window.Telegram.WebApp.MainButton.setText('Подписаться за ' + SUBSCRIPTION_PRICE + ' Star');
        window.Telegram.WebApp.MainButton.color = '#2481cc';
        window.Telegram.WebApp.MainButton.textColor = '#ffffff';
        window.Telegram.WebApp.MainButton.enable();
        window.Telegram.WebApp.MainButton.onClick(handlePaymentClick);
    } else if (window?.Telegram?.WebApp && window?.Telegram?.WebApp.MainButton) {
        // Скрываем кнопку, если виджет не активен (на другой вкладке)
        window.Telegram.WebApp.MainButton.hide();
    }
    // Очистка при размонтировании
    return () => {
        if (window?.Telegram?.WebApp && window?.Telegram?.WebApp.MainButton) {
            window.Telegram.WebApp.MainButton.offClick(handlePaymentClick);
            window.Telegram.WebApp.MainButton.hide();
        }
    };
  }, [userId, isActive]);

  const handlePaymentClick = async () => {
    if (!userId) return;
    setIsSubscribing(true);
    try {
      if (window?.Telegram?.WebApp && typeof window?.Telegram?.WebApp.openInvoice === 'function') {
        window.Telegram.WebApp.openInvoice(
          { slug: 'stars', amount: SUBSCRIPTION_PRICE },
          (invoiceStatus) => {
            setIsSubscribing(false); // Сбрасываем индикатор загрузки
            if (invoiceStatus === 'paid') {
              fetchSubscriptionStatus(); // Обновляем статус в UI
              if (window?.Telegram?.WebApp?.showPopup) {
                window.Telegram.WebApp.showPopup({
                  title: 'Успешная оплата',
                  message: 'Ваша подписка Premium активирована!',
                  buttons: [{ type: 'ok' }]
                });
              }
              // Закрываем Mini App после успеха
              setTimeout(() => window?.Telegram?.WebApp?.close(), 1500);
            } else if (invoiceStatus === 'failed' || invoiceStatus === 'cancelled') {
              if (window?.Telegram?.WebApp?.showPopup) {
                window.Telegram.WebApp.showPopup({
                  title: 'Оплата не удалась',
                  message: `Статус: ${invoiceStatus}. Попробуйте снова.`, // Добавили статус
                  buttons: [{ type: 'ok' }]
                });
              }
            }
          }
        );
      } else {
        throw new Error('Telegram WebApp или openInvoice недоступен.');
      }
    } catch (err: any) {
      setError(err.message || 'Ошибка при попытке оплаты');
      setIsSubscribing(false);
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('ru-RU', { year: 'numeric', month: 'long', day: 'numeric' });
    } catch {
      return 'Неверная дата';
    }
  };

  return (
    <div className="subscription-widget">
      <h3>Управление подпиской</h3>
      {loading && <p>Загрузка статуса...</p>}
      {error && <div className="error-message">{error}</div>}
      {!loading && !error && status && (
        <>
          {status.has_subscription ? (
            <div className="subscription-active">
              <span className="status-badge premium">Premium</span>
              <p>Ваша подписка активна до: <strong>{formatDate(status.subscription_end_date)}</strong></p>
              <p>Ограничения сняты.</p>
            </div>
          ) : (
            <div className="subscription-free">
              <span className="status-badge free">Бесплатный план</span>
              <p>Осталось бесплатных анализов: <strong>{Math.max(0, FREE_ANALYSIS_LIMIT - status.analysis_count)} из {FREE_ANALYSIS_LIMIT}</strong></p>
              <p>Осталось бесплатных генераций постов: <strong>{Math.max(0, FREE_POST_LIMIT - status.post_generation_count)} из {FREE_POST_LIMIT}</strong></p>
              <div className="subscription-offer">
                <h4>Получите Premium</h4>
                <p>Снимите все ограничения за {SUBSCRIPTION_PRICE} Star в месяц.</p>
                {/* Кнопка теперь управляется через MainButton */}
                {isSubscribing && <p>Обработка платежа...</p>}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

// Добавляем константы лимитов (можно вынести в отдельный файл)
const FREE_ANALYSIS_LIMIT = 2;
const FREE_POST_LIMIT = 2;

export default SubscriptionWidget; 