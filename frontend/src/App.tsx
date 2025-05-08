import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './App.css';
import { TelegramAuth } from './components/TelegramAuth';
import { v4 as uuidv4 } from 'uuid';
import { Toaster, toast } from 'react-hot-toast';
import { ClipLoader } from 'react-spinners';
import SubscriptionWidget from './components/SubscriptionWidget';
import DirectPremiumStatus from './components/DirectPremiumStatus'; // <-- Импортируем новый компонент
import ImageUploader from './components/ImageUploader';
import ImageGallery from './components/ImageGallery';
import { createUUID } from './utils/helpers';

// Определяем базовый URL API
// Так как фронтенд и API на одном домене, используем пустую строку
// чтобы axios использовал относительные пути (например, /generate-plan)
const API_BASE_URL = '';
// const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000'; // Убираем использование process.env

// --- ДОБАВЛЕНО: Вспомогательная функция для ключей localStorage ---
const getUserSpecificKey = (baseKey: string, userId: string | null): string | null => {
  if (!userId) return null; // Не работаем с localStorage без ID пользователя
  return `${userId}_${baseKey}`;
};
// --- КОНЕЦ ДОБАВЛЕНИЯ ---

// Компоненты для отображения загрузки и сообщений
const Loading = ({ message }: { message: string }) => (
  <div className="loading-indicator">
    <div className="loading-spinner"></div>
    <p>{message}</p>
  </div>
);

const ErrorMessage = ({ message, onClose }: { message: string | null, onClose: () => void }) => (
  <div className="error-message">
    <p>{message}</p>
    <button className="action-button small" onClick={onClose}>Закрыть</button>
  </div>
);

const SuccessMessage = ({ message, onClose }: { message: string | null, onClose: () => void }) => (
  <div className="success-message">
    <p>{message}</p>
    <button className="action-button small" onClick={onClose}>Закрыть</button>
  </div>
);

// Simple error boundary component
class SimpleErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return <div className="error-message">Что-то пошло не так. Пожалуйста, перезагрузите страницу.</div>;
    }
    return this.props.children;
  }
}

// Типы для typescript
declare global {
  interface Window {
    Telegram?: {
      WebApp?: any;
    };
  }
}

// Инициализируем Telegram WebApp сразу
try {
  if (window.Telegram?.WebApp) {
    console.log('Инициализация Telegram WebApp...');
    window.Telegram.WebApp.ready();
  } else if (typeof (window as any).WebApp?.ready === 'function') {
    console.log('Инициализация WebApp из SDK...');
    (window as any).WebApp.ready();
  }
} catch (e) {
  console.error('Ошибка при инициализации Telegram WebApp:', e);
}

// Определяем типы для данных приложения
type ViewType = 'analyze' | 'suggestions' | 'plan' | 'details' | 'calendar' | 'edit' | 'posts';

// Тип для результата анализа
interface AnalysisResult {
  message?: string;
  themes: string[];
  styles: string[];
  analyzed_posts_sample: string[];
  best_posting_time: string;
  analyzed_posts_count: number;
}

// Тип для идеи
interface SuggestedIdea {
  id: string;
  created_at: string;
  channel_name: string;
  topic_idea: string;
  format_style: string;
  day?: number;
  is_detailed?: boolean;
  user_id?: string;
}

// Тип для детализированного поста
interface DetailedPost {
  post_text: string;
  images: PostImage[];
}

// Тип для изображения поста
interface PostImage {
  url: string;
  id?: string;
  preview_url?: string;
  alt?: string;
  author?: string;
  author_url?: string;
  source?: string;
}

// Тип для плана публикаций
interface PlanItem {
  day: number;
  topic_idea: string;
  format_style: string;
}

// Тип для сохраненного поста
interface SavedPost {
  id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  target_date: string;
  topic_idea: string;
  format_style: string;
  final_text: string;
  image_url?: string;
  channel_name?: string;
  images_ids?: string[];
  selected_image_data?: PostImage; // Добавляем поле для данных выбранного изображения
}

// Тип для дня календаря
interface CalendarDay {
  date: Date;
  posts: SavedPost[];
  isCurrentMonth: boolean;
  isToday: boolean;
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<ViewType>('analyze');
  const [channelName, setChannelName] = useState<string>('');
  
