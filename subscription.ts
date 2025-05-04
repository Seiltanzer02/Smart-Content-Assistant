import axios from 'axios';

// Определение интерфейса для статуса подписки
export interface SubscriptionStatus {
  has_subscription: boolean;
  analysis_count: number;
  post_generation_count: number;
  subscription_end_date?: string;
}

// API_URL пустая строка для относительных путей
const API_URL = '';

/**
 * Получение статуса подписки через прямой запрос к базе данных
 * Использует специальный API-эндпоинт, который всегда возвращает JSON
 * 
 * @param userId ID пользователя Telegram
 * @returns Promise с данными о статусе подписки
 */
export const getForcePremiumStatus = async (userId: string | null): Promise<SubscriptionStatus> => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }

  console.log(`[API] Прямая проверка подписки для пользователя ID: ${userId}`);
  
  try {
    // Добавляем случайный параметр для предотвращения кэширования
    const nocache = new Date().getTime();
    
    const response = await axios.get(`${API_URL}/force-premium-status/${userId}?nocache=${nocache}`, {
      headers: { 
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
      }
    });
    
    console.log(`[API] Получен ответ о статусе подписки:`, response.data);
    
    // Преобразуем формат ответа от API к нашему интерфейсу
    const result: SubscriptionStatus = {
      has_subscription: response.data.has_premium || false,
      analysis_count: response.data.analysis_count || 0,
      post_generation_count: response.data.post_generation_count || 0
    };
    
    if (response.data.subscription_end_date) {
      result.subscription_end_date = response.data.subscription_end_date;
    }
    
    return result;
  } catch (error) {
    console.error('Ошибка при получении статуса подписки:', error);
    // В случае ошибки возвращаем базовый статус без подписки
    return {
      has_subscription: false,
      analysis_count: 1,
      post_generation_count: 1
    };
  }
};

/**
 * Получает статус подписки пользователя
 * @param userId ID пользователя Telegram
 * @returns Promise с данными о статусе подписки
 */
export const getUserSubscriptionStatus = async (userId: string | null): Promise<SubscriptionStatus> => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }

  console.log(`[API] Запрос статуса подписки для пользователя ID: ${userId}`);
  
  try {
    // Сначала пробуем использовать прямой запрос к базе данных
    try {
      return await getForcePremiumStatus(userId);
    } catch (forceError) {
      console.warn("Не удалось использовать прямой запрос, пробуем стандартный API", forceError);
    }
    
    // Добавляем случайный параметр для предотвращения кэширования
    const nocache = new Date().getTime();
    
    // Получаем Telegram WebApp initData, если доступен
    const telegramInitData = window.Telegram?.WebApp?.initData || '';
    
    // Используем стандартный эндпоинт
    const response = await axios.get(`${API_URL}/subscription/status?nocache=${nocache}`, {
      headers: { 
        'x-telegram-user-id': userId,
        // Отправляем initData для безопасной аутентификации
        'x-telegram-init-data': telegramInitData,
        // Отключаем кэширование
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
      }
    });
    
    console.log(`[API] Получен ответ о подписке:`, response.data);
    return response.data;
  } catch (error) {
    console.error('Ошибка при получении статуса подписки:', error);
    
    // В случае ошибки возвращаем базовый статус без подписки
    return {
      has_subscription: false,
      analysis_count: 1,
      post_generation_count: 1
    };
  }
}; 