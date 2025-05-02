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
    console.error('%c[getUserSubscriptionStatus] 🛑 ОШИБКА: Не передан userId!', 'color:red;font-weight:bold');
    throw new Error('ID пользователя не предоставлен');
  }
  console.log(`%c[getUserSubscriptionStatus] 🚀 ЗАПРОС статуса подписки для userId: ${userId}`, 'color:blue;font-weight:bold');
  
  try {
    // Добавляем случайный параметр для предотвращения кэширования
    const timestamp = Date.now();
    const randomParam = Math.random().toString(36).substring(2, 10);
    // Дополнительный параметр skipCache для форсирования обновления
    const url = `/subscription/status?user_id=${userId}&t=${timestamp}&nocache=${randomParam}&skipCache=true&_=${Math.random()}`;
    
    console.log(`%c[getUserSubscriptionStatus] 📡 GET ${url}`, 'color:purple');
    console.log(`%c[getUserSubscriptionStatus] ⏱️ Время запроса: ${new Date().toISOString()}`, 'color:gray');
    
    // Добавляем заголовки для запрета кэширования
    const response = await axios.get(url, {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
        'Pragma': 'no-cache',
        'Expires': '0',
        'X-Requested-With': 'XMLHttpRequest'
      },
      // Принудительно игнорируем кэш браузера
      params: {
        _: new Date().getTime() // Дополнительное предотвращение кэширования
      }
    });
    
    console.log(`%c[getUserSubscriptionStatus] ✅ Ответ от сервера [${response.status}]:`, 'color:green;font-weight:bold');
    console.log(`%c[getUserSubscriptionStatus] 📦 Полные данные ответа:`, 'color:green');
    console.log(response.data);
    
    // Проверяем и логируем debug-информацию, если она есть
    if (response.data.debug) {
      console.log(`%c[getUserSubscriptionStatus] 🔍 DEBUG-ИНФОРМАЦИЯ:`, 'color:orange;font-weight:bold');
      console.log(response.data.debug);
    }
    
    // Проверяем наличие ошибки в ответе
    if (response.data.error) {
      console.error(`%c[getUserSubscriptionStatus] 🛑 Ошибка API: ${response.data.error}`, 'color:red');
    }
    
    // Деструктурируем нужные поля из ответа с проверкой и принудительным приведением к нужным типам
    const has_subscription = typeof response.data.has_subscription === 'boolean' 
      ? response.data.has_subscription 
      : false;
      
    const is_active = typeof response.data.is_active === 'boolean' 
      ? response.data.is_active 
      : false;
      
    const subscription_end_date = response.data.subscription_end_date || null;
    
    // Подробно логируем извлеченные поля
    console.log(`%c[getUserSubscriptionStatus] 📊 ДАННЫЕ ПОДПИСКИ:`, 'color:blue');
    console.log(`  • has_subscription: ${has_subscription} (${typeof has_subscription})`);
    console.log(`  • is_active: ${is_active} (${typeof is_active})`);
    console.log(`  • subscription_end_date: ${subscription_end_date}`);
    
    // Радикальное решение: если end_date в будущем, то подписка активна независимо от is_active
    let computedIsActive = is_active;
    if (subscription_end_date) {
      const endDate = new Date(subscription_end_date);
      const now = new Date();
      if (endDate > now) {
        computedIsActive = true;
        console.log(`%c[getUserSubscriptionStatus] 🔄 Обнаружена активная подписка: end_date в будущем`, 'color:green;font-weight:bold');
      }
    }
    
    // Возвращаем объект с проверенными полями
    const result = { 
      has_subscription: !!computedIsActive, // Приводим к boolean и используем вычисленное значение
      is_active: !!computedIsActive, // Приводим к boolean и используем вычисленное значение
      subscription_end_date 
    };
    
    console.log(`%c[getUserSubscriptionStatus] ↩️ Возвращаемый результат:`, 'color:blue;font-weight:bold');
    console.log(result);
    
    // Альтернативное решение - сохраняем результат в localStorage
    try {
      localStorage.setItem('subscription_status', JSON.stringify({
        ...result,
        timestamp: Date.now()
      }));
      console.log(`%c[getUserSubscriptionStatus] 💾 Статус подписки сохранен в localStorage`, 'color:gray');
    } catch (e) {
      console.warn(`%c[getUserSubscriptionStatus] ⚠️ Не удалось сохранить статус в localStorage:`, 'color:orange', e);
    }
    
    return result;
  } catch (error) {
    console.error(`%c[getUserSubscriptionStatus] 🔥 КРИТИЧЕСКАЯ ОШИБКА при получении статуса подписки:`, 'color:red;font-weight:bold');
    
    if (axios.isAxiosError(error)) {
      console.error(`%c[getUserSubscriptionStatus] 🌐 Ошибка запроса: ${error.message}`, 'color:red');
      console.error(`Статус: ${error.response?.status || 'Нет ответа'}`);
      console.error(`Данные ошибки:`, error.response?.data);
      console.error(`Заголовки:`, error.response?.headers);
    } else {
      console.error(`%c[getUserSubscriptionStatus] ⚠️ Неизвестная ошибка:`, 'color:red');
      console.error(error);
    }
    
    // Попытка восстановить данные из localStorage в случае ошибки сети
    try {
      const savedStatus = localStorage.getItem('subscription_status');
      if (savedStatus) {
        const parsed = JSON.parse(savedStatus);
        const savedTimestamp = parsed.timestamp || 0;
        // Используем кэшированные данные только если они не старше 1 часа
        if (Date.now() - savedTimestamp < 3600000) {
          console.log(`%c[getUserSubscriptionStatus] 🔄 Используем сохраненный статус подписки из localStorage`, 'color:orange;font-weight:bold');
          return {
            has_subscription: !!parsed.has_subscription,
            is_active: !!parsed.is_active,
            subscription_end_date: parsed.subscription_end_date
          };
        }
      }
    } catch (e) {
      console.warn(`%c[getUserSubscriptionStatus] ⚠️ Не удалось восстановить статус из localStorage:`, 'color:orange', e);
    }
    
    // Выбрасываем исходную ошибку для обработки выше
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