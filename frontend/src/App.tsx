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
import { fetchWithAuth } from './utils/fetchWithAuth';

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
type ViewType = 'analyze' | 'suggestions' | 'plan' | 'details' | 'calendar' | 'edit' | 'posts' | 'partner';

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

// Удаляем хардкод TELEGRAM_CHANNEL, используем channelUsername из API

async function checkChannelSubscription(userId: string): Promise<{ has_channel_subscription: boolean, error?: string }> {
  // Новый эндпоинт, аналогично премиум
  try {
    const nocache = new Date().getTime();
    const response = await fetch(`/api-v2/channel-subscription/check?user_id=${userId}&nocache=${nocache}`, {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'Accept': 'application/json'
      }
    });
    
    if (!response.ok) {
      console.error(`Ошибка API при проверке подписки: ${response.status} ${response.statusText}`);
      return { has_channel_subscription: false, error: `Ошибка сервера: ${response.status}` };
    }
    
    const contentType = response.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
      console.error(`Неверный Content-Type: ${contentType}`);
      return { has_channel_subscription: false, error: "Сервер вернул неверный формат данных" };
    }
    
    return await response.json();
  } catch (error) {
    console.error("Ошибка при проверке подписки на канал:", error);
    return { has_channel_subscription: false, error: "Ошибка при проверке подписки" };
  }
}

