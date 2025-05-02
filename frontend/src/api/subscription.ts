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
    // Формируем самый радикальный запрос без кэширования
    const timestamp = Date.now();
    const randomParam = Math.random().toString(36).substring(2, 15);
    const absolutelyNoCache = `nocache_${randomParam}_${timestamp}`;
    const url = `/subscription/status?user_id=${userId}&t=${timestamp}&nocache=${randomParam}&force=true&_=${Math.random()}&absolute_nocache=${absolutelyNoCache}`;
    
    console.log(`%c[getUserSubscriptionStatus] 📡 GET ${url}`, 'color:purple;font-weight:bold');
    console.log(`%c[getUserSubscriptionStatus] ⏱️ Время запроса: ${new Date().toISOString()}`, 'color:gray');
    
    // Мега-агрессивный режим запроса с запретом кэширования
    const response = await axios.get(url, {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
        'Pragma': 'no-cache',
        'Expires': '0',
        'X-Requested-With': 'XMLHttpRequest',
        'X-Force-Refresh': 'true',
        'X-No-Cache': absolutelyNoCache
      },
      // Полный запрет кэширования
      params: {
        _: new Date().getTime(),
        force_nocache: absolutelyNoCache
      },
      // Дополнительные опции для запрета кэширования
      ...{
        cache: false,
        timeout: 30000, // 30 сек таймаут
        responseType: 'json',
        withCredentials: false
      }
    });
    
    console.log(`%c[getUserSubscriptionStatus] ✅ Ответ от сервера [${response.status}]:`, 'color:green;font-weight:bold');
    console.log(`%c[getUserSubscriptionStatus] 📦 Полные данные ответа:`, 'color:green');
    console.log(response.data);
    
    // СУПЕР-ДИАГНОСТИКА: глубокий анализ полученных данных
    if (response.data) {
      const responseData = response.data;
      console.log(`%c[getUserSubscriptionStatus] 🔬 ГЛУБОКИЙ АНАЛИЗ ОТВЕТА:`, 'color:blue;background-color:#f0f8ff;padding:3px;border-radius:3px;font-weight:bold');
      
      // Проверяем тип данных каждого поля
      console.log(`%c• has_subscription:`, 'color:blue', responseData.has_subscription, `(${typeof responseData.has_subscription})`);
      console.log(`%c• is_active:`, 'color:blue', responseData.is_active, `(${typeof responseData.is_active})`);
      console.log(`%c• subscription_end_date:`, 'color:blue', responseData.subscription_end_date, 
        responseData.subscription_end_date ? `(${typeof responseData.subscription_end_date})` : '(null)');
      
      // Проверка на строковые 'true'/'false' вместо boolean
      if (typeof responseData.has_subscription === 'string') {
        console.warn(`%c⚠️ has_subscription пришел как строка, не булево значение!`, 'color:orange;font-weight:bold');
      }
      
      if (typeof responseData.is_active === 'string') {
        console.warn(`%c⚠️ is_active пришел как строка, не булево значение!`, 'color:orange;font-weight:bold');
      }
    }
    
    // Проверяем и логируем debug-информацию с особым вниманием
    if (response.data.debug) {
      console.log(`%c[getUserSubscriptionStatus] 🔍 DEBUG-ИНФОРМАЦИЯ:`, 'color:orange;font-weight:bold;background-color:#fff3e0;padding:3px;border-radius:3px;');
      
      const debug = response.data.debug;
      // Особое внимание к важным полям в отладочной информации
      if (debug.direct_subscription) {
        console.log(`%c📊 ПОДПИСКА ИЗ ПРЯМОГО SQL:`, 'color:darkgreen;font-weight:bold');
        console.log(debug.direct_subscription);
        
        // Прямой анализ данных из БД
        console.log(`%c• ID подписки:`, 'color:green', debug.direct_subscription_id);
        console.log(`%c• is_active из БД:`, 'color:green', debug.direct_is_active, `(${typeof debug.direct_is_active})`);
        console.log(`%c• end_date из БД:`, 'color:green', debug.direct_end_date);
        console.log(`%c• Валидность end_date:`, 'color:green', debug.end_date_valid);
        
        if (debug.date_comparison) {
          console.log(`%c• Результат сравнения дат:`, 'color:green', debug.date_comparison);
        }
        
        // Если было автоисправление в БД
        if (debug.update_sql) {
          console.log(`%c✅ ВЫПОЛНЕНО АВТОИСПРАВЛЕНИЕ В БД:`, 'color:green;font-weight:bold');
          console.log(debug.update_sql);
          console.log(debug.update_result);
        }
      }
      
      // Проверка на ошибки
      if (debug.direct_sql_error) {
        console.error(`%c❌ ОШИБКА ПРЯМОГО SQL:`, 'color:red;font-weight:bold');
        console.error(debug.direct_sql_error);
      }
      
      // Отображаем итоговое решение бэкенда
      if (debug.final_has_subscription !== undefined) {
        console.log(`%c📌 ИТОГОВОЕ РЕШЕНИЕ БЭКЕНДА:`, 'color:blue;font-weight:bold');
        console.log(`• has_subscription: ${debug.final_has_subscription}`);
        console.log(`• is_active: ${debug.final_is_active}`);
      }
    }
    
    // Проверяем наличие ошибки в ответе
    if (response.data.error) {
      console.error(`%c[getUserSubscriptionStatus] 🛑 Ошибка API: ${response.data.error}`, 'color:red;font-weight:bold');
    }
    
    // РАДИКАЛЬНОЕ решение: принудительно приводим поля к правильным типам
    // И проверяем end_date даже на фронтенде
    
    // 1. Обработка поля has_subscription с приведением типа
    let has_subscription = false;
    if (typeof response.data.has_subscription === 'boolean') {
      has_subscription = response.data.has_subscription;
    } else if (typeof response.data.has_subscription === 'string') {
      has_subscription = response.data.has_subscription.toLowerCase() === 'true';
    } else if (typeof response.data.has_subscription === 'number') {
      has_subscription = response.data.has_subscription !== 0;
    }
    
    // 2. Обработка поля is_active с приведением типа
    let is_active = false;
    if (typeof response.data.is_active === 'boolean') {
      is_active = response.data.is_active;
    } else if (typeof response.data.is_active === 'string') {
      is_active = response.data.is_active.toLowerCase() === 'true';
    } else if (typeof response.data.is_active === 'number') {
      is_active = response.data.is_active !== 0;
    }
    
    // 3. Обработка end_date и проверка валидности даты
    const subscription_end_date = response.data.subscription_end_date || null;
    let end_date_valid = false;
    
    if (subscription_end_date) {
      try {
        const parsedEndDate = new Date(subscription_end_date);
        const now = new Date();
        
        // Проверяем что дата корректно распарсилась и в будущем
        if (!isNaN(parsedEndDate.getTime()) && parsedEndDate > now) {
          end_date_valid = true;
          console.log(`%c[getUserSubscriptionStatus] 📆 Проверка end_date на фронтенде: ВАЛИДНА`, 'color:green');
          console.log(`Конец подписки: ${parsedEndDate.toISOString()}, Сейчас: ${now.toISOString()}`);
        } else {
          console.log(`%c[getUserSubscriptionStatus] 📆 Проверка end_date на фронтенде: НЕВАЛИДНА`, 'color:orange');
          console.log(`Конец подписки: ${parsedEndDate.toISOString()}, Сейчас: ${now.toISOString()}`);
        }
      } catch (e) {
        console.error(`%c[getUserSubscriptionStatus] ⚠️ Ошибка парсинга end_date на фронтенде:`, 'color:red', e);
      }
    }
    
    // СУПЕР-РАДИКАЛЬНОЕ РЕШЕНИЕ: считаем подписку активной, если:
    // 1. Либо поле is_active = true 
    // 2. Либо end_date валидна и в будущем
    const computed_is_active = is_active || end_date_valid;
    
    // Логируем результат на фронтенде
    console.log(`%c[getUserSubscriptionStatus] 🧠 ИТОГОВОЕ РЕШЕНИЕ ФРОНТЕНДА:`, 'color:blue;font-weight:bold;background-color:#e3f2fd;padding:3px;border-radius:3px;');
    console.log(`• from is_active: ${is_active}`);
    console.log(`• from end_date: ${end_date_valid}`);
    console.log(`• computed_is_active: ${computed_is_active}`);
    
    // Формируем итоговый результат
    const result = { 
      has_subscription: computed_is_active, // Приводим к boolean для надежности
      is_active: computed_is_active, // Приводим к boolean для надежности
      subscription_end_date 
    };
    
    console.log(`%c[getUserSubscriptionStatus] ↩️ ФИНАЛЬНЫЙ РЕЗУЛЬТАТ:`, 'color:blue;font-weight:bold;background-color:#bbdefb;padding:3px;border-radius:3px;');
    console.log(result);
    
    // Сохраняем результат в localStorage
    try {
      const storageData = {
        ...result,
        timestamp: Date.now(),
        raw_response: response.data
      };
      localStorage.setItem('subscription_status', JSON.stringify(storageData));
      console.log(`%c[getUserSubscriptionStatus] 💾 Статус подписки сохранен в localStorage`, 'color:gray');
      
      // ОСОБОЕ РАДИКАЛЬНОЕ РЕШЕНИЕ: дублирующее сохранение статуса
      localStorage.setItem(`subscription_status_${userId}`, JSON.stringify(storageData));
      sessionStorage.setItem(`subscription_status_${userId}`, JSON.stringify(storageData));
    } catch (e) {
      console.warn(`%c[getUserSubscriptionStatus] ⚠️ Не удалось сохранить статус в localStorage:`, 'color:orange', e);
    }
    
    return result;
  } catch (error) {
    console.error(`%c[getUserSubscriptionStatus] 🔥 КРИТИЧЕСКАЯ ОШИБКА при получении статуса подписки:`, 'color:red;font-weight:bold;background-color:#ffebee;padding:3px;border-radius:3px;');
    
    if (axios.isAxiosError(error)) {
      console.error(`%c[getUserSubscriptionStatus] 🌐 Ошибка запроса: ${error.message}`, 'color:red');
      console.error(`Статус: ${error.response?.status || 'Нет ответа'}`);
      console.error(`Данные ошибки:`, error.response?.data);
      console.error(`Заголовки:`, error.response?.headers);
      
      // Для отладки показываем полную конфигурацию запроса
      console.error(`%c[getUserSubscriptionStatus] 🔧 Конфигурация запроса:`, 'color:orange');
      console.error(error.config);
    } else {
      console.error(`%c[getUserSubscriptionStatus] ⚠️ Неизвестная ошибка:`, 'color:red');
      console.error(error);
    }
    
    // Попытка восстановить данные из localStorage в случае ошибки сети
    try {
      // Сначала пробуем специфичный для пользователя ключ
      const userSpecificKey = `subscription_status_${userId}`;
      let savedStatus = localStorage.getItem(userSpecificKey) || sessionStorage.getItem(userSpecificKey);
      
      // Если не нашли, пробуем общий ключ
      if (!savedStatus) {
        savedStatus = localStorage.getItem('subscription_status');
      }
      
      if (savedStatus) {
        const parsed = JSON.parse(savedStatus);
        const savedTimestamp = parsed.timestamp || 0;
        // Используем кэшированные данные только если они не старше 1 часа
        if (Date.now() - savedTimestamp < 3600000) {
          console.log(`%c[getUserSubscriptionStatus] 🔄 Используем сохраненный статус подписки из Storage`, 'color:orange;font-weight:bold');
          console.log(parsed);
          
          return {
            has_subscription: !!parsed.has_subscription,
            is_active: !!parsed.is_active,
            subscription_end_date: parsed.subscription_end_date
          };
        }
      }
    } catch (e) {
      console.warn(`%c[getUserSubscriptionStatus] ⚠️ Не удалось восстановить статус из Storage:`, 'color:orange', e);
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