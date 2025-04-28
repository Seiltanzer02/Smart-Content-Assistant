import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './App.css';
import { TelegramAuth } from './components/TelegramAuth';
import SubscriptionManager from './components/SubscriptionManager';
import { v4 as uuidv4 } from 'uuid';
import { Toaster, toast } from 'react-hot-toast';
import { ClipLoader } from 'react-spinners';
import WebApp from '@twa-dev/sdk';

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

// Добавляем к типам статуса подписки
interface SubscriptionStatus {
  has_subscription: boolean;
  free_analysis_count: number;
  free_post_details_count: number;
  subscription_expires_at: string | null;
  days_left: number;
}

// Компонент загрузки изображений
// --- ИЗМЕНЕНО: Добавляем userId в пропсы --- 
// --- ИСПРАВЛЕНО: Синтаксис типа пропсов --- 
const ImageUploader = ({ onImageUploaded, userId }: { onImageUploaded: (imageUrl: string) => void, userId: string | null }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    
    const file = files[0];
    // Проверка размера (менее 5 МБ)
    if (file.size > 5 * 1024 * 1024) {
      setUploadError("Размер файла должен быть не более 5 МБ");
      return;
    }
    
    // Проверка типа (только изображения)
    if (!file.type.startsWith('image/')) {
      setUploadError("Разрешены только изображения");
      return;
    }
    
    // Загружаем файл на сервер
    setUploading(true);
    setUploadError(null);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await axios.post(`${API_BASE_URL}/upload-image`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          // --- ДОБАВЛЕНО: Передача userId --- 
          'x-telegram-user-id': userId
        }
      });
      
      if (response.data && response.data.url) {
        onImageUploaded(response.data.url);
      } else {
        setUploadError("Ошибка при загрузке. Попробуйте еще раз.");
      }
    } catch (error: any) {
      console.error("Ошибка загрузки изображения:", error);
      setUploadError(error.response?.data?.detail || "Ошибка при загрузке");
    } finally {
      setUploading(false);
    }
  };
  
  return (
    <div className="image-uploader">
      <label className="upload-button-label">
        <input 
          type="file" 
          accept="image/*" 
          onChange={handleFileChange} 
          disabled={uploading}
          style={{ display: 'none' }}
        />
        <span className="action-button">
          {uploading ? "Загрузка..." : "Загрузить изображение"}
        </span>
      </label>
      {uploadError && <p className="error-message">{uploadError}</p>}
    </div>
  );
};