  // Состояния для функциональности приложения
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisLoadedFromDB, setAnalysisLoadedFromDB] = useState(false);
  const [isGeneratingIdeas, setIsGeneratingIdeas] = useState(false);
  const [suggestedIdeas, setSuggestedIdeas] = useState<SuggestedIdea[]>([]);
  const [selectedIdea, setSelectedIdea] = useState<SuggestedIdea | null>(null);
  const [isGeneratingPostDetails, setIsGeneratingPostDetails] = useState<boolean>(false);
  const [suggestedImages, setSuggestedImages] = useState<PostImage[]>([]);
  const [error, setError] = useState<string | null>(null); 
  const [success, setSuccess] = useState<string | null>(null);
  const [selectedImage, setSelectedImage] = useState<PostImage | null>(null);

  // Состояния для календаря и сохраненных постов
  const [savedPosts, setSavedPosts] = useState<SavedPost[]>([]);
  const [loadingSavedPosts, setLoadingSavedPosts] = useState(false);
  const [calendarDays, setCalendarDays] = useState<CalendarDay[]>([]);
  
  const [isSavingPost, setIsSavingPost] = useState(false);
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [allChannels, setAllChannels] = useState<string[]>([]);

  // Состояния для редактирования/создания поста
  const [currentPostId, setCurrentPostId] = useState<string | null>(null);
  const [currentPostDate, setCurrentPostDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [currentPostTopic, setCurrentPostTopic] = useState('');
  const [currentPostFormat, setCurrentPostFormat] = useState('');
  const [currentPostText, setCurrentPostText] = useState('');

  // Добавляем состояние для подписки
  const [showSubscription, setShowSubscription] = useState<boolean>(false);

  // --- ВОССТАНОВЛЕНО: Состояние для текущего месяца календаря --- 
  const [currentMonth, setCurrentMonth] = useState<Date>(new Date());

  // --- ИЗМЕНЕНИЕ: Загрузка состояния ИЗ localStorage ПОСЛЕ аутентификации ---
  useEffect(() => {
    if (isAuthenticated && userId) {
      // Восстанавливаем состояние из localStorage, используя user-specific ключи
      const channelKey = getUserSpecificKey('channelName', userId);
      if (channelKey) {
        const storedChannel = localStorage.getItem(channelKey);
    if (storedChannel) {
      setChannelName(storedChannel);
        }
    }
    
      const selectedChannelsKey = getUserSpecificKey('selectedChannels', userId);
      if (selectedChannelsKey) {
        const storedSelectedChannels = localStorage.getItem(selectedChannelsKey);
    if (storedSelectedChannels) {
      try {
        setSelectedChannels(JSON.parse(storedSelectedChannels));
    } catch (e) {
        console.error('Ошибка при восстановлении выбранных каналов:', e);
      }
    }
      }

      const allChannelsKey = getUserSpecificKey('allChannels', userId);
      if (allChannelsKey) {
        const storedChannels = localStorage.getItem(allChannelsKey);
      if (storedChannels) {
        try {
          setAllChannels(JSON.parse(storedChannels));
        } catch (e) {
          console.error('Ошибка при восстановлении списка каналов:', e);
        }
        }
      } else {
          // Если список каналов не найден, загружаем его из постов
          // (Это произойдет ниже в другом useEffect, зависящем от isAuthenticated)
      }
      
      // Загружаем сохраненные посты (перенесено сюда для ясности, т.к. зависит от userId для заголовка)
      fetchSavedPosts();

      // Загрузка сохраненного анализа для ТЕКУЩЕГО выбранного канала
      if (channelName) { // channelName будет установлен выше, если есть в localStorage
        fetchSavedAnalysis(channelName);
    }
    }

    // Устанавливаем флаг загрузки после попытки аутентификации/загрузки
    // (Перенесено из старого useEffect)
    setTimeout(() => {
      setLoading(false);
    }, 500);
  }, [isAuthenticated, userId]); // Запускаем при изменении статуса аутентификации и userId

  // --- ИЗМЕНЕНИЕ: Сохраняем канал в localStorage при изменении (ИСПОЛЬЗУЯ user-specific ключ) ---
  useEffect(() => {
    const key = getUserSpecificKey('channelName', userId);
    if (key && channelName) {
      localStorage.setItem(key, channelName);
    }
  }, [channelName, userId]); // Запускаем при изменении канала ИЛИ userId

  // Загружаем список всех каналов при авторизации (этот useEffect можно упростить или объединить)
  useEffect(() => {
    if (isAuthenticated && userId) {
       // Если allChannels пуст после попытки загрузки из localStorage, пробуем собрать из постов
       if (allChannels.length === 0) {
         console.log("Список каналов пуст, пытаемся обновить из постов...");
         updateChannelsFromPosts(savedPosts); // Используем уже загруженные посты
       }
    }
  }, [isAuthenticated, userId, allChannels.length, savedPosts]); // Добавили allChannels.length и savedPosts
  
  // --- ВОССТАНОВЛЕНО: useEffect для генерации дней календаря --- 
  useEffect(() => {
    if (currentMonth && currentView === 'calendar') { // Добавляем проверку currentView
      generateCalendarDays();
    }
  }, [currentMonth, savedPosts, currentView]); // Добавляем currentView в зависимости
  // --- КОНЕЦ ВОССТАНОВЛЕНИЯ ---
  
  // --- ВОССТАНОВЛЕНО: Функция для генерации дней календаря --- 
  const generateCalendarDays = () => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    let firstDayOfWeek = firstDay.getDay();
    firstDayOfWeek = firstDayOfWeek === 0 ? 6 : firstDayOfWeek - 1;
    
    const days: CalendarDay[] = [];
    const prevMonthLastDay = new Date(year, month, 0).getDate();
    for (let i = firstDayOfWeek - 1; i >= 0; i--) {
      const date = new Date(year, month - 1, prevMonthLastDay - i);
      days.push({
        date,
        posts: savedPosts.filter(post => new Date(post.target_date).toDateString() === date.toDateString()),
        isCurrentMonth: false,
        isToday: date.toDateString() === new Date().toDateString()
      });
    }
    
    for (let i = 1; i <= lastDay.getDate(); i++) {
      const date = new Date(year, month, i);
      days.push({
        date,
        posts: savedPosts.filter(post => new Date(post.target_date).toDateString() === date.toDateString()),
        isCurrentMonth: true,
        isToday: date.toDateString() === new Date().toDateString()
      });
    }
    
    const daysToAdd = 42 - days.length; // 6 строк * 7 дней
    for (let i = 1; i <= daysToAdd; i++) {
      const date = new Date(year, month + 1, i);
      days.push({
        date,
        posts: savedPosts.filter(post => new Date(post.target_date).toDateString() === date.toDateString()),
        isCurrentMonth: false,
        isToday: date.toDateString() === new Date().toDateString()
      });
    }
    
    setCalendarDays(days);
  };
  // --- КОНЕЦ ВОССТАНОВЛЕНИЯ ---
  
  // --- ВОССТАНОВЛЕНО: Функции навигации по месяцам --- 
  const goToPrevMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
  };
  
  const goToNextMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
  };
  // --- КОНЕЦ ВОССТАНОВЛЕНИЯ ---
  
  // --- ИЗМЕНЕНИЕ: useEffect для загрузки данных при смене канала --- 
  useEffect(() => {
    if (isAuthenticated && channelName) {
      // --- ДОБАВЛЕНО: Очистка состояния перед загрузкой ---
      setAnalysisResult(null); // Очищаем предыдущий анализ
      setSuggestedIdeas([]);  // Очищаем предыдущие идеи
      setSavedPosts([]); // Очищаем предыдущие посты
      setSelectedIdea(null); // Сбрасываем выбранную идею
      // --- КОНЕЦ ДОБАВЛЕНИЯ ---

      // Загрузка сохраненного анализа для выбранного канала
      fetchSavedAnalysis(channelName);
      // Загрузка сохраненных идей для выбранного канала
      fetchSavedIdeas();
      // Загрузка сохраненных постов для выбранного канала
      fetchSavedPosts(); 
    } else if (isAuthenticated) {
      // Если канал не выбран, очищаем специфичные для канала данные
      setAnalysisResult(null);
      setSuggestedIdeas([]);
      // --- ДОБАВЛЕНО: Также очищаем посты, если канал сброшен ---
      setSavedPosts([]); 
      // --- КОНЕЦ ДОБАВЛЕНИЯ ---
    setSelectedIdea(null); 
      // Возможно, загрузить все посты пользователя, если канал не выбран?
      fetchSavedPosts(); // Загружаем все посты пользователя
    }
  }, [isAuthenticated, channelName]); // Зависимости остаются прежними
  // --- КОНЕЦ ИЗМЕНЕНИЯ --- 
  
  // Функция для загрузки сохраненных постов
  const fetchSavedPosts = async () => {
    setLoadingSavedPosts(true);
    setError(null);
    
    // --- ДОБАВЛЕНО: Логирование userId перед запросом --- 
    console.log(`[fetchSavedPosts] Используемый userId для заголовка: ${userId}`);
    if (!userId) {
      console.error("[fetchSavedPosts] userId отсутствует, запрос постов не будет выполнен корректно.");
      setLoadingSavedPosts(false);
      // --- ДОБАВЛЕНО: Очищаем посты при ошибке userId ---
      setSavedPosts([]);
      // --- КОНЕЦ ДОБАВЛЕНИЯ ---
      return; // Прерываем выполнение
    }
    // --- КОНЕЦ ДОБАВЛЕНИЯ ---

    try {
      // --- ИЗМЕНЕНИЕ: Заменяем postsToSet на postsResult, чтобы гарантировать перезапись --- 
      let postsResult: SavedPost[] = [];
      const useChannelFilter = selectedChannels.length > 0;
      
      if (useChannelFilter) {
        // Используем фильтр selectedChannels
        const allFilteredPosts: SavedPost[] = [];
        // --- ИЗМЕНЕНО: Используем Promise.all для параллельной загрузки ---
        const promises = selectedChannels.map(channel =>
          axios.get('/posts', {
            params: { channel_name: channel },
            headers: { 'x-telegram-user-id': userId }
          }).then(response => {
            if (response.data && Array.isArray(response.data)) {
              return response.data;
            }
            return [];
          }).catch(err => {
            console.error(`Ошибка при загрузке постов для канала ${channel}:`, err);
            return []; // Возвращаем пустой массив при ошибке
          })
        );
        const results = await Promise.all(promises);
        postsResult = results.flat(); // Объединяем массивы результатов
        // --- КОНЕЦ ИЗМЕНЕНИЯ ---
      } else if (channelName) {
        // Если фильтр не активен, но выбран канал вверху, грузим посты для него
        const response = await axios.get('/posts', {
          params: { channel_name: channelName }, 
          headers: { 'x-telegram-user-id': userId } 
        });
        if (response.data && Array.isArray(response.data)) {
          postsResult = response.data;
        }
      } else {
        // Если ни фильтр, ни канал не выбраны, грузим все посты пользователя
        const response = await axios.get('/posts', { 
           headers: { 'x-telegram-user-id': userId } 
        });
        if (response.data && Array.isArray(response.data)) {
          postsResult = response.data;
        }
      }
      
      // --- ИЗМЕНЕНИЕ: Гарантированно перезаписываем состояние --- 
      setSavedPosts(postsResult); 
      // Обновляем список всех каналов на основе ТОЛЬКО ЧТО полученных постов
      updateChannelsFromPosts(postsResult); 
      // --- КОНЕЦ ИЗМЕНЕНИЯ ---
      
    } catch (err: any) {
      console.error('Ошибка при загрузке сохраненных постов:', err);
      setError(err.response?.data?.detail || err.message || 'Ошибка при загрузке сохраненных постов');
      // --- ДОБАВЛЕНО: Очищаем посты при ошибке загрузки ---
      setSavedPosts([]); 
      // --- КОНЕЦ ДОБАВЛЕНИЯ ---
    } finally {
      setLoadingSavedPosts(false);
    }
  };
  
  // Вспомогательная функция для обновления списка каналов из постов
  const updateChannelsFromPosts = (posts: SavedPost[]) => {
    const currentUserPosts = posts.filter(post => String(post.user_id) === String(userId));
    if (posts.length !== currentUserPosts.length) {
        console.warn(`[updateChannelsFromPosts] Обнаружены посты (${posts.length - currentUserPosts.length} шт.), не принадлежащие текущему пользователю (${userId}). Они будут проигнорированы при обновлении списка каналов.`);
    }
    
    // Собираем уникальные каналы из ТОЛЬКО ЧТО полученных и отфильтрованных постов
    const newChannels = [...new Set(currentUserPosts 
      .map(post => post.channel_name)
      .filter((channel): channel is string => !!channel) 
    )];
    
    // Обновляем список всех каналов, добавляя новые, которых еще нет
    if (newChannels.length > 0) {
      // --- ИЗМЕНЕНИЕ: Обновляем, беря текущее состояние и добавляя новые каналы ---
      setAllChannels(prevChannels => {
        const updatedChannels = [...new Set([...prevChannels, ...newChannels])];
        // Сохраняем обновленный список в localStorage
        const key = getUserSpecificKey('allChannels', userId);
        if (key) {
          localStorage.setItem(key, JSON.stringify(updatedChannels));
        }
        return updatedChannels; // Возвращаем новое состояние
      });
      // --- КОНЕЦ ИЗМЕНЕНИЯ ---
    }
  };
  
  // Добавляем функцию для регенерации только изображений
  const regeneratePostDetails = async () => {
    if (!selectedIdea) return;
    
    setIsGeneratingPostDetails(true);
    setError('');
    setSuccess('');

    try {
      const response = await axios.post(`${API_BASE_URL}/generate-post-details`, {
        topic_idea: selectedIdea.topic_idea,
        format_style: selectedIdea.format_style || '',
        channel_name: selectedIdea.channel_name || '',
        regenerate_images_only: true
      }, {
        headers: {
          'x-telegram-user-id': userId ? userId : 'unknown'
        }
      });

      if (response.data && response.data.found_images && selectedIdea) {
        const newImages = response.data.found_images.map((img: any) => ({
          url: img.url || img.urls?.regular || img.regular_url || img.preview_url || '',
          alt: img.alt_description || img.description || 'Изображение для поста',
          author: img.user?.name || img.author_name || '',
          author_url: img.user?.links?.html || img.author_url || ''
        }));

        setSelectedIdea(prevState => {
          if (!prevState) return null;
          return {
            ...prevState,
            images: newImages
          };
        });

        if (selectedIdea) {
          setSuggestedImages(newImages);
        setSuccess('Изображения успешно обновлены');
        }
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при обновлении изображений');
      console.error('Ошибка при обновлении изображений:', err);
    } finally {
      setIsGeneratingPostDetails(false);
    }
  };

  // Функция сохранения поста
  const handleSaveOrUpdatePost = async () => {
    setIsSavingPost(true);
    setError("");
    setSuccess("");

    // Prepare payload
    const postPayload: {
      target_date: string;
      topic_idea: string;
      format_style: string;
      final_text: string;
      channel_name?: string;
      selected_image_data?: PostImage | null;
    } = {
      target_date: currentPostDate,
      topic_idea: currentPostTopic,
      format_style: currentPostFormat,
      final_text: currentPostText,
      channel_name: channelName || undefined,
      selected_image_data: selectedImage
    };

    try {
      let response;
      if (currentPostId) {
        // Update existing post
        console.log(`Updating post ${currentPostId} with payload:`, postPayload);
        response = await axios.put(`/posts/${currentPostId}`, postPayload, {
           headers: { 'x-telegram-user-id': userId }
        });
        setSuccess("Пост успешно обновлен");
      } else {
        // Create new post
        console.log("Creating new post with payload:", postPayload);
        response = await axios.post('/posts', postPayload, {
           headers: { 'x-telegram-user-id': userId }
        });
        setSuccess("Пост успешно сохранен");
      }
      
      if (response.data) {
        // Update local state and navigate
        await fetchSavedPosts();
        setCurrentView('calendar');
        setCurrentPostId(null);
        setCurrentPostDate(new Date().toISOString().split('T')[0]);
        setCurrentPostTopic('');
        setCurrentPostFormat('');
        setCurrentPostText('');
        setSelectedImage(null);
        setSuggestedImages([]);
      }
    } catch (err: any) { 
      const errorMsg = err.response?.data?.detail || err.message || (currentPostId ? 'Ошибка при обновлении поста' : 'Ошибка при сохранении поста');
      setError(errorMsg);
      console.error(currentPostId ? 'Ошибка при обновлении поста:' : 'Ошибка при сохранении поста:', err);
    } finally {
      setIsSavingPost(false);
    }
  };
  
  // Функция для удаления поста
  const deletePost = async (postId: string) => {
    try {
      setLoadingSavedPosts(true);
      const response = await axios.delete(`/posts/${postId}`, {
        headers: { 'x-telegram-user-id': userId ? userId : undefined }
      });
      
      if (response.data && response.data.success) {
        // Удаляем пост из локального состояния
        setSavedPosts(currentPosts => currentPosts.filter(post => post.id !== postId));
        setSuccess('Пост успешно удален');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при удалении поста');
    } finally {
      setLoadingSavedPosts(false);
    }
  };
  
  // Функция для загрузки данных сохраненного изображения и установки его как выбранного
  const fetchAndSetSavedImage = async (imageId: string) => {
    if (!imageId) return;
    try {
      console.log(`Загрузка данных для сохраненного изображения: ${imageId}`);
      const response = await axios.get(`${API_BASE_URL}/images/${imageId}`, {
          headers: { 'x-telegram-user-id': userId }
      });
      if (response.data && !response.data.error) {
          // Преобразуем данные из БД в формат PostImage
          const imageData = response.data;
          const imageObject: PostImage = {
              id: imageData.id,
              url: imageData.url,
              preview_url: imageData.preview_url || imageData.url, 
              alt: imageData.alt || '',
              author: imageData.author_name || '', // Используем author_name из БД
              author_url: imageData.author_url || '',
              source: imageData.source || 'db'
          };
          setSelectedImage(imageObject);
          console.log(`Установлено сохраненное изображение:`, imageObject);
      } else {
          console.warn(`Не удалось загрузить данные для изображения ${imageId}.`);
          setSelectedImage(null); // Сбрасываем, если не удалось загрузить
      }
    } catch (err: any) {
        if (err.response && err.response.status === 404) {
            console.warn(`Сохраненное изображение ${imageId} не найдено (404).`);
        } else {
            console.error(`Ошибка при загрузке сохраненного изображения ${imageId}:`, err);
        }
        setSelectedImage(null); // Сбрасываем при любой ошибке
    }
  };

  // --- ДОБАВЛЕНО: Обработчик загрузки своего изображения --- 
  const handleCustomImageUpload = (imageUrl: string) => {
    if (!imageUrl) return;
    // --- ИЗМЕНЕНИЕ: Преобразуем относительный URL в абсолютный ---
    // Предполагаем, что бэкенд запущен на том же хосте, порт 8000
    const backendBaseUrl = `${window.location.protocol}//${window.location.hostname}:8000`;
    const absoluteImageUrl = imageUrl.startsWith('http') ? imageUrl : `${backendBaseUrl}${imageUrl}`;
    // --- КОНЕЦ ИЗМЕНЕНИЯ ---

    // Создаем объект PostImage для загруженного файла
    const uploadedImage: PostImage = {
      id: `uploaded-${uuidv4()}`, // Генерируем уникальный ID
      // --- ИЗМЕНЕНИЕ: Используем абсолютный URL ---
      url: absoluteImageUrl,
      preview_url: absoluteImageUrl, // Используем тот же URL для превью
      // --- КОНЕЦ ИЗМЕНЕНИЯ ---
      alt: 'Загруженное изображение',
      // --- ИЗМЕНЕНИЕ: Добавим отметку об источнике в автора для ясности ---
      author: 'Пользователь (upload)', 
      // --- КОНЕЦ ИЗМЕНЕНИЯ ---
      source: 'upload' // Указываем источник
    };
    setSelectedImage(uploadedImage); // Устанавливаем как выбранное
    // Опционально: можно добавить в suggestedImages, но лучше держать их раздельно
    // setSuggestedImages(prev => [uploadedImage, ...prev]); 
    setSuccess("Изображение успешно загружено и выбрано");
  };
  // --- КОНЕЦ ДОБАВЛЕНИЯ ---
  
  // Функция для открытия редактирования поста
  const startEditingPost = (post: SavedPost) => {
    setCurrentPostId(post.id);
    setCurrentPostDate(post.target_date);
    setCurrentPostTopic(post.topic_idea);
    setCurrentPostFormat(post.format_style);
    setCurrentPostText(post.final_text);
    setChannelName(post.channel_name || '');
    setSuggestedImages([]); // Очищаем предложенные
    setIsGeneratingPostDetails(false);
    setError(null);
    setSuccess(null);
    setCurrentView('edit');

    // --- ИСПРАВЛЕНО: Используем selected_image_data напрямую ---
    // Проверяем, есть ли данные о выбранном изображении
    if (post.selected_image_data) {
      // Используем данные напрямую, не нужно загружать их отдельно
      setSelectedImage(post.selected_image_data);
    } else {
      // Для обратной совместимости: если selected_image_data нет, но есть images_ids
      const savedImageId = post.images_ids && post.images_ids.length > 0 ? post.images_ids[0] : null;
      if (savedImageId) {
        fetchAndSetSavedImage(savedImageId);
      } else {
        // Если нет ни selected_image_data, ни images_ids, сбрасываем selectedImage
        setSelectedImage(null);
      }
    }
    // --- КОНЕЦ ИСПРАВЛЕНИЯ ---
  };
  
  // Функция для сохранения идей в базу данных
  const saveIdeasToDatabase = async (ideasToSave: SuggestedIdea[]) => { // Принимаем идеи как аргумент
    if (!userId) {
      console.error('Невозможно сохранить идеи: userId отсутствует');
      return; 
    }
    
    console.log('Попытка сохранения идей в БД:', ideasToSave);
    
    try {
      await axios.post(
        `${API_BASE_URL}/save-suggested-ideas`, 
        {
          ideas: ideasToSave,
          channel_name: channelName // Передаем текущее имя канала
        },
        {
          headers: {
            'x-telegram-user-id': userId
          }
        }
      );
      console.log('Идеи успешно отправлены на сохранение');
      // Опционально: показать сообщение об успехе, но тихое сохранение лучше
      // toast.success('Идеи сохранены в фоне');
    } catch (err: any) {
      console.error('Ошибка при сохранении идей:', err);
      setError(err.response?.data?.detail || err.message || 'Ошибка при сохранении идей');
      toast.error('Ошибка при сохранении идей'); // Показываем ошибку пользователю
    }
  };
  
  // Функция для фильтрации постов по каналам
  const filterPostsByChannels = async () => {
    if (selectedChannels.length === 0) {
       // --- ИЗМЕНЕНИЕ: Вместо ошибки, просто загружаем все посты пользователя ---
       console.log("Фильтр каналов пуст, загружаем все посты пользователя...");
       // setError("Выберите хотя бы один канал для фильтрации"); // Убираем ошибку
       // return;
    }
    
    // Просто используем основную функцию загрузки постов,
    // она сама обработает пустой selectedChannels или выбранный channelName
    await fetchSavedPosts();
    // --- КОНЕЦ ИЗМЕНЕНИЯ ---
  };

  // Обработчик успешной авторизации
  const handleAuthSuccess = (authUserId: string) => {
    console.log('Авторизация успешна:', authUserId);
    setUserId(authUserId);
    setIsAuthenticated(true);
    axios.defaults.headers.common['X-Telegram-User-Id'] = authUserId;
  };

  // Функция для анализа канала
  const analyzeChannel = async () => {
    if (!channelName) {
      setError("Введите имя канала");
      return;
    }

    setIsAnalyzing(true);
    // Сбрасываем флаг загрузки из БД перед новым анализом
    setAnalysisLoadedFromDB(false);
    setError(null);
    setSuccess(null);
    setAnalysisResult(null);

    try {
      const response = await axios.post('/analyze', { username: channelName }, {
        headers: { 'x-telegram-user-id': userId }
      });
      setAnalysisResult(response.data);
      setSuccess('Анализ успешно завершен');
      
      // Только после успешного анализа добавляем канал в список всех каналов
      if (!allChannels.includes(channelName)) {
        const updatedChannels = [...allChannels, channelName];
        setAllChannels(updatedChannels);
        const allKey = getUserSpecificKey('allChannels', userId);
        if (allKey) {
          localStorage.setItem(allKey, JSON.stringify(updatedChannels));
        }
      
        // Добавляем канал в список выбранных, если его там нет
        if (!selectedChannels.includes(channelName)) {
          const updatedSelected = [...selectedChannels, channelName];
          setSelectedChannels(updatedSelected);
          const selectedKey = getUserSpecificKey('selectedChannels', userId);
          if (selectedKey) {
            localStorage.setItem(selectedKey, JSON.stringify(updatedSelected));
          }
        }
      }
      // Устанавливаем флаг, что анализ загружен из БД
      setAnalysisLoadedFromDB(true);
    } catch (err: any) { 
      setError(err.response?.data?.detail || err.message || 'Ошибка при анализе канала');
      console.error('Ошибка при анализе:', err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Функция для генерации идей
  const generateIdeas = async () => {
    try {
      // Если уже есть идеи, спрашиваем подтверждение
      if (suggestedIdeas.length > 0) {
        const confirmed = confirm("У вас уже есть сгенерированные идеи. Сгенерировать новые? Старые идеи будут удалены.");
        if (!confirmed) {
          return;
        }
      }
      
      setIsGeneratingIdeas(true);
      setError("");
      setSuggestedIdeas([]);

      // Если анализ не завершен
      if (!analysisResult) {
        setError("Пожалуйста, сначала проведите анализ канала");
        setIsGeneratingIdeas(false);
      return;
    }

      // Запрос на генерацию идей
      const response = await axios.post(
        `${API_BASE_URL}/generate-plan`,
        {
          themes: analysisResult.themes,
          styles: analysisResult.styles,
          period_days: 7,
          channel_name: channelName
        },
        {
          headers: {
            'x-telegram-user-id': userId || 'unknown'
          }
        }
      );

      if (response.data && response.data.plan) {
        console.log('Полученные идеи:', response.data.plan);
        
        // Преобразуем полученные идеи в нужный формат
        const formattedIdeas = response.data.plan.map((idea: any, index: number) => ({
          id: `idea-${Date.now()}-${index}`,
          topic_idea: idea.topic_idea || idea.title,
          format_style: idea.format_style || idea.format,
          day: idea.day,
          channel_name: channelName, // Привязываем к текущему каналу
          isNew: true, // Помечаем как новые
        }));

        setSuggestedIdeas(formattedIdeas);
        setSuccess('Идеи успешно сгенерированы');
        
        // Сохраняем сгенерированные идеи В ФОНЕ (не ждем завершения)
        saveIdeasToDatabase(formattedIdeas); // Передаем новые идеи в функцию сохранения
      }
    } catch (err: any) { 
      setError(err.response?.data?.detail || err.message || 'Ошибка при генерации идей');
      console.error('Ошибка при генерации идей:', err);
    } finally {
      setIsGeneratingIdeas(false);
      setCurrentView('suggestions');
    }
  };

  // Функция для загрузки сохраненных идей
  const fetchSavedIdeas = async () => {
    if (!channelName) {
      setSuggestedIdeas([]); // Очищаем идеи, если канал не выбран
      return;
    }
    
    setIsGeneratingIdeas(true); // Используем тот же флаг загрузки
    setError(null);
    
    try {
      const response = await axios.get('/ideas', {
        params: { channel_name: channelName }, // Всегда фильтруем по текущему каналу
        headers: { 'x-telegram-user-id': userId }
      });
      if (response.data && Array.isArray(response.data.ideas)) {
        const validIdeas = response.data.ideas.map((idea: any) => ({
          ...idea,
          id: String(idea.id) // Приводим ID к строке на всякий случай
        }));
        setSuggestedIdeas(validIdeas);
      } else {
        setSuggestedIdeas([]); // Очищаем, если от сервера пришел некорректный ответ
      }
    } catch (err: any) {
      console.error('Ошибка при загрузке идей:', err);
      setError('Не удалось загрузить сохраненные идеи');
      setSuggestedIdeas([]); // Очищаем при ошибке
    } finally {
      setIsGeneratingIdeas(false);
    }
  };

  // Функция для получения подробностей идеи
  const handleDetailIdea = (idea: SuggestedIdea) => {
      setSelectedIdea(idea);
    setCurrentPostId(null);
    setChannelName(idea.channel_name || '');
    setCurrentPostTopic(idea.topic_idea);
    setCurrentPostFormat(idea.format_style);
    setCurrentPostDate(new Date().toISOString().split('T')[0]);
    setCurrentPostText('');
      setSelectedImage(null);
    setSuggestedImages([]);
    setError(null);
    setSuccess(null);
    
    setCurrentView('edit');
  };

  // Function to handle selecting/deselecting a suggested image
  const handleImageSelection = (imageToSelect: PostImage | undefined) => {
    console.log('handleImageSelection вызван с изображением:', imageToSelect);

    if (!imageToSelect) {
      console.error("Попытка выбрать undefined изображение");
      return;
    }

    // Сравниваем URL для определения, выбрано ли уже это изображение
    const isCurrentlySelected = selectedImage && selectedImage.url === imageToSelect.url;

    if (isCurrentlySelected) {
      // Если изображение уже выбрано, снимаем выбор
      setSelectedImage(null);
      setSuccess(null);
    } else {
      // Иначе, выбираем новое изображение
      // Создаем новый объект изображения с обязательными полями для API
      const processedImage: PostImage = {
        ...imageToSelect,
        id: imageToSelect.id || `img-${Date.now()}`,
        url: imageToSelect.url,
        preview_url: imageToSelect.preview_url || imageToSelect.url,
        alt: imageToSelect.alt || 'Изображение для поста',
        author: imageToSelect.author || ''
      };
      
      setSelectedImage(processedImage);
      setSuccess("Изображение выбрано");
    }
  };

  // Effect to fetch post details when creating a new post from an idea
  // --- ИЗМЕНЕНО: Оборачиваем логику в useCallback --- 
  const fetchDetailsCallback = useCallback(async () => {
      // Only run if: we are in 'edit' view, creating a NEW post (no currentPostId), and an idea is selected
      if (currentView === 'edit' && !currentPostId && selectedIdea) {
        console.log(`Fetching details for new post based on idea: ${selectedIdea.topic_idea}`);
        setIsGeneratingPostDetails(true);
        setError(null);
        setSuccess(null);
        setSuggestedImages([]); // Clear any potentially stale images
        setSelectedImage(null); // Ensure no image is pre-selected

        try {
          const response = await axios.post(`${API_BASE_URL}/generate-post-details`, {
            topic_idea: selectedIdea.topic_idea,
          format_style: selectedIdea.format_style,
          post_samples: analysisResult?.analyzed_posts_sample || [] // Передаем примеры постов, если есть
        },
        {
          headers: {
            'x-telegram-user-id': userId || 'unknown' // Передаем строку или 'unknown'
          }
        }
        );
        setCurrentPostText(response.data.generated_text);
        setSuggestedImages(response.data.found_images || []);
        setSuccess("Детали поста успешно сгенерированы");

    } catch (err: any) {
        setError(err.response?.data?.detail || err.message || 'Ошибка при генерации деталей поста');
        console.error('Ошибка при генерации деталей поста:', err);
    } finally {
          setIsGeneratingPostDetails(false);
        }
      }
    // Зависимости для useCallback: все внешние переменные, используемые внутри
  }, [currentView, currentPostId, selectedIdea, userId, API_BASE_URL, analysisResult, setIsGeneratingPostDetails, setError, setSuccess, setSuggestedImages, setSelectedImage, setCurrentPostText]);

  // Вызываем useCallback-функцию внутри useEffect
  useEffect(() => {
    fetchDetailsCallback();
    // Зависимость useEffect теперь - это сама useCallback-функция
  }, [fetchDetailsCallback]);
  // --- КОНЕЦ ИЗМЕНЕНИЯ ---

  // Функция для загрузки сохраненного анализа канала
  const fetchSavedAnalysis = async (channel: string) => {
    if (!channel) return;
    setLoadingAnalysis(true);
    // Сбрасываем текущий результат, чтобы не показывать старые данные во время загрузки
    setAnalysisResult(null);
    // Сбрасываем флаг загрузки из БД
    setAnalysisLoadedFromDB(false);
    try {
      console.log(`Загрузка сохраненного анализа для канала: ${channel}`);
      const response = await axios.get(`${API_BASE_URL}/channel-analysis`, {
        params: { channel_name: channel },
        headers: { 'x-telegram-user-id': userId }
      });
      
      // Проверяем, что ответ содержит данные и не является объектом ошибки
      if (response.data && !response.data.error) {
        console.log('Сохраненный анализ найден:', response.data);
        setAnalysisResult(response.data); 
        setSuccess(`Загружен сохраненный анализ для @${channel}`);
        // Устанавливаем флаг, что анализ загружен из БД
        setAnalysisLoadedFromDB(true);
      } else {
        console.log(`Сохраненный анализ для @${channel} не найден.`);
        // Если анализ не найден (или пришла ошибка), оставляем analysisResult null
        setAnalysisResult(null); 
        // Можно очистить сообщение об успехе или установить сообщение о том, что анализ не найден
        // setSuccess(null);
      }
    } catch (err: any) {
      // Обрабатываем ошибку 404 (Не найдено) отдельно, чтобы не показывать как ошибку
      if (err.response && err.response.status === 404) {
         console.log(`Сохраненный анализ для @${channel} не найден (404).`);
         setAnalysisResult(null);
      } else {
        console.error('Ошибка при загрузке сохраненного анализа:', err);
        setError(err.response?.data?.detail || err.message || 'Ошибка при загрузке сохраненного анализа');
        setAnalysisResult(null); // Сбрасываем результат при ошибке
      }
    } finally {
      setLoadingAnalysis(false);
    }
  }; // <-- ДОБАВЛЕНА ТОЧКА С ЗАПЯТОЙ

  // Компонент загрузки
  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Загрузка приложения...</p>
    </div>
  );
  }

  // Компонент авторизации
  if (!isAuthenticated) {
    return <TelegramAuth onAuthSuccess={handleAuthSuccess} />;
  }

  // Основной интерфейс
  return (
    <div className="app-container">
      <header className="app-header">
        <div className="logo">Smart Content Assistant</div>
        <div className="header-icons">
          {/* Кнопка для управления подпиской */}
          <button
            className="icon-button"
            onClick={() => setShowSubscription(!showSubscription)}
            title="Управление подпиской"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
            </svg>
          </button>
          <button
            className={`icon-button ${currentView === 'analyze' ? 'active' : ''}`}
            onClick={() => {setCurrentView('analyze'); setShowSubscription(false);}}
            title="Анализ канала"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M10 20H14V4H10V20ZM4 20H8V12H4V20ZM16 9V20H20V9H16Z" fill="currentColor"/>
            </svg>
          </button>
          <button
            className={`icon-button ${currentView === 'suggestions' ? 'active' : ''}`}
            onClick={() => {setCurrentView('suggestions'); setShowSubscription(false);}}
            title="Идеи для постов"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 22C6.477 22 2 17.523 2 12C2 6.477 6.477 2 12 2C17.523 2 22 6.477 22 12C22 17.523 17.523 22 12 22ZM12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM11 7H13V9H11V7ZM11 11H13V17H11V11Z" fill="currentColor"/>
            </svg>
          </button>
          <button
            className={`icon-button ${currentView === 'calendar' ? 'active' : ''}`}
            onClick={() => {setCurrentView('calendar'); setShowSubscription(false);}}
            title="Календарь"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M17 3H21C21.5523 3 22 3.44772 22 4V20C22 20.5523 21.5523 21 21 21H3C2.44772 21 2 20.5523 2 20V4C2 3.44772 2.44772 3 3 3H7V1H9V3H15V1H17V3ZM4 9V19H20V9H4ZM4 5V7H20V5H4ZM6 11H8V13H6V11ZM10 11H12V13H10V11ZM14 11H16V13H14V11Z" fill="currentColor"/>
            </svg>
          </button>
        </div>
      </header>
      
      {/* Блок подписки */}
      {showSubscription && (
        <>
          <SubscriptionWidget userId={userId} isActive={true}/> {/* Передаем isActive в старый виджет */} 
          <DirectPremiumStatus userId={userId} /> {/* <-- Добавляем новый компонент */} 
        </>
      )}

      <main className="app-main">
        {/* Сообщения об ошибках и успешном выполнении */}
        {error && <ErrorMessage message={error} onClose={() => setError(null)} />}
        {success && <SuccessMessage message={success} onClose={() => setSuccess(null)} />}

        {/* Навигация */}
    <div className="navigation-buttons">
          <button 
            onClick={() => setCurrentView('analyze')} 
            className={`action-button ${currentView === 'analyze' ? 'active' : ''}`}
          >
            Анализ
          </button>
          <button 
            onClick={() => {
              setCurrentView('suggestions');
              if (suggestedIdeas.length === 0) {
                fetchSavedIdeas();
              }
            }} 
            className={`action-button ${currentView === 'suggestions' ? 'active' : ''}`}
            disabled={!channelName}
          >
            Идеи
          </button>
          <button 
            onClick={() => {
              setCurrentView('calendar');
              fetchSavedPosts();
            }} 
            className={`action-button ${currentView === 'calendar' ? 'active' : ''}`}
          >
            Календарь
          </button>
          <button 
            onClick={() => {
              setCurrentView('posts');
              fetchSavedPosts();
            }} 
            className={`action-button ${currentView === 'posts' ? 'active' : ''}`}
          >
            Посты
          </button>
    </div>

        {/* Выбор канала */}
        <div className="channel-selector">
          <label>Каналы: </label>
          <select 
            value={channelName} 
            onChange={(e) => setChannelName(e.target.value)}
            className="channel-select"
          >
            <option value="">Выберите канал</option>
            {allChannels.map(channel => (
              <option key={channel} value={channel}>{channel}</option>
            ))}
          </select>
        </div>

        {/* Контент */}
        <div className="view-container">
          {/* Вид анализа */}
          {currentView === 'analyze' && ( 
            <div className="view analyze-view">
      <h2>Анализ Telegram-канала</h2>
      <div className="input-container">
        <input
          type="text"
          className="channel-input"
          value={channelName}
          onChange={(e) => setChannelName(e.target.value.replace(/^@/, ''))}
          placeholder="Введите username канала (без @)"
                  disabled={isAnalyzing}
                />
                <button 
                  onClick={analyzeChannel} 
                  className="action-button"
                  disabled={isAnalyzing || !channelName}
                >
                  {isAnalyzing ? 'Анализ...' : 'Анализировать'}
        </button>
      </div>

              {/* Добавляем индикатор загрузки сохраненного анализа */}
              {loadingAnalysis && (
                  <div className="loading-indicator small">
                      <div className="loading-spinner small"></div>
                      <p>Загрузка сохраненного анализа...</p>
                  </div>
              )}

              {isAnalyzing && (
                <div className="loading-indicator">
                  <div className="loading-spinner"></div>
                  <p>Анализируем канал...</p>
                </div>
              )}

      {analysisResult && (
          <div className="results-container">
              <h3>Результаты анализа:</h3>
              {/* Показываем сообщение, если анализ был загружен из БД */}
              {analysisLoadedFromDB && !isAnalyzing && (
                <p className="info-message small"><em>Результаты загружены из сохраненных данных.</em></p>
              )}
              <p><strong>Темы:</strong> {analysisResult.themes.join(', ')}</p>
              <p><strong>Стили:</strong> {analysisResult.styles.join(', ')}</p>
                  <p><strong>Лучшее время для постинга:</strong> {analysisResult.best_posting_time}</p>
                  <p><strong>Проанализировано постов:</strong> {analysisResult.analyzed_posts_count}</p>
                  
              <button 
                    onClick={generateIdeas} 
                    className="action-button generate-button"
                    disabled={isGeneratingIdeas || !analysisResult} 
                  >
                    {isGeneratingIdeas ? 'Генерация...' : 'Сгенерировать идеи'}
              </button>
          </div>
      )}

              {!analysisResult && !isAnalyzing && (
                <p>Введите имя канала для начала анализа. Например: durov</p>
      )}
    </div>
          )}

          {/* Вид идей */}
          {currentView === 'suggestions' && channelName && (
            <div className="view suggestions-view">
              <h2>Идеи контента для @{channelName}</h2>
              
              {isGeneratingIdeas && (
                <div className="loading-indicator">
                  <div className="loading-spinner"></div>
                  <p>Загрузка идей...</p>
              </div>
              )}

              {suggestedIdeas.length > 0 ? (
                <div className="ideas-list">
                  {suggestedIdeas.map((idea) => (
                    <div key={idea.id} className="idea-item">
                      <div className="idea-content">
                        <div className="idea-header">
                          <span className="idea-title">{idea.topic_idea}</span>
                          <span className="idea-style">({idea.format_style})</span>
            </div>
                        {idea.day && <div className="idea-day">День {idea.day}</div>}
                                </div>
                            <button 
                        className="action-button small"
                        onClick={() => handleDetailIdea(idea)}
                      >
                        Детализировать
                            </button>
                        </div>
                  ))}
                    </div>
              ) : !isGeneratingIdeas ? (
                <p>
                  {analysisResult 
                    ? 'Нажмите "Сгенерировать идеи" на вкладке Анализ, чтобы создать новые идеи для контента.' 
                    : loadingAnalysis 
                        ? 'Загрузка сохраненного анализа...' 
                        : 'Сначала выполните анализ канала на вкладке "Анализ" или выберите канал с сохраненным анализом.'
                  }
                </p>
              ) : null}
        <button 
                    onClick={generateIdeas} 
                    className="action-button generate-button"
                    disabled={isGeneratingIdeas || !analysisResult} 
                    style={{marginTop: '20px'}} // Добавим отступ
                  >
                    {isGeneratingIdeas ? 'Генерация...' : 'Сгенерировать новые идеи'}
        </button>
             </div>
              )}
            {/* Сообщение, если канал не выбран для идей */} 
            {currentView === 'suggestions' && !channelName && (
                <p>Пожалуйста, выберите канал для просмотра или генерации идей.</p>
            )}

          {/* Календарь и Посты показываем всегда, но данные фильтруются по channelName/selectedChannels */} 
          {currentView === 'calendar' && (
            <div className="view calendar-view">
              <h2>Календарь публикаций</h2>
              
              {/* Фильтр по каналам (оставляем) */}
              <div className="channels-filter">
                <h3>Фильтр по каналам:</h3>
                
                {/* Компактная кнопка добавления/удаления канала в фильтр */}
                <div className="channels-actions">
                <button 
                    className="action-button"
                    onClick={() => {
                      // Добавить текущий канал в фильтр, если его еще нет
                      if (channelName && !selectedChannels.includes(channelName)) {
                        const updatedSelected = [...selectedChannels, channelName];
                        setSelectedChannels(updatedSelected);
                        // --- ИЗМЕНЕНИЕ: Сохраняем selectedChannels с user-specific ключом ---
                        const key = getUserSpecificKey('selectedChannels', userId);
                        if (key) {
                          localStorage.setItem(key, JSON.stringify(updatedSelected));
                        }
                        // --- КОНЕЦ ИЗМЕНЕНИЯ ---
                      }
                    }}
                  >
                    + Добавить текущий канал
                </button>
                  
                  <button
                    className="action-button"
                    onClick={filterPostsByChannels}
                  >
                    Применить фильтр
                </button>
          </div>
                
                {/* Отображение выбранных каналов */}
                <div className="selected-channels">
                  {selectedChannels.map((channel) => (
                    <div key={channel} className="selected-channel">
                      <span className="channel-name">@{channel}</span>
                      <button 
                        className="remove-channel"
                        onClick={() => {
                          const updatedSelected = selectedChannels.filter(c => c !== channel);
                          setSelectedChannels(updatedSelected);
                          // --- ИЗМЕНЕНИЕ: Сохраняем selectedChannels с user-specific ключом ---
                          const key = getUserSpecificKey('selectedChannels', userId);
                          if (key) {
                             localStorage.setItem(key, JSON.stringify(updatedSelected));
                          }
                          // --- КОНЕЦ ИЗМЕНЕНИЯ ---
                        }}
                      >
                        ✕
                      </button>
      </div>
                  ))}
      </div>
              </div>
              
              {/* Календарь - ВОССТАНОВЛЕННЫЙ КОД */}
              <div className="calendar-container">
                {/* Заголовок с названием месяца и навигацией */}
                <div className="calendar-header">
                  <button 
                    className="nav-button"
                    onClick={goToPrevMonth} // Используем восстановленную функцию
                  >
                    &lt;
                  </button>
                  
                  <h3>{currentMonth.toLocaleString('default', { month: 'long', year: 'numeric' })}</h3>
                  
                  <button 
                    className="nav-button"
                    onClick={goToNextMonth} // Используем восстановленную функцию
                  >
                    &gt;
                  </button>
                </div>
                
                {/* Дни недели */}
                <div className="weekdays">
                  {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day) => (
                    <div key={day} className="weekday">{day}</div>
                  ))}
                </div>
                
                {/* Дни календаря */}
                <div className="calendar-grid">
                  {calendarDays.map((day, index) => (
                    <CalendarDay 
                      key={index} 
                      day={day} 
                      onEditPost={startEditingPost}
                      onDeletePost={(postId) => {
                        if (window.confirm('Вы уверены, что хотите удалить этот пост?')) {
                          deletePost(postId);
                        }
                      }}
                    />
                  ))}
                </div>
              </div>
              {/* КОНЕЦ ВОССТАНОВЛЕННОГО КОДА */}
            </div>
          )}
          {/* --- КОНЕЦ ИЗМЕНЕНИЯ --- */}
          
          {/* --- НАЧАЛО: НОВЫЙ Вид "Посты" с таблицей --- */}
          {currentView === 'posts' && (
            <div className="view posts-view"> {/* Добавляем класс posts-view для возможных специфичных стилей */} 
              <h2>
                Список сохраненных постов 
                {selectedChannels.length > 0 
                  ? `(Каналы: ${selectedChannels.join(', ')})` 
                  : channelName 
                    ? `(Канал: @${channelName})` 
                    : '(Все каналы)'}
              </h2>
              
              {/* Фильтр по каналам (копируем из календаря) */}
              <div className="channels-filter">
                 <h3>Фильтр по каналам:</h3>
                  <div className="channels-actions">
                     <button 
                        className="action-button"
                        onClick={() => {
                           if (channelName && !selectedChannels.includes(channelName)) {
                              const updatedSelected = [...selectedChannels, channelName];
                              setSelectedChannels(updatedSelected);
                              // --- ИЗМЕНЕНИЕ: Сохраняем selectedChannels с user-specific ключом ---
                              const key = getUserSpecificKey('selectedChannels', userId);
                              if (key) {
                                localStorage.setItem(key, JSON.stringify(updatedSelected));
                              }
                              // --- КОНЕЦ ИЗМЕНЕНИЯ ---
                           }
                        }}
                     >
                        + Добавить текущий канал
              </button>
                     <button
                        className="action-button"
                        onClick={filterPostsByChannels}
                     >
                        Применить фильтр
                     </button>
                  </div>
                  <div className="selected-channels">
                     {selectedChannels.map((channel) => (
                        <div key={channel} className="selected-channel">
                           <span className="channel-name">@{channel}</span>
                           <button 
                              className="remove-channel"
                              onClick={() => {
                                 const updatedSelected = selectedChannels.filter(c => c !== channel);
                                 setSelectedChannels(updatedSelected);
                                 // --- ИЗМЕНЕНИЕ: Сохраняем selectedChannels с user-specific ключом ---
                                 const key = getUserSpecificKey('selectedChannels', userId);
                                 if (key) {
                                    localStorage.setItem(key, JSON.stringify(updatedSelected));
                                 }
                                 // --- КОНЕЦ ИЗМЕНЕНИЯ ---
                              }}
                           >
                              ✕
                           </button>
                        </div>
                     ))}
                  </div>
              </div>
              
              {/* Таблица постов (перемещенный код) */}
              <div className="posts-table-container">
                 {loadingSavedPosts ? (
                     <Loading message="Загрузка постов..." />
                 ) : savedPosts.length > 0 ? (
                    <table className="posts-table">
                      <thead>
                        <tr>
                          <th>Дата</th>
                          <th>Канал</th>
                          <th>Тема/Идея</th>
                          <th>Действия</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...savedPosts]
                          .sort((a, b) => new Date(b.target_date).getTime() - new Date(a.target_date).getTime()) 
                          .map((post) => (
                            <tr key={post.id}>
                              <td>{new Date(post.target_date).toLocaleDateString()}</td>
                              <td>{post.channel_name || 'N/A'}</td>
                              <td>{post.topic_idea}</td>
                              <td>
                                <button 
                                  className="action-button edit-button small"
                                  onClick={() => startEditingPost(post)}
                                  title="Редактировать"
                                >
                                  <span>📝</span>
                                </button>
                                <button 
                                  className="action-button delete-button small"
                                  onClick={() => {
                                    if (window.confirm('Вы уверены, что хотите удалить этот пост?')) {
                                      deletePost(post.id);
                                    }
                                  }}
                                  title="Удалить"
                                >
                                  <span>🗑️</span>
                                </button>
                              </td>
                            </tr>
                        ))}
                      </tbody>
                    </table>
                 ) : (
                    <p>Нет сохраненных постов для выбранных каналов.</p>
                 )}
              </div>
            </div>
           )}
          {/* --- КОНЕЦ НОВОГО ВИДА "Посты" --- */}

          {/* Вид редактирования/детализации поста */}
          {(currentView === 'edit' || currentView === 'details') && (
            <div className="view edit-view">
              <h2>{currentPostId ? 'Редактирование поста' : 'Создание нового поста'}</h2>

              {/* Индикатор загрузки деталей */}
              {isGeneratingPostDetails && (
                 <div className="loading-indicator small">
                    <div className="loading-spinner small"></div>
                    <p>Генерация деталей поста...</p>
                </div>
              )}

              {/* --- Основные поля поста --- */}
              <div className="post-fields">
                <div className="form-group">
                  <label htmlFor="channelName">Канал:</label>
                  <input 
                    type="text" 
                    id="channelName"
                    value={channelName || ''}
                    onChange={(e) => setChannelName(e.target.value)} 
                    disabled 
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="postDate">Дата публикации:</label>
                  <input 
                    type="date" 
                    id="postDate"
                    value={currentPostDate}
                    onChange={(e) => setCurrentPostDate(e.target.value)} 
                    disabled={isSavingPost}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="postTopic">Тема/Идея:</label>
                  <input 
                    type="text" 
                    id="postTopic"
                    value={currentPostTopic}
                    onChange={(e) => setCurrentPostTopic(e.target.value)}
                    disabled
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="postFormat">Формат/Стиль:</label>
                  <input 
                    type="text" 
                    id="postFormat"
                    value={currentPostFormat}
                    onChange={(e) => setCurrentPostFormat(e.target.value)}
                    disabled
                  />
                </div>
              </div>
              
              {/* --- Редактор текста поста --- */}
              <div className="form-group post-text-editor">
                <label htmlFor="postText">Текст поста:</label>
                  <textarea 
                  id="postText"
                  value={currentPostText}
                  onChange={(e) => setCurrentPostText(e.target.value)}
                  rows={10}
                  placeholder="Введите или сгенерируйте текст поста..."
                  disabled={isSavingPost || isGeneratingPostDetails}
                  />
                </div>
                
              {/* --- НАЧАЛО: Секция управления изображениями --- */}
              <div className="image-management-section">
                  
                  {/* --- Предложенные изображения (если есть) --- */}
                  {suggestedImages.length > 0 && (
                      <div className="suggested-images-section">
                          <h3>Предложенные изображения:</h3>
                          <div style={{ 
                              display: 'flex', 
                              flexWrap: 'wrap', 
                              gap: '10px',
                              marginBottom: '20px' 
                          }}>
                              {suggestedImages.map((image, index) => {
                                  // Проверяем, выбрано ли это изображение
                                  const isSelected = selectedImage && selectedImage.url === image.url;
                                  
                                  return (
                                      <div 
                                          key={image.id || `suggested-${index}`} 
                                          onClick={() => handleImageSelection(image)}
                                          style={{ 
                                              cursor: 'pointer', 
                                              position: 'relative', 
                                              width: '150px',
                                              height: '150px',
                                              border: isSelected ? '3px solid #2196f3' : '2px solid #e0e0e0',
                                              borderRadius: '5px',
                                              overflow: 'hidden',
                                              transition: 'all 0.2s ease',
                                              boxShadow: isSelected ? '0 0 10px rgba(33, 150, 243, 0.5)' : 'none'
                                          }}
                                      >
                                      <img 
                                          src={image.preview_url || image.url} 
                                          alt={image.alt || 'Suggested image'} 
                                          style={{ 
                                              width: '100%', 
                                              height: '100%', 
                                              objectFit: 'cover' 
                                          }}
                                          onError={(e) => {
                                              const target = e.target as HTMLImageElement;
                                              target.src = 'https://via.placeholder.com/150?text=Ошибка'; 
                                              console.error('Image load error:', image.preview_url || image.url);
                                          }}
                                      />
                                      {isSelected && (
                                          <div style={{ 
                                              position: 'absolute', 
                                              top: '5px', 
                                              right: '5px', 
                                              backgroundColor: '#2196f3', 
                                              color: 'white', 
                                              borderRadius: '50%', 
                                              width: '24px',
                                              height: '24px',
                                              display: 'flex',
                                              alignItems: 'center',
                                              justifyContent: 'center',
                                              fontWeight: 'bold',
                                              zIndex: 10
                                          }}>✓</div> 
                                      )}
                                      </div>
                                  );
                              })}
                          </div>
                      </div>
                  )}
                  
                  {/* --- Блок для своего изображения: Загрузчик и Превью --- */}
                  <div className="custom-image-section">
                      <h4>Свое изображение:</h4>
                      {/* Показываем загрузчик */} 
                      <ImageUploader onImageUploaded={handleCustomImageUpload} userId={userId} />
                  </div>

                  {/* --- Блок предпросмотра выбранного изображения --- */}
                  {selectedImage && (
                      <div style={{
                        marginTop: '20px',
                        padding: '15px',
                        border: '1px solid #2196f3',
                        borderRadius: '8px',
                        backgroundColor: '#f5f5f5'
                      }}>
                          <h4 style={{
                            color: '#2196f3',
                            marginTop: 0,
                            display: 'flex',
                            alignItems: 'center'
                          }}>
                            <span style={{ marginRight: '8px' }}>✅</span>
                            Выбранное изображение:
                          </h4>
                          <div style={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: '15px',
                            flexWrap: 'wrap'
                          }}>
                              <div style={{
                                maxWidth: '300px',
                                flex: '1'
                              }}>
                                  <img 
                                      src={selectedImage.preview_url || selectedImage.url} 
                                      alt={selectedImage.alt || 'Выбранное изображение'} 
                                      style={{
                                        width: '100%',
                                        maxHeight: '250px',
                                        objectFit: 'contain',
                                        borderRadius: '5px',
                                        boxShadow: '0 2px 10px rgba(0,0,0,0.1)'
                                      }}
                                  />
                              </div>
                              <div style={{ flex: '1', minWidth: '200px' }}>
                                  {selectedImage.author && (
                                      <p style={{
                                        margin: '0 0 8px 0',
                                        fontSize: '14px'
                                      }}>
                                          <strong>Автор:</strong> {selectedImage.author}
                                      </p>
                                  )}
                                  <p className="selected-confirmation">
                                      Это изображение будет сохранено с постом
                                  </p>
                                  <button 
                                      onClick={() => setSelectedImage(null)}
                                      className="remove-image-btn"
                                  >
                                      🗑️ Отменить выбор
                                  </button>
                              </div>
                          </div>
                      </div>
                  )}
                </div>
              </div>
              {/* --- КОНЕЦ: Секция управления изображениями --- */} {/* <-- ИСПРАВЛЕНО: Убран лишний символ */} 
                
              {/* Кнопки действий */}
              <div className="form-actions">
                  <button 
                    onClick={handleSaveOrUpdatePost} 
                    className="action-button save-button"
                    disabled={isSavingPost || isGeneratingPostDetails || !currentPostText}
                  >
                    {isSavingPost ? 'Сохранение...' : (currentPostId ? 'Обновить пост' : 'Сохранить пост')}
                  </button>
                 {/* Добавляем кнопку Отмена */}
                  <button 
                    onClick={() => {
                        setCurrentView('calendar'); // Возвращаемся в календарь
                        // Сбрасываем состояние редактирования
                        setCurrentPostId(null);
                        setCurrentPostDate(new Date().toISOString().split('T')[0]);
                        setCurrentPostTopic('');
                        setCurrentPostFormat('');
                        setCurrentPostText('');
                        setSelectedImage(null);
                        setSuggestedImages([]);
                    }}
                    className="action-button cancel-button"
                    disabled={isSavingPost}
                  >
                    Отмена
                  </button>
                </div>

            </div>
          )}
        </div>
      </main>

      <footer className="app-footer">
        <p>© 2024 Smart Content Assistant</p>
      </footer>
    </div>
  );
}

export default App;
