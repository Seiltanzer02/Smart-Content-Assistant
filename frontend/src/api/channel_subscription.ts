import axios from 'axios';
import { API_URL } from './constants';

/**
 * Интерфейс ответа о статусе подписки на канал
 */
export interface ChannelSubscriptionStatus {
  success: boolean;
  is_subscribed: boolean;
  channel: string;
  user_id: number;
  subscription_required: boolean;
  error?: string;
}

/**
 * Проверяет, подписан ли пользователь на требуемый канал
 * @param userId ID пользователя Telegram
 * @returns Promise с информацией о подписке
 */
export const checkChannelSubscription = async (userId: string | null): Promise<ChannelSubscriptionStatus> => {
  if (!userId) {
    return {
      success: false,
      is_subscribed: false,
      channel: '',
      user_id: 0,
      subscription_required: true,
      error: 'ID пользователя не предоставлен'
    };
  }

  try {
    const nocache = `nocache=${new Date().getTime()}`;
    const response = await axios.get(`${API_URL}/channel/subscription/status?user_id=${userId}&${nocache}`, {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'X-Telegram-User-Id': userId
      }
    });

    return response.data;
  } catch (error) {
    console.error('Ошибка при проверке подписки на канал:', error);
    return {
      success: false,
      is_subscribed: false,
      channel: '',
      user_id: Number(userId),
      subscription_required: true,
      error: 'Ошибка при проверке подписки на канал'
    };
  }
};

/**
 * Получает URL для подписки на канал
 * @returns Promise с URL канала
 */
export const getChannelSubscriptionUrl = async (): Promise<string> => {
  try {
    const response = await axios.get(`${API_URL}/channel/subscription/url`);
    if (response.data?.success && response.data?.url) {
      return response.data.url;
    }
    return '';
  } catch (error) {
    console.error('Ошибка при получении URL канала:', error);
    return '';
  }
};

/**
 * Открывает канал для подписки
 */
export const openChannelSubscription = async (): Promise<void> => {
  try {
    const url = await getChannelSubscriptionUrl();
    if (!url) return;
    
    // Если мы внутри Telegram WebApp, используем специальный метод
    if (window.Telegram?.WebApp?.openTelegramLink) {
      window.Telegram.WebApp.openTelegramLink(url);
    } else {
      // Обычное открытие в новой вкладке
      window.open(url, '_blank');
    }
  } catch (e) {
    console.error('Ошибка при открытии канала для подписки:', e);
  }
}; 