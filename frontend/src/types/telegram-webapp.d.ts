// Объявление типов для Telegram WebApp, доступного глобально
interface Window {
  Telegram?: {
    WebApp?: {
      initData: string;
      initDataUnsafe: {
        query_id?: string;
        user?: {
          id: number;
          first_name: string;
          last_name?: string;
          username?: string;
          language_code?: string;
          photo_url?: string;
        };
        auth_date: number;
        hash: string;
      };
      close: () => void;
      showAlert: (message: string) => void;
      showConfirm: (message: string, callback: (confirmed: boolean) => void) => void;
      ready: () => void;
      expand: () => void;
      openLink: (url: string) => void;
      mainButton: {
        show: () => void;
        hide: () => void;
        setText: (text: string) => void;
        onClick: (callback: () => void) => void;
        offClick: (callback: () => void) => void;
        showProgress: (leaveText?: boolean) => void;
        hideProgress: () => void;
        isActive: boolean;
        isVisible: boolean;
        text: string;
      };
      BackButton: {
        isVisible: boolean;
        show: () => void;
        hide: () => void;
        onClick: (callback: () => void) => void;
        offClick: (callback: () => void) => void;
      };
    };
  };
} 