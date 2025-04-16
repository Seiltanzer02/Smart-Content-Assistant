import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './App.css';
import { TelegramAuth } from './components/TelegramAuth';
import { v4 as uuidv4 } from 'uuid';

// Определяем базовый URL API
const API_BASE_URL = '';

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
  alt?: string;
  author?: string;
  author_url?: string;
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
  images_ids?: string[]; // Добавляем поддержку массива ID изображений
}

// Тип для дня календаря
interface CalendarDay {
  date: Date;
  posts: SavedPost[];
  isCurrentMonth: boolean;
  isToday: boolean;
}

// Добавим новый тип для кешированных деталей постов
interface CachedPostDetails {
  [key: string]: DetailedPost;
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

// Компонент для выбора изображений из галереи
const ImageGallery = ({ onImageSelect }) => {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedImages, setSelectedImages] = useState([]);

  useEffect(() => {
    fetchUserImages();
  }, []);

  const fetchUserImages = async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await axios.get(`${API_BASE_URL}/images`, {
        headers: { "x-telegram-user-id": userId || 'unknown' }
      });
      
      setImages(response.data);
    } catch (err) {
      console.error('Ошибка при загрузке изображений:', err);
      setError('Не удалось загрузить изображения');
    } finally {
      setLoading(false);
    }
  };

  const handleImageClick = (image) => {
    // Если изображение уже выбрано, удаляем его из выбранных
    if (selectedImages.some(img => img.id === image.id)) {
      setSelectedImages(selectedImages.filter(img => img.id !== image.id));
    } else {
      // Иначе добавляем в выбранные
      setSelectedImages([...selectedImages, image]);
    }
  };

  const confirmSelection = () => {
    // Передаем выбранные изображения через callback
    onImageSelect(selectedImages);
  };

  return (
    <div style={{ marginTop: '20px' }}>
      <h3>Выберите изображения</h3>
      
      {loading && <div>Загрузка изображений...</div>}
      {error && <div style={{ color: 'red' }}>{error}</div>}
      
      {images.length === 0 && !loading && !error && (
        <div>У вас пока нет сохраненных изображений</div>
      )}
      
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', 
        gap: '10px', 
        marginTop: '10px' 
      }}>
        {images.map(image => (
          <div 
            key={image.id} 
            style={{ 
              border: selectedImages.some(img => img.id === image.id) 
                ? '3px solid blue' 
                : '1px solid #ddd',
              borderRadius: '4px',
              padding: '5px',
              cursor: 'pointer'
            }}
            onClick={() => handleImageClick(image)}
          >
            <img 
              src={image.url} 
              alt={image.alt_description || 'Изображение'} 
              style={{ 
                width: '100%', 
                height: '120px', 
                objectFit: 'cover',
                borderRadius: '2px'
              }} 
            />
          </div>
        ))}
      </div>
      
      {images.length > 0 && (
        <button 
          onClick={confirmSelection}
          style={{
            marginTop: '15px',
            padding: '8px 16px',
            backgroundColor: '#0088cc',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Подтвердить выбор ({selectedImages.length})
        </button>
      )}
    </div>
  );
};

