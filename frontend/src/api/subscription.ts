import axios from 'axios';

// Определение интерфейса для статуса подписки
export interface SubscriptionStatus {
  has_subscription: boolean;
  is_active: boolean;
  subscription_end_date?: string | null;
  analysis_count?: number;
  post_generation_count?: number;
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
 * Получает статус подписки пользователя (только через /subscription/status)
 * @param userId ID пользователя Telegram
 * @returns Promise с данными о статусе подписки
 */
export const getUserSubscriptionStatus = async (userId: string | null): Promise<SubscriptionStatus> => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }
  const response = await fetch(`/bot-style-premium-check/${userId}`);
  const data = await response.json();
  return {
    has_subscription: !!data.has_premium,
    is_active: !!data.has_premium,
    subscription_end_date: data.subscription_end_date || null
  };
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
      subscription_end_date: undefined,
      analysis_count: 3,
      post_generation_count: 1
    };
  }
};

/**
 * Получает статус премиума напрямую с нестандартного URL, который не должен перехватываться SPA роутером
 * @param userId ID пользователя Telegram
 * @param nocache Параметр для предотвращения кэширования
 * @returns Promise с данными о статусе премиума
 */
export const getRawPremiumStatus = async (userId: string | null, nocache: string = ''): Promise<PremiumStatus> => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }

  console.log(`[API] Запрос RAW статуса премиума для пользователя ID: ${userId}`);
  
  try {
    // Используем необычный URL, который не должен быть перехватан SPA роутером
    const response = await fetch(`/raw-api-data/xyz123/premium-data/${userId}?${nocache}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache'
      },
      cache: 'no-store'
    });

    if (!response.ok) {
      const text = await response.text();
      
      // Проверяем, не получили ли мы HTML вместо JSON
      if (text.includes('<!doctype html>') || text.includes('<html>')) {
        console.error('[API] Получен HTML вместо JSON. Используем альтернативный метод.');
        
        // Проверяем наличие данных в localStorage
        const cachedData = localStorage.getItem(`premium_data_${userId}`);
        if (cachedData) {
          console.log('[API] Используем кэшированные данные из localStorage');
          return JSON.parse(cachedData);
        }
        
        throw new Error('Ошибка API: получен HTML вместо JSON');
      }
      
      throw new Error(`Ошибка API: ${response.status} ${text}`);
    }

    const data = await response.json();
    console.log(`[API] Получен RAW ответ о премиуме:`, data);

    // Сохраняем успешный ответ в localStorage для резервного использования
    localStorage.setItem(`premium_data_${userId}`, JSON.stringify(data));
    
    return data;
  } catch (error) {
    console.error('[API] Ошибка при получении RAW статуса премиума:', error);
    
    // Проверяем наличие данных в localStorage как запасной вариант
    const cachedData = localStorage.getItem(`premium_data_${userId}`);
    if (cachedData) {
      console.log('[API] Используем кэшированные данные из localStorage');
      return JSON.parse(cachedData);
    }
    
    // Если данных нет, возвращаем ошибку
    return {
      has_premium: false,
      user_id: userId,
      subscription_end_date: undefined,
      analysis_count: 3,
      post_generation_count: 1
    };
  }
};

/**
 * Открывает отдельную страницу с информацией о премиум-статусе
 * Это обходное решение, когда API-вызовы не работают из-за маршрутизации
 * @param userId ID пользователя
 * @param newWindow Открыть в новом окне (true) или в текущем (false)
 */
export const openPremiumStatusPage = (userId: string | null, newWindow: boolean = false): void => {
  if (!userId) {
    console.error('[API] Попытка открыть страницу премиум-статуса без userId');
    return;
  }
  
  const url = `/premium-page/${userId}`;
  
  if (newWindow) {
    window.open(url, '_blank');
  } else {
    window.location.href = url;
  }
};

/**
 * Открывает чат с ботом и отправляет команду для проверки статуса подписки
 * Это альтернативный способ, когда другие методы не работают
 * 
 * @param botName имя бота без символа @ (например 'SmartContentHelperBot')
 */
export const checkPremiumViaBot = (botName: string = 'SmartContentHelperBot'): void => {
  try {
    // Формируем URL для открытия чата с ботом и отправки команды
    const command = '/check_premium';
    const url = `https://t.me/${botName}?start=check_premium`;
    
    console.log(`[API] Открываем чат с ботом для проверки премиума: ${url}`);
    
    // Если мы внутри Telegram WebApp, используем специальный метод
    if (window.Telegram?.WebApp?.openTelegramLink) {
      window.Telegram.WebApp.openTelegramLink(url);
    } else {
      // Обычное открытие в новой вкладке
      window.open(url, '_blank');
    }
  } catch (e) {
    console.error('[API] Ошибка при открытии чата с ботом:', e);
  }
};

/**
 * Используем гарантированный метод для получения статуса премиума с необычным URL
 * Путь специально сделан необычным, чтобы не был перехвачен SPA роутером
 * 
 * @param userId ID пользователя Telegram
 * @returns Promise с данными о премиум-статусе
 */
export const getDirectPremiumStatus = async (userId: string | null): Promise<PremiumStatus> => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }

  console.log(`[API] Запрос прямого премиум-статуса для пользователя ID: ${userId}`);
  
  try {
    // Добавляем случайный параметр для предотвращения кэширования
    const nocache = `_nocache=${new Date().getTime()}`;
    
    // Используем URL, который гарантированно не будет перехвачен SPA роутером
    const response = await fetch(`/raw-api-data/xyz123/premium-data/${userId}?${nocache}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache'
      },
      cache: 'no-store'
    });

    if (!response.ok) {
      throw new Error(`Ошибка API: ${response.status}`);
    }
    
    const data = await response.json();
    console.log(`[API] Получен прямой ответ о премиуме:`, data);
    
    return data;
  } catch (error) {
    console.error('[API] Ошибка при получении прямого премиум-статуса:', error);
    
    // Возвращаем базовые данные при ошибке
    return {
      has_premium: false,
      user_id: userId,
      subscription_end_date: undefined,
      analysis_count: 3,
      post_generation_count: 1
    };
  }
};

/**
 * Проверяет статус премиум-подписки напрямую через бот-стиль API, который работает так же, как и бот
 * @param userId ID пользователя Telegram
 * @returns Promise с данными о премиум-статусе в формате, совместимом с форматом ответа из бота
 */
export const getBotStylePremiumStatus = async (userId: string | null): Promise<PremiumStatus> => {
  if (!userId) {
    throw new Error('ID пользователя не предоставлен');
  }

  console.log(`[API] Запрос премиум-статуса через бот-стиль API для пользователя ID: ${userId}`);
  
  try {
    // Добавляем случайный параметр для предотвращения кэширования
    const nocache = `_nocache=${new Date().getTime()}`;
    
    // Используем прямой URL, который работает как в боте
    const response = await fetch(`/bot-style-premium-check/${userId}?${nocache}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache'
      },
      cache: 'no-store'
    });

    if (!response.ok) {
      const text = await response.text();
      if (text.includes('<!doctype html>') || text.includes('<html>')) {
        throw new Error('Ошибка API: получен HTML вместо JSON. Проверьте серверный роутинг!');
      }
      throw new Error(`Ошибка API: ${response.status} ${text}`);
    }
    const data = await response.json();
    console.log(`[API] Получен ответ из бот-стиль API:`, data);
    return {
      has_premium: data.has_premium,
      user_id: userId,
      subscription_end_date: data.subscription_end_date === null ? undefined : data.subscription_end_date,
      analysis_count: data.analysis_count,
      post_generation_count: data.post_generation_count
    };
  } catch (error) {
    console.error('[API] Ошибка при получении премиум-статуса через бот-стиль API:', error);
    
    // Возвращаем базовые данные при ошибке
    return {
      has_premium: false,
      user_id: userId,
      subscription_end_date: undefined,
      analysis_count: 3,
      post_generation_count: 1
    };
  }
}; 