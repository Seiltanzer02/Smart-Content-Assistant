import axios from 'axios';

// Новый интерфейс для статуса подписки
export interface SubscriptionStatus {
  has_subscription: boolean;
  is_active: boolean;
  subscription_end_date?: string | null;
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
    console.error('[getUserSubscriptionStatus] Не передан userId!');
    throw new Error('ID пользователя не предоставлен');
  }
  console.log(`[getUserSubscriptionStatus] Запрос статуса подписки для userId: ${userId}`);
  try {
    const url = `/subscription/status?user_id=${userId}&t=${Date.now()}`;
    console.log(`[getUserSubscriptionStatus] GET ${url}`);
    const response = await axios.get(url);
    console.log('[getUserSubscriptionStatus] Ответ от сервера:', response.data);
    const { has_subscription, is_active, subscription_end_date } = response.data;
    console.log('[getUserSubscriptionStatus] Возвращаемые поля:', { has_subscription, is_active, subscription_end_date });
    return { has_subscription, is_active, subscription_end_date };
  } catch (error) {
    console.error('[getUserSubscriptionStatus] Ошибка при получении статуса подписки:', error);
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
    console.error('[createSubscription] Не передан userId!');
    throw new Error('ID пользователя не предоставлен');
  }
  console.log(`[createSubscription] Создание подписки для userId: ${userId}, paymentId: ${paymentId}`);
  try {
    const response = await axios.post(`${API_URL}/subscription/create`, 
      { payment_id: paymentId },
      { headers: { 'x-telegram-user-id': userId } }
    );
    console.log('[createSubscription] Ответ от сервера:', response.data);
    return response.data;
  } catch (error) {
    console.error('[createSubscription] Ошибка при создании подписки:', error);
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
  console.log(`[generateInvoice] Генерация инвойса для userId: ${userId}, amount: ${amount}`);
  try {
    const response = await axios.post(`${API_URL}/generate-invoice`, {
      user_id: userId,
      amount
    });
    console.log('[generateInvoice] Ответ от сервера:', response.data);
    return response.data;
  } catch (error) {
    console.error('[generateInvoice] Ошибка при генерации инвойса:', error);
    throw error;
  }
}; 