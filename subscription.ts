import axios from 'axios';

// Определение интерфейса для статуса подписки
export interface SubscriptionStatus {
  has_subscription: boolean;
  analysis_count: number;
  post_generation_count: number;
  subscription_end_date?: string;
  error?: string;
}

// Определение интерфейса для прямой проверки премиума
export interface PremiumStatus {
  has_premium: boolean;
  user_id: string;
  error?: string;
  subscription_end_date?: string;
  analysis_count?: number;
  post_generation_count?: number;
}

// API_URL пустая строка для относительных путей
const API_URL = '';

/**
 * Используем новый API-V2 для получения премиум-статуса
 * Устойчивый к маршрутизации запрос, гарантированно возвращает JSON
 * 
 * @param userId ID пользователя Telegram
 * @returns Promise с данными о премиум-статусе
 */
export const getPremiumStatus = async (userId: string | null): Promise<PremiumStatus> => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }

  console.log(`[API] Запрос премиум-статуса для пользователя ID: ${userId}`);
  
  try {
    // Добавляем случайный параметр nocache для предотвращения кэширования
    const nocache = new Date().getTime();
    
    const response = await axios.get(`${API_URL}/api-v2/premium/check?user_id=${userId}&nocache=${nocache}`, {
      headers: { 
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'Accept': 'application/json'
      }
    });
    
    console.log(`[API] Получен премиум-статус:`, response.data);
    return response.data;
  } catch (error) {
    console.error('[API] Ошибка при получении премиум-статуса:', error);
    
    // Ошибка сети или сервера
    return {
      has_premium: false,
      user_id: userId,
      error: error instanceof Error ? error.message : 'Неизвестная ошибка'
    };
  }
};

/**
 * Используем новый API-V2 для получения статуса подписки
 * Устойчивый к маршрутизации запрос, гарантированно возвращает JSON
 * 
 * @param userId ID пользователя Telegram
 * @returns Promise с данными о статусе подписки
 */
export const getSubscriptionStatusV2 = async (userId: string | null): Promise<SubscriptionStatus> => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }

  console.log(`[API] Запрос статуса подписки V2 для пользователя ID: ${userId}`);
  
  try {
    // Добавляем случайный параметр для предотвращения кэширования
    const nocache = new Date().getTime();
    
    const response = await axios.get(`${API_URL}/api-v2/subscription/status?user_id=${userId}&nocache=${nocache}`, {
      headers: { 
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'Accept': 'application/json'
      }
    });
    
    console.log(`[API] Получен ответ о подписке V2:`, response.data);
    return response.data;
  } catch (error) {
    console.error('[API] Ошибка при получении статуса подписки V2:', error);
    throw error;
  }
};

/**
 * Очищает localStorage от всех данных, связанных с премиум-подпиской
 */
export const clearPremiumDataFromLocalStorage = (): void => {
  console.log('[API] Очистка localStorage от премиум-данных');
  localStorage.removeItem('premium_status');
  localStorage.removeItem('premium_expiry');
  localStorage.removeItem('subscription_data');
  
  // Очищаем все ключи, содержащие "premium" или "subscription"
  Object.keys(localStorage).forEach(key => {
    if (key.includes('premium') || key.includes('subscription')) {
      localStorage.removeItem(key);
    }
  });
};

/**
 * Получает статус подписки пользователя
 * 
 * Пробует несколько способов получения статуса подписки для максимальной надежности:
 * 1. Новый V2 API
 * 2. Старый API с проверкой премиума
 * 3. Резервный вариант - только базовые данные 
 * 
 * @param userId ID пользователя Telegram
 * @returns Promise с данными о статусе подписки
 */
export const getUserSubscriptionStatus = async (userId: string | null): Promise<SubscriptionStatus> => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }

  console.log(`[API] Основной запрос статуса подписки для пользователя ID: ${userId}`);
  
  // Пробуем разные способы получения данных о подписке последовательно
  try {
    // Метод 1: Новый V2 API
    try {
      const subscriptionData = await getSubscriptionStatusV2(userId);
      console.log(`[API] Успешно получены данные через V2 API`);
      
      // Очищаем localStorage, если нет активной подписки
      if (!subscriptionData.has_subscription) {
        clearPremiumDataFromLocalStorage();
      }
      
      return subscriptionData;
    } catch (v2Error) {
      console.warn(`[API] Не удалось получить данные через V2 API:`, v2Error);
    }
    
    // Метод 2: Проверка премиума и преобразование в формат SubscriptionStatus
    try {
      const premiumData = await getPremiumStatus(userId);
      console.log(`[API] Успешно получены данные через премиум API`);
      
      // Очищаем localStorage, если нет активной подписки
      if (!premiumData.has_premium) {
        clearPremiumDataFromLocalStorage();
      }
      
      return {
        has_subscription: premiumData.has_premium,
        analysis_count: premiumData.analysis_count || 1,
        post_generation_count: premiumData.post_generation_count || 1,
        subscription_end_date: premiumData.subscription_end_date
      };
    } catch (premiumError) {
      console.warn(`[API] Не удалось получить данные через премиум API:`, premiumError);
    }
    
    // Метод 3: Старый API (оставляем для обратной совместимости)
    try {
      const nocache = new Date().getTime();
      const response = await axios.get(`${API_URL}/subscription/status?user_id=${userId}&nocache=${nocache}`, {
        headers: { 
          'x-telegram-user-id': userId,
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0',
          'Accept': 'application/json'
        }
      });
      
      console.log(`[API] Успешно получены данные через старый API:`, response.data);
      
      // Очищаем localStorage, если нет активной подписки
      if (!response.data.has_subscription) {
        clearPremiumDataFromLocalStorage();
      }
      
      return response.data;
    } catch (oldApiError) {
      console.warn(`[API] Не удалось получить данные через старый API:`, oldApiError);
    }
    
    // Если все методы не сработали, возвращаем базовые данные
    console.warn(`[API] Все методы получения подписки не сработали, возвращаем базовые данные`);
    
    // Очищаем localStorage на всякий случай
    clearPremiumDataFromLocalStorage();
    
    return {
      has_subscription: false,
      analysis_count: 1,
      post_generation_count: 1,
      error: 'Все методы получения статуса подписки не сработали'
    };
  } catch (error) {
    console.error('[API] Критическая ошибка при получении статуса подписки:', error);
    
    // Очищаем localStorage на всякий случай
    clearPremiumDataFromLocalStorage();
    
    // Возвращаем базовые данные в случае полного сбоя
    return {
      has_subscription: false,
      analysis_count: 1,
      post_generation_count: 1,
      error: error instanceof Error ? error.message : 'Неизвестная ошибка'
    };
  }
};

/**
 * Генерирует счет на оплату для подписки
 * 
 * @param userId ID пользователя Telegram
 * @returns Promise с информацией о счете
 */
export const generateInvoice = async (userId: string): Promise<any> => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }

  try {
    const response = await axios.post(`${API_URL}/generate-invoice`, {
      user_id: userId
    }, {
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    });
    
    return response.data;
  } catch (error) {
    console.error('Ошибка при генерации счета:', error);
    throw error;
  }
}; 