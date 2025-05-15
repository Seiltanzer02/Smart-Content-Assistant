import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import axios from 'axios';
import './App.css';
import { TelegramAuth } from './components/TelegramAuth';
import { v4 as uuidv4 } from 'uuid';
import { Toaster, toast } from 'react-hot-toast';
import { ClipLoader } from 'react-spinners';
import SubscriptionWidget from './components/SubscriptionWidget';
import DirectPremiumStatus from './components/DirectPremiumStatus'; // <-- Импортируем новый компонент
import ProgressBar from './components/ProgressBar';

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

// Функция для форматирования даты сброса лимита в человекочитаемый вид
function formatResetAtDate(isoString: string | null | undefined): string {
  if (!isoString) return '';
  try {
    const date = new Date(isoString);
    // Формат: 11.05.2025 18:15 МСК
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${day}.${month}.${year} ${hours}:${minutes} МСК`;
  } catch {
    return isoString;
  }
}

// Модифицированный ErrorMessage для форматирования reset_at
const ErrorMessage = ({ message, onClose }: { message: string | null, onClose: () => void }) => {
  // Заменяем reset_at в тексте на человекочитаемый вид
  let formatted = message;
  if (message && message.includes('reset_at')) {
    formatted = message.replace(/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+\d{2}:\d{2}))/g, (match) => formatResetAtDate(match));
  }
  // Также обрабатываем стандартные тексты лимитов
  if (message && message.match(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)) {
    formatted = message.replace(/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+\d{2}:\d{2})?)/g, (match) => formatResetAtDate(match));
  }
  return (
    <div className="error-message">
      <p>{formatted}</p>
      <button className="action-button small" onClick={onClose}>Закрыть</button>
    </div>
  );
};

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
    Telegram?: any; // Simpler, should resolve linter
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
  onEditPost
}: { 
  day: CalendarDay; 
  onEditPost: (post: SavedPost) => void;
}) => {
  const { date, posts, isCurrentMonth, isToday } = day;
  const dayNumber = date.getDate();
  const cellClass = `calendar-day ${isCurrentMonth ? '' : 'other-month'} ${isToday ? 'today' : ''}`;
  return (
    <div className={cellClass}>
      <div className="day-number">{dayNumber}</div>
      {posts.length > 0 && (
        <div className="day-posts">
          {posts.map((post) => (
            <div key={post.id} className="post-item">
              <div className="post-actions">
                <button 
                  className="action-button edit-button" 
                  onClick={() => onEditPost(post)}
                  title="Редактировать"
                >
                  <span>📝</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// === ДОБАВЛЯЕМ ИНТЕРФЕЙСЫ ДЛЯ НАСТРОЕК ПОЛЬЗОВАТЕЛЯ ===
interface ApiUserSettings {
  channelName: string | null;
  selectedChannels: string[];
  allChannels: string[];
  // Можно добавить id, user_id, created_at, updated_at если они нужны на фронте
}

interface UserSettingsPayload {
  channelName?: string | null;
  selectedChannels?: string[];
  allChannels?: string[];
}
// === КОНЕЦ ИНТЕРФЕЙСОВ ===

// === ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ФОРМАТА КАНАЛА ===
const normalizeChannelName = (name: string) => name.replace(/^@/, '').toLowerCase();
// === КОНЕЦ ФУНКЦИИ ===

// Код, который вызывал ошибки Cannot find name, перемещен внутрь функции App

// --- ДОБАВЛЯЮ: Модалка для подписки ---
const ChannelSubscriptionModal = ({ open, onCheck, channelUrl }: { open: boolean, onCheck: () => void, channelUrl: string }) => {
  console.log('Рендер ChannelSubscriptionModal, состояние open:', open);
  if (!open) return null;
  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,0,0,0.85)', zIndex: 2000,
      display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', color: '#fff',
    }}>
      <div style={{ background: '#222', padding: 32, borderRadius: 16, maxWidth: 400, textAlign: 'center', boxShadow: '0 2px 16px #0008' }}>
        <h2 style={{ marginBottom: 16 }}>Подпишитесь на наш канал</h2>
        <p style={{ marginBottom: 24 }}>
          Чтобы пользоваться приложением, подпишитесь на наш Telegram-канал.<br />
          <a href={channelUrl} target="_blank" rel="noopener noreferrer" style={{ color: '#ffd600', fontWeight: 600, fontSize: 18, textDecoration: 'underline' }}>
            Перейти в канал
          </a>
        </p>
        <button className="action-button" onClick={onCheck} style={{ fontSize: 18, padding: '10px 28px', marginBottom: 8 }}>
          Проверить подписку
        </button>
        <p style={{ fontSize: 13, color: '#bbb', marginTop: 12 }}>После подписки вернитесь и нажмите кнопку</p>
      </div>
    </div>
  );
};

// --- ДОБАВЛЯЮ: Базовая функция для очистки текста поста (замена для cleanPostText) ---
const cleanPostText = (text: string): string => {
  if (!text) return '';
  // Удаляем специальные символы и лишние пробелы
  return text.replace(/\s+/g, ' ').trim();
};

// Глобальное объявление для process.env (CRA)
declare var process: {
  env: {
    [key: string]: string | undefined;
    REACT_APP_TARGET_CHANNEL_USERNAME?: string;
  };
};

function App() {
  console.log('Рендер приложения App');
  
  // === ВСЕ useState и другие хуки объявляются ЗДЕСЬ, ВНУТРИ App ===
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true); // Предполагается, что loading есть
  const [userId, setUserId] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<ViewType>('analyze');
  const [channelName, setChannelName] = useState<string>('');
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [allChannels, setAllChannels] = useState<string[]>([]);
  const [initialSettingsLoaded, setInitialSettingsLoaded] = useState(false);
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
  const [savedPosts, setSavedPosts] = useState<SavedPost[]>([]);
  const [loadingSavedPosts, setLoadingSavedPosts] = useState(false);
  const [calendarDays, setCalendarDays] = useState<CalendarDay[]>([]);
  const [isSavingPost, setIsSavingPost] = useState(false);
  const [currentPostId, setCurrentPostId] = useState<string | null>(null);
  const [currentPostDate, setCurrentPostDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [currentPostTopic, setCurrentPostTopic] = useState('');
  const [currentPostFormat, setCurrentPostFormat] = useState('');
  const [currentPostText, setCurrentPostText] = useState('');
  const [showSubscription, setShowSubscription] = useState<boolean>(false);
  const [currentMonth, setCurrentMonth] = useState<Date>(new Date());
  const [channelInput, setChannelInput] = useState<string>('');
  const [userSettings, setUserSettings] = useState<ApiUserSettings | null>(null);
  const [progress, setProgress] = useState(0);
  const [analyzeLimitExceeded, setAnalyzeLimitExceeded] = useState(false);
  const [ideasLimitExceeded, setIdeasLimitExceeded] = useState(false);
  const [postLimitExceeded, setPostLimitExceeded] = useState(false);
  // === ДОБАВЛЯЮ: Состояние для модального окна предпросмотра ===
  const [isImageModalOpen, setIsImageModalOpen] = useState(false);
  // Добавляю состояние для хранения времени сброса лимита
  const [ideasLimitResetTime, setIdeasLimitResetTime] = useState<string | null>(null);
  const [subscriptionModalOpen, setSubscriptionModalOpen] = useState(false);
  const [checkingSubscription, setCheckingSubscription] = useState(false);
  const [channelUrl, setChannelUrl] = useState('');
  
  // === ДОБАВЛЯЮ: Массивы забавных сообщений для прогресс-баров ===
  const postDetailsMessages = [
    "Завариваем кофе для музы... Обычно это занимает некоторое время. ☕",
    "Наши нейроны шевелятся быстрее, чем вы думаете! (но не всегда) 😉",
    "Почти готово! Если 'почти' для вас — это как 'скоро' у разработчиков. 😅",
    "Идет сложный процесс превращения байтов в буквы... и обратно. 🤖",
    "Согласовываем текст с главным редактором — котиком. Он очень строг. 😼",
    "Так-так-так... что бы такого остроумного написать?.. 🤔",
    "Наши алгоритмы сейчас проходят тест Тьюринга... на выдержку. 🧘"
  ];
  
  const ideasGenerationMessages = [
    "Перебираем триллионы идей... Осталось всего пара миллиардов. 🤯",
    "Штурмуем мозговой центр! Иногда там бывает ветрено. 💨",
    "Ловим вдохновение сачком... Оно такое неуловимое! 🦋",
    "Ищем нестандартные подходы... Иногда находим носки под диваном. 🤷‍♂️",
    "Генератор идей заряжается... Пожалуйста, не отключайте от розетки! 🔌",
    "Анализируем тренды, мемы и фазы Луны... для полной картины. 🌕",
    "Разбудили креативного директора. Он просил передать, что 'еще 5 минуточек'. 😴"
  ];
  
  const [currentPostDetailsMessage, setCurrentPostDetailsMessage] = useState(postDetailsMessages[0]);
  const [currentIdeasMessage, setCurrentIdeasMessage] = useState(ideasGenerationMessages[0]);
  
  // === ДОБАВЛЯЮ: Функция для добавления канала в allChannels ===
  const addChannelToAllChannels = (channel: string) => {
    const normalized = normalizeChannelName(channel);
    if (!normalized) return;
    setAllChannels(prev => {
      // Берём актуальный массив, добавляем новый канал, если его нет
      const updated = prev.includes(normalized) ? prev : [...prev, normalized];
      // Сохраняем весь массив, а не только новый канал
      saveUserSettings({ allChannels: updated });
      return updated;
    });
  };
  // === ДОБАВЛЯЮ: Кастомный выпадающий список каналов ===
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const handleRemoveChannel = (channel: string) => {
    setAllChannels(prev => {
      const updated = prev.filter(c => c !== channel);
      // Сохраняем весь массив, а не только изменённый канал
      saveUserSettings({ allChannels: updated });
      if (channelName === channel) setChannelName('');
      return updated;
    });
  };
  // Функция для отправки изображения в чат через backend
  const handleSendImageToChat = async () => {
    if (!selectedImage || !userId) return;
    try {
      const response = await axios.post('/api/send-image-to-chat', {
        imageUrl: selectedImage.url,
        alt: selectedImage.alt || '',
      }, {
        headers: { 'x-telegram-user-id': userId }
      });
      if (response.data && response.data.success) {
        toast.success('Изображение отправлено вам в чат!');
      } else {
        toast.error('Не удалось отправить изображение в чат.');
      }
    } catch (err) {
      toast.error('Не удалось отправить изображение в чат.');
    }
  };
  // === ДОБАВЛЕНО: ФУНКЦИИ ДЛЯ РАБОТЫ С API НАСТРОЕК ===
  const fetchUserSettings = async (): Promise<ApiUserSettings | null> => {
    if (!userId) return null;
    try {
      const response = await axios.get<ApiUserSettings>(`${API_BASE_URL}/api/user/settings`);
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        console.log('User settings not found (404), returning null.');
        return null; // Настройки еще не созданы для этого пользователя
      }
      console.error('Failed to fetch user settings:', error);
      throw error; // Перебрасываем ошибку для обработки выше
    }
  };

  const saveUserSettings = async (settings: UserSettingsPayload) => {
    if (!userId) return;
    try {
      await axios.put(`${API_BASE_URL}/api/user/settings`, settings); // PUT вместо PATCH
    } catch (error) {
      console.error('Failed to save user settings:', error);
      toast.error('Ошибка сохранения настроек на сервере.');
    }
  };
  // === КОНЕЦ ФУНКЦИЙ API ===

  // === ОБЪЕДИНЕНИЕ КАНАЛОВ ИЗ ПОСТОВ И НАСТРОЕК ===
  // useEffect(() => {
  //   if (savedPosts.length > 0 || (userSettings && userSettings.allChannels)) {
  //     // Получаем каналы из текущих постов
  //     const channelsFromPosts = savedPosts.map(post => normalizeChannelName(post.channel_name || '')).filter(Boolean);
  //     
  //     // Получаем каналы из настроек пользователя
  //     const channelsFromSettings = (userSettings?.allChannels || []).map(normalizeChannelName).filter(Boolean);
  //     
  //     // Объединяем каналы из текущих постов и из настроек
  //     const uniqueChannels = [...new Set([...channelsFromPosts, ...channelsFromSettings])];
  //     
  //     // ВАЖНО: Сохраняем предыдущие каналы, чтобы они не исчезали при фильтрации
  //     setAllChannels(prevChannels => {
  //       // Объединяем с предыдущими каналами, чтобы не терять их при фильтрации
  //       const mergedChannels = [...new Set([...prevChannels, ...uniqueChannels])];
  //       
  //       // Сохраняем на сервере только если список действительно изменился
  //       if (userSettings && JSON.stringify(mergedChannels) !== JSON.stringify(userSettings.allChannels)) {
  //         saveUserSettings({ allChannels: mergedChannels });
  //       }
  //       
  //       return mergedChannels;
  //     });
  //   }
  // }, [savedPosts, userSettings]);

  // --- ИЗМЕНЕНИЕ: Загрузка состояния ИЗ API ПОСЛЕ аутентификации ---
  useEffect(() => {
    const loadData = async () => {
      if (isAuthenticated && userId) {
        // === ДОБАВЛЕНО: инициализация лимитов пользователя ===
        try {
          await axios.post('/api/user/init-usage', {}, {
            headers: { 'X-Telegram-User-Id': userId }
          });
        } catch (e) {
          console.error('Ошибка инициализации лимитов пользователя:', e);
          toast.error('Ошибка инициализации лимитов пользователя.');
        }
        // === КОНЕЦ ДОБАВЛЕНИЯ ===
        setLoading(true); // Используем общий loading или можно ввести loadingSettings
        setInitialSettingsLoaded(false);
        try {
          const settings = await fetchUserSettings();
          if (settings) {
            setChannelName(settings.channelName || '');
            setSelectedChannels(settings.selectedChannels || []);
            setAllChannels(settings.allChannels || []);
          } else {
            // Если настроек нет, устанавливаем значения по умолчанию (пустые)
            setChannelName('');
            setSelectedChannels([]);
            setAllChannels([]);
          }
        } catch (error) {
          console.error('Error fetching initial user settings:', error);
          toast.error('Не удалось загрузить настройки пользователя.');
          // В случае ошибки, оставляем значения по умолчанию (пустые)
          setChannelName('');
          setSelectedChannels([]);
          setAllChannels([]);
        }
        setInitialSettingsLoaded(true);

        // Загружаем остальные данные, которые зависят от userId
        // (например, fetchSavedPosts, fetchSavedIdeas, и т.д.)
        // Убедитесь, что эти вызовы не конфликтуют с channelName, selectedChannels, allChannels
        // которые только что были установлены.
        fetchSavedPosts(); // Эта функция может использовать allChannels, поэтому порядок важен
        
        // Загрузка сохраненного анализа для ТЕКУЩЕГО выбранного канала (если он есть)
        // Этот useEffect должен зависеть от channelName и initialSettingsLoaded
        // if (channelName) { // channelName будет установлен выше, если есть в localStorage
        //   fetchSavedAnalysis(channelName);
        // }
      } else {
        // Если не аутентифицирован, сбрасываем состояние настроек
        setChannelName('');
        setSelectedChannels([]);
        setAllChannels([]);
        setInitialSettingsLoaded(false);
      }
      setLoading(false); // Общий loading завершен
    };

    loadData();

    // Убираем прямую загрузку channelName, selectedChannels, allChannels из localStorage
    // Эта логика теперь обрабатывается через fetchUserSettings

  }, [isAuthenticated, userId]); // Запускаем при изменении статуса аутентификации и userId

  // --- ИЗМЕНЕНИЕ: Удаляем useEffect, который сохранял channelName в localStorage ---
  // useEffect(() => {
  //   const key = getUserSpecificKey('channelName', userId);
  //   if (key && channelName) {
  //     localStorage.setItem(key, channelName);
  //   }
  // }, [channelName, userId]); 

  // === ДОБАВЛЕНО: useEffect для сохранения настроек на сервере ===
  const settingsToSave = useMemo(() => ({
    channelName,
    selectedChannels,
    allChannels,
  }), [channelName, selectedChannels, allChannels]);

  useEffect(() => {
    if (isAuthenticated && userId && initialSettingsLoaded) {
      // Дебаунсинг для предотвращения слишком частых запросов
      const handler = setTimeout(() => {
        saveUserSettings(settingsToSave);
      }, 1500); // Задержка в 1.5 секунды

      return () => {
        clearTimeout(handler);
      };
    }
  }, [isAuthenticated, userId, initialSettingsLoaded, settingsToSave]);
  // === КОНЕЦ useEffect для сохранения настроек ===

  // ... (существующий useEffect для загрузки списка всех каналов при авторизации, если он еще нужен)
  // useEffect(() => {
  //   if (isAuthenticated && userId && initialSettingsLoaded) { // Добавлено initialSettingsLoaded
  //      if (allChannels.length === 0) {
  //        console.log("Список каналов пуст, пытаемся обновить из постов...");
  //        updateChannelsFromPosts(savedPosts); 
  //      }
  //   }
  // }, [isAuthenticated, userId, initialSettingsLoaded, allChannels.length, savedPosts]);
  // Этот useEffect может быть изменен или удален, т.к. allChannels теперь синхронизируется

  // ... (существующий useEffect для fetchSavedAnalysis)
  useEffect(() => {
    if (isAuthenticated && userId && initialSettingsLoaded && channelName) {
        fetchSavedAnalysis(channelName);
    }
  }, [isAuthenticated, userId, initialSettingsLoaded, channelName]); // Добавлен initialSettingsLoaded
  
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
      // --- ИЗМЕНЕНО: Не очищаем полностью посты, чтобы не терять список каналов ---
      // setAnalysisResult(null); // Очищаем предыдущий анализ
      // setSuggestedIdeas([]);  // Очищаем предыдущие идеи
      // setSavedPosts([]); // Очищаем предыдущие посты - УБРАНО, чтобы сохранить каналы
      // setSelectedIdea(null); // Сбрасываем выбранную идею
      // --- КОНЕЦ ИЗМЕНЕНИЯ ---

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
      // --- ИЗМЕНЕНО: Не очищаем посты, чтобы сохранить список каналов ---
      // setSavedPosts([]); 
      // --- КОНЕЦ ИЗМЕНЕНИЯ ---
      setSelectedIdea(null); 
      // Загружаем все посты пользователя
      fetchSavedPosts(); 
    }
  }, [isAuthenticated, channelName]); // Зависимости остаются прежними
  // --- КОНЕЦ ИЗМЕНЕНИЯ --- 
  
  // Функция для загрузки сохраненных постов
  const fetchSavedPosts = async () => {
    setLoadingSavedPosts(true);
    try {
      let url = `${API_BASE_URL}/posts`;
      const params: any = {};
      if (channelName) {
        params.channel_name = normalizeChannelName(channelName);
      }
      const response = await axios.get(url, {
        params,
          headers: { 'x-telegram-user-id': userId } 
        });
      setSavedPosts(response.data || []);
    } catch (err) {
      // обработка ошибок
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
        // --- УДАЛЯЕМ: Сохранение в localStorage ---
        // const key = getUserSpecificKey('allChannels', userId);
        // if (key) {
        //   localStorage.setItem(key, JSON.stringify(updatedChannels));
        // }
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
          url: img.regular_url || img.urls?.regular || img.url || img.urls?.raw || img.preview_url || img.urls?.small || img.urls?.thumb || '',
          alt: img.alt_description || img.description || 'Изображение для поста',
          author: img.user?.name || img.author_name || '',
          author_url: img.user?.links?.html || img.author_url || '',
          id: img.id || `unsplash-${uuidv4()}`,
          preview_url: img.preview_url || img.urls?.small || img.urls?.thumb || img.urls?.regular || img.regular_url || img.url || img.urls?.raw || '',
          source: img.source || 'unsplash'
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
    setPostLimitExceeded(false);

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
      if (err.response && err.response.status === 403 && err.response.data?.error?.includes('лимит генерации постов')) {
        setPostLimitExceeded(true);
        toast.error(err.response.data.error);
      } else {
        const errorMsg = err.response?.data?.detail || err.message || (currentPostId ? 'Ошибка при обновлении поста' : 'Ошибка при сохранении поста');
        setError(errorMsg);
        console.error(currentPostId ? 'Ошибка при обновлении поста:' : 'Ошибка при сохранении поста:', err);
      }
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
      if (err.response?.data?.detail?.limit_reached) {
        // Новый формат с детальной информацией об ошибке
        setIdeasLimitExceeded(true);
        setIdeasLimitResetTime(err.response.data.detail.reset_at);
        toast.error(err.response.data.detail.message || 'Достигнут лимит сохранения идей');
      } else {
      setError(err.response?.data?.detail || err.message || 'Ошибка при сохранении идей');
      toast.error('Ошибка при сохранении идей'); // Показываем ошибку пользователю
      }
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
    console.log('handleAuthSuccess вызван с userId:', authUserId);
    if (!authUserId || authUserId === '123456789') {
      console.error('Некорректный ID пользователя:', authUserId);
      setError('Ошибка авторизации: некорректный ID пользователя');
      setIsAuthenticated(false);
      setUserId(null);
      return;
    }
    console.log('Авторизация успешна, устанавливаем userId:', authUserId);
    setUserId(authUserId);
    // Устанавливаем глобальный заголовок для всех запросов axios
    axios.defaults.headers.common['X-Telegram-User-Id'] = authUserId;
    setIsAuthenticated(true);
    
    // Инициализируем лимиты пользователя сразу после авторизации
    axios.post('/api/user/init-usage', {}, {
      headers: { 'x-telegram-user-id': authUserId }
    }).then(() => {
      console.log('Лимиты пользователя инициализированы при входе в приложение');
    }).catch(initError => {
      console.warn('Не удалось инициализировать лимиты пользователя при входе:', initError);
    });
    
    // setLoading(false); // Управление loading теперь в useEffect [isAuthenticated, userId]
  };

  // Функция для анализа канала теперь принимает имя канала как аргумент
  const analyzeChannel = async (inputChannel?: string) => {
    const channelToAnalyze = inputChannel !== undefined ? normalizeChannelName(inputChannel) : normalizeChannelName(channelInput);
    console.log("Клик по кнопке Анализировать", channelToAnalyze);
    if (!userId) {
      console.error("userId не определён!");
      setError("Ошибка авторизации: не найден userId");
      return;
    }
    if (!channelToAnalyze) {
      console.error("channelName не заполнен!");
      setError("Введите имя канала");
      return;
    }
    setChannelName(channelToAnalyze); // Обновляем выбранный канал
    addChannelToAllChannels(channelToAnalyze);
    setIsAnalyzing(true);
    setAnalysisLoadedFromDB(false);
    setError(null);
    setSuccess(null);
    setAnalysisResult(null);
    setAnalyzeLimitExceeded(false);
    try {
      // Сначала вызовем эндпоинт /api/user/init-usage для инициализации лимитов
      try {
        console.log("Инициализация лимитов пользователя...");
        const initResponse = await axios.post('/api/user/init-usage', {}, {
          headers: { 'x-telegram-user-id': userId }
        });
        console.log('Лимиты пользователя инициализированы успешно:', initResponse.data);
      } catch (initError) {
        console.warn('Не удалось инициализировать лимиты пользователя:', initError);
        // Продолжаем выполнение, даже если инициализация не удалась
      }
      // Теперь выполняем анализ канала
      console.log(`Отправляем запрос на анализ канала: ${channelToAnalyze}, userId: ${userId}`);
      const response = await axios.post('/analyze', { username: channelToAnalyze }, {
        headers: { 'x-telegram-user-id': userId }
      });
      console.log('Получен ответ от сервера по анализу:', response.data);
      
      // Проверяем, есть ли ошибка в ответе
      if (response.data.error) {
        setError(response.data.error);
        return;
      }
      
      if (!response.data || !response.data.themes || !response.data.styles) {
        console.error('Некорректный формат данных от сервера:', response.data);
        throw new Error('Сервер вернул некорректные данные анализа');
      }
      setAnalysisResult(response.data);
      setSuccess('Анализ успешно завершен');
    } catch (err) {
      console.error('Ошибка при анализе:', err);
      // Обрабатываем ошибки с разными форматами
      if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else if (err.response?.status === 403) {
        setAnalyzeLimitExceeded(true);
        setError("Достигнут лимит анализа каналов для бесплатной подписки");
      } else {
        setError(err.message || 'Ошибка при анализе канала');
      }
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Функция для генерации идей
  const generateIdeas = async () => {
    setIdeasLimitExceeded(false);
    setIdeasLimitResetTime(null);
    try {
      if (suggestedIdeas.length > 0) {
        const confirmed = confirm("У вас уже есть сгенерированные идеи. Сгенерировать новые? Старые идеи будут удалены.");
        if (!confirmed) {
          return;
        }
      }
      setIsGeneratingIdeas(true);
      setError("");
      setSuggestedIdeas([]);
      if (!analysisResult) {
        setError("Пожалуйста, сначала проведите анализ канала");
        setIsGeneratingIdeas(false);
        return;
      }
      
      // Сначала вызовем эндпоинт /api/user/init-usage для инициализации лимитов
      try {
        await axios.post('/api/user/init-usage', {}, {
          headers: { 'x-telegram-user-id': userId }
        });
        console.log('Лимиты пользователя инициализированы успешно перед генерацией идей');
      } catch (initError) {
        console.warn('Не удалось инициализировать лимиты пользователя перед генерацией идей:', initError);
        // Продолжаем выполнение, даже если инициализация не удалась
      }
      
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
        const formattedIdeas = response.data.plan.map((idea, index) => ({
          id: `idea-${Date.now()}-${index}`,
          topic_idea: idea.topic_idea || idea.title,
          format_style: idea.format_style || idea.format,
          day: idea.day,
          channel_name: channelName,
          isNew: true,
        }));
        setSuggestedIdeas(formattedIdeas);
        setSuccess('Идеи успешно сгенерированы');
        saveIdeasToDatabase(formattedIdeas);
      } else if (response.data && response.data.limit_reached) {
        // Обработка случая, когда достигнут лимит
        setIdeasLimitExceeded(true);
        setIdeasLimitResetTime(response.data.reset_at);
        toast.error(response.data.message || 'Достигнут лимит генерации идей');
      }
    } catch (err) {
      console.error('Ошибка при генерации идей:', err);
      if (err.response?.data?.detail?.limit_reached) {
        // Новый формат с детальной информацией об ошибке
        setIdeasLimitExceeded(true);
        setIdeasLimitResetTime(err.response.data.detail.reset_at);
        toast.error(err.response.data.detail.message || 'Достигнут лимит генерации идей');
      } else if (err.response && err.response.status === 403) {
        // Обрабатываем старый формат ошибки
        setIdeasLimitExceeded(true);
        toast.error(err.response.data.detail || err.response.data.error || 'Достигнут лимит генерации идей');
      } else {
        setError(err.response?.data?.detail || err.response?.data?.error || err.message || 'Ошибка при генерации идей');
      }
    } finally {
      setIsGeneratingIdeas(false);
      setCurrentView('suggestions');
      addChannelToAllChannels(channelName);
    }
  };

  // Функция для загрузки сохраненных идей
  const fetchSavedIdeas = async () => {
    setLoading(true);
    try {
      let url = `${API_BASE_URL}/ideas`;
      const params: any = {};
      if (channelName) {
        params.channel_name = channelName;
      }
      const response = await axios.get(url, {
        params,
        headers: { 'x-telegram-user-id': userId }
      });
      setSuggestedIdeas(response.data.ideas || []);
    } catch (err) {
      // обработка ошибок
    } finally {
      setLoading(false);
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

    // Отображаем состояние до изменения
    console.log('Текущее выбранное изображение:', selectedImage);

    // Сравниваем URL для определения, выбрано ли уже это изображение
    const isCurrentlySelected = selectedImage && selectedImage.url === imageToSelect.url;
    console.log('Изображение уже выбрано?', isCurrentlySelected);

    if (isCurrentlySelected) {
      // Если изображение уже выбрано, снимаем выбор
      console.log('Снимаем выбор с изображения');
      setSelectedImage(null);
    } else {
      // Иначе, выбираем новое изображение
      console.log('Выбираем новое изображение');
      setSelectedImage(imageToSelect);
    }

    // Для наглядности покажем сообщение пользователю
    if (!isCurrentlySelected) {
      toast.success("Изображение выбрано"); // Используем toast для более заметного уведомления
    } else {
      // toast.info("Выбор изображения отменен"); // Можно добавить и для отмены
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
        // setSuccess(null); // Убрано, т.к. toast используется для успеха выбора картинки
        setSuggestedImages([]); // Clear any potentially stale images
        setSelectedImage(null); // Ensure no image is pre-selected

        try {
          const response = await axios.post(`${API_BASE_URL}/generate-post-details`, {
            topic_idea: selectedIdea.topic_idea,
          format_style: selectedIdea.format_style,
          post_samples: analysisResult?.analyzed_posts_sample || [] 
        },
        {
          headers: {
            'x-telegram-user-id': userId || 'unknown' 
          }
        }
        );
        setCurrentPostText(cleanPostText(response.data.generated_text));
        
        // Улучшенное формирование объектов PostImage из found_images
        if (response.data.found_images && Array.isArray(response.data.found_images)) {
          const formattedSuggestedImages = response.data.found_images.map((img: any) => ({
            id: img.id || `unsplash-${uuidv4()}`, // Используем ID от Unsplash или генерируем, если нет
            url: img.regular_url || img.urls?.regular || img.url || img.urls?.raw || img.preview_url || img.urls?.small || img.urls?.thumb || '', // URL для загрузки (предпочтительно качественный)
            preview_url: img.preview_url || img.urls?.small || img.urls?.thumb || img.urls?.regular || img.regular_url || img.url || img.urls?.raw || '', // URL для превью
            alt: img.alt_description || img.description || 'Предложенное изображение',
            author: img.user?.name || img.author_name || '',
            author_url: img.user?.links?.html || img.author_url || '',
            source: img.source || 'unsplash' // Четко указываем источник
          }));
          setSuggestedImages(formattedSuggestedImages);
        } else {
          setSuggestedImages([]);
        }
        toast.success("Детали поста успешно сгенерированы"); // Используем toast

    } catch (err: any) {
        setError(err.response?.data?.detail || err.message || 'Ошибка при генерации деталей поста');
        console.error('Ошибка при генерации деталей поста:', err);
    } finally {
          setIsGeneratingPostDetails(false);
        }
      }
  }, [currentView, currentPostId, selectedIdea, userId, API_BASE_URL, analysisResult, setIsGeneratingPostDetails, setError, setSuggestedImages, setSelectedImage, setCurrentPostText]);

  // Вызываем useCallback-функцию внутри useEffect
  useEffect(() => {
    fetchDetailsCallback();
    // Зависимость useEffect теперь - это сама useCallback-функция
  }, [fetchDetailsCallback]);
  // --- КОНЕЦ ИЗМЕНЕНИЯ ---

  // Функция для загрузки сохраненного анализа канала
  const fetchSavedAnalysis = async (channel: string) => {
    setLoadingAnalysis(true);
    setAnalysisResult(null);
    setAnalysisLoadedFromDB(false);
    try {
      let url = `${API_BASE_URL}/channel-analysis`;
      const params: any = { channel_name: channel };
      const response = await axios.get(url, {
        params,
        headers: { 'x-telegram-user-id': userId }
      });
      if (response.data && !response.data.error) {
        setAnalysisResult(response.data); 
        setSuccess(`Загружен сохраненный анализ для @${channel}`);
        setAnalysisLoadedFromDB(true);
      } else {
        setAnalysisResult(null); 
      }
    } catch (err: any) {
      if (err.response && err.response.status === 404) {
         setAnalysisResult(null);
      } else {
        setError(err.response?.data?.detail || err.message || 'Ошибка при загрузке сохраненного анализа');
        setAnalysisResult(null);
      }
    } finally {
      setLoadingAnalysis(false);
    }
  };

  // === ИСПРАВЛЕНИЕ: Формирование allChannels из постов ===
  // useEffect(() => {
  //   if (savedPosts.length > 0) {
  //     const uniqueChannels = [
  //       ...new Set(savedPosts.map(post => post.channel_name).filter((c): c is string => typeof c === 'string' && c.length > 0))
  //     ];
  //     setAllChannels(uniqueChannels);
  //     // Можно также обновить настройки пользователя на сервере, если нужно
  //     // saveUserSettings({ allChannels: uniqueChannels });
  //   }
  // }, [savedPosts]);
  // ... существующий код ...

  useEffect(() => {
    let interval: number | null = null;
    if (isAnalyzing || isGeneratingPostDetails) {
      setProgress(0);
      interval = window.setInterval(() => {
        setProgress(prev => (prev < 98 ? prev + Math.random() * 0.6 : prev)); // Уменьшаем скорость в 2.5 раза
      }, 100);
    } else if (isGeneratingIdeas) {
      setProgress(0);
      interval = window.setInterval(() => {
        setProgress(prev => (prev < 98 ? prev + Math.random() * 1.25 : prev)); // Уменьшаем скорость в 2 раза
      }, 150); // Настраиваем скорость
    } else if (!isAnalyzing && !isGeneratingPostDetails && !isGeneratingIdeas) {
      setProgress(100);
      setTimeout(() => setProgress(0), 500);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isAnalyzing, isGeneratingPostDetails, isGeneratingIdeas]);

  // === ДОБАВЛЯЮ: Эффект для смены сообщений в прогресс-баре генерации деталей поста ===
  useEffect(() => {
    let messageInterval: number | null = null;
    
    if (isGeneratingPostDetails) {
      // Начинаем с первого сообщения
      setCurrentPostDetailsMessage(postDetailsMessages[0]);
      
      // Настраиваем интервал для смены сообщений
      let messageIndex = 0;
      messageInterval = window.setInterval(() => {
        messageIndex = (messageIndex + 1) % postDetailsMessages.length;
        setCurrentPostDetailsMessage(postDetailsMessages[messageIndex]);
      }, 3500); // Меняем сообщение каждые 3.5 секунды
    }
    
    return () => {
      if (messageInterval) window.clearInterval(messageInterval);
    };
  }, [isGeneratingPostDetails]);
  
  // === ДОБАВЛЯЮ: Эффект для смены сообщений в прогресс-баре генерации идей ===
  useEffect(() => {
    let messageInterval: number | null = null;
    
    if (isGeneratingIdeas) {
      // Начинаем с первого сообщения
      setCurrentIdeasMessage(ideasGenerationMessages[0]);
      
      // Настраиваем интервал для смены сообщений
      let messageIndex = 0;
      messageInterval = window.setInterval(() => {
        messageIndex = (messageIndex + 1) % ideasGenerationMessages.length;
        setCurrentIdeasMessage(ideasGenerationMessages[messageIndex]);
      }, 3500); // Меняем сообщение каждые 3.5 секунды
    }
    
    return () => {
      if (messageInterval) window.clearInterval(messageInterval);
    };
  }, [isGeneratingIdeas]);
  
  // --- Эффект слежения за userId для загрузки пользовательских настроек ---

  // Добавляем CSS для анимации сообщений
  useEffect(() => {
    // Создаем стили для анимации сообщений
    const styleElement = document.createElement('style');
    styleElement.textContent = `
      @keyframes fadeInOut {
        0% { opacity: 0; }
        10% { opacity: 1; }
        90% { opacity: 1; }
        100% { opacity: 0; }
      }
      
      .loading-message {
        animation: fadeInOut 3.5s ease-in-out;
        opacity: 1;
        font-size: 14px;
        margin-top: 10px;
        color: #555;
      }
      
      .subscription-button {
        background-color: #8e44ad !important;
        color: white !important;
        border: none !important;
        transition: background-color 0.3s ease;
      }
      
      .subscription-button:hover {
        background-color: #9b59b6 !important;
      }
      
      .error-message {
        background-color: #fff8f8;
        border: 1px solid #ffebee;
        padding: 15px;
        border-radius: 8px;
        margin: 15px 0;
        color: #d32f2f;
      }
      
      .error-message p {
        margin: 5px 0;
      }
      
      .error-message strong {
        font-weight: 600;
      }
    `;
    
    document.head.appendChild(styleElement);
    
    return () => {
      document.head.removeChild(styleElement);
    };
  }, []);

  // --- Функция для получения userId только для проверки подписки на канал ---
  function getUserIdForChannelSubscription() {
    return window.Telegram?.WebApp?.initDataUnsafe?.user?.id
      ? String(window.Telegram.WebApp.initDataUnsafe.user.id)
      : null;
  }

  // --- Функция для проверки подписки на канал ---
  const handleCheckSubscription = async () => {
    // Используем только userId из Telegram WebApp для проверки подписки на канал
    const channelUserId = getUserIdForChannelSubscription();
    console.log('Вызов handleCheckSubscription, channelUserId:', channelUserId);
    if (!channelUserId) {
      console.error('handleCheckSubscription: userId не определен через Telegram WebApp!');
      toast.error('Не удалось определить ваш Telegram ID. Откройте приложение внутри Telegram.');
      return;
    }
    setCheckingSubscription(true);
    try {
      console.log('Отправка запроса на /api/check-channel-subscription');
      const resp = await axios.get('/api/check-channel-subscription', {
        headers: { 'X-Telegram-User-Id': channelUserId }
      });
      console.log('Ответ от /api/check-channel-subscription:', resp.data);
      if (resp.data && resp.data.subscribed) {
        setSubscriptionModalOpen(false);
        toast.success('Подписка подтверждена!');
      } else {
        if (!channelUrl) {
          const channelUsername = process.env.REACT_APP_TARGET_CHANNEL_USERNAME || 'smart_content_helper';
          console.log('Установка channelUrl для канала:', channelUsername);
          setChannelUrl(`https://t.me/${channelUsername.replace(/^@/, '')}`);
        }
        setSubscriptionModalOpen(true);
        toast.error('Вы ещё не подписаны на канал!');
      }
    } catch (e) {
      console.error('Ошибка при проверке подписки:', e);
      if (!channelUrl) {
        const channelUsername = process.env.REACT_APP_TARGET_CHANNEL_USERNAME || 'smart_content_helper';
        console.log('Установка channelUrl при ошибке для канала:', channelUsername);
        setChannelUrl(`https://t.me/${channelUsername.replace(/^@/, '')}`);
      }
      setSubscriptionModalOpen(true);
      toast.error('Ошибка проверки подписки');
    } finally {
      setCheckingSubscription(false);
    }
  };

  // --- Проверка подписки на канал при запуске ---
  useEffect(() => {
    console.log('useEffect для проверки подписки запущен, isAuthenticated:', isAuthenticated, 'userId:', userId);
    
    const checkSubscription = async () => {
      // Используем только userId из Telegram WebApp для проверки подписки на канал
      const channelUserId = getUserIdForChannelSubscription();
      console.log('Функция checkSubscription запущена, channelUserId:', channelUserId);
      if (!channelUserId || !isAuthenticated) {
        console.log('Выход из checkSubscription: !channelUserId || !isAuthenticated');
        return;
      }
      setCheckingSubscription(true);
      try {
        console.log('Отправка запроса на /api/check-channel-subscription внутри useEffect');
        const resp = await axios.get('/api/check-channel-subscription', {
          headers: { 'X-Telegram-User-Id': channelUserId }
        });
        console.log('Ответ от /api/check-channel-subscription внутри useEffect:', resp.data);
        if (resp.data && resp.data.subscribed) {
          setSubscriptionModalOpen(false);
        } else {
          const channelUsername = process.env.REACT_APP_TARGET_CHANNEL_USERNAME || 'smart_content_helper';
          console.log('Установка channelUrl внутри useEffect для канала:', channelUsername);
          setChannelUrl(`https://t.me/${channelUsername.replace(/^@/, '')}`);
          setSubscriptionModalOpen(true);
        }
      } catch (e) {
        console.error('Ошибка при первоначальной проверке подписки:', e);
        const channelUsername = process.env.REACT_APP_TARGET_CHANNEL_USERNAME || 'smart_content_helper';
        console.log('Установка channelUrl при ошибке внутри useEffect для канала:', channelUsername);
        setChannelUrl(`https://t.me/${channelUsername.replace(/^@/, '')}`);
        setSubscriptionModalOpen(true);
      } finally {
        setCheckingSubscription(false);
      }
    };

    checkSubscription();
    // eslint-disable-next-line
  }, [isAuthenticated]);
  
  // Компонент загрузки
  if (loading) {
    console.log('Рендер: loading === true, показываем индикатор загрузки');
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Загрузка приложения...</p>
      </div>
    );
  }

  // Компонент авторизации
  if (!isAuthenticated) {
    console.log('Рендер: !isAuthenticated === true, показываем форму авторизации');
    return <TelegramAuth onAuthSuccess={handleAuthSuccess} />;
  }

  console.log('Рендер: основной UI приложения, isAuthenticated:', isAuthenticated, 'userId:', userId, 'subscriptionModalOpen:', subscriptionModalOpen);

  // Основной интерфейс
  return (
    <div className="app-container">
      <ChannelSubscriptionModal open={subscriptionModalOpen} onCheck={handleCheckSubscription} channelUrl={channelUrl} />
      {/* Основной контент приложения рендерится только если модальное окно не открыто или если проверка прошла */}
      {!subscriptionModalOpen && (
        <>
          <header className="app-header" style={{ minHeight: '36px', padding: '6px 0', fontSize: '1.1em' }}>
            <h1 style={{ margin: 0, fontSize: '1.2em', fontWeight: 600 }}>Smart Content Assistant</h1>
          </header>
          {/* ... (остальной JSX вашего приложения: навигация, main, footer) ... */}
          <main className="app-main">
            {/* ... ваш контент ... */}
          </main>
      <footer className="app-footer">
        <p>© 2024 Smart Content Assistant</p>
      </footer>
        </>
      )}
      <Toaster position="top-center" reverseOrder={false} />
    </div>
  );
}

export default App;
