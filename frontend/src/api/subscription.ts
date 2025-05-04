import axios from 'axios';

// Определение интерфейса для статуса подписки
export interface SubscriptionStatus {
  has_subscription: boolean;
  analysis_count: number;
  post_generation_count: number;
  subscription_end_date?: string;
}

// Интерфейс для прямой проверки премиум-статуса
export interface PremiumStatus {
  has_premium: boolean;
  user_id: string;
  error?: string | null;
  subscription_end_date?: string | null;
  analysis_count?: number | null;
  post_generation_count?: number | null;
}

// API_URL пустая строка для относительных путей
const API_URL = '';

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
    // Добавляем случайный параметр для предотвращения кэширования
    const nocache = new Date().getTime();
    
    // Получаем Telegram WebApp initData, если доступен
    const telegramInitData = window.Telegram?.WebApp?.initData || '';
    
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
    throw error;
  }
};

/**
 * Создает подписку для пользователя
 * @param userId ID пользователя Telegram
 * @param paymentId ID платежа (опционально)
 * @returns Promise с данными о созданной подписке
 */
export const createSubscription = async (userId: string | null, paymentId?: string) => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }

  try {
    const response = await axios.post(`${API_URL}/subscription/create`, 
      { payment_id: paymentId },
      { headers: { 'x-telegram-user-id': userId } }
    );
    
    return response.data;
  } catch (error) {
    console.error('Ошибка при создании подписки:', error);
    throw error;
  }
};

/**
 * Генерирует инвойс для оплаты через Telegram
 * @param userId ID пользователя Telegram
 * @param amount Сумма платежа в Stars
 * @returns Promise с данными инвойса, включая URL
 */
export const generateInvoice = async (userId: number, amount: number = 70) => {
  try {
    const response = await axios.post(`${API_URL}/generate-invoice`, {
      user_id: userId,
      amount
    });
    
    return response.data;
  } catch (error) {
    console.error('Ошибка при генерации инвойса:', error);
    throw error;
  }
};

/**
 * Получает статус подписки v2 с использованием нового API
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
        'Expires': '0'
      }
    });
    
    console.log(`[API] Получен ответ о подписке V2:`, response.data);
    return response.data;
  } catch (error) {
    console.error('Ошибка при получении статуса подписки V2:', error);
    throw error;
  }
};

/**
 * Прямая проверка премиум-статуса пользователя
 * @param userId ID пользователя Telegram
 * @param nocacheParam Дополнительный параметр для защиты от кэширования (опционально)
 * @returns Promise с данными о премиум-статусе
 */
export const getPremiumStatus = async (userId: string | null, nocacheParam?: string): Promise<PremiumStatus> => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }

  console.log(`[API] Прямая проверка премиума для пользователя ID: ${userId}`);
  
  try {
    // Добавляем случайный параметр для предотвращения кэширования
    const nocache = nocacheParam || `nocache=${new Date().getTime()}`;
    
    const response = await axios.get(`${API_URL}/api-v2/premium/check?user_id=${userId}&${nocache}`, {
      headers: { 
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
      }
    });
    
    console.log(`[API] Получен ответ о премиум-статусе:`, response.data);
    return response.data;
  } catch (error) {
    console.error('Ошибка при прямой проверке премиума:', error);
    // Возвращаем отрицательный статус при ошибке
    return {
      has_premium: false,
      user_id: userId,
      error: error instanceof Error ? error.message : 'Неизвестная ошибка'
    };
  }
}; 