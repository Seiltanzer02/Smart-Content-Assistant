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
    console.log('Запрашиваем статус подписки для пользователя:', userId);
    
    const response = await axios.get(
      `${API_URL}/subscription/status?user_id=${userId}`, 
      {
        headers: { 
          'x-telegram-user-id': userId,
          'Accept': 'application/json' 
        }
      }
    );
    
    console.log('Получены данные от /subscription/status:', response.data);
    
    // Просто возвращаем данные как есть
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