function App() {
  // --- ВСЕ useState ТОЛЬКО ЗДЕСЬ ---
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
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
  const [channelChecked, setChannelChecked] = useState(false);
  const [hasChannelAccess, setHasChannelAccess] = useState(false);
  const [channelCheckError, setChannelCheckError] = useState<string | null>(null);
  const [channelUsername, setChannelUsername] = useState<string>('');
  // --- Состояния для партнёрской программы ---
  // const [partnerLink, setPartnerLink] = useState<string | null>(null);
  // const [partnerLoading, setPartnerLoading] = useState(false);
  // const [partnerError, setPartnerError] = useState<string | null>(null);
  // const fetchPartnerLink = ...
  
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
        imageUrl: selectedImage.url
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
    if (!authUserId || authUserId === '123456789') {
      console.error('Некорректный ID пользователя:', authUserId);
      setError('Ошибка авторизации: некорректный ID пользователя');
      setIsAuthenticated(false);
      setUserId(null);
      return;
    }
    console.log('Авторизация успешна:', authUserId);
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
        setProgress(prev => (prev < 98 ? prev + Math.random() * 0.6 : prev)); // Было *1.5, стало *0.6 (в 2.5 раза медленнее)
      }, 100);
    } else if (isGeneratingIdeas) {
      setProgress(0);
      interval = window.setInterval(() => {
        setProgress(prev => (prev < 98 ? prev + Math.random() * 1.25 : prev)); // Было *2.5, стало *1.25 (в 2 раза медленнее)
      }, 150); // Можно подстроить скорость
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

  // Получаем username канала с backend
  useEffect(() => {
    async function fetchChannelUsername() {
      // --- ДОБАВЛЕНО: Проверка userId ---
      if (!userId) {
        // Можно также сбросить channelUsername, если userId пропал
        // setChannelUsername(''); 
        return;
      }
      // --- КОНЕЦ ДОБАВЛЕНИЯ ---
      try {
        const res = await fetch('/api/user/channel-info'); // Этот эндпоинт все еще нужен
        const data = await res.json();
        if (data.channel_username) setChannelUsername(data.channel_username);
      } catch (e) {
        // fallback не нужен, просто не будет ссылки
        console.error("Ошибка при загрузке channel username:", e);
      }
    }
    fetchChannelUsername();
  }, [userId]); // <--- ИЗМЕНЕНО: Добавлен userId в зависимости

  // Проверка подписки на канал
  const handleCheckChannel = async () => {
    setChannelCheckError(null);
    // --- ИЗМЕНЕНО: Проверка userId в начале ---
    if (!userId) {
      setChannelCheckError("Пользователь не авторизован для проверки подписки.");
      // Не устанавливаем channelChecked в true, так как проверка не состоялась
      return; 
    }
    // --- КОНЕЦ ИЗМЕНЕНИЯ ---

    try { // --- ДОБАВЛЕНО: try-catch для обработки ошибок запроса ---
      const res = await checkChannelSubscription(userId);
      // --- ИЗМЕНЕНО: setChannelChecked(true) после ответа ---
      setChannelChecked(true); 
      setHasChannelAccess(res.has_channel_subscription);
      if (!res.has_channel_subscription) {
        setChannelCheckError(res.error || 'Вы не подписаны на канал. Пожалуйста, подпишитесь и попробуйте снова.');
      }
    } catch (apiError: any) {
      console.error("Ошибка API при проверке подписки на канал:", apiError);
      setChannelChecked(true); // Проверка была, но с ошибкой
      setHasChannelAccess(false); // Считаем, что доступа нет
      setChannelCheckError(apiError?.message || "Ошибка при проверке подписки. Попробуйте позже.");
    }
    // --- КОНЕЦ ДОБАВЛЕНИЯ ---
  };

  // Показываем экран подписки, если не подписан
  // --- ИЗМЕНЕНИЕ: Добавил начальную проверку isAuthenticated && userId, чтобы handleCheckChannel не вызывался слишком рано ---
  useEffect(() => {
    if (isAuthenticated && userId && !channelChecked) {
      // Вызываем проверку только если пользователь аутентифицирован, есть ID,
      // и проверка еще не выполнялась (или ее нужно выполнить повторно)
      handleCheckChannel();
    }
    // Зависимости: isAuthenticated, userId, channelChecked 
    // Если channelChecked сбрасывать при выходе/потере userId, то этот useEffect будет срабатывать правильно
  }, [isAuthenticated, userId, channelChecked]); 

  // --- ДОБАВЛЯЮ обработку параметра tgWebAppStartParam для отслеживания рефералов ---
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const startParam = urlParams.get('tgWebAppStartParam');
    if (startParam === 'starref') {
      // Здесь можно добавить логику: показать сообщение, записать в базу и т.д.
      console.log('Пользователь пришёл по реферальной ссылке (starref)');
      // Например, можно показать уведомление:
      // toast.success('Вы пришли по партнёрской ссылке!');
    }
  }, []);

  // --- ИЗМЕНЕНИЕ: Логика отображения загрузки/авторизации/экрана подписки ---
  if (loading) { // Общая загрузка приложения (например, скрипты Telegram)
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Загрузка приложения...</p>
    </div>
  );
  }

  if (!isAuthenticated || !userId) { // Если не аутентифицирован или нет userId
    return <TelegramAuth onAuthSuccess={handleAuthSuccess} />;
  }

  // Если аутентифицирован и есть userId, но проверка подписки еще не завершена ИЛИ нет доступа
  if (!channelChecked || !hasChannelAccess) {
    // Если channelUsername еще не загружен, можно показать другую загрузку или просто подождать
    // Этот блок теперь зависит от channelChecked
    // Если handleCheckChannel еще не вызывался (например, channelChecked = false), он вызовется из useEffect выше.
    // Если вызвался, но hasChannelAccess = false, покажем этот экран.

    // Если channelUsername пуст, но проверка уже идет/была, то ссылка будет неполной.
    // Можно добавить условие на channelUsername или просто показать "загрузка..." для ссылки.
    const channelLink = channelUsername 
      ? `https://t.me/${channelUsername}` 
      : "#"; // Или какой-то placeholder

    return (
      <div style={{ textAlign: 'center', marginTop: 40, padding: 20 }}>
        <h3>Проверка доступа</h3>
        {!channelChecked && ( // Если проверка еще не была инициирована или в процессе
           <div style={{ margin: '20px 0' }}>
             <ClipLoader color="#36d7b7" size={35} />
             <p style={{ marginTop: 10 }}>Проверяем вашу подписку на канал...</p>
           </div>
        )}
        {channelChecked && !hasChannelAccess && ( // Если проверка была, но доступа нет
          <>
            <p>Для доступа к приложению, пожалуйста, подпишитесь на наш Telegram-канал:</p>
            <a
              href={channelLink}
              target="_blank"
              rel="noopener noreferrer"
              style={{ 
                fontWeight: 'bold', 
                fontSize: 18, 
                color: '#1976d2', 
                display: 'inline-block', 
                margin: '10px 0',
                pointerEvents: channelUsername ? 'auto' : 'none', // Делаем ссылку некликабельной, если имя не загружено
                opacity: channelUsername ? 1 : 0.5
              }}
            >
              {channelUsername ? `Перейти в канал @${channelUsername}` : "Загрузка имени канала..."}
            </a>
            <br /><br />
            <button 
              onClick={handleCheckChannel} 
              style={{ padding: '10px 20px', fontSize: 16, cursor: 'pointer' }}
              disabled={!userId} // Блокируем, если вдруг userId пропал
            >
              Проверить подписку еще раз
            </button>
            {channelCheckError && (
              <div style={{ color: 'red', marginTop: 15, padding: '10px', border: '1px solid red', borderRadius: '4px', backgroundColor: '#ffeeee' }}>
                {channelCheckError}
              </div>
            )}
          </>
        )}
      </div>
    );
  }
  // --- КОНЕЦ ИЗМЕНЕНИЯ ---

  // Основной интерфейс (если все проверки пройдены)
  return (
    <div className="app-container">
      <header className="app-header" style={{ minHeight: '36px', padding: '6px 0', fontSize: '1.1em' }}>
        <h1 style={{ margin: 0, fontSize: '1.2em', fontWeight: 600 }}>Smart Content Assistant</h1>
      </header>
      
      {/* Блок подписки */}
      {showSubscription && (
        <>
          <SubscriptionWidget userId={userId} isActive={true}/> {/* Передаем isActive в старый виджет */} 
        </>
      )}

      <main className="app-main">
        {/* Сообщения об ошибках и успешном выполнении */}
        {error && <ErrorMessage message={error} onClose={() => setError(null)} />}
        {success && <SuccessMessage message={success} onClose={() => setSuccess(null)} />}

        {/* Навигация */}
    <div className="navigation-buttons">
      <button 
        onClick={() => setShowSubscription(true)} 
        className="action-button"
      >
        {/* SVG звезды */}
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" style={{marginRight: '8px'}}>
          <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
        </svg>
        <span>Подписка</span>
      </button>
      <button 
        onClick={() => setCurrentView('analyze')} 
        className={`action-button ${currentView === 'analyze' ? 'active' : ''}`}
      >
        {/* SVG анализ */}
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{marginRight: '8px'}}>
          <path d="M10 20H14V4H10V20ZM4 20H8V12H4V20ZM16 9V20H20V9H16Z" fill="currentColor"/>
        </svg>
        <span>Анализ</span>
      </button>
      <button 
        onClick={() => { setCurrentView('suggestions'); if (suggestedIdeas.length === 0) fetchSavedIdeas(); }} 
        className={`action-button ${currentView === 'suggestions' ? 'active' : ''}`}
        disabled={!channelName}
      >
        {/* SVG идея */}
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{marginRight: '8px'}}>
          <path d="M12 22C6.477 22 2 17.523 2 12C2 6.477 6.477 2 12 2C17.523 2 22 6.477 22 12C22 17.523 17.523 22 12 22ZM12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM11 7H13V9H11V7ZM11 11H13V17H11V11Z" fill="currentColor"/>
        </svg>
        <span>Идеи</span>
      </button>
      <button 
        onClick={() => { setCurrentView('calendar'); fetchSavedPosts(); }} 
        className={`action-button ${currentView === 'calendar' ? 'active' : ''}`}
      >
        {/* SVG календарь */}
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{marginRight: '8px'}}>
          <path d="M17 3H21C21.5523 3 22 3.44772 22 4V20C22 20.5523 21.5523 21 21 21H3C2.44772 21 2 20.5523 2 20V4C2 3.44772 2.44772 3 3 3H7V1H9V3H15V1H17V3ZM4 9V19H20V9H4ZM4 5V7H20V5H4ZM6 11H8V13H6V11ZM10 11H12V13H10V11ZM14 11H16V13H14V11Z" fill="currentColor"/>
        </svg>
        <span>Календарь</span>
      </button>
      <button 
        onClick={() => { setCurrentView('posts'); fetchSavedPosts(); }} 
        className={`action-button ${currentView === 'posts' ? 'active' : ''}`}
      >
        {/* SVG посты (добавляю иконку списка) */}
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{marginRight: '8px'}}>
          <rect x="4" y="5" width="16" height="2" fill="currentColor"/>
          <rect x="4" y="11" width="16" height="2" fill="currentColor"/>
          <rect x="4" y="17" width="16" height="2" fill="currentColor"/>
        </svg>
        <span>Посты</span>
      </button>
      <button 
        onClick={() => setCurrentView('partner')} 
        className={`action-button ${currentView === 'partner' ? 'active' : ''}`}
      >
        {/* SVG handshake/партнёрство */}
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{marginRight: '8px'}}>
          <path d="M2 17l4.24-4.24a3 3 0 014.24 0l1.06 1.06a3 3 0 004.24 0L22 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M18 19a2 2 0 002-2v-7a2 2 0 00-2-2h-7a2 2 0 00-2 2v7a2 2 0 002 2h7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span>Партнёрка</span>
      </button>
    </div>
	{currentView === 'partner' && (
  <div className="view partner-view">
    <h2>Партнёрская программа Telegram Stars</h2>
    <p>Станьте аффилиатом и зарабатывайте Stars, продвигая наше мини-приложение!<br/>
    <b>Чтобы подключиться к программе:</b></p>
    <ol style={{textAlign: 'left', maxWidth: 500, margin: '0 auto 16px auto', color: '#ccc'}}>
      <li>Нажмите кнопку ниже — Telegram сразу откроет подключение к нашей партнёрской программе.</li>
      <li>Если не сработало, откройте Telegram → Настройки → Мои звёзды → найдите "SmartContentHelperBot" и подключитесь вручную.</li>
    </ol>
    <button
      className="action-button"
      onClick={() => window.open('https://t.me/SmartContentHelperBot?startapp=starref', '_blank')}
      style={{marginBottom: 16}}
    >
      Стать аффилиатом
    </button>
    <div style={{marginTop: 24, fontSize: 14, color: '#666'}}>
      <b>Как это работает?</b><br/>
      1. После подключения Telegram выдаст вам уникальную реферальную ссылку.<br/>
      2. Делитесь ссылкой с друзьями, в соцсетях, на сайтах.<br/>
      3. За каждую покупку по вашей ссылке Telegram начислит вам Stars.<br/>
      <i>Вся статистика и начисления ведутся автоматически через Telegram.</i>
    </div>
  </div>
)}
        {/* Выбор канала */}
        {currentView !== 'partner' && (
          <div className="channel-selector">
            <label>Каналы: </label>
            <div className="custom-dropdown" style={{ position: 'relative', display: 'inline-block', minWidth: 220 }}>
              <div className="selected" onClick={() => setDropdownOpen(v => !v)} style={{ border: '1px solid #ccc', borderRadius: 6, padding: '7px 12px', background: '#fff', cursor: 'pointer', minWidth: 180, color: '#222', fontWeight: 500 }}>
                {channelName || 'Выберите канал'}
                <span style={{ float: 'right', fontSize: 14, color: '#888' }}>{dropdownOpen ? '▲' : '▼'}</span>
              </div>
              {dropdownOpen && (
                <ul className="dropdown-list" style={{ position: 'absolute', zIndex: 10, background: '#fff', border: '1px solid #ccc', borderRadius: 6, margin: 0, padding: 0, listStyle: 'none', width: '100%' }}>
                  {allChannels.length === 0 && <li style={{ padding: '8px 12px', color: '#888' }}>Нет каналов</li>}
                  {allChannels.map(channel => (
                    <li key={channel} className="dropdown-item" style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', borderBottom: '1px solid #eee', cursor: 'pointer', color: '#222' }}>
                      <span style={{ flex: 1, color: '#222' }} onClick={() => { setChannelName(channel); setDropdownOpen(false); }}>{channel}</span>
                      <button
                        className="remove-btn"
                        onClick={e => { e.stopPropagation(); handleRemoveChannel(channel); }}
                        style={{ marginLeft: 8, color: 'red', cursor: 'pointer', border: 'none', background: 'none', fontSize: 18 }}
                        title="Удалить канал"
                      >×</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

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
          value={channelInput}
          onChange={e => setChannelInput(e.target.value.replace(/^@/, ''))}
          placeholder="Введите username канала (без @)"
                  disabled={isAnalyzing}
                />
                <button 
                  onClick={() => analyzeChannel(channelInput)} 
                  className="action-button"
                  disabled={isAnalyzing || !channelInput || analyzeLimitExceeded}
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
                <div style={{ margin: '20px 0' }}>
                  <ProgressBar progress={progress} />
                  <p>Анализируем канал...</p>
                </div>
              )}
              
              {error && !isAnalyzing && !analysisResult && (
                <div className="error-message" style={{ margin: '20px 0', padding: '15px', borderRadius: '8px' }}>
                  <p style={{ marginBottom: '10px', fontWeight: 'bold' }}>Ошибка анализа:</p>
                  <p>{error}</p>
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
                    disabled={isGeneratingIdeas || !analysisResult || ideasLimitExceeded} 
                    style={{marginTop: '20px'}}
                  >
                    {isGeneratingIdeas ? 'Генерация...' : 'Сгенерировать новые идеи'}
              </button>
              {isGeneratingIdeas && (
                <div style={{ margin: '20px 0' }}>
                  <ProgressBar progress={progress} />
                  <p className="loading-message" style={{ textAlign: 'center', fontStyle: 'italic', transition: 'opacity 0.5s ease-in-out' }}>
                    {currentIdeasMessage}
                  </p>
                </div>
              )}
              {ideasLimitExceeded && (
                <div className="error-message">
                  <p>Достигнут лимит генерации идей для бесплатной подписки.</p>
                  {ideasLimitResetTime && (
                    <p>Следующая попытка будет доступна после: <strong>{new Date(ideasLimitResetTime).toLocaleString()}</strong></p>
                  )}
                  <p style={{ marginTop: '10px' }}>
                    <button 
                      onClick={() => setShowSubscription(true)} 
                      className="action-button subscription-button"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" style={{marginRight: '8px', verticalAlign: 'middle'}}>
                        <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
                      </svg>
                      <span style={{verticalAlign: 'middle'}}>Оформить подписку</span>
                    </button>
                  </p>
                </div>
              )}
          </div>
      )}

              {!analysisResult && !isAnalyzing && (
                <p>Введите имя канала для начала анализа. Например: durov</p>
      )}
      {analyzeLimitExceeded && (
        <div className="error-message small">Достигнут лимит анализа каналов для бесплатной подписки. Оформите подписку для снятия ограничений.</div>
      )}
    </div>
          )}

          {/* Вид идей */}
          {currentView === 'suggestions' && channelName && (
            <div className="view suggestions-view">
              {ideasLimitExceeded && (
                <div className="error-message">
                  <p>Достигнут лимит генерации идей для бесплатной подписки.</p>
                  {ideasLimitResetTime && (
                    <p>Следующая попытка будет доступна после: <strong>{new Date(ideasLimitResetTime).toLocaleString()}</strong></p>
                  )}
                  <p style={{ marginTop: '10px' }}>
                    <button 
                      onClick={() => setShowSubscription(true)} 
                      className="action-button subscription-button"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" style={{marginRight: '8px', verticalAlign: 'middle'}}>
                        <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
                      </svg>
                      <span style={{verticalAlign: 'middle'}}>Оформить подписку</span>
                    </button>
                  </p>
                </div>
              )}
              
              <h2>Идеи контента для @{channelName}</h2>
              
              {isGeneratingIdeas && (
                <div style={{ margin: '20px 0' }}>
                  <ProgressBar progress={progress} />
                  <p className="loading-message" style={{ textAlign: 'center', fontStyle: 'italic', transition: 'opacity 0.5s ease-in-out' }}>
                    {currentIdeasMessage}
                  </p>
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
              ) : (
                <p>
                  {analysisResult 
                    ? 'Нажмите "Сгенерировать идеи" на вкладке Анализ, чтобы создать новые идеи для контента.' 
                    : loadingAnalysis 
                        ? 'Загрузка сохраненного анализа...' 
                        : 'Сначала выполните анализ канала на вкладке "Анализ" или выберите канал с сохраненным анализом.'
                  }
                </p>
              )}
              
        <button 
                    onClick={generateIdeas} 
                    className="action-button generate-button"
                    disabled={isGeneratingIdeas || !analysisResult || ideasLimitExceeded} 
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
              {/* Календарь - ВОССТАНОВЛЕННЫЙ КОД */}
              <div className="calendar-container">
                {/* Заголовок с названием месяца и навигацией */}
                <div className="calendar-header">
                  <button 
                    className="nav-button"
                    onClick={goToPrevMonth}
                  >
                    &lt;
                  </button>
                  <h3>{currentMonth.toLocaleString('default', { month: 'long', year: 'numeric' })}</h3>
                  <button 
                    className="nav-button"
                    onClick={goToNextMonth}
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
            <div className="view posts-view">
              <h2>
                Список сохраненных постов
                {/* Убираем отображение выбранных каналов */}
              </h2>
              {/* Удалён фильтр по каналам для вкладки Посты */}
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

              {/* Прогресс-бар генерации с забавными сообщениями */}
              {isGeneratingPostDetails && (
                <div style={{ margin: '20px 0' }}>
                  <ProgressBar progress={progress} />
                  <p className="loading-message" style={{ textAlign: 'center', fontStyle: 'italic', transition: 'opacity 0.5s ease-in-out' }}>
                    {currentPostDetailsMessage}
                  </p>
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
                  rows={16}
                  style={{ minHeight: '220px', fontSize: '1.1em', padding: '14px', borderRadius: '8px' }}
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
                              {suggestedImages.map((image, index) => {
                                  const isSelected = selectedImage ? selectedImage.url === image.url : false;
                                  return (
                                      <div 
                                          key={image.url || image.id || `suggested-${index}`} // Более надежный ключ
                                          className={`image-item ${isSelected ? 'selected' : ''}`}
                                          onClick={() => handleImageSelection(image)}
                                          style={{ cursor: 'pointer', position: 'relative', border: isSelected ? '3px solid #1976d2' : '2px solid transparent', padding: '2px' }} // Явная рамка для выбранного
                                      >
                                      <img 
                                          src={image.preview_url || image.url} 
                                          alt={image.alt || 'Suggested image'} 
                                          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                                          onError={(e) => {
                                              const target = e.target as HTMLImageElement;
                                              target.src = 'https://via.placeholder.com/100?text=Ошибка'; 
                                              console.error('Image load error:', image.preview_url || image.url);
                                          }}
                                      />
                                      {isSelected && (
                                          <div className="checkmark" style={{ 
                                              position: 'absolute', 
                                              top: '5px', 
                                              right: '5px', 
                                              backgroundColor: '#1976d2', 
                                              color: 'white', 
                                              borderRadius: '50%', 
                                              width: '20px',
                                              height: '20px',
                                              display: 'flex',
                                              alignItems: 'center',
                                              justifyContent: 'center',
                                              fontSize: '12px',
                                              fontWeight: 'bold',
                                              zIndex: 10
                                          }}>✔</div> 
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
                      <ImageUploader onImageUploaded={handleCustomImageUpload} userId={userId} />
                      
                      {selectedImage && (
                          <div className="selected-image-preview" style={{ marginTop: '15px', padding: '10px', border: 'none', borderRadius: '8px', background: 'none' }}>
                              <h5 style={{ marginTop: '0', marginBottom: '10px' }}>Выбранное изображение:</h5>
                              <div className="preview-container" style={{ textAlign: 'center' }}>
                                <div className="image-preview-container" style={{ background: 'none', maxWidth: '100%', margin: 0, padding: 0, display: 'inline-block', position: 'relative' }}>
                                  {selectedImage && (
                                    <img
                                      src={selectedImage.preview_url || selectedImage.url}
                                      alt={selectedImage.alt || 'Изображение'}
                                      style={{ display: 'block', maxWidth: '100%', height: 'auto', maxHeight: '60vh', margin: '0 auto', background: 'none', borderRadius: '8px' }}
                                    />
                                  )}
                                </div>
                                <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', marginTop: '10px' }}>
                                  <button 
                                    className="action-button delete-button small remove-image-btn"
                                    onClick={() => {
                                      setSelectedImage(null);
                                    }}
                                    title="Удалить выбранное изображение"
                                  >
                                    <span>🗑️ Отменить выбор</span>
                                  </button>
                                  <button
                                    className="action-button download-button small"
                                    onClick={handleSendImageToChat}
                                    title="Скачать изображение"
                                  >
                                    ⬇️ Скачать
                                  </button>
                                  <button
                                    className="action-button small"
                                    onClick={() => setIsImageModalOpen(true)}
                                    title="Приблизить изображение"
                                  >
                                    🔍 Приблизить
                                  </button>
                                </div>
                              </div>
                          </div>
                      )}
                </div>
              </div>
              {/* --- КОНЕЦ: Секция управления изображениями --- */} 
                
              {/* Кнопки действий */}
              <div className="form-actions">
                  <button 
                    onClick={handleSaveOrUpdatePost} 
                    className="action-button save-button"
                    disabled={isSavingPost || isGeneratingPostDetails || !currentPostText || postLimitExceeded}
                  >
                    {isSavingPost ? 'Сохранение...' : (currentPostId ? 'Обновить пост' : 'Сохранить пост')}
                  </button>
                  
                  {selectedImage && (
                    <div style={{ marginTop: '10px', color: 'green', fontWeight: 'bold', textAlign: 'center' }}>
                      ✅ Изображение "{selectedImage.alt?.substring(0,30) || 'Выбранное'}{selectedImage.alt && selectedImage.alt.length > 30 ? '...' : ''}" будет сохранено с постом.
                    </div>
                  )}
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

      {/* Модальное окно предпросмотра изображения */}
      {isImageModalOpen && selectedImage && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          background: 'rgba(0,0,0,0.85)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <div style={{ position: 'relative', maxWidth: '90vw', maxHeight: '90vh', padding: '16px' }}>
            <img
              src={selectedImage.url}
              alt={selectedImage.alt || 'Изображение'}
              style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: '10px', boxShadow: '0 2px 16px #0008', display: 'block' }}
            />
            <button
              onClick={() => setIsImageModalOpen(false)}
              style={{
                position: 'absolute',
                top: 16,
                right: 16,
                background: '#fff',
                color: '#222',
                border: 'none',
                borderRadius: '50%',
                width: 36,
                height: 36,
                fontSize: 22,
                fontWeight: 'bold',
                cursor: 'pointer',
                boxShadow: '0 2px 8px #0004',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              title="Закрыть"
            >✖</button>
          </div>
        </div>
      )}
      <Toaster position="top-center" reverseOrder={false} />
    </div>
  );
}

// === ДОБАВЛЯЮ: Функция для очистки текста поста от лишних символов ===
function cleanPostText(text: string) {
  // Удаляем звездочки, markdown-символы, лишние пробелы
  return text.replace(/[\*\_\#\-]+/g, '').replace(/\s{2,}/g, ' ').trim();
}

export default App;