// Компонент для отображения выбранных изображений
const SelectedImagesPreview = ({ images, onRemove }) => {
  if (!images || images.length === 0) return null;
  
  return (
    <div style={{ marginTop: '15px' }}>
      <h4>Выбранные изображения</h4>
      <div style={{ 
        display: 'flex', 
        flexWrap: 'wrap', 
        gap: '10px' 
      }}>
        {images.map(image => (
          <div 
            key={image.id} 
            style={{ 
              position: 'relative',
              border: '1px solid #ddd',
              borderRadius: '4px',
              padding: '5px',
              width: '120px'
            }}
          >
            <img 
              src={image.url} 
              alt={image.alt_description || 'Изображение'} 
              style={{ 
                width: '100%', 
                height: '100px', 
                objectFit: 'cover',
                borderRadius: '2px'
              }} 
            />
            <button
              onClick={() => onRemove(image)}
              style={{
                position: 'absolute',
                top: '5px',
                right: '5px',
                background: 'rgba(255, 255, 255, 0.7)',
                border: 'none',
                borderRadius: '50%',
                width: '24px',
                height: '24px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer'
              }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
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
  const [isGeneratingIdeas, setIsGeneratingIdeas] = useState(false);
  const [suggestedIdeas, setSuggestedIdeas] = useState<SuggestedIdea[]>([]);
  const [selectedIdea, setSelectedIdea] = useState<SuggestedIdea | null>(null);
  const [detailedPost, setDetailedPost] = useState<DetailedPost | null>(null);
  const [isDetailGenerating, setIsDetailGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null); 
  const [success, setSuccess] = useState<string | null>(null);
  // Добавляем состояние для выбранного изображения
  const [selectedImage, setSelectedImage] = useState<number | null>(null);
  // Новые состояния для предпросмотра и выбора изображений
  const [previewVisible, setPreviewVisible] = useState<boolean>(false);
  const [previewUrl, setPreviewUrl] = useState<string>('');
  
  // Новые состояния для календаря и сохраненных постов
  const [savedPosts, setSavedPosts] = useState<SavedPost[]>([]);
  const [loadingSavedPosts, setLoadingSavedPosts] = useState(false);
  const [currentMonth, setCurrentMonth] = useState<Date>(new Date());
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [calendarDays, setCalendarDays] = useState<CalendarDay[]>([]);
  
  // Состояния для редактирования постов
  const [editingPost, setEditingPost] = useState<SavedPost | null>(null);
  const [editedText, setEditedText] = useState<string>('');
  const [editedImageUrl, setEditedImageUrl] = useState<string>('');
  const [editedDate, setEditedDate] = useState<string>('');
  const [isSavingPost, setIsSavingPost] = useState(false);
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [allChannels, setAllChannels] = useState<string[]>([]);

  // Добавляем кеш для детализированных постов
  const [detailsCache, setDetailsCache] = useState<CachedPostDetails>({});

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
    }
  }, [isAuthenticated]);
  
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
    
    setIsDetailGenerating(true);
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
          'x-telegram-user-id': userId || 'unknown'
        }
      });

      if (response.data && response.data.found_images && detailedPost) {
        const newImages = response.data.found_images.map((img: any) => ({
          url: img.url || img.urls?.regular || img.regular_url || img.preview_url || '',
          alt: img.alt_description || img.description || 'Изображение для поста',
          author: img.user?.name || img.author_name || '',
          author_url: img.user?.links?.html || img.author_url || ''
        }));

        setDetailedPost(prevState => {
          if (!prevState) return null;
          return {
            ...prevState,
            images: newImages
          };
        });

        if (selectedIdea && detailedPost) {
          setDetailsCache(prev => {
            const updatedCache = prev || {};
            return {
              ...updatedCache,
              [selectedIdea.id]: {
                ...detailedPost,
                images: newImages
              }
            };
          });
        }
        
        // Сбрасываем выбранное изображение после обновления
        setSelectedImage(null);
        setSuccess('Изображения успешно обновлены');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при обновлении изображений');
      console.error('Ошибка при обновлении изображений:', err);
    } finally {
      setIsDetailGenerating(false);
    }
  };

  // Сохранение поста с правильной обработкой
  const handleSavePost = async () => {
    if (!selectedIdea || !detailedPost) {
      setError("Пожалуйста, выберите идею и создайте пост перед сохранением");
      return;
    }

    setIsSavingPost(true);
    setError("");
    setSuccess("");

    // Сохраняем выбранные изображения перед сохранением поста
    const savedImageIds: string[] = [];
    
    // Проверяем, есть ли изображения в детализированном посте
    if (detailedPost.images && detailedPost.images.length > 0) {
      for (const img of detailedPost.images) {
        // Проверяем, что изображение имеет url перед сохранением
        if (img && img.url) {
          try {
            // Генерируем уникальный ID для изображения, если его нет
            const imageId = `img_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
            
            // Сохраняем изображение в базе данных
            const response = await axios.post(`${API_BASE_URL}/save-image`, {
              id: imageId,
              url: img.url,
              alt_description: img.alt || "",
              source: "unsplash"
            }, {
              headers: { "x-telegram-user-id": userId || 'unknown' }
            });
            
            savedImageIds.push(imageId);
            console.log("Изображение успешно сохранено:", response.data);
          } catch (error) {
            // Логируем ошибку, но продолжаем процесс - не прерываем сохранение поста из-за ошибки с изображением
            console.error("Ошибка при сохранении изображения:", error);
            setError(`Ошибка при сохранении изображения: ${error instanceof Error ? error.message : String(error)}`);
          }
        } else {
          console.warn("Пропущено изображение без URL:", img);
        }
      }
    }

    try {
      const postData = {
        topic_idea: selectedIdea?.topic_idea || "",
        format_style: selectedIdea?.format_style || "",
        post_text: detailedPost.post_text,
        channel_name: selectedIdea?.channel_name || "",
        target_date: selectedDate,
        images: savedImageIds
      };

      console.log("Сохраняемые данные поста:", postData);
      
      const response = await axios.post(`${API_BASE_URL}/posts`, postData, {
        headers: { "x-telegram-user-id": userId || 'unknown' }
      });

      console.log("Пост успешно сохранен:", response.data);
      setSuccess("Пост успешно сохранен!");
      
      // Обновляем список сохраненных постов
      fetchSavedPosts();
      
      // Очищаем выбранные данные
      setSelectedIdea(null);
      setDetailedPost(null);
    } catch (error) {
      console.error("Ошибка при сохранении поста:", error);
      setError(`Ошибка при сохранении поста: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsSavingPost(false);
    }
  };
  
  // Функция для обновления поста
  const updatePost = async () => {
    if (!editingPost) return;
    
    setIsSavingPost(true);
    setError(null);
    
    try {
      const postData = {
        ...editingPost,
        final_text: editedText,
        image_url: editedImageUrl,
        target_date: editedDate
      };
      
      const response = await axios.put(`/posts/${editingPost.id}`, postData);
      
      if (response.data) {
        // Обновляем пост в списке сохраненных
        setSavedPosts(savedPosts.map(post => 
          post.id === editingPost.id ? response.data : post
        ));
        setSuccess('Пост успешно обновлен');
        setCurrentView('calendar');
        setEditingPost(null);
      }
    } catch (err: any) { 
      console.error('Ошибка при обновлении поста:', err);
      setError(err.response?.data?.detail || err.message || 'Ошибка при обновлении поста');
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
  
  // Функция для открытия редактирования поста
  const startEditingPost = (post: SavedPost) => {
    setEditingPost(post);
    setEditedText(post.final_text);
    setEditedImageUrl(post.image_url || '');
    setEditedDate(post.target_date);
    setCurrentView('edit');
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
  const handleDetailIdea = async (idea: SuggestedIdea) => {
    try {
      setSelectedIdea(idea);
      setIsDetailGenerating(true);
      setDetailedPost(null);
      // Сбрасываем выбранное изображение при новой детализации
      setSelectedImage(null);
      setError("");

      // Запрос на генерацию деталей поста
      const response = await axios.post(
        `${API_BASE_URL}/generate-post-details`,
        {
          topic_idea: idea.topic_idea,
          format_style: idea.format_style,
          channel_name: idea.channel_name
        },
        {
          headers: {
            'x-telegram-user-id': userId || 'unknown'
          }
        }
      );

      // Если успешно получили данные
      if (response.data) {
        const newDetails = {
          post_text: response.data.generated_text || 'Не удалось сгенерировать текст поста.',
          images: response.data.found_images ? response.data.found_images.map((img: any) => ({
            url: img.regular_url || img.preview_url,
            alt: img.description,
            author: img.author_name,
            author_url: img.author_url
          })) : []
        };
        
        // Устанавливаем первое изображение как выбранное, если есть изображения
        if (newDetails.images.length > 0) {
          setSelectedImage(0);
        }
        
        // Сохраняем в кеш и в текущее состояние
        setDetailedPost(newDetails);
        setDetailsCache(prev => ({
          ...prev,
          [idea.id]: newDetails
        }));
        
        setSuccess('Детализация успешно создана');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при детализации идеи');
      console.error('Ошибка при детализации:', err);
    } finally {
      setCurrentView('details');
      setIsDetailGenerating(false);
    }
  };

  // Возврат к списку идей
  const backToIdeas = () => {
    setCurrentView('suggestions');
    setSelectedIdea(null);
    setDetailedPost(null);
  };

  // Добавим функцию для предпросмотра изображения
  const handlePreviewImage = (imageUrl: string) => {
    setPreviewUrl(imageUrl);
    setPreviewVisible(true);
  };

  // Функция для закрытия предпросмотра
  const handleClosePreview = () => {
    setPreviewVisible(false);
  };

  // Функция для выбора изображения
  const handleSelectImage = (index: number) => {
    setSelectedImage(index === selectedImage ? null : index);
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
        {error && <div className="error-message">{error}</div>}
        {success && <div className="success-message">{success}</div>}

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
              setCurrentView('plan');
              fetchSavedPosts();
            }} 
            className={`action-button ${currentView === 'plan' ? 'active' : ''}`}
          >
            План
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

              {isAnalyzing && (
                <div className="loading-indicator">
                  <div className="loading-spinner"></div>
                  <p>Анализируем канал...</p>
                </div>
              )}

      {analysisResult && (
          <div className="results-container">
              <h3>Результаты анализа:</h3>
              <p><strong>Темы:</strong> {analysisResult.themes.join(', ')}</p>
              <p><strong>Стили:</strong> {analysisResult.styles.join(', ')}</p>
                  <p><strong>Лучшее время для постинга:</strong> {analysisResult.best_posting_time}</p>
                  <p><strong>Проанализировано постов:</strong> {analysisResult.analyzed_posts_count}</p>
                  
              <button 
                    onClick={generateIdeas} 
                    className="action-button generate-button"
                    disabled={isGeneratingIdeas}
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
                    : 'Сначала выполните анализ канала на вкладке "Анализ".'
                  }
                </p>
              ) : null}
                </div>
            )}

          {/* Вид плана */}
          {currentView === 'plan' && (
            <div className="view plan-view">
              <h2>План публикаций</h2>
              
              {loadingSavedPosts ? (
                <div className="loading-indicator">
                  <div className="loading-spinner"></div>
                  <p>Загрузка сохраненных постов...</p>
                                </div>
              ) : savedPosts.length > 0 ? (
                <div className="plan-display">
                  <h3>План публикаций для канала {channelName ? `@${channelName}` : ""}</h3>
                  <ul className="plan-list">
                    {savedPosts
                      .sort((a, b) => new Date(a.target_date).getTime() - new Date(b.target_date).getTime())
                      .map((post) => (
                        <li key={post.id} className="plan-list-item-clickable" onClick={() => startEditingPost(post)}>
                          <strong>{new Date(post.target_date).toLocaleDateString()}:</strong> {post.topic_idea} 
                          <em>({post.format_style})</em>
                          {post.channel_name && <span className="post-channel">@{post.channel_name}</span>}
                            </li>
                        ))}
                    </ul>
            </div>
              ) : (
                <div className="empty-plan">
                  <p>У вас пока нет сохранённых постов. Создайте посты на вкладке "Идеи", затем детализируйте и сохраните их.</p>
        <button 
                    className="action-button" 
          onClick={() => {
                      setCurrentView('suggestions');
                      if (suggestedIdeas.length === 0) {
                        fetchSavedIdeas();
                      }
                    }}
                  >
                    Перейти к идеям
        </button>
             </div>
              )}
               </div>
          )}

          {/* Вид детализации */}
          {currentView === 'details' && (
            <div className="details-view">
              {selectedIdea ? (
                <>
                  <h2>Детализация контент-идеи</h2>
                  <div className="idea-details">
                    <p><strong>Тема:</strong> {selectedIdea.topic_idea}</p>
                    <p><strong>Формат:</strong> {selectedIdea.format_style}</p>
                    <p><strong>Канал:</strong> {selectedIdea.channel_name}</p>
                  </div>
                  
                  {isDetailGenerating ? (
                    <Loading message="Генерируем детали поста..." />
                  ) : error ? (
                    <ErrorMessage message={error} onClose={() => setError(null)} />
                  ) : success ? (
                    <SuccessMessage message={success} onClose={() => setSuccess(null)} />
                  ) : detailedPost ? (
                    <div className="post-details">
                      <div className="text-section">
                        <h3>Текст поста:</h3>
              <textarea
                          value={detailedPost.post_text}
                          onChange={(e) => 
                            setDetailedPost({
                              ...detailedPost,
                              post_text: e.target.value
                            })
                          }
                rows={10}
                          className="post-text-editor"
              />
            </div>
                      
                      {detailedPost.images && detailedPost.images.length > 0 && (
                        <div className="image-section">
                          <h3>Изображения:</h3>
                <div className="image-thumbnails">
                            {detailedPost.images.map((img, index) => (
                              <div key={index} className={`image-item ${selectedImage === index ? 'selected' : ''}`}>
                                <img 
                                  src={img.url} 
                                  alt={img.alt || "Изображение для поста"} 
                                  className="thumbnail"
                                  onClick={() => setSelectedImage(index)}
                                  onError={(e) => {
                                    // Обработка ошибки загрузки изображения
                                    const target = e.target as HTMLImageElement;
                                    target.onerror = null; // Предотвращаем циклическую обработку ошибок
                                    target.src = 'https://via.placeholder.com/150?text=Ошибка+загрузки';
                                  }}
                                />
                                <div className="image-overlay">
                                  <button 
                                    className="select-image-button"
                                    onClick={() => setSelectedImage(index)}
                                  >
                                    {selectedImage === index ? '✓ Выбрано' : 'Выбрать'}
                                  </button>
                                </div>
                    </div>
                  ))}
                </div>
                    <div className="selected-image-preview">
                            {selectedImage !== null && detailedPost.images[selectedImage] && (
                              <div className="preview-container">
                                <h4>Выбранное изображение:</h4>
                      <img 
                                  src={detailedPost.images[selectedImage].url} 
                                  alt={detailedPost.images[selectedImage].alt || "Выбранное изображение"} 
                        className="preview-image" 
                                  onError={(e) => {
                                    // Обработка ошибки загрузки изображения в превью
                                    const target = e.target as HTMLImageElement;
                                    target.onerror = null;
                                    target.src = 'https://via.placeholder.com/300?text=Ошибка+загрузки';
                                  }}
                                />
                                {detailedPost.images[selectedImage].author && (
                                  <p className="image-credit">
                                    Автор: <a href={detailedPost.images[selectedImage].author_url} target="_blank" rel="noopener noreferrer">
                                      {detailedPost.images[selectedImage].author}
                                    </a>
                                  </p>
                                )}
              </div>
            )}
                  </div>
                  <div className="image-actions">
                            <button 
                              onClick={regeneratePostDetails}
                              className="action-button"
                              disabled={isDetailGenerating}
                            >
                              Обновить изображения
                    </button>
                            <div className="custom-image-upload">
                              <h4>Загрузить свое изображение:</h4>
                              <ImageUploader 
                                onImageUploaded={(url) => {
                                  // Добавляем загруженное изображение к детализации
                                  const newImage = {
                                    url: url,
                                    alt: "Пользовательское изображение"
                                  };
                                  
                                  // Проверяем, существует ли detailedPost и есть ли у него массив images
                                  if (detailedPost) {
                                    const updatedImages = detailedPost.images ? [newImage, ...detailedPost.images] : [newImage];
                                    const updatedPost: DetailedPost = {
                                      ...detailedPost,
                                      images: updatedImages
                                    };
                                    
                                    setDetailedPost(updatedPost);
                                    
                                    // Устанавливаем загруженное изображение как выбранное
                                    setSelectedImage(0);
                                    
                                    // Обновляем кеш
                                    if (selectedIdea) {
                                      setDetailsCache(prev => {
                                        if (prev === null) return { [selectedIdea.id]: updatedPost };
                                        return {
                                          ...prev,
                                          [selectedIdea.id]: updatedPost
                                        };
                                      });
                                    }
                                  }
                                }} 
                              />
                  </div>
                </div>
              </div>
            )}

                      {/* Добавляем кнопку сохранения поста */}
                      <div className="actions-section">
                        <h3>Сохранить пост:</h3>
                        <div className="date-picker-container">
                          <label>Выберите дату публикации: </label>
                    <input 
                            type="date" 
                            value={selectedDate.toISOString().split('T')[0]}
                            onChange={(e) => setSelectedDate(new Date(e.target.value))}
                            className="date-input"
                          />
                        </div>
                    <button 
                          onClick={handleSavePost}
                          className="action-button save-button"
                          disabled={isSavingPost}
                        >
                          {isSavingPost ? 'Сохранение...' : 'Сохранить пост'}
                    </button>
                      </div>
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="empty-details">
                  <p>Выберите идею для детализации</p>
               </div>
            )}
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
          {currentView === 'edit' && editingPost && (
            <div className="view edit-view">
              <button onClick={() => {
                setCurrentView('calendar');
                setEditingPost(null);
              }} className="back-button">
                ← Назад к календарю
              </button>
              
              <h2>Редактирование поста</h2>
              
              <div className="post-source-info">
                <p><strong>Тема:</strong> {editingPost.topic_idea}</p>
                <p><strong>Формат:</strong> {editingPost.format_style}</p>
                <div className="date-picker-container">
                  <label><strong>Дата публикации:</strong></label>
                  <input 
                    type="date" 
                    value={editedDate}
                    onChange={(e) => setEditedDate(e.target.value)}
                    className="date-input"
                  />
                </div>
                {editingPost.channel_name && (
                  <p><strong>Канал:</strong> @{editingPost.channel_name}</p>
                )}
              </div>
              
              <div className="edit-form">
                <div className="edit-text-section">
                  <h3>Текст поста:</h3>
                  <textarea 
                    className="edit-textarea" 
                    value={editedText} 
                    onChange={(e) => setEditedText(e.target.value)}
                  />
                </div>
                
                <div className="edit-image-section">
                  <h3>Изображение поста:</h3>
                  {editedImageUrl && (
                    <div className="current-image">
                      <div className="image-preview">
                        <img 
                          src={editedImageUrl} 
                          alt="Предпросмотр изображения"
                          className="preview-image"
                          onError={(e) => {
                            (e.target as HTMLImageElement).src = 'https://via.placeholder.com/300x200?text=Ошибка+загрузки';
                          }}
                        />
                        <button 
                          className="action-button small delete" 
                          onClick={() => setEditedImageUrl('')}
                        >
                          Удалить изображение
                        </button>
                      </div>
                    </div>
                  )}
                  
                  <div className="image-selection">
                    <h4>Выбрать изображение из галереи:</h4>
                    <PostImageGallery 
                      postId={editingPost.id}
                      onImageSelect={(imageUrl) => setEditedImageUrl(imageUrl)}
                    />
                    
                    <h4>или загрузить новое изображение:</h4>
                    <ImageUploader onImageUploaded={(url) => setEditedImageUrl(url)} />
                    
                    <h4>или ввести URL изображения:</h4>
                    <div className="image-url-input-container">
                      <input 
                        type="text"
                        className="image-url-input"
                        value={editedImageUrl}
                        onChange={(e) => setEditedImageUrl(e.target.value)}
                        placeholder="URL изображения"
                      />
                    </div>
                  </div>
                </div>
                
                <div className="edit-actions">
                  <button 
                    onClick={updatePost}
                    className="action-button save-button"
                    disabled={isSavingPost}
                  >
                    {isSavingPost ? 'Сохранение...' : 'Сохранить изменения'}
                  </button>
                  <button 
                    onClick={() => {
                      setCurrentView('calendar');
                      setEditingPost(null);
                    }}
                    className="action-button cancel-button"
                    disabled={isSavingPost}
                  >
                    Отмена
                  </button>
                </div>
              </div>
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