// Компонент для отображения галереи изображений поста
const PostImageGallery = ({ 
  postId, 
  onImageSelect 
}: { 
  postId: string; 
  onImageSelect?: (imageUrl: string) => void 
}) => {
  const [images, setImages] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  
  // Функция для загрузки изображений
  const loadImages = useCallback(async () => {
    if (!postId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      // Запрашиваем изображения для поста
      const response = await axios.get(`${API_BASE_URL}/posts/${postId}/images`);
      
      if (response.data && response.data.images) {
        setImages(response.data.images);
      }
    } catch (err: any) {
      console.error('Ошибка при загрузке изображений поста:', err);
      setError('Не удалось загрузить изображения');
      } finally {
        setLoading(false);
      }
  }, [postId]);
  
  // Загружаем изображения при монтировании
  useEffect(() => {
    loadImages();
  }, [loadImages]);
  
  // Функция для выбора изображения
  const handleSelect = (image: any) => {
    if (onImageSelect) {
      onImageSelect(image.url);
    }
  };
  
  // Отображаем загрузку
  if (loading) {
    return (
      <div className="post-image-gallery loading">
        <div className="loading-spinner small"></div>
        <p>Загрузка изображений...</p>
      </div>
    );
  }

  // Отображаем ошибку
  if (error) {
    return (
      <div className="post-image-gallery error">
        <p>{error}</p>
      </div>
    );
  }
  
  // Отображаем пустое состояние
  if (!images || images.length === 0) {
    return (
      <div className="post-image-gallery empty">
        <p>Нет изображений</p>
      </div>
    );
  }
  
  // Отображаем галерею
  return (
    <div className="post-image-gallery">
      <div className="image-grid">
        {images.map((image, index) => (
          <div 
            key={image.id || index} 
            className="image-item"
            onClick={() => handleSelect(image)}
          >
            <img 
              src={image.preview_url || image.url} 
              alt={image.alt || "Изображение поста"} 
              className="thumbnail"
              onError={(e) => {
                // Обработка ошибки загрузки изображения
                const target = e.target as HTMLImageElement;
                target.onerror = null;
                target.src = 'https://via.placeholder.com/100?text=Ошибка';
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

// Компонент для отображения дня календаря
const CalendarDay = ({ 
  day, 
  onEditPost, 
  onDeletePost 
}: { 
  day: CalendarDay; 
  onEditPost: (post: SavedPost) => void;
  onDeletePost: (postId: string) => void;
}) => {
  const { date, posts, isCurrentMonth, isToday } = day;
  const dayNumber = date.getDate();
  
  // Класс для ячейки календаря
  const cellClass = `calendar-day ${isCurrentMonth ? '' : 'other-month'} ${isToday ? 'today' : ''}`;
  
  return (
    <div className={cellClass}>
      <div className="day-number">{dayNumber}</div>
      {posts.length > 0 && (
        <div className="day-posts">
          {posts.map((post) => (
            <div key={post.id} className="post-item">
              <div className="post-title" title={post.topic_idea}>
                {post.topic_idea.length > 25 
                  ? post.topic_idea.substring(0, 22) + '...' 
                  : post.topic_idea
                }
              </div>
              <div className="post-actions">
                <button 
                  className="action-button edit-button" 
                  onClick={() => onEditPost(post)}
                  title="Редактировать"
                >
                  <span>📝</span>
                </button>
                <button 
                  className="action-button delete-button" 
                  onClick={() => onDeletePost(post.id)}
                  title="Удалить"
                >
                  <span>🗑️</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

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

  // --- ВОССТАНОВЛЕНО: Состояние для текущего месяца календаря --- 
  const [currentMonth, setCurrentMonth] = useState<Date>(new Date());
  // --- КОНЕЦ ВОССТАНОВЛЕНИЯ ---

  // Добавляем новые состояния для подписки
  const [subscriptionStatus, setSubscriptionStatus] = useState<SubscriptionStatus>({
    has_subscription: false,
    free_analysis_count: 0,
    free_post_details_count: 0,
    subscription_expires_at: null,
    days_left: 0
  });
  const [showSubscriptionModal, setShowSubscriptionModal] = useState<boolean>(false);

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

    // Проверяем возможность анализа с учетом подписки
    try {
      const canAnalyzeResponse = await axios.get(`/subscription/can-analyze?user_id=${userId}`);
      
      if (!canAnalyzeResponse.data.can_analyze) {
        setError("Для анализа канала необходима подписка или бесплатные попытки");
        setShowSubscriptionModal(true);
      return;
    }

    setIsAnalyzing(true);
    // Сбрасываем флаг загрузки из БД перед новым анализом
    setAnalysisLoadedFromDB(false);
    setError(null);
    setSuccess(null);
    setAnalysisResult(null);

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
      
      // Обновляем статус подписки после использования
      updateSubscriptionStatus();
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

  // Функция для получения подробностей идеи с проверкой подписки
  const handleDetailIdea = (idea: SuggestedIdea) => {
    // Сначала проверяем возможность получения деталей с учетом подписки
    axios.get(`/subscription/can-get-post-details?user_id=${userId}`)
      .then(response => {
        if (!response.data.can_get_details) {
          setError("Для получения деталей поста необходима подписка или бесплатные попытки");
          setShowSubscriptionModal(true);
          return;
        }
        
        // Если доступ разрешен, продолжаем получение деталей
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
      })
      .catch(err => {
        console.error('Ошибка при проверке доступа к деталям поста:', err);
        setError('Не удалось проверить возможность получения деталей поста');
      });
  };

  // Function to handle selecting/deselecting a suggested image
  const handleImageSelection = (image: PostImage | undefined) => {
    if (image) {
      // Если кликнутое изображение уже выбрано (сравниваем по ID или URL), снимаем выбор
      // Иначе, выбираем кликнутое изображение
      setSelectedImage(prevSelected => (prevSelected?.id === image.id || prevSelected?.url === image.url) ? null : image);
    } else {
      console.error("Attempted to select an image with undefined data.");
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

  // Функция для обновления статуса подписки
  const updateSubscriptionStatus = () => {
    if (!userId) return;
    
    axios.get(`/subscription/status?user_id=${userId}`)
      .then(response => {
        if (response.data.success && response.data.status) {
          setSubscriptionStatus(response.data.status);
        }
      })
      .catch(err => {
        console.error('Ошибка при получении статуса подписки:', err);
      });
  };

  // Обновляем useEffect для получения статуса подписки при авторизации
  useEffect(() => {
    if (userId) {
      updateSubscriptionStatus();
    }
  }, [userId]);

  // Добавляем обработчик изменения статуса подписки
  const handleSubscriptionStatusChange = (status: SubscriptionStatus) => {
    setSubscriptionStatus(status);
    setShowSubscriptionModal(false); // Закрываем модальное окно после обновления
  };

  // Модальное окно подписки
  const SubscriptionModal = () => (
    <div className="modal-overlay" onClick={() => setShowSubscriptionModal(false)}>
      <div className="modal-content subscription-modal" onClick={e => e.stopPropagation()}>
        <button className="close-button" onClick={() => setShowSubscriptionModal(false)}>×</button>
        <h2>Подписка</h2>
        {userId && <SubscriptionManager userId={userId} onStatusChange={handleSubscriptionStatusChange} />}
      </div>
    </div>
  );

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
    <SimpleErrorBoundary>
    <div className="app-container">
        {/* Telegram Auth component */}
        <div className="auth-container">
          {!userId ? (
            <TelegramAuth onAuthSuccess={handleAuthSuccess} />
          ) : (
            <div className="user-info">
              <span>ID: {userId}</span>
                                 <button 
                className="subscription-button" 
                onClick={() => setShowSubscriptionModal(true)}
              >
                {subscriptionStatus.has_subscription ? 'Подписка активна' : 'Подписка'}
                {(!subscriptionStatus.has_subscription && 
                 (subscriptionStatus.free_analysis_count > 0 || 
                  subscriptionStatus.free_post_details_count > 0)) && 
                  ` (${subscriptionStatus.free_analysis_count}/${subscriptionStatus.free_post_details_count})`}
                                  </button>
                  </div>
                      )}
                </div>

        {/* Остальной код интерфейса */}
        {/* ... existing JSX ... */}

        {/* Модальное окно подписки */}
        {showSubscriptionModal && <SubscriptionModal />}
        
        <Toaster position="bottom-center" />
    </div>
    </SimpleErrorBoundary>
  );
}

export default App;
