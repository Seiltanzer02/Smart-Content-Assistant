import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './App.css';
import { TelegramAuth } from './components/TelegramAuth';
import { v4 as uuidv4 } from 'uuid';
import { Toaster, toast } from 'react-hot-toast';
import { ClipLoader } from 'react-spinners';
import SubscriptionWidget from './components/SubscriptionWidget';

// Определяем базовый URL API
const API_BASE_URL = '';

// Вспомогательная функция для ключей localStorage
const getUserSpecificKey = (baseKey: string, userId: string | null): string | null => {
  if (!userId) return null;
  return `${userId}_${baseKey}`;
};

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

// Компонент загрузки изображений
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

// --- ДОБАВЛЕНО: компонент SuccessMessage ---
const SuccessMessage = ({ message, onClose }: { message: string | null, onClose: () => void }) => (
  <div className="success-message">
    <p>{message}</p>
    <button className="action-button small" onClick={onClose}>Закрыть</button>
  </div>
);
// --- КОНЕЦ ДОБАВЛЕНИЯ ---

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userId, setUserId] = useState<string | null>(null); 
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [channelName, setChannelName] = useState('');
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [suggestedIdeas, setSuggestedIdeas] = useState<SuggestedIdea[]>([]);
  const [isGeneratingIdeas, setIsGeneratingIdeas] = useState(false);
  const [currentView, setCurrentView] = useState<ViewType>('analyze');
  const [detailedPost, setDetailedPost] = useState<DetailedPost | null>(null);
  const [selectedIdea, setSelectedIdea] = useState<SuggestedIdea | null>(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [savedPosts, setSavedPosts] = useState<SavedPost[]>([]);
  const [isSavingPost, setIsSavingPost] = useState(false);
  const [selectedImage, setSelectedImage] = useState<PostImage | null>(null);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [currentPostId, setCurrentPostId] = useState<string | null>(null);
  const [currentPostDate, setCurrentPostDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [currentPostTopic, setCurrentPostTopic] = useState('');
  const [currentPostFormat, setCurrentPostFormat] = useState('');
  const [currentPostText, setCurrentPostText] = useState('');
  const [showSubscription, setShowSubscription] = useState<boolean>(false);
  const [currentMonth, setCurrentMonth] = useState<Date>(new Date());
  const [calendarDays, setCalendarDays] = useState<CalendarDay[]>([]); // State for calendar days
  const [loadingSavedPosts, setLoadingSavedPosts] = useState(false); // State for loading saved posts
  const [activeChannels, setActiveChannels] = useState<string[]>([]); // Use activeChannels instead of allChannels
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  // --- ДОБАВЛЕНО: недостающие состояния ---
  const [suggestedImages, setSuggestedImages] = useState<PostImage[]>([]);
  const [isGeneratingPostDetails, setIsGeneratingPostDetails] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisLoadedFromDB, setAnalysisLoadedFromDB] = useState(false);
  // --- КОНЕЦ ДОБАВЛЕНИЯ ---
  let savedChannel: string | null = null; // <-- перемещено в начало App

  // --- ИЗМЕНЕНИЕ: Загрузка состояния ИЗ localStorage ПОСЛЕ аутентификации ---
  useEffect(() => {
    if (isAuthenticated && userId) {
      const savedChannelKey = getUserSpecificKey('channelName', userId);
      if (savedChannelKey) { 
          savedChannel = localStorage.getItem(savedChannelKey);
      }
      if (savedChannel) setChannelName(savedChannel);

      const savedViewKey = getUserSpecificKey('currentView', userId);
      const savedView = savedViewKey ? localStorage.getItem(savedViewKey) as ViewType : null;
      if (savedView) setCurrentView(savedView);
      
      const activeChannelsKey = getUserSpecificKey('activeChannels', userId);
      if (activeChannelsKey) {
        const storedChannels = localStorage.getItem(activeChannelsKey);
        if (storedChannels) {
          try { setActiveChannels(JSON.parse(storedChannels)); } 
          catch (e) { console.error('Ошибка при восстановлении активных каналов:', e); }
        }
      } else {
        // Maybe fetch active channels from posts if not in local storage
      }
      
      const selectedChannelsKey = getUserSpecificKey('selectedChannels', userId);
      if (selectedChannelsKey) {
        const storedSelectedChannels = localStorage.getItem(selectedChannelsKey);
        if (storedSelectedChannels) {
          try { setSelectedChannels(JSON.parse(storedSelectedChannels)); } 
          catch (e) { console.error('Ошибка при восстановлении выбранных каналов:', e); }
        } else {
           // Initialize selected channels if not in storage? Maybe from active channels?
           // setSelectedChannels(activeChannels); // Example
        }
      } else {
          // Initialize selected channels if key missing?
          // setSelectedChannels(activeChannels); // Example
      }

      // Исправлено: вызываем функции только если savedChannel не null
      if (savedChannel) { 
          fetchSavedAnalysis(savedChannel);
          fetchSavedIdeas(); 
          fetchSavedPosts(savedChannel as string); 
      } else {
          fetchSavedPosts();
      }
    }
  }, [isAuthenticated, userId, activeChannels, setActiveChannels, setSelectedChannels]); // Added dependencies

  // --- ИЗМЕНЕНИЕ: Сохранение состояния В localStorage ПРИ ИЗМЕНЕНИИ и наличии userId ---
  useEffect(() => {
    if (userId) {
      const channelKey = getUserSpecificKey('channelName', userId);
      if (channelKey) localStorage.setItem(channelKey, channelName);
    }
  }, [channelName, userId]);

  useEffect(() => {
    if (userId) {
      const viewKey = getUserSpecificKey('currentView', userId);
      if (viewKey) localStorage.setItem(viewKey, currentView);
    }
  }, [currentView, userId]);
  
  // --- КОНЕЦ ИЗМЕНЕНИЙ localStorage ---

  useEffect(() => {
      if (userId) {
          const activeChannelsKey = getUserSpecificKey('activeChannels', userId);
          if (activeChannelsKey) localStorage.setItem(activeChannelsKey, JSON.stringify(activeChannels));
      }
  }, [activeChannels, userId]);

  useEffect(() => {
      if (userId) {
          const selectedChannelsKey = getUserSpecificKey('selectedChannels', userId);
          if (selectedChannelsKey) localStorage.setItem(selectedChannelsKey, JSON.stringify(selectedChannels));
      }
  }, [selectedChannels, userId]);
  // --- КОНЕЦ useEffects для сохранения --- 

  const editorRef = useRef<any>(null); // Ref для доступа к Editor

  // --- ИЗМЕНЕНИЕ: Инициализация Telegram WebApp и получение данных ---
  useEffect(() => {
    const initApp = async () => {
      try {
        console.log("App.tsx: Инициализация Telegram WebApp...");
        const TWA = window.Telegram?.WebApp;
        if (TWA) {
          TWA.ready();
          TWA.expand();
          TWA.setHeaderColor('#1a1a1a'); // Темный цвет хедера
          TWA.setBackgroundColor('#1a1a1a'); // Темный фон

          console.log("App.tsx: Telegram WebApp инициализирован.");

          // Попытка получить userId через TelegramAuth компонент
          // `handleAuthSuccess` будет вызван TelegramAuth компонентом
          setLoading(false); // Убираем главный лоадер после инициализации TWA
                                // Теперь ждем аутентификации через TelegramAuth
                                
        } else {
          console.error("App.tsx: Telegram WebApp не найден.");
          setError("Не удалось инициализировать приложение Telegram. Пожалуйста, убедитесь, что вы запускаете его внутри Telegram.");
          setLoading(false);
        }
      } catch (e) {
        console.error('App.tsx: Ошибка при инициализации Telegram WebApp:', e);
        setError("Произошла ошибка при запуске приложения.");
        setLoading(false);
      }
    };
    initApp();
  }, []);

  // Обновляем заголовки axios при изменении userId
  useEffect(() => {
    axios.defaults.headers.common['x-telegram-user-id'] = userId || '';
    console.log(`App.tsx: Установлен заголовок x-telegram-user-id: ${userId}`);
  }, [userId]);

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
      fetchSavedPosts(savedChannel as string); 
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
  
  // --- Re-add useEffect for calendar --- 
  useEffect(() => {
    if (currentMonth && currentView === 'calendar') { 
      generateCalendarDays();
    }
  }, [currentMonth, savedPosts, currentView]);
  
  // --- Re-add calendar functions --- 
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

  const goToPrevMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
  };
  
  const goToNextMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
  };
  // --- End re-added calendar functions --- 

  // --- Function to fetch saved posts (add loading state) --- 
  const fetchSavedPosts = async (channel?: string) => {
    if (!userId) return; 
    setLoadingSavedPosts(true); // Use the re-added state
    setError(null);
    try {
      const params = channel ? { channel_name: channel } : {};
      // Use selectedChannels if available and no specific channel is passed
      if (!channel && selectedChannels.length > 0) {
         // Fetch posts for multiple selected channels - requires backend support or multiple requests
         // For now, let's just fetch all user posts if multiple channels selected
         console.log("Fetching posts for selected channels: ", selectedChannels);
         // Fetching all user posts for now if multiple selected
         delete params.channel_name; 
      } 
      const response = await axios.get(`${API_BASE_URL}/posts`, { params });
      const posts: SavedPost[] = response.data || [];
      setSavedPosts(posts);
      updateChannelsFromPosts(posts); // Keep updating active channels
    } catch (err) {
      console.error("Ошибка при загрузке сохраненных постов:", err);
      setError("Не удалось загрузить сохраненные посты.");
    } finally {
       setLoadingSavedPosts(false); // Use the re-added state
    }
  };
  
  // Вспомогательная функция для обновления списка каналов из постов
  const updateChannelsFromPosts = (posts: SavedPost[]) => {
    const uniqueChannels = Array.from(new Set(posts.map(p => p.channel_name).filter(Boolean))) as string[];
    setActiveChannels(uniqueChannels);
    const allChannelsKey = getUserSpecificKey('allChannels', userId);
    if (allChannelsKey) {
        localStorage.setItem(allChannelsKey, JSON.stringify(uniqueChannels));
    }
    if (selectedChannels.length === 0 || !uniqueChannels.some(ch => selectedChannels.includes(ch))) {
        setSelectedChannels(uniqueChannels);
        const selectedChannelsKey = getUserSpecificKey('selectedChannels', userId);
        if (selectedChannelsKey) {
            localStorage.setItem(selectedChannelsKey, JSON.stringify(uniqueChannels));
        }
    }
  };
  
  // Добавляем функцию для регенерации только изображений
  const regeneratePostDetails = async () => {
    if (!selectedIdea || !userId) return;
    setIsLoadingDetails(true);
    setError(null);
    try {
        const response = await axios.post(
            `${API_BASE_URL}/generate-detailed-post/${selectedIdea.id}`,
            {},
            { headers: { 'x-telegram-user-id': userId } } 
        );
        if (response.data && response.data.post_text) {
            setDetailedPost(response.data);
            toast.success("Детали поста успешно обновлены.");
        } else {
            throw new Error(response.data.error || "Не удалось получить детали поста.");
        }
    } catch (err: any) {
        console.error("Ошибка при повторной генерации деталей поста:", err);
        setError(err.message || "Произошла ошибка при обновлении деталей поста.");
        toast.error(err.message || "Произошла ошибка при обновлении деталей поста.");
    } finally {
        setIsLoadingDetails(false);
    }
  };

  // Функция сохранения поста
  const handleSaveOrUpdatePost = async () => {
      if (!currentPostTopic || !currentPostText || !userId) {
          setError("Необходимо указать тему и текст поста.");
          return;
      }
      setIsSavingPost(true);
      setError(null);
      // setSuccess(null); // Удалено
      const TWA = window.Telegram?.WebApp;

      const postData: Partial<SavedPost> & { images_ids?: string[] } = {
          user_id: userId,
          target_date: currentPostDate,
          topic_idea: currentPostTopic,
          format_style: currentPostFormat,
          final_text: currentPostText,
          channel_name: channelName, // Используем текущий канал из состояния App
          // Передаем ID выбранного изображения, если оно есть и имеет id
          images_ids: selectedImage && selectedImage.id ? [selectedImage.id] : [],
      };

      try {
          let response;
          if (isEditing && currentPostId) {
              // Обновление существующего поста
              response = await axios.put(`${API_BASE_URL}/posts/${currentPostId}`, postData);
              toast.success("Пост успешно обновлен!");
              // setSuccess("Пост успешно обновлен!"); // Заменено
          } else {
              // Создание нового поста
              response = await axios.post(`${API_BASE_URL}/posts`, postData);
              setCurrentPostId(response.data.id); // Сохраняем ID нового поста
              setIsEditing(true); // Переключаемся в режим редактирования после первого сохранения
              toast.success("Пост успешно сохранен!");
              // setSuccess("Пост успешно сохранен!"); // Заменено
          }
          
          // Обновляем список постов после сохранения/обновления
          await fetchSavedPosts(channelName); 
          
          // Показываем сообщение в TWA, если доступно
          if (TWA?.showPopup) {
              TWA.showPopup({
                  title: "Успех",
                  message: isEditing ? "Пост успешно обновлен!" : "Пост успешно сохранен!",
                  buttons: [{ type: 'ok' }]
              });
          }
          
          // Очищаем выбор изображения после сохранения
          setSelectedImage(null);
          
          // Переключаемся на просмотр постов или календаря
          setCurrentView('posts'); 
          
      } catch (err: any) {
          console.error("Ошибка при сохранении поста:", err);
          const errorMsg = err.response?.data?.detail || err.message || "Не удалось сохранить пост.";
          setError(errorMsg);
          toast.error(errorMsg);
      } finally {
          setIsSavingPost(false);
      }
  };
  
  // Функция для удаления поста
  const deletePost = async (postId: string) => {
      if (!userId) return;
      if (!confirm("Вы уверены, что хотите удалить этот пост?")) {
          return;
      }
      try {
          await axios.delete(`${API_BASE_URL}/posts/${postId}`);
          // setSuccess("Пост успешно удален"); // Заменено
          toast.success("Пост успешно удален");
          // Обновляем список постов
          setSavedPosts(prevPosts => prevPosts.filter(post => post.id !== postId));
      } catch (err: any) {
          console.error("Ошибка при удалении поста:", err);
          setError(err.response?.data?.detail || "Не удалось удалить пост");
          toast.error(err.response?.data?.detail || "Не удалось удалить пост");
      }
  };
  
  // Функция для загрузки данных сохраненного изображения и установки его как выбранного
  const fetchAndSetSavedImage = async (imageId: string) => {
      if (!imageId || !userId) return;
      try {
          console.log(`Загрузка данных для сохраненного изображения: ${imageId}`);
          const response = await axios.get(`${API_BASE_URL}/images/${imageId}`);
          if (response.data && !response.data.error) {
              const imageData = response.data;
              const imageObject: PostImage = {
                  id: imageData.id,
                  url: imageData.url,
                  preview_url: imageData.preview_url || imageData.url,
                  alt: imageData.alt || '',
                  author: imageData.author || '',
                  author_url: imageData.author_url || '',
                  source: imageData.source || 'db'
              };
              setSelectedImage(imageObject);
              console.log(`Установлено сохраненное изображение:`, imageObject);
          } else {
              console.warn(`Не удалось загрузить данные для изображения ${imageId}. Ошибка: ${response.data.error}`);
              setSelectedImage(null);
              toast.error(`Не удалось загрузить данные для изображения ${imageId}.`);
          }
      } catch (err: any) {
          if (err.response && err.response.status === 404) {
              console.warn(`Сохраненное изображение ${imageId} не найдено (404).`);
              // toast.warn(`Сохраненное изображение ${imageId} не найдено.`);
              toast(`Сохраненное изображение ${imageId} не найдено.`); // Заменяем toast.warn на toast()
          } else {
              console.error(`Ошибка при загрузке сохраненного изображения ${imageId}:`, err);
              toast.error(`Ошибка при загрузке изображения ${imageId}.`);
          }
          setSelectedImage(null);
      }
  };

  // --- ДОБАВЛЕНО: Обработчик загрузки своего изображения --- 
  const handleCustomImageUpload = (imageUrl: string) => {
    // Сразу устанавливаем загруженное изображение как выбранное
    const newImage: PostImage = {
      id: uuidv4(), // Генерируем временный ID
      url: imageUrl,
      preview_url: imageUrl,
      alt: 'Загруженное изображение',
      author: 'Пользователь (upload)',
      source: 'upload'
    };
    setSelectedImage(newImage);
    // setSuccess("Изображение успешно загружено и выбрано!"); // Заменено
    toast.success("Изображение успешно загружено и выбрано!");
    
    // Здесь можно добавить логику для немедленного сохранения данных изображения в БД,
    // если это необходимо, или положиться на сохранение при сохранении поста.
  };
  // --- КОНЕЦ ДОБАВЛЕНИЯ ---
  
  // Функция для открытия редактирования поста
  const startEditingPost = (post: SavedPost) => {
      setCurrentPostId(post.id);
      setCurrentPostDate(post.target_date.split('T')[0]); // Форматируем дату
      setCurrentPostTopic(post.topic_idea);
      setCurrentPostFormat(post.format_style);
      setCurrentPostText(post.final_text);
      setIsEditing(true);
      // setSuggestedImages([]); // Очищаем предложенные ранее изображения
      setSelectedImage(null); // Очищаем выбранное изображение
      // Загружаем данные сохраненного изображения, если оно есть
      if (post.images_ids && post.images_ids.length > 0) {
        fetchAndSetSavedImage(post.images_ids[0]);
      }
      setCurrentView('edit');
      // Прокрутка вверх
      window.scrollTo(0, 0);
  };
  
  // Функция для сохранения идей в базу данных
  const saveIdeasToDatabase = async (ideasToSave: SuggestedIdea[]) => { 
      if (!userId) {
          console.error("Невозможно сохранить идеи: userId отсутствует.");
          toast.error("Ошибка: Не удалось определить пользователя для сохранения идей.");
          return;
      }
      try {
          console.log("Отправка идей на сохранение в БД:", ideasToSave);
          const response = await axios.post(`${API_BASE_URL}/ideas/batch`, {
              ideas: ideasToSave,
              user_id: parseInt(userId, 10), // Убедимся, что user_id это число
              channel_name: channelName 
          });
          if (response.data && response.data.success) {
              console.log("Идеи успешно сохранены в БД", response.data);
              // setSuccess("Идеи успешно сохранены!"); // Заменено
              toast.success("Идеи успешно сохранены!");
              // Обновляем список идей из ответа, чтобы получить ID
              if (response.data.saved_ideas && response.data.saved_ideas.length > 0) {
                  setSuggestedIdeas(response.data.saved_ideas);
              }
          } else {
              throw new Error(response.data?.error || 'Неизвестная ошибка при сохранении идей.');
          }
      } catch (error: any) {
          console.error('Ошибка при сохранении идей в БД:', error);
          setError(error.response?.data?.detail || error.message || 'Не удалось сохранить идеи.');
          toast.error(error.response?.data?.detail || error.message || 'Не удалось сохранить идеи.');
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
    if (!channelName || !userId) {
      setError("Пожалуйста, введите название канала");
      return;
    }
    setIsAnalyzing(true);
    setError(null);
    setAnalysisResult(null);
    // REMOVED: setAnalysisLoadedFromDB(false);
    // REMOVED: setSuccess(null);
    
    const channelKey = getUserSpecificKey('channelName', userId);
    if (channelKey) localStorage.setItem(channelKey, channelName);
    
    try {
      const response = await axios.post(`${API_BASE_URL}/analyze-channel`, 
        { channel_name: channelName },
        { headers: { 'x-telegram-user-id': userId } }
      );
      setAnalysisResult(response.data);
      setCurrentView('suggestions');
      toast.success("Анализ канала успешно завершен!");
      
      if (!activeChannels.includes(channelName)) {
         const updatedChannels = [...activeChannels, channelName];
         setActiveChannels(updatedChannels);
         // REMOVED: setAllChannels(updatedChannels);
         // Update localStorage for activeChannels here
         const activeChannelsKey = getUserSpecificKey('activeChannels', userId);
         if (activeChannelsKey) localStorage.setItem(activeChannelsKey, JSON.stringify(updatedChannels));
      }
      // REMOVED: setAnalysisLoadedFromDB(true);
          
    } catch (err: any) {
      // ... error handling ...
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
        // REMOVED: setSuccess('Идеи успешно сгенерированы'); // REMOVE
        toast.success('Идеи успешно сгенерированы'); // Replace setSuccess
        
        // Сохраняем сгенерированные идеи В ФОНЕ (не ждем завершения)
        saveIdeasToDatabase(formattedIdeas); // Передаем новые идеи в функцию сохранения
        setCurrentView('suggestions');
      }
    } catch (err: any) { 
      setError(err.response?.data?.detail || err.message || 'Ошибка при генерации идей');
      console.error('Ошибка при генерации идей:', err);
    } finally {
      setIsGeneratingIdeas(false);
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
    // REMOVED: setSuccess(null); // REMOVE
    setCurrentView('edit');
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
      // REMOVED: setIsGeneratingPostDetails(true); // REMOVE
      setError(null);
      // REMOVED: setSuccess(null); // REMOVE
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
        // REMOVED: setSuccess("Детали поста успешно сгенерированы"); // REMOVE
        toast.success("Детали поста успешно сгенерированы"); // Replace setSuccess

      } catch (err: any) {
        setError(err.response?.data?.detail || err.message || 'Ошибка при генерации деталей поста');
        console.error('Ошибка при генерации деталей поста:', err);
      } finally {
        // REMOVED: setIsGeneratingPostDetails(false); // REMOVE
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
    if (!channel || !userId) return;
    setIsAnalyzing(true);
    setAnalysisResult(null); 
    // REMOVED: setLoadingAnalysis(true);
    // REMOVED: setAnalysisLoadedFromDB(false);
    try {
      console.log(`Загрузка сохраненного анализа для канала: ${channel}`);
      const response = await axios.get(`${API_BASE_URL}/channel-analysis`, {
        params: { channel_name: channel },
        headers: { 'x-telegram-user-id': userId }
      });
      
      // Проверяем, что ответ содержит данные и не является объектом ошибки
      if (response.data && Object.keys(response.data).length > 0 && !response.data.error) {
        console.log('Сохраненный анализ найден:', response.data);
        setAnalysisResult(response.data); 
        // REMOVED: setAnalysisLoadedFromDB(true);
        toast.success(`Загружен сохраненный анализ для @${channel}`, { id: `analysis-${channel}` });
        // REMOVED: setSuccess(`Загружен сохраненный анализ для @${channel}`);
      } else {
        console.log(`Сохраненный анализ для @${channel} не найден.`);
        // Если анализ не найден (или пришла ошибка), оставляем analysisResult null
        setAnalysisResult(null); 
        // Можно очистить сообщение об успехе или установить сообщение о том, что анализ не найден
        // REMOVED: setSuccess(null);
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
      setIsAnalyzing(false);
      // REMOVED: setLoadingAnalysis(false);
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
        // Remove isActive prop
        <SubscriptionWidget userId={userId} /> 
      )}

      <main className="app-main">
        {/* Сообщения об ошибках и успешном выполнении */} 
        {error && <ErrorMessage message={error} onClose={() => setError(null)} />}
        {/* Use success state for now */} 
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
            {/* Use activeChannels */} 
            {activeChannels.map(channel => (
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
                          <div className="image-gallery suggested">
                              {suggestedImages.map((image, index) => (
                                  <div 
                                      key={image.id || `suggested-${index}`} 
                                      className={`image-item ${selectedImage?.id === image.id || selectedImage?.url === image.url ? 'selected' : ''}`}
                                      onClick={() => handleImageSelection(image)}
                                  >
                                  <img 
                                      src={image.preview_url || image.url} 
                                      alt={image.alt || 'Suggested image'} 
                          onError={(e) => {
                                          const target = e.target as HTMLImageElement;
                                          target.src = 'https://via.placeholder.com/100?text=Ошибка'; 
                                          console.error('Image load error:', image.preview_url || image.url);
                                      }}
                                  />
                                  {(selectedImage?.id === image.id || selectedImage?.url === image.url) && (
                                      <div className="checkmark">✔</div> 
                                  )}
                                  </div>
                              ))}
                      </div>
                    </div>
                  )}
                  
                  {/* --- Блок для своего изображения: Загрузчик и Превью --- */}
                  <div className="custom-image-section">
                     <h4>Свое изображение:</h4>
                      {/* Показываем загрузчик */} 
                      {/* --- ИЗМЕНЕНО: Передаем userId --- */}
                      <ImageUploader onImageUploaded={handleCustomImageUpload} userId={userId} />
                      
                      {/* Показываем превью ВЫБРАННОГО изображения (любого) и кнопку удаления */} 
                      {selectedImage && (
                          <div className="selected-image-preview">
                              <h5>Выбранное изображение:</h5>
                              <div className="preview-container">
                                 <img src={selectedImage.preview_url || selectedImage.url} alt={selectedImage.alt || 'Выбрано'} />
                                 <button 
                                      className="action-button delete-button small remove-image-btn"
                                      onClick={() => setSelectedImage(null)} // Сброс выбранного изображения
                                      title="Удалить выбранное изображение"
                                  >
                                      <span>🗑️ Удалить</span>
                                  </button>
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
      </main> {/* <-- ИСПРАВЛЕНО: Добавлен закрывающий тег */} 

      <footer className="app-footer">
        <p>© 2024 Smart Content Assistant</p>
      </footer>
    </div>
  );
}

export default App;
