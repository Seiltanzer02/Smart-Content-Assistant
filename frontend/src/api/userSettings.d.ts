// Типы для работы с настройками пользователя
export interface UserSettings {
  channelName: string | null;
  selectedChannels: string[];
  allChannels: string[];
}

// Дополнительные объявления типов
declare global {
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
        setHeaderColor?: (color: string) => void;
        setBackgroundColor?: (color: string) => void;
        setSwipeSettings?: (params: { allow_vertical_swipe: boolean }) => void;
        MainButton?: {
          show: () => void;
          hide: () => void;
          setText: (text: string) => void;
          onClick: (callback: () => void) => void;
        }
      }
    }
  }
} 