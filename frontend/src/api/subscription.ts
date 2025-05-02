import axios from 'axios';

// Новый интерфейс для статуса подписки
export interface SubscriptionStatus {
  has_subscription: boolean;
  is_active: boolean;
  subscription_end_date: string | null;
  debug?: any; // Отладочная информация, может содержать любые поля
  error?: string; // Возможная ошибка
}

// API_URL пустая строка для относительных путей
const API_URL = '';

/**
 * Получает статус подписки пользователя
 * @param userId ID пользователя Telegram
 * @param forceRefresh Принудительное обновление данных из БД
 * @returns Promise с информацией о подписке
 */
export const getUserSubscriptionStatus = async (
  userId: string | number,
  forceRefresh: boolean = true
): Promise<SubscriptionStatus> => {
  try {
    // Добавляем параметры для обхода кэширования
    const timestamp = Date.now();
    const nocache = Math.random().toString(36).substring(2, 15);
    
    // Добавляем агрессивный подход к обходу кэширования
    const params = {
      user_id: userId,
      t: timestamp,
      nocache,
      force: forceRefresh,
      "_": timestamp,
      absolute_nocache: `nocache_${nocache}_${timestamp}`,
      force_nocache: `nocache_${nocache}_${timestamp}`
    };
    
    console.log(`[API] Запрос статуса подписки для userId=${userId}, timestamp=${timestamp}, nocache=${nocache}`);
    
    // Выполняем запрос с таймаутом
    const response = await axios.get('/subscription/status', {
      params,
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0, s-max-age=0',
        'Pragma': 'no-cache',
        'Expires': '0',
        'x-telegram-user-id': String(userId),
      },
      // Добавляем таймаут, чтобы не ждать ответа вечно
      timeout: 10000
    });
    
    // Проверяем, что пришел корректный ответ
    if (response.data) {
      // Валидируем и нормализуем данные
      const subscriptionData: SubscriptionStatus = {
        has_subscription: Boolean(response.data.has_subscription),
        is_active: Boolean(response.data.is_active),
        subscription_end_date: response.data.subscription_end_date || null
      };
      
      console.log(`[API] Получен статус подписки:`, subscriptionData);
      console.log(`[API] Отладочная информация:`, response.data.debug || 'Нет отладочной информации');
      
      return subscriptionData;
    } else {
      console.error('[API] Ошибка: Ответ не содержит данных');
      // Возвращаем базовый статус (неактивный)
      return {
        has_subscription: false,
        is_active: false,
        subscription_end_date: null
      };
    }
  } catch (error) {
    console.error('[API] Ошибка при получении статуса подписки:', error);
    
    // В случае ошибки возвращаем базовый статус (неактивный)
    return {
      has_subscription: false,
      is_active: false,
      subscription_end_date: null
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