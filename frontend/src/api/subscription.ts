import axios from 'axios';

// Интерфейс для статуса подписки
export interface SubscriptionStatus {
  has_subscription: boolean;
  subscription_end_date?: string;
  analysis_count: number;
  post_generation_count: number;
}

// API_URL пустая строка для относительных путей
const API_URL = '';

/**
 * Получение статуса подписки пользователя
 */
export async function getUserSubscriptionStatus(userId: string | null): Promise<SubscriptionStatus> {
  try {
    console.log(`Запрашиваем статус подписки для userId: ${userId}`);
    
    if (!userId) {
      console.warn('getUserSubscriptionStatus вызван с пустым userId');
      return {
        has_subscription: false,
        analysis_count: 0,
        post_generation_count: 0
      };
    }
    
    const response = await fetch('/subscription/status', {
      headers: {
        'X-Telegram-User-Id': userId
      }
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Ошибка при получении статуса подписки. Статус: ${response.status}, Текст: ${errorText}`);
      throw new Error(`Ошибка при получении статуса подписки: ${errorText}`);
    }
    
    const data = await response.json();
    console.log(`Получен ответ от /subscription/status:`, data);
    
    return {
      has_subscription: Boolean(data.has_subscription),
      subscription_end_date: data.subscription_end_date,
      analysis_count: data.analysis_count || 0,
      post_generation_count: data.post_generation_count || 0
    };
  } catch (error) {
    console.error('Ошибка при получении статуса подписки:', error);
    // Возвращаем базовый статус при ошибке
    return {
      has_subscription: false,
      analysis_count: 0,
      post_generation_count: 0
    };
  }
}

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
 * Генерация ссылки на инвойс для оплаты подписки
 */
export async function generateInvoice(userId: number) {
  try {
    const response = await fetch('/generate-invoice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, amount: 70 })
    });
    
    if (!response.ok) {
      throw new Error(`Ошибка при создании инвойса: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Ошибка при генерации инвойса:', error);
    throw error;
  }
} 