import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './App.css';
import { TelegramAuth } from './components/TelegramAuth';
import { v4 as uuidv4 } from 'uuid';
import { Toaster, toast } from 'react-hot-toast';
import { ClipLoader } from 'react-spinners';
import SubscriptionWidget from './components/SubscriptionWidget';
import DirectPremiumStatus from './components/DirectPremiumStatus';
import { getUserSettings, saveUserSettings } from './api/userSettings';

// Определяем базовый URL API
const API_BASE_URL = '';

// --- ИЗМЕНЕНО: Убираем функцию для localStorage, так как теперь используем API ---
// const getUserSpecificKey = (baseKey: string, userId: string | null): string | null => {
//   if (!userId) return null; // Не работаем с localStorage без ID пользователя
//   return `${userId}_${baseKey}`;
// };

// --- ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ И ТИПЫ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ ---

// Оставляем остальной код без изменений

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  const [channelName, setChannelName] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [savedAnalysis, setSavedAnalysis] = useState<any>(null);
  const [savedPosts, setSavedPosts] = useState<SavedPost[]>([]);
  const [loadingSavedPosts, setLoadingSavedPosts] = useState(false);
  const [currentView, setCurrentView] = useState<'analysis' | 'posts' | 'calendar'>('analysis');
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [allChannels, setAllChannels] = useState<string[]>([]);
  const [filteredPosts, setFilteredPosts] = useState<SavedPost[]>([]);

  // --- МОДИФИЦИРОВАНО: Добавляем эффект для загрузки настроек пользователя с API ---
  useEffect(() => {
    if (isAuthenticated && userId) {
      const loadUserSettings = async () => {
        try {
          console.log('[App] Загрузка настроек пользователя с сервера...');
          const settings = await getUserSettings();
          
          // Применяем полученные настройки
          if (settings.channelName) {
            setChannelName(settings.channelName);
          }
          
          if (settings.selectedChannels && settings.selectedChannels.length > 0) {
            setSelectedChannels(settings.selectedChannels);
          }
          
          if (settings.allChannels && settings.allChannels.length > 0) {
            setAllChannels(settings.allChannels);
          }
          
          console.log('[App] Настройки пользователя успешно загружены:', settings);
          
          // Загружаем сохраненные посты
          fetchSavedPosts();
          
          // Загрузка сохраненного анализа для текущего выбранного канала
          if (settings.channelName) {
            fetchSavedAnalysis(settings.channelName);
          }
        } catch (error) {
          console.error('[App] Ошибка при загрузке настроек пользователя:', error);
          
          // Если не удалось загрузить настройки с сервера, используем локальные данные (временное решение)
          // Это будет удалено после полного перехода на API
          const channelKey = `${userId}_channelName`;
        const storedChannel = localStorage.getItem(channelKey);
    if (storedChannel) {
      setChannelName(storedChannel);
    }
    
          const selectedChannelsKey = `${userId}_selectedChannels`;
        const storedSelectedChannels = localStorage.getItem(selectedChannelsKey);
    if (storedSelectedChannels) {
      try {
        setSelectedChannels(JSON.parse(storedSelectedChannels));
    } catch (e) {
        console.error('Ошибка при восстановлении выбранных каналов:', e);
    }
      }

          const allChannelsKey = `${userId}_allChannels`;
        const storedChannels = localStorage.getItem(allChannelsKey);
      if (storedChannels) {
        try {
          setAllChannels(JSON.parse(storedChannels));
        } catch (e) {
          console.error('Ошибка при восстановлении списка каналов:', e);
        }
      }
      
          // Загружаем сохраненные посты
      fetchSavedPosts();

          // Загрузка сохраненного анализа для текущего выбранного канала
          if (channelName) {
        fetchSavedAnalysis(channelName);
    }
        }
      };
      
      loadUserSettings();
    }

    // Устанавливаем флаг загрузки после попытки аутентификации/загрузки
    setTimeout(() => {
      setLoading(false);
    }, 500);
  }, [isAuthenticated, userId]);

  // --- МОДИФИЦИРОВАНО: Сохраняем настройки при изменении канала ---
  useEffect(() => {
    if (userId && channelName) {
      // Сохраняем настройки через API
      const saveSettings = async () => {
        try {
          await saveUserSettings({
            channelName,
            selectedChannels,
            allChannels
          });
          console.log('[App] Настройки успешно сохранены на сервере');
        } catch (error) {
          console.error('[App] Ошибка при сохранении настроек:', error);
          
          // Временное решение: сохраняем в localStorage в случае ошибки API
          localStorage.setItem(`${userId}_channelName`, channelName);
        }
      };
      
      saveSettings();
    }
  }, [channelName, userId]);

  // --- МОДИФИЦИРОВАНО: Сохраняем выбранные каналы при их изменении ---
  useEffect(() => {
    if (userId && selectedChannels.length > 0) {
      // Сохраняем настройки через API
      const saveSettings = async () => {
        try {
          await saveUserSettings({
            channelName,
            selectedChannels,
            allChannels
          });
          console.log('[App] Настройки (выбранные каналы) успешно сохранены на сервере');
        } catch (error) {
          console.error('[App] Ошибка при сохранении настроек (выбранные каналы):', error);
          
          // Временное решение: сохраняем в localStorage в случае ошибки API
          localStorage.setItem(`${userId}_selectedChannels`, JSON.stringify(selectedChannels));
        }
      };
      
      saveSettings();
    }
  }, [selectedChannels, userId]);

  // --- МОДИФИЦИРОВАНО: Сохраняем все каналы при их изменении ---
  useEffect(() => {
    if (userId && allChannels.length > 0) {
      // Сохраняем настройки через API
      const saveSettings = async () => {
        try {
          await saveUserSettings({
            channelName,
            selectedChannels,
            allChannels
          });
          console.log('[App] Настройки (все каналы) успешно сохранены на сервере');
        } catch (error) {
          console.error('[App] Ошибка при сохранении настроек (все каналы):', error);
          
          // Временное решение: сохраняем в localStorage в случае ошибки API
          localStorage.setItem(`${userId}_allChannels`, JSON.stringify(allChannels));
        }
      };
      
      saveSettings();
    }
  }, [allChannels, userId]);

  // --- ОСТАЛЬНЫЕ ФУНКЦИИ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ ---

  // Функция для обновления channelName для разных представлений
  const handleChannelNameChange = (newChannelName: string) => {
    setChannelName(newChannelName);
  };

  // Обновление списка каналов на основе полученных постов
  const updateChannelsFromPosts = (posts: SavedPost[]) => {
    if (!posts.length) return;
    const channels = Array.from(new Set(posts.map(post => post.channel_name)));
    setAllChannels(prevChannels => {
      const updatedChannels = [...new Set([...prevChannels, ...channels])];
      
      // Сохраняем через API вместо localStorage
      if (userId) {
        saveUserSettings({
          channelName,
          selectedChannels,
          allChannels: updatedChannels
        }).catch(err => {
          console.error('[App] Ошибка при сохранении обновленных каналов:', err);
          // В случае ошибки, сохраняем в localStorage как резервный вариант
          const key = `${userId}_allChannels`;
          if (key) {
            localStorage.setItem(key, JSON.stringify(updatedChannels));
          }
        });
      }
      
      return updatedChannels;
    });
  };

  // ... остальные функции приложения

  // Места где используется кнопка добавления канала в фильтр
  // Например, внутри JSX:
  // <button 
  //   className="action-button"
  //   onClick={() => {
  //     if (channelName && !selectedChannels.includes(channelName)) {
  //       const updatedSelected = [...selectedChannels, channelName];
  //       setSelectedChannels(updatedSelected);
  //       
  //       // --- ИЗМЕНЕНО: Сохраняем через API вместо localStorage ---
  //       if (userId) {
  //         saveUserSettings({
  //           channelName,
  //           selectedChannels: updatedSelected,
  //           allChannels
  //         }).catch(err => {
  //           console.error('[App] Ошибка при сохранении выбранных каналов:', err);
  //         });
  //       }
  //     }
  //   }}
  // >
  //   + Добавить текущий канал
  // </button>
  //
  // И кнопка удаления канала из фильтра:
  // <button 
  //   className="remove-channel"
  //   onClick={() => {
  //     const updatedSelected = selectedChannels.filter(c => c !== channel);
  //     setSelectedChannels(updatedSelected);
  //     
  //     // --- ИЗМЕНЕНО: Сохраняем через API вместо localStorage ---
  //     if (userId) {
  //       saveUserSettings({
  //         channelName,
  //         selectedChannels: updatedSelected,
  //         allChannels
  //       }).catch(err => {
  //         console.error('[App] Ошибка при сохранении выбранных каналов:', err);
  //       });
  //     }
  //   }}
  // >
  //   ✕
  // </button>

  // ... остальной код компонента App
}
