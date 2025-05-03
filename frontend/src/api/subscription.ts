import axios from 'axios';

// Определение интерфейса для статуса подписки
export interface SubscriptionStatus {
  has_subscription: boolean;
  analysis_count: number;
  post_generation_count: number;
  subscription_end_date?: string;
  is_active_flag?: boolean;
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

  try {
    // Проверяем, есть ли подписка в Supabase напрямую через таблицу user_subscription
    console.log('Запрашиваем статус подписки для пользователя:', userId);
    
    // Добавляем случайный параметр для обхода SPA-роутера и кэширования
    const randomParam = Math.random().toString(36).substring(2, 15);
    
    // ПРЯМОЙ ДОСТУП - обходим проблему маршрутизации SPA, запрашивая данные через axios
    const response = await axios.get(
      `${API_URL}/subscription/status?user_id=${userId}&_=${randomParam}`, 
      {
        headers: { 
          'x-telegram-user-id': userId,
          'Accept': 'application/json',
          // Добавляем заголовки для предотвращения кэширования
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      }
    );
    
    console.log('Данные ответа о подписке:', response.data);
    
    // Если в данных нет поля has_subscription, создаем его на основе is_active_flag
    if (response.data && response.data.is_active_flag !== undefined && response.data.has_subscription === undefined) {
      response.data.has_subscription = response.data.is_active_flag;
    }
    
    // Если подписка активна, но в ответе это не указано, исправляем ответ
    if (response.data && response.data.is_active_flag === true && response.data.has_subscription === false) {
      console.log('Исправляем несоответствие: is_active_flag=true, но has_subscription=false');
      response.data.has_subscription = true;
    }
    
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