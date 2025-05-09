// Расширяем интерфейс Window для доступа к глобальным переменным и Telegram API
interface Window {
  INJECTED_USER_ID?: string;
  Telegram?: {
    WebApp?: {
      ready: () => void;
      expand: () => void;
      initDataUnsafe?: {
        user?: {
          id?: number;
          username?: string;
          first_name?: string;
          last_name?: string;
        }
      }
    }
  }
}

// Объявляем типы для Telegram WebApp SDK
declare namespace WebApp {
  interface EventParams {
    initDataUnsafe: {
      user?: {
        id?: number;
        username?: string;
      }
    }
  }
} 