import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './App.css';
import { TelegramAuth } from './components/TelegramAuth';
import { v4 as uuidv4 } from 'uuid';
import { Toaster, toast } from 'react-hot-toast';
import { ClipLoader } from 'react-spinners';

// Определяем базовый URL API
// Так как фронтенд и API на одном домене, используем пустую строку
// чтобы axios использовал относительные пути (например, /generate-plan)
const API_BASE_URL = '';
// const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000'; // Убираем использование process.env

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
type ViewType = 'analyze' | 'suggestions' | 'plan' | 'details' | 'calendar' | 'edit';

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
}

// Тип для дня календаря
interface CalendarDay {
  date: Date;
  posts: SavedPost[];
  isCurrentMonth: boolean;
  isToday: boolean;
}

// Компонент загрузки изображений
const ImageUploader = ({ onImageUploaded }: { onImageUploaded: (imageUrl: string) => void }) => {
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
          'Content-Type': 'multipart/form-data'
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
            {image.author && (
              <div className="image-author">
                {image.author}
              </div>
            )}
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
  const [currentMonth, setCurrentMonth] = useState<Date>(new Date());
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

  // Быстрая инициализация без localStorage
  useEffect(() => {
    // Восстанавливаем состояние из localStorage
    const storedChannel = localStorage.getItem('channelName');
    if (storedChannel) {
      setChannelName(storedChannel);
    }
    
    const storedSelectedChannels = localStorage.getItem('selectedChannels');
    if (storedSelectedChannels) {
      try {
        setSelectedChannels(JSON.parse(storedSelectedChannels));
    } catch (e) {
        console.error('Ошибка при восстановлении выбранных каналов:', e);
      }
    }
    
    setTimeout(() => {
      setLoading(false);
    }, 500);
  }, []);

  // Сохраняем канал в localStorage при изменении
  useEffect(() => {
    if (channelName) {
      localStorage.setItem('channelName', channelName);
      
      // НЕ добавляем канал в список каналов здесь - 
      // это будет происходить только после успешного анализа
    }
  }, [channelName]);
  
  // Загружаем список всех каналов при авторизации
  useEffect(() => {
    if (isAuthenticated) {
      const storedChannels = localStorage.getItem('allChannels');
      if (storedChannels) {
        try {
          setAllChannels(JSON.parse(storedChannels));
        } catch (e) {
          console.error('Ошибка при восстановлении списка каналов:', e);
        }
      }
      
      // Загружаем сохраненные посты
      fetchSavedPosts();

      // Загрузка сохраненного анализа для ТЕКУЩЕГО выбранного канала
      if (channelName) {
        fetchSavedAnalysis(channelName);
      }
    }
  }, [isAuthenticated, channelName]);
  
  // Формируем дни календаря при изменении месяца или сохраненных постов
  useEffect(() => {
    if (currentMonth) {
      generateCalendarDays();
    }
  }, [currentMonth, savedPosts]);
  
  // Функция для генерации дней календаря
  const generateCalendarDays = () => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    
    // Первый день месяца
    const firstDay = new Date(year, month, 1);
    // Последний день месяца
    const lastDay = new Date(year, month + 1, 0);
    
    // День недели первого дня (0 - воскресенье, 1 - понедельник и т.д.)
    let firstDayOfWeek = firstDay.getDay();
    // Преобразуем для начала недели с понедельника (0 - понедельник, 6 - воскресенье)
    firstDayOfWeek = firstDayOfWeek === 0 ? 6 : firstDayOfWeek - 1;
    
    // Создаем массив дней для календаря
    const days: CalendarDay[] = [];
    
    // Добавляем дни предыдущего месяца
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
    
    // Добавляем дни текущего месяца
    for (let i = 1; i <= lastDay.getDate(); i++) {
      const date = new Date(year, month, i);
      days.push({
        date,
        posts: savedPosts.filter(post => new Date(post.target_date).toDateString() === date.toDateString()),
        isCurrentMonth: true,
        isToday: date.toDateString() === new Date().toDateString()
      });
    }
    
    // Добавляем дни следующего месяца
    const daysToAdd = 42 - days.length; // 6 строк по 7 дней
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
  
  // Функция для перемещения календаря на предыдущий месяц
  const goToPrevMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
  };
  
  // Функция для перемещения календаря на следующий месяц
  const goToNextMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
  };
  
  // Функция для загрузки сохраненных постов
  const fetchSavedPosts = async () => {
    setLoadingSavedPosts(true);
    setError(null);
    
    try {
      // Если выбранных каналов нет, загружаем все посты
      if (selectedChannels.length === 0) {
        const response = await axios.get('/posts');
        
        if (response.data && Array.isArray(response.data)) {
          setSavedPosts(response.data);
          
          // Собираем уникальные каналы из постов
          updateChannelsFromPosts(response.data);
      }
    } else {
        // Если есть выбранные каналы - используем фильтр
        const allPosts: SavedPost[] = [];
        
        // Загружаем посты для каждого выбранного канала
        for (const channel of selectedChannels) {
          try {
            const response = await axios.get('/posts', {
              params: { channel_name: channel }
            });
            
            if (response.data && Array.isArray(response.data)) {
              allPosts.push(...response.data);
            }
          } catch (err) {
            console.error(`Ошибка при загрузке постов для канала ${channel}:`, err);
            // Продолжаем с другими каналами
          }
        }
        
        setSavedPosts(allPosts);
      }
    } catch (err: any) {
      console.error('Ошибка при загрузке сохраненных постов:', err);
      setError(err.response?.data?.detail || err.message || 'Ошибка при загрузке сохраненных постов');
    } finally {
      setLoadingSavedPosts(false);
    }
  };
  
  // Вспомогательная функция для обновления списка каналов из постов
  const updateChannelsFromPosts = (posts: SavedPost[]) => {
    // Собираем уникальные каналы из постов
    const channels = [...new Set(posts
      .map(post => post.channel_name)
      .filter((channel): channel is string => !!channel) // Отфильтровываем undefined и приводим к типу string
    )];
    
    // Обновляем список всех каналов
    if (channels.length > 0) {
      const updatedChannels = [...new Set([...allChannels, ...channels])];
      setAllChannels(updatedChannels);
      localStorage.setItem('allChannels', JSON.stringify(updatedChannels));
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
          'x-telegram-user-id': userId ? Number(userId) : 'unknown'
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
    if (!confirm('Вы уверены, что хотите удалить этот пост?')) return;
    
    try {
      await axios.delete(`/posts/${postId}`);
      
      // Удаляем пост из списка сохраненных
      setSavedPosts(savedPosts.filter(post => post.id !== postId));
      setSuccess('Пост успешно удален');
    } catch (err: any) {
      console.error('Ошибка при удалении поста:', err);
      setError(err.response?.data?.detail || err.message || 'Ошибка при удалении поста');
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

  // Функция для открытия редактирования поста
  const startEditingPost = (post: SavedPost) => {
    setCurrentPostId(post.id);
    setCurrentPostDate(post.target_date);
    setCurrentPostTopic(post.topic_idea);
    setCurrentPostFormat(post.format_style);
    setCurrentPostText(post.final_text);
    // setSelectedImage(null); // Убираем старый сброс
    setChannelName(post.channel_name || '');
    setSuggestedImages([]); // Очищаем предложенные
    setIsGeneratingPostDetails(false);
    setError(null);
    setSuccess(null);
    setCurrentView('edit');

    // Пытаемся загрузить сохраненное изображение для поста
    const savedImageId = post.images_ids && post.images_ids.length > 0 ? post.images_ids[0] : null;
    if (savedImageId) {
        fetchAndSetSavedImage(savedImageId);
    } else {
        // Если ID изображения нет в данных поста, сбрасываем selectedImage
        setSelectedImage(null);
    }
  };
  
  // Функция для сохранения идей в базу данных
  const saveIdeasToDatabase = async () => {
    if (suggestedIdeas.length === 0) return;
    
    setIsGeneratingIdeas(true);
    setError(null);
    
    try {
      const response = await axios.post('/save-ideas', {
        ideas: suggestedIdeas,
          channel_name: channelName 
      });
      
      if (response.data && response.data.message) {
        setSuccess(response.data.message);
      }
    } catch (err: any) {
      console.error('Ошибка при сохранении идей:', err);
      setError(err.response?.data?.detail || err.message || 'Ошибка при сохранении идей');
    } finally {
      setIsGeneratingIdeas(false);
    }
  };
  
  // Функция для фильтрации постов по каналам
  const filterPostsByChannels = async () => {
    if (selectedChannels.length === 0) {
      setError("Выберите хотя бы один канал для фильтрации");
      return;
    }
    
    // Просто используем основную функцию загрузки постов
    await fetchSavedPosts();
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
      const response = await axios.post('/analyze', { username: channelName });
      setAnalysisResult(response.data);
      setSuccess('Анализ успешно завершен');
      
      // Только после успешного анализа добавляем канал в список всех каналов
      if (!allChannels.includes(channelName)) {
        const updatedChannels = [...allChannels, channelName];
        setAllChannels(updatedChannels);
        localStorage.setItem('allChannels', JSON.stringify(updatedChannels));
      
        // Добавляем канал в список выбранных, если его там нет
        if (!selectedChannels.includes(channelName)) {
          const updatedSelected = [...selectedChannels, channelName];
          setSelectedChannels(updatedSelected);
          localStorage.setItem('selectedChannels', JSON.stringify(updatedSelected));
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
            'x-telegram-user-id': userId ? Number(userId) : 'unknown'
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
          channel_name: channelName,
          isNew: true,
        }));

        setSuggestedIdeas(formattedIdeas);
        setSuccess('Идеи успешно сгенерированы');
        
        // Сохраняем сгенерированные идеи
        saveIdeasToDatabase();
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
    if (!channelName) return;
    
    setIsGeneratingIdeas(true);
    setError(null);
    
    try {
      const response = await axios.get('/ideas', {
        params: { channel_name: channelName }
      });
      if (response.data && Array.isArray(response.data.ideas)) {
        setSuggestedIdeas(response.data.ideas);
      }
    } catch (err: any) {
      console.error('Ошибка при загрузке идей:', err);
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
  useEffect(() => {
    const fetchDetailsForNewPost = async () => {
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
            format_style: selectedIdea.format_style || '',
            channel_name: selectedIdea.channel_name || '',
            regenerate_images_only: false // We need both text and images
          }, {
            headers: {
              'x-telegram-user-id': userId ? Number(userId) : 'unknown'
            }
          });

          if (response.data) {
            console.log("Received post details:", response.data);
            // Update the post text state - Используем generated_text!
            setCurrentPostText(response.data.generated_text || ''); 

            // Process and update suggested images
            const fetchedImages = response.data.images || response.data.found_images || []; // Check multiple possible fields
            const formattedImages: PostImage[] = fetchedImages.map((img: any) => ({
              id: img.id || uuidv4(), // Generate UUID if ID is missing
              url: img.url || img.urls?.regular || img.regular_url || img.preview_url || '',
              preview_url: img.preview_url || img.urls?.thumb || img.urls?.small || img.url || '', // Use specific preview sizes if available
              alt: img.alt_description || img.description || 'Suggested image',
              author: img.user?.name || img.author_name || '',
              author_url: img.user?.links?.html || img.author_url || '',
              source: img.links?.html || 'API' // Link to image source if possible
            }));
            setSuggestedImages(formattedImages);
            if (!response.data.generated_text) {
                console.warn("Received post details, but generated_text is empty.");
                // Устанавливаем более логичную ошибку
                setError('Не удалось сгенерировать текст для выбранной идеи. Возможно, возникла временная проблема с AI или тема/формат оказались сложными. Пожалуйста, попробуйте повторить попытку позже или выберите другую идею.');
            }
          } else {
             console.warn('Received empty response when fetching post details.');
             setError('Не удалось получить детали поста (пустой ответ).');
          }
        } catch (err: any) {
          // Улучшаем логирование и отображение ошибки
          const errorMsg = err.response?.data?.detail || err.message || 'Ошибка при загрузке деталей поста';
          setError(errorMsg); 
          console.error('Ошибка при загрузке деталей поста:', errorMsg, err.response?.data || err);
        } finally {
          setIsGeneratingPostDetails(false);
        }
      }
    };

    fetchDetailsForNewPost();
  // Dependencies: This effect should run when the view changes to 'edit' for a new post (currentPostId is null)
  // and when the selectedIdea that triggers the view change is set.
  // Also include userId and API_BASE_URL as they are used in the fetch.
  }, [currentView, currentPostId, selectedIdea, userId, API_BASE_URL]);

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
  };

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
        <h1>Smart Content Assistant</h1>
      </header>

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
          {currentView === 'suggestions' && (
            <div className="view suggestions-view">
              <h2>Идеи контента</h2>
              
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
                </div>
            )}

          {/* Вид календаря */}
          {currentView === 'calendar' && (
            <div className="view calendar-view">
              <h2>Календарь публикаций</h2>
              
              {/* Фильтр по каналам */}
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
                        localStorage.setItem('selectedChannels', JSON.stringify(updatedSelected));
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
                          localStorage.setItem('selectedChannels', JSON.stringify(updatedSelected));
                        }}
                      >
                        ✕
                      </button>
      </div>
                  ))}
      </div>
              </div>
              
              {/* Календарь */}
              <div className="calendar-container">
                {/* Заголовок с названием месяца и навигацией */}
                <div className="calendar-header">
                  <button 
                    className="nav-button"
                    onClick={() => {
                      const newDate = new Date(currentMonth);
                      newDate.setMonth(newDate.getMonth() - 1);
                      setCurrentMonth(newDate);
                    }}
                  >
                    &lt;
                  </button>
                  
                  <h3>{currentMonth.toLocaleString('default', { month: 'long', year: 'numeric' })}</h3>
                  
                  <button 
                    className="nav-button"
                    onClick={() => {
                      const newDate = new Date(currentMonth);
                      newDate.setMonth(newDate.getMonth() + 1);
                      setCurrentMonth(newDate);
                    }}
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
            </div>
          )}
          
          {/* Вид редактирования поста */}
          {currentView === 'edit' && (
            <div className="view edit-view">
              <h2>{currentPostId ? 'Редактирование поста' : 'Создание нового поста'}</h2>
              
              {/* Индикатор загрузки при генерации деталей */}
              {isGeneratingPostDetails && <Loading message="Генерируем детали поста..." />}

              {/* Поля для редактирования (отображаются всегда, но могут быть пустыми во время загрузки) */}
              {!isGeneratingPostDetails && (
                <>
                  <div className="form-group">
                    <label>Канал:</label>
                    <input 
                      type="text" 
                      value={channelName} 
                      onChange={(e) => !currentPostId && setChannelName(e.target.value.replace(/^@/, ''))} 
                      placeholder="Имя канала (без @)"
                      readOnly={!!currentPostId}
                      className={currentPostId ? 'read-only-input' : ''}
                    />
                  </div>
                  <div className="form-group">
                    <label>Дата публикации:</label>
                    <input 
                      type="date" 
                      value={currentPostDate} 
                      onChange={(e) => setCurrentPostDate(e.target.value)} 
                    />
                  </div>
                  <div className="form-group">
                    <label>Тема/Идея:</label>
                    <input 
                      type="text" 
                      value={currentPostTopic} 
                      onChange={(e) => setCurrentPostTopic(e.target.value)} 
                    />
                  </div>
                  <div className="form-group">
                    <label>Формат/Стиль:</label>
                    <input 
                      type="text" 
                      value={currentPostFormat} 
                      onChange={(e) => setCurrentPostFormat(e.target.value)} 
                    />
                  </div>
                  <div className="form-group">
                    <label>Текст поста:</label>
                    <textarea 
                      value={currentPostText} 
                      onChange={(e) => setCurrentPostText(e.target.value)}
                      rows={15}
                      placeholder="Введите или отредактируйте текст поста..."
                      className="post-text-editor"
                    />
                  </div>
                  
                  {/* Отображение предложенных изображений */}
                  {suggestedImages.length > 0 && (
                    <div className="suggested-images-section">
                      <h3>Предложенные изображения (выберите одно):</h3>
                      <div className="image-gallery suggested">
                         {suggestedImages.map((image) => (
                          <div
                            key={image.id}
                            className={`image-item ${selectedImage?.id === image.id || selectedImage?.url === image.url ? 'selected' : ''}`}
                            onClick={() => {
                              // Передаем весь объект image в обработчик
                              handleImageSelection(image);
                            }}
                          >
                            <img src={image.preview_url || image.url} alt={image.alt || 'Suggested image'} />
                            {image.author && (
                              <span className="image-author">
                                {image.author_url ? 
                                    <a href={image.author_url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>by {image.author}</a> 
                                    : `by ${image.author}`
                                }
                              </span>
                            )}
                            {(selectedImage?.id === image.id || selectedImage?.url === image.url) && <span className="checkmark">✓</span>}
                          </div>
                         ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Placeholder or message if no images are suggested or selected */}
                  {!selectedImage && suggestedImages.length === 0 && (
                      <p>Нет предложенных изображений. Вы можете сохранить пост без изображения.</p>
                  )}

                  {/* ---- ДОБАВЛЯЕМ КНОПКУ СОХРАНЕНИЯ ---- */}
                  <button
                    onClick={handleSaveOrUpdatePost}
                    className="action-button save-update-button"
                    // Кнопка неактивна, если идет сохранение/генерация деталей или текст пустой
                    disabled={isSavingPost || isGeneratingPostDetails || !currentPostText.trim()}
                  >
                    {isSavingPost ? (
                      <ClipLoader size={20} color={"#fff"} />
                    ) : (
                      currentPostId ? 'Обновить пост' : 'Сохранить пост'
                    )}
                  </button>
                  {/* ---- КОНЕЦ ДОБАВЛЕНИЯ КНОПКИ ---- */}
                </>
              )} 
            </div>
          )}
        </div>
      </main>

      <footer className="app-footer">
        <p>Telegram User ID: {userId}</p>
      </footer>
    </div>
  );
}

export default App;
