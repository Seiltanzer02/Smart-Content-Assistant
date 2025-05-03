import axios from 'axios';

// Определение интерфейса для статуса подписки
export interface SubscriptionStatus {
  has_subscription: boolean;
  analysis_count: number;
  post_generation_count: number;
  subscription_end_date?: string;
  is_active_flag?: boolean;
  error?: string;
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
    
    // Проверяем корректность ответа
    if (!response.data) {
      throw new Error('Пустой ответ от сервера');
    }
    
    // Валидация данных
    const statusData: SubscriptionStatus = {
      has_subscription: !!response.data.has_subscription,
      analysis_count: response.data.analysis_count || 0,
      post_generation_count: response.data.post_generation_count || 0
    };
    
    // Добавляем опциональные поля если они есть
    if (response.data.subscription_end_date) {
      statusData.subscription_end_date = response.data.subscription_end_date;
    }
    
    if ('is_active_flag' in response.data) {
      statusData.is_active_flag = !!response.data.is_active_flag;
    }
    
    if (response.data.error) {
      statusData.error = response.data.error;
    }
    
    return statusData;
    
  } catch (error: any) {
    console.error('Ошибка при получении статуса подписки:', error);
    
    // Возвращаем объект с ошибкой и пустыми данными
    return {
      has_subscription: false,
      analysis_count: 0,
      post_generation_count: 0,
      error: error.response?.data?.detail || error.message || 'Неизвестная ошибка'
    };
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
 * Генерирует инвойс для оплаты через Telegram Stars
 * @param userId ID пользователя Telegram
 * @param amount Сумма платежа в Stars (по умолчанию 1)
 * @returns Promise с данными инвойса, включая URL
 */
export const generateInvoice = async (userId: number, amount: number = 1) => {
  try {
    console.log(`Запрос на генерацию инвойса для пользователя ${userId} на сумму ${amount} Stars`);
    
    const response = await axios.post(`${API_URL}/generate-stars-invoice-link`, {
      user_id: userId,
      amount
    });
    
    console.log('Ответ на запрос генерации инвойса:', response.data);
    
    if (!response.data.success) {
      throw new Error(response.data.error || 'Не удалось создать инвойс');
    }
    
    return response.data;
  } catch (error: any) {
    console.error('Ошибка при генерации инвойса:', error);
    throw new Error(error.response?.data?.detail || error.message || 'Ошибка при генерации инвойса');
  }
}; 