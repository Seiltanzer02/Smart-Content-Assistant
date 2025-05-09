import axios from 'axios';
import { fetchWithAuth } from '../utils/fetchWithAuth';

export interface UserSettings {
  channelName: string | null;
  selectedChannels: string[];
  allChannels: string[];
}

/**
 * Получение пользовательских настроек с сервера
 * @returns Объект с настройками пользователя
 */
export const getUserSettings = async (): Promise<UserSettings> => {
  try {
    // Используем fetchWithAuth для автоматического добавления заголовка с ID пользователя
    const response = await fetch('/user-settings', { 
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      throw new Error(`Ошибка при получении настроек: ${response.status}`);
    }
    
    const data = await response.json();
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
    // Используем axios с заголовком X-Telegram-User-Id
    const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
    
    const response = await axios.post('/user-settings', settings, {
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-User-Id': userId ? String(userId) : ''
      }
    });
    
    return response.data;
  } catch (error) {
    console.error('Ошибка при сохранении пользовательских настроек:', error);
    throw error;
  }
}; 