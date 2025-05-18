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
  debug?: string;
}

// Fallback канал, если API недоступен
const FALLBACK_CHANNEL = 'yourtestchannel';

/**
 * Проверяет, подписан ли пользователь на требуемый канал
 * @param userId ID пользователя Telegram
 * @returns Promise с информацией о подписке
 */
export const checkChannelSubscription = async (userId: string | null): Promise<ChannelSubscriptionStatus> => {
  if (!userId) {
    console.error('checkChannelSubscription: userId не предоставлен');
    return {
      success: false,
      is_subscribed: false,
      channel: FALLBACK_CHANNEL,
      user_id: 0,
      subscription_required: true,
      error: 'ID пользователя не предоставлен',
      debug: 'userId is null or empty'
    };
  }

  try {
    console.log(`checkChannelSubscription: Проверяем подписку для пользователя ${userId}`);
    const nocache = `nocache=${new Date().getTime()}`;
    
    // Полный URL для отладки
    const fullUrl = `${API_URL}/channel/subscription/status?user_id=${userId}&${nocache}`;
    console.log(`checkChannelSubscription: Отправляем запрос на ${fullUrl}`);
    
    const response = await axios.get(fullUrl, {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'X-Telegram-User-Id': userId
      },
      timeout: 10000 // 10 секунд таймаут
    });

    console.log('checkChannelSubscription: Получен ответ', response.data);
    
    // Проверка на корректность ответа
    if (!response.data || typeof response.data !== 'object') {
      console.error('checkChannelSubscription: Некорректный формат ответа', response.data);
      return {
        success: false,
        is_subscribed: true, // Временно считаем подписанным для отладки
        channel: FALLBACK_CHANNEL,
        user_id: Number(userId),
        subscription_required: true,
        error: 'Некорректный формат ответа',
        debug: `Response: ${JSON.stringify(response.data)}`
      };
    }
    
    return {
      ...response.data,
      debug: `Success response: ${JSON.stringify(response.data)}`
    };
  } catch (error: any) {
    console.error('Ошибка при проверке подписки на канал:', error);
    
    // Более подробная информация об ошибке
    const errorMessage = error.message || 'Неизвестная ошибка';
    const statusCode = error.response?.status || 'нет кода';
    const responseData = error.response?.data ? JSON.stringify(error.response.data) : 'нет данных';
    
    const debugInfo = `Error: ${errorMessage}, Status: ${statusCode}, Data: ${responseData}`;
    console.log('checkChannelSubscription: Debug info:', debugInfo);
    
    // В случае ошибки считаем пользователя подписанным, чтобы не блокировать функциональность
    return {
      success: false,
      is_subscribed: true, // Временно считаем подписанным для отладки
      channel: FALLBACK_CHANNEL,
      user_id: Number(userId),
      subscription_required: true,
      error: 'Ошибка при проверке подписки на канал',
      debug: debugInfo
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
    // Если API не вернул URL, используем fallback
    return `https://t.me/${FALLBACK_CHANNEL}`;
  } catch (error) {
    console.error('Ошибка при получении URL канала:', error);
    // В случае ошибки также используем fallback
    return `https://t.me/${FALLBACK_CHANNEL}`;
  }
};

/**
 * Открывает канал для подписки
 */
export const openChannelSubscription = async (): Promise<void> => {
  try {
    const url = await getChannelSubscriptionUrl();
    if (!url) return;
    
    console.log('openChannelSubscription: Открываем URL', url);
    
    // Если мы внутри Telegram WebApp, используем специальный метод
    if (window.Telegram?.WebApp?.openTelegramLink) {
      console.log('openChannelSubscription: Используем Telegram.WebApp.openTelegramLink');
      window.Telegram.WebApp.openTelegramLink(url);
    } else {
      // Обычное открытие в новой вкладке
      console.log('openChannelSubscription: Используем window.open');
      window.open(url, '_blank');
    }
  } catch (e) {
    console.error('Ошибка при открытии канала для подписки:', e);
  }
}; 