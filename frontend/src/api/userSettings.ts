import axios from 'axios';
import { fetchWithAuth } from '../utils/fetchWithAuth';

export interface UserSettings {
  channelName: string | null;
  selectedChannels: string[];
  allChannels: string[];
}

// Извлечение user_id из Telegram WebApp или параметров
const getUserId = (): string | null => {
  try {
    // Пытаемся получить userId из Telegram WebApp
    if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
      return String(window.Telegram.WebApp.initDataUnsafe.user.id);
    }
    
    // Пытаемся получить из URL параметров
    const urlParams = new URLSearchParams(window.location.search);
    const userIdParam = urlParams.get('user_id');
    if (userIdParam) {
      return userIdParam;
    }
    
    // В крайнем случае можно использовать данные из глобальной переменной
    if (window.INJECTED_USER_ID) {
      return String(window.INJECTED_USER_ID);
    }
    
    return null;
  } catch (e) {
    console.error('Ошибка при получении userId:', e);
    return null;
  }
};

/**
 * Получение пользовательских настроек с сервера
 * @returns Объект с настройками пользователя
 */
export const getUserSettings = async (): Promise<UserSettings> => {
  try {
    const userId = getUserId();
    if (!userId) {
      console.warn('getUserSettings: userId не найден');
      return {
        channelName: null,
        selectedChannels: [],
        allChannels: []
      };
    }
    
    // Используем обычный fetch с добавлением заголовка с ID пользователя
    const response = await fetch('/user-settings', { 
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-User-Id': userId
      }
    });
    
    if (!response.ok) {
      throw new Error(`Ошибка при получении настроек: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('Получены настройки пользователя:', data);
    return data;
  } catch (error) {
    console.error('Ошибка при получении пользовательских настроек:', error);
    // Возвращаем пустые настройки в случае ошибки
    return {
      channelName: null,
      selectedChannels: [],
      allChannels: []
    };
  }
};

/**
 * Сохранение пользовательских настроек на сервере
 * @param settings Объект с настройками пользователя для сохранения
 * @returns Сохраненные настройки
 */
export const saveUserSettings = async (settings: UserSettings): Promise<UserSettings> => {
  try {
    const userId = getUserId();
    if (!userId) {
      console.warn('saveUserSettings: userId не найден');
      return settings;
    }
    
    // Используем axios с заголовком X-Telegram-User-Id
    const response = await axios.post('/user-settings', settings, {
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-User-Id': userId
      }
    });
    
    console.log('Настройки успешно сохранены:', response.data);
    return response.data;
  } catch (error) {
    console.error('Ошибка при сохранении пользовательских настроек:', error);
    return settings;
  }
}; 