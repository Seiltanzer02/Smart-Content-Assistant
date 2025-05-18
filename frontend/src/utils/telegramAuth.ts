/**
 * Утилиты для работы с аутентификацией Telegram и извлечения данных пользователя
 */

// Имя ключа для хранения ID пользователя в localStorage
const USER_ID_KEY = 'telegram_user_id';

/**
 * Извлекает и возвращает ID пользователя Telegram из различных источников
 * 1. Из localStorage (если был ранее сохранен)
 * 2. Из URL параметра tgWebAppData (если приложение запущено из Telegram WebApp)
 * 3. Из window.Telegram.WebApp.initDataUnsafe (если доступен)
 * 
 * @returns ID пользователя Telegram или null
 */
export const getTelegramUserId = (): string | null => {
  try {
    // 1. Сначала проверяем localStorage
    const savedUserId = localStorage.getItem(USER_ID_KEY);
    if (savedUserId) {
      return savedUserId;
    }

    // 2. Пытаемся получить ID из параметров URL (если запущено из Telegram)
    const urlParams = new URLSearchParams(window.location.search);
    const initData = urlParams.get('tgWebAppData');
    
    if (initData) {
      // Извлекаем user_id из строки initData
      const userIdMatch = decodeURIComponent(initData).match(/"id":(\d+)/);
      if (userIdMatch && userIdMatch[1]) {
        const extractedUserId = userIdMatch[1];
        localStorage.setItem(USER_ID_KEY, extractedUserId);
        return extractedUserId;
      }
    }

    // 3. Пытаемся получить ID из Telegram WebApp API
    if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
      const webAppUserId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
      localStorage.setItem(USER_ID_KEY, webAppUserId);
      return webAppUserId;
    }

    // 4. Проверяем, есть ли ID в путе URL (например, /inject-user-id/123456789)
    const pathMatch = window.location.pathname.match(/\/inject-user-id\/(\d+)/);
    if (pathMatch && pathMatch[1]) {
      const pathUserId = pathMatch[1];
      localStorage.setItem(USER_ID_KEY, pathUserId);
      return pathUserId;
    }

    return null;
  } catch (error) {
    console.error('Ошибка при получении Telegram ID:', error);
    return null;
  }
};

/**
 * Сохраняет ID пользователя Telegram в localStorage
 * 
 * @param userId ID пользователя для сохранения
 */
export const saveTelegramUserId = (userId: string): void => {
  if (userId) {
    localStorage.setItem(USER_ID_KEY, userId);
  }
};

/**
 * Удаляет сохраненный ID пользователя Telegram из localStorage
 */
export const clearTelegramUserId = (): void => {
  localStorage.removeItem(USER_ID_KEY);
};

/**
 * Проверяет, запущено ли приложение из Telegram WebApp
 * 
 * @returns true если приложение запущено из Telegram WebApp
 */
export const isRunningInTelegramWebApp = (): boolean => {
  return !!window.Telegram?.WebApp;
};

// Определение типа для объекта Telegram WebApp
declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initDataUnsafe?: {
          user?: {
            id: number;
            first_name?: string;
            last_name?: string;
            username?: string;
          };
        };
      };
    };
  }
} 