import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './App.css';
import TelegramAuth from './components/TelegramAuth';
import { v4 as uuidv4 } from 'uuid';
import { Toaster, toast } from 'react-hot-toast';
import { ClipLoader } from 'react-spinners';
import SubscriptionWidget from './components/SubscriptionWidget';

// Вспомогательная функция для получения user-specific ключа
const getUserSpecificKey = (baseKey: string, userId: string | null): string | null => {
  if (!userId) return null;
  return `${baseKey}_${userId}`;
};

// Компонент для отображения индикатора загрузки
const Loading = ({ message }: { message: string }) => (
  <div className="loading-indicator small">
    <div className="loading-spinner small"></div>
    <p>{message}</p>
  </div>
);

// Компонент для отображения сообщения об ошибке
const ErrorMessage = ({ message, onClose }: { message: string | null, onClose: () => void }) => (
  <div className="error-message">
    <p>{message}</p>
    <button onClick={onClose}>×</button>
  </div>
);

// Компонент для отображения сообщения об успехе
const SuccessMessage = ({ message, onClose }: { message: string | null, onClose: () => void }) => (
  <div className="success-message">
    <p>{message}</p>
    <button onClick={onClose}>×</button>
  </div>
);

// Простой компонент ErrorBoundary для отлова ошибок
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
      return (
        <div className="error-boundary">
          <h2>Что-то пошло не так :(</h2>
          <p>Пожалуйста, попробуйте перезагрузить страницу.</p>
          <button onClick={() => window.location.reload()}>Перезагрузить</button>
        </div>
      );
    }
    return this.props.children;
  }
}

// Добавляем расширение интерфейса Window для Telegram
declare global {
  interface Window {
    Telegram?: {
      WebApp?: any;
    };
  }
}

// Типы для представления разных видов/режимов приложения
type ViewType = 'analyze' | 'suggestions' | 'plan' | 'details' | 'calendar' | 'edit' | 'posts';

// Интерфейс для результатов анализа канала
interface AnalysisResult {
  message?: string;
  themes: string[];
  styles: string[];
  analyzed_posts_sample: string[];
  best_posting_time: string;
  analyzed_posts_count: number;
}

// Интерфейс для идеи поста
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

// Интерфейс для детализированного поста
interface DetailedPost {
  post_text: string;
  images: PostImage[];
}

// Интерфейс для изображения поста
interface PostImage {
  url: string;
  id?: string;
  preview_url?: string;
  alt?: string;
  author?: string;
  author_url?: string;
  source?: string;
}

// Интерфейс для элемента плана публикаций
interface PlanItem {
  day: number;
  topic_idea: string;
  format_style: string;
}

// Интерфейс для сохраненного поста
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
  selected_image_data?: PostImage;
}

// Интерфейс для дня календаря
interface CalendarDay {
  date: Date;
  posts: SavedPost[];
  isCurrentMonth: boolean;
  isToday: boolean;
}

// Компонент для загрузки изображений
const ImageUploader = ({ onImageUploaded, userId }: { onImageUploaded: (imageUrl: string) => void, userId: string | null }) => {
  const [isUploading, setIsUploading] = useState(false);
  
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setIsUploading(true);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      // Добавляем user_id в formData для правильной привязки изображения к пользователю
      if (userId) {
        formData.append('user_id', userId);
      }
      
      const response = await fetch('/upload-image', {
        method: 'POST',
        body: formData,
        headers: {
          'X-Telegram-User-Id': userId || ''
        }
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Ошибка загрузки изображения');
      }
      
      const data = await response.json();
      
      if (data.url) {
        onImageUploaded(data.url);
      } else {
        throw new Error('Не удалось получить URL изображения');
      }
    } catch (error) {
      console.error('Ошибка загрузки:', error);
      toast.error('Не удалось загрузить изображение');
    } finally {
      setIsUploading(false);
    }
  };
  
  return (
    <div className="image-uploader">
      <label className="upload-button" htmlFor="file-upload">
        {isUploading ? 'Загрузка...' : 'Загрузить своё изображение'}
      </label>
      <input 
        id="file-upload" 
        type="file" 
        onChange={handleFileChange} 
        accept="image/*" 
        style={{ display: 'none' }} 
        disabled={isUploading}
      />
      {isUploading && <span className="upload-spinner"></span>}
    </div>
  );
};

// Компонент для галереи изображений поста
const PostImageGallery = ({ 
  postId, 
  onImageSelect 
}: { 
  postId: string; 
  onImageSelect?: (imageUrl: string) => void 
}) => {
  const [images, setImages] = useState<PostImage[]>([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchImages = async () => {
      try {
        const response = await fetch(`/post-images/${postId}`);
        if (response.ok) {
          const data = await response.json();
          setImages(data);
        } else {
          console.error('Ошибка загрузки изображений');
        }
      } catch (error) {
        console.error('Ошибка:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchImages();
  }, [postId]);
  
  // Обработчик выбора изображения
  const handleSelect = (image: any) => {
    if (onImageSelect) {
      onImageSelect(image.url);
    }
  };
  
  if (loading) {
    return <p>Загрузка изображений...</p>;
  }
  
  if (images.length === 0) {
    return <p>Нет доступных изображений</p>;
  }
  
  return (
    <div className="image-gallery">
      {images.map((image, index) => (
        <div key={index} className="image-item" onClick={() => handleSelect(image)}>
          <img src={image.url} alt={image.alt || `Image ${index + 1}`} />
        </div>
      ))}
    </div>
  );
};

// Основной компонент приложения
function App() {
  // Состояния для аутентификации
  const [userId, setUserId] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  // Состояния для UI
  const [currentView, setCurrentView] = useState<ViewType>('analyze');
  const [channelName, setChannelName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showSubscription, setShowSubscription] = useState(false);

  // Календарь и посты
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [calendarDays, setCalendarDays] = useState<CalendarDay[]>([]);
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [savedPosts, setSavedPosts] = useState<SavedPost[]>([]);
  const [loadingSavedPosts, setLoadingSavedPosts] = useState(false);
  
  // Состояния для анализа и идей
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [analysisLoadedFromDB, setAnalysisLoadedFromDB] = useState(false);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [suggestedIdeas, setSuggestedIdeas] = useState<SuggestedIdea[]>([]);
  const [isGeneratingIdeas, setIsGeneratingIdeas] = useState(false);
  
  // Состояния для редактирования поста
  const [currentPostId, setCurrentPostId] = useState<string | null>(null);
  const [currentPostDate, setCurrentPostDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [currentPostTopic, setCurrentPostTopic] = useState('');
  const [currentPostFormat, setCurrentPostFormat] = useState('');
  const [currentPostText, setCurrentPostText] = useState('');
  const [isSavingPost, setIsSavingPost] = useState(false);
  const [isGeneratingPostDetails, setIsGeneratingPostDetails] = useState(false);
  const [suggestedImages, setSuggestedImages] = useState<PostImage[]>([]);
  const [selectedImage, setSelectedImage] = useState<PostImage | null>(null);

  // Для генерации дней календаря
  const generateCalendarDays = () => {
    // Логика генерации дней календаря
    // ...
  };

  // Функции для навигации по календарю
  const goToPrevMonth = () => {
    // ...
  };

  const goToNextMonth = () => {
    // ...
  };

  // Функция для получения сохраненных постов
  const fetchSavedPosts = async () => {
    try {
      setLoadingSavedPosts(true);
      
      // Строим URL на основе выбранных каналов или текущего канала
      let url = '/posts';
      if (selectedChannels.length > 0) {
        // Отфильтрованные посты по выбранным каналам
        const channelsParam = selectedChannels.join(',');
        url += `?channels=${encodeURIComponent(channelsParam)}`;
      } else if (channelName) {
        // Посты только по текущему каналу
        url += `?channel_name=${encodeURIComponent(channelName)}`;
      }
      
      const response = await fetch(url, {
        headers: {
          'X-Telegram-User-Id': userId || ''
        }
      });
      
      if (!response.ok) {
        throw new Error('Не удалось загрузить сохраненные посты');
      }
      
      const posts = await response.json();
      setSavedPosts(posts);
      
      // Сохраняем уникальные имена каналов для возможной фильтрации
      if (posts.length > 0) {
        const uniqueChannels = [...new Set(posts.map(post => post.channel_name).filter(Boolean))];
        // Можно добавить сохранение списка каналов в состояние, если требуется
      }
      
    } catch (error) {
      console.error('Ошибка при загрузке постов:', error);
      setError('Не удалось загрузить сохраненные посты');
    } finally {
      setLoadingSavedPosts(false);
    }
  };

  // Функция фильтрации постов по выбранным каналам
  const filterPostsByChannels = async () => {
    if (selectedChannels.length > 0 || channelName) {
      await fetchSavedPosts();
    } else {
      setError('Пожалуйста, выберите хотя бы один канал для фильтрации');
    }
  };

  // Функция для запуска редактирования поста
  const startEditingPost = (post: SavedPost) => {
    // Устанавливаем данные поста в форму
    setCurrentPostId(post.id);
    setCurrentPostDate(post.target_date.split('T')[0]);
    setCurrentPostTopic(post.topic_idea);
    setCurrentPostFormat(post.format_style);
    setCurrentPostText(post.final_text);
    
    // Если у поста есть выбранное изображение, устанавливаем его
    if (post.selected_image_data) {
      setSelectedImage(post.selected_image_data);
    } else if (post.image_url) {
      // Создаем базовый объект изображения, если есть только URL
      setSelectedImage({
        url: post.image_url,
        alt: 'Изображение поста'
      });
    } else {
      setSelectedImage(null);
    }
    
    // Очищаем предложенные изображения при редактировании
    setSuggestedImages([]);
    
    // Переключаемся на вид редактирования
    setCurrentView('edit');
  };

  // Функция для удаления поста
  const deletePost = async (postId: string) => {
    try {
      const response = await fetch(`/post/${postId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-User-Id': userId || ''
        }
      });
      
      if (!response.ok) {
        throw new Error('Не удалось удалить пост');
      }
      
      // Обновляем список постов, удаляя удаленный пост
      setSavedPosts(prevPosts => prevPosts.filter(post => post.id !== postId));
      setSuccess('Пост успешно удален');
      
      // Если мы находимся в режиме редактирования этого поста, то очищаем состояние
      if (currentPostId === postId) {
        setCurrentPostId(null);
        setCurrentPostDate(new Date().toISOString().split('T')[0]);
        setCurrentPostTopic('');
        setCurrentPostFormat('');
        setCurrentPostText('');
        setSelectedImage(null);
        setSuggestedImages([]);
        setCurrentView('calendar');
      }
    } catch (error) {
      console.error('Ошибка при удалении поста:', error);
      setError('Не удалось удалить пост');
    }
  };

  // Функция для обработки загрузки пользовательского изображения
  const handleCustomImageUpload = (imageUrl: string) => {
    // Создаем новый объект изображения для загруженного изображения
    const customImage: PostImage = {
      url: imageUrl,
      preview_url: imageUrl,
      alt: 'Загруженное изображение',
      author: 'Пользователь (upload)',
      source: 'upload'
    };
    
    // Устанавливаем загруженное изображение как выбранное
    setSelectedImage(customImage);
    
    // Показываем сообщение об успешной загрузке
    setSuccess('Изображение успешно загружено');
  };

  // Функция для управления изображениями
  const handleImageSelection = (image: PostImage | undefined) => {
    if (image) {
      setSelectedImage(image);
    } else {
      setSelectedImage(null);
    }
  };

  // Функция для генерации деталей поста
  const regeneratePostDetails = async () => {
    if (!channelName || !currentPostTopic || !currentPostFormat) {
      setError('Пожалуйста, укажите канал, тему и формат поста');
      return;
    }
    
    try {
      setIsGeneratingPostDetails(true);
      
      const response = await fetch('/generate-post-details', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-User-Id': userId || ''
        },
        body: JSON.stringify({
          channel_name: channelName,
          topic_idea: currentPostTopic,
          format_style: currentPostFormat
        })
      });
      
      if (!response.ok) {
        throw new Error('Не удалось сгенерировать детали поста');
      }
      
      const data = await response.json();
      
      if (data.post_text) {
        setCurrentPostText(data.post_text);
      }
      
      if (data.images && data.images.length > 0) {
        setSuggestedImages(data.images);
      }
      
      setSuccess('Детали поста успешно сгенерированы');
    } catch (error) {
      console.error('Ошибка при генерации деталей поста:', error);
      setError('Не удалось сгенерировать детали поста');
    } finally {
      setIsGeneratingPostDetails(false);
    }
  };
  
  // Функция для сохранения или обновления поста
  const handleSaveOrUpdatePost = async () => {
    if (!channelName || !currentPostDate || !currentPostText) {
      setError('Пожалуйста, заполните все обязательные поля');
      return;
    }
    
    try {
      setIsSavingPost(true);
      
      // Подготавливаем данные поста
      const postData = {
        id: currentPostId || uuidv4(), // Если новый пост, генерируем ID
        user_id: userId,
        channel_name: channelName,
        target_date: currentPostDate,
        topic_idea: currentPostTopic,
        format_style: currentPostFormat,
        final_text: currentPostText,
        selected_image_data: selectedImage || undefined
      };
      
      // Выбираем метод запроса
      const method = currentPostId ? 'PUT' : 'POST';
      const url = currentPostId ? `/post/${currentPostId}` : '/post';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-User-Id': userId || ''
        },
        body: JSON.stringify(postData)
      });
      
      if (!response.ok) {
        throw new Error(`Не удалось ${currentPostId ? 'обновить' : 'сохранить'} пост`);
      }
      
      // Обновляем сохраненные посты
      await fetchSavedPosts();
      
      // Сбрасываем форму редактирования
      setCurrentPostId(null);
      setCurrentPostDate(new Date().toISOString().split('T')[0]);
      setCurrentPostTopic('');
      setCurrentPostFormat('');
      setCurrentPostText('');
      setSelectedImage(null);
      setSuggestedImages([]);
      
      // Переключаемся на вид календаря
      setCurrentView('calendar');
      
      setSuccess(`Пост успешно ${currentPostId ? 'обновлен' : 'сохранен'}`);
    } catch (error) {
      console.error('Ошибка при сохранении поста:', error);
      setError(`Не удалось ${currentPostId ? 'обновить' : 'сохранить'} пост`);
    } finally {
      setIsSavingPost(false);
    }
  };

  // Загрузка данных при инициализации
  useEffect(() => {
    if (isAuthenticated && userId) {
      // Загрузка сохраненных постов при первой аутентификации
      fetchSavedPosts();
      
      // Загрузка сохраненных каналов пользователя из localStorage
      const channelsKey = getUserSpecificKey('selectedChannels', userId);
      if (channelsKey) {
        const savedChannels = localStorage.getItem(channelsKey);
        if (savedChannels) {
          try {
            const parsedChannels = JSON.parse(savedChannels);
            if (Array.isArray(parsedChannels)) {
              setSelectedChannels(parsedChannels);
            }
          } catch (error) {
            console.error('Ошибка при парсинге сохраненных каналов:', error);
          }
        }
      }
      
      // Дополнительно можно загрузить другие настройки пользователя
    }
  }, [isAuthenticated, userId]);

  // Дополнительный useEffect для загрузки данных при переключении на вкладку постов
  useEffect(() => {
    if (currentView === 'posts' && isAuthenticated && userId) {
      fetchSavedPosts();
    }
  }, [currentView]);

  // Обработчик успешной аутентификации
  const handleAuthSuccess = (authUserId: string) => {
    console.log('Авторизация успешна:', authUserId);
    setUserId(authUserId);
    setIsAuthenticated(true);
    
    // Настраиваем axios для всех запросов
    axios.defaults.headers.common['X-Telegram-User-Id'] = authUserId;
    
    // Показываем виджет подписки при первой аутентификации
    setShowSubscription(true);
  };

  // Основной интерфейс после авторизации
  return (
    <SimpleErrorBoundary>
      <div className="app-container">
        <Toaster position="top-right" />
        
        {/* Компонент авторизации */}
        {!isAuthenticated ? (
          <TelegramAuth onAuthSuccess={handleAuthSuccess} />
        ) : (
          <main className="app-main">
            <header className="app-header">
              <div className="app-title">
                <h1>Smart Content Assistant</h1>
                <p>Умный помощник для контент-менеджеров Telegram</p>
              </div>
              
              {/* Информация о подписке */}
              {showSubscription && userId && (
                <SubscriptionWidget userId={userId} />
              )}
              
              <nav className="app-nav">
                <button 
                  className={`nav-button ${currentView === 'analyze' ? 'active' : ''}`}
                  onClick={() => setCurrentView('analyze')}
                >
                  Анализ
                </button>
                <button 
                  className={`nav-button ${currentView === 'suggestions' ? 'active' : ''}`}
                  onClick={() => setCurrentView('suggestions')}
                >
                  Идеи
                </button>
                <button 
                  className={`nav-button ${currentView === 'calendar' ? 'active' : ''}`}
                  onClick={() => setCurrentView('calendar')}
                >
                  Календарь
                </button>
                <button 
                  className={`nav-button ${currentView === 'posts' ? 'active' : ''}`}
                  onClick={() => setCurrentView('posts')}
                >
                  Посты
                </button>
              </nav>
            </header>
            
            {/* Сообщения об ошибках и успехе */}
            {error && <ErrorMessage message={error} onClose={() => setError(null)} />}
            {success && <SuccessMessage message={success} onClose={() => setSuccess(null)} />}
            
            <div className="content-container">
              {/* Селектор канала */}
              <div className="channel-selector">
                <label htmlFor="channelName">Канал:</label>
                <div className="input-group">
                  <span className="input-prefix">@</span>
                  <input 
                    type="text"
                    id="channelName" 
                    placeholder="durov"
                    value={channelName}
                    onChange={(e) => setChannelName(e.target.value.trim())}
                  />
                </div>
              </div>
              
              {/* Индикаторы загрузки */}
              {loadingSavedPosts && <Loading message="Загрузка данных..." />}
              
              {/* Вид "Посты" с таблицей (упрощенная версия для исправления синтаксической ошибки) */}
              {currentView === 'posts' && (
                <div className="view posts-view">
                  <h2>
                    Список сохраненных постов 
                    {selectedChannels.length > 0 
                      ? `(Каналы: ${selectedChannels.join(', ')})` 
                      : channelName 
                        ? `(Канал: @${channelName})` 
                        : '(Все каналы)'}
                  </h2>
                  
                  {/* Фильтр по каналам */}
                  <div className="channels-filter">
                    <h3>Фильтр по каналам:</h3>
                    <div className="channels-actions">
                      <button 
                        className="action-button"
                        onClick={() => {
                          if (channelName && !selectedChannels.includes(channelName)) {
                            const updatedSelected = [...selectedChannels, channelName];
                            setSelectedChannels(updatedSelected);
                            const key = getUserSpecificKey('selectedChannels', userId);
                            if (key) {
                              localStorage.setItem(key, JSON.stringify(updatedSelected));
                            }
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
                              const key = getUserSpecificKey('selectedChannels', userId);
                              if (key) {
                                localStorage.setItem(key, JSON.stringify(updatedSelected));
                              }
                            }}
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                        
                  {/* Таблица постов */}
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
              
              {/* Вид редактирования поста */}
              {(currentView === 'edit' || currentView === 'details') && (
                <div className="view edit-view">
                  <h2>{currentPostId ? 'Редактирование поста' : 'Создание нового поста'}</h2>
                  
                  {/* Индикатор загрузки деталей */}
                  {isGeneratingPostDetails && (
                    <Loading message="Генерация деталей поста..." />
                  )}
                  
                  {/* Основные поля поста */}
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
                        disabled={isSavingPost}
                      />
                    </div>
                    
                    <div className="form-group">
                      <label htmlFor="postFormat">Формат/Стиль:</label>
                      <input 
                        type="text" 
                        id="postFormat"
                        value={currentPostFormat}
                        onChange={(e) => setCurrentPostFormat(e.target.value)}
                        disabled={isSavingPost}
                      />
                    </div>
                  </div>
                  
                  {/* Редактор текста поста */}
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
                    
                    {/* Кнопка генерации текста */}
                    {!currentPostText && (
                      <button 
                        onClick={regeneratePostDetails}
                        className="action-button generate-button"
                        disabled={isGeneratingPostDetails || !currentPostTopic || !currentPostFormat}
                      >
                        {isGeneratingPostDetails ? 'Генерация...' : 'Сгенерировать текст'}
                      </button>
                    )}
                  </div>
                  
                  {/* Секция управления изображениями */}
                  <div className="image-management-section">
                    {/* Предложенные изображения (если есть) */}
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
                    
                    {/* Блок для своего изображения: Загрузчик и Превью */}
                    <div className="custom-image-section">
                      <h4>Свое изображение:</h4>
                      {/* Показываем загрузчик */}
                      <ImageUploader onImageUploaded={handleCustomImageUpload} userId={userId} />
                      
                      {/* Показываем превью ВЫБРАННОГО изображения (любого) и кнопку удаления */}
                      {selectedImage && (
                        <div className="selected-image-preview">
                          <h5>Выбранное изображение:</h5>
                          <div className="preview-container">
                            <img 
                              src={selectedImage.preview_url || selectedImage.url} 
                              alt={selectedImage.alt || 'Выбрано'} 
                            />
                            <button 
                              className="action-button delete-button small remove-image-btn"
                              onClick={() => setSelectedImage(null)}
                              title="Удалить выбранное изображение"
                            >
                              <span>🗑️ Удалить</span>
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* Кнопки действий */}
                  <div className="form-actions">
                    <button 
                      onClick={handleSaveOrUpdatePost} 
                      className="action-button save-button"
                      disabled={isSavingPost || isGeneratingPostDetails || !currentPostText}
                    >
                      {isSavingPost ? 'Сохранение...' : (currentPostId ? 'Обновить пост' : 'Сохранить пост')}
                    </button>
                    
                    {/* Кнопка Отмена */}
                    <button 
                      onClick={() => {
                        setCurrentView('calendar');
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
        )}
        
        <footer className="app-footer">
          <p>© 2024 Smart Content Assistant</p>
        </footer>
      </div>
    </SimpleErrorBoundary>
  );
}

export default App; 
