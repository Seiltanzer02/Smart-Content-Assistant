import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import { TelegramAuth } from './components/TelegramAuth';
import { v4 as uuidv4 } from 'uuid';

// Определяем базовый URL API
const API_BASE_URL = '';

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

  // Функция для сохранения поста
  const savePost = async (dateForPost: Date) => {
    if (!selectedIdea || !detailedPost) {
      setError('Не удалось сохранить пост: отсутствуют данные');
      return;
    }
    
    setIsSavingPost(true);
    setError('');
    setSuccess('');
    
    try {
      // Формируем данные для сохранения
      const postData = {
        topic_idea: selectedIdea.topic_idea,
        format_style: selectedIdea.format_style,
        post_text: detailedPost.post_text,
        channel_name: selectedIdea.channel_name,
        target_date: dateForPost.toISOString(),
        // Если выбрано изображение, отправляем только его, иначе первое изображение или пустой массив
        images: selectedImage !== null && detailedPost.images.length > 0 
          ? [detailedPost.images[selectedImage]]
          : detailedPost.images.length > 0 
            ? [detailedPost.images[0]] 
            : []
      };
      
      // Отправляем запрос на сохранение
      const response = await axios.post(`${API_BASE_URL}/posts`, postData, {
        headers: {
          'x-telegram-user-id': userId || 'unknown'
        }
      });
      
      if (response.data) {
        setSuccess('Пост успешно сохранен');
        
        // Обновляем список сохраненных постов
        fetchSavedPosts();
        
        // Если у идеи есть id и он не генерируемый, пытаемся обновить её статус
        if (selectedIdea.id && !selectedIdea.id.startsWith('idea-')) {
          try {
            await axios.put(`${API_BASE_URL}/ideas/${selectedIdea.id}`, 
              { status: 'completed' },
              {
                headers: {
                  'x-telegram-user-id': userId || 'unknown'
                }
              }
            );
          } catch (ideasErr) {
            console.warn('Не удалось обновить статус идеи:', ideasErr);
            // Не показываем эту ошибку пользователю, так как пост уже сохранен
          }
        }
        
        // Возвращаемся к списку идей или плана после короткой задержки
        setTimeout(() => {
          setCurrentView('plan');
          setSelectedIdea(null);
          setDetailedPost(null);
        }, 1500);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при сохранении поста');
      console.error('Ошибка при сохранении поста:', err);
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

  // Сохранение поста с правильной обработкой
  const handleSavePost = async () => {
    if (!detailedPost || !selectedIdea) return;
    
    setIsSavingPost(true);
    setError(null);
    setSuccess(null);
    
    try {
      // Получаем URL выбранного изображения, если есть
      const selectedImageUrl = selectedImage !== null && detailedPost.images && detailedPost.images.length > 0
        ? detailedPost.images[selectedImage].url
        : null;
      
      // Создаем объект поста
      const postData = {
        post_id: `post-${Date.now()}`, // Генерируем ID для нового поста
        idea_id: selectedIdea.id,
        text: detailedPost.post_text,
        image_url: selectedImageUrl,
        created_at: new Date().toISOString(),
        status: 'draft',
        channel_name: selectedIdea.channel_name,
        topic: selectedIdea.topic_idea,
        format: selectedIdea.format_style,
        telegram_user_id: userId || 'unknown'
      };
      
      // Отправляем запрос на сохранение поста
      const response = await axios.post(`${API_BASE_URL}/posts`, postData, {
        headers: {
          'x-telegram-user-id': userId || 'unknown'
        }
      });
      
      // Обновляем список сохраненных постов
      if (response.data && response.data.post_id) {
        // Добавляем новый пост в список
        setSavedPosts(prev => [...prev, response.data]);
        
        // Обновляем статус идеи, если это возможно
        // Не пытаемся преобразовать ID идеи в UUID
        const ideaUpdateResponse = await axios.patch(
          `${API_BASE_URL}/ideas/${selectedIdea.id}/status`,
          { status: 'done' },
          {
            headers: {
              'x-telegram-user-id': userId || 'unknown'
            }
          }
        ).catch(err => {
          // Если ошибка связана с UUID, просто логируем и продолжаем
          console.warn('Не удалось обновить статус идеи:', err.message);
          return null;
        });
        
        if (ideaUpdateResponse) {
          // Обновляем список идей с новым статусом
          setSuggestedIdeas(prev => 
            prev.map(idea => 
              idea.id === selectedIdea.id 
                ? { ...idea, status: 'done' } 
                : idea
            )
          );
        }
        
        setSuccess('Пост успешно сохранен');
        
        // Переходим на вкладку календаря
        setCurrentView('calendar');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при сохранении поста');
      console.error('Ошибка при сохранении поста:', err);
    } finally {
      setIsSavingPost(false);
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
              {selectedIdea && (
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
                      
                      {/* Section for displaying images */}
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
                  )}
                </>
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
                    disabled={!channelName || selectedChannels.includes(channelName)}
                  >
                    Добавить текущий канал
                </button>
                  
                  <button
                    className="action-button"
                    onClick={() => {
                      // Сбросить фильтр (показать все каналы)
                      setSelectedChannels([]);
                      localStorage.setItem('selectedChannels', JSON.stringify([]));
                      fetchSavedPosts();
                    }}
                    disabled={selectedChannels.length === 0}
                  >
                    Сбросить фильтр
                </button>
          </div>
                
                <div className="channels-checkboxes">
                  {allChannels.map(channel => (
                    <label key={channel} className="channel-checkbox">
                      <input 
                        type="checkbox"
                        checked={selectedChannels.includes(channel)}
                        onChange={() => {
                          const newSelected = selectedChannels.includes(channel)
                            ? selectedChannels.filter(ch => ch !== channel)
                            : [...selectedChannels, channel];
                          setSelectedChannels(newSelected);
                          localStorage.setItem('selectedChannels', JSON.stringify(newSelected));
                        }}
                      />
                      {channel}
                      {/* Добавляем кнопку удаления канала из списка */}
                      <button 
                        className="remove-channel-button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          
                          // Удаляем канал из списка всех каналов
                          const updatedChannels = allChannels.filter(ch => ch !== channel);
                          setAllChannels(updatedChannels);
                          localStorage.setItem('allChannels', JSON.stringify(updatedChannels));
                          
                          // Также удаляем из выбранных, если он там был
                          if (selectedChannels.includes(channel)) {
                            const updatedSelected = selectedChannels.filter(ch => ch !== channel);
                            setSelectedChannels(updatedSelected);
                            localStorage.setItem('selectedChannels', JSON.stringify(updatedSelected));
                          }
                        }}
                      >
                        ✕
                      </button>
                    </label>
                  ))}
                </div>
                
                <button 
                  onClick={filterPostsByChannels}
                  className="action-button apply-filter-button"
                  disabled={loadingSavedPosts}
                >
                  Применить фильтр
                </button>
               </div>
            
              {loadingSavedPosts ? (
                <div className="loading-indicator">
                  <div className="loading-spinner"></div>
                  <p>Загрузка постов...</p>
          </div>
              ) : (
                <>
                  {/* Навигация по месяцам */}
                  <div className="calendar-navigation">
                    <button onClick={goToPrevMonth} className="calendar-nav-button">
                      &lt; Предыдущий
                </button>
                    <h3>
                      {currentMonth.toLocaleString('ru-RU', { month: 'long', year: 'numeric' })}
                    </h3>
                    <button onClick={goToNextMonth} className="calendar-nav-button">
                      Следующий &gt;
                    </button>
                  </div>
                  
                  {/* Сетка календаря */}
                  <div className="calendar-grid">
                    {/* Заголовки дней недели */}
                    <div className="calendar-weekdays">
                      {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map(day => (
                        <div key={day} className="calendar-weekday">{day}</div>
                      ))}
                    </div>
                    
                    {/* Дни календаря */}
                    <div className="calendar-days">
                      {calendarDays.map((day, index) => (
                        <div 
                          key={index} 
                          className={`calendar-day ${!day.isCurrentMonth ? 'other-month' : ''} ${day.isToday ? 'today' : ''}`}
                        >
                          <div className="day-number">{day.date.getDate()}</div>
                          
                          {day.posts.length > 0 && (
                            <div className="day-posts">
                              {day.posts.map(post => (
                                <div key={post.id} className="calendar-post">
                                  <div className="post-summary">
                                    <strong>{post.topic_idea}</strong>
                                    <span className="post-format">{post.format_style}</span>
                                    {post.channel_name && (
                                      <span className="post-channel">@{post.channel_name}</span>
                                    )}
                                  </div>
                                  <div className="post-actions">
                <button 
                                      onClick={() => startEditingPost(post)}
                                      className="action-button small"
                                    >
                                      Изменить
                </button>
                                    <button 
                                      onClick={() => deletePost(post.id)}
                                      className="action-button small delete"
                                    >
                                      Удалить
                </button>
                                  </div>
                                </div>
                              ))}
                            </div>
            )}
          </div>
                      ))}
      </div>
      </div>
                </>
              )}
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
                  <h3>Изображение:</h3>
                  <div className="image-options">
                    <div className="image-url-input-container">
                      <input 
                        type="text"
                        className="image-url-input"
                        value={editedImageUrl}
                        onChange={(e) => setEditedImageUrl(e.target.value)}
                        placeholder="URL изображения"
                      />
                    </div>
                    <div className="image-upload-container">
                      <p>или</p>
                      <ImageUploader onImageUploaded={(url) => setEditedImageUrl(url)} />
                    </div>
                  </div>
                  
                  {editedImageUrl && (
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
                  )}
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
