import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import './App.css';
import { TelegramAuth } from './components/TelegramAuth';
import { v4 as uuidv4 } from 'uuid';
import { Toaster, toast } from 'react-hot-toast';
import { ClipLoader } from 'react-spinners';
import SubscriptionWidget from './components/SubscriptionWidget';
import DirectPremiumStatus from './components/DirectPremiumStatus';

const API_BASE_URL = ''; // Оставляем пустым для относительных путей

// Вспомогательная функция для ключей localStorage (если где-то еще используется, иначе можно удалить)
const getUserSpecificKey = (baseKey: string, userId: string | null): string | null => {
  if (!userId) return null;
  return `${userId}_${baseKey}`;
};

// Вспомогательные компоненты
const Loading = ({ message }: { message: string }) => (
  <div className="loading-indicator">
    <ClipLoader size={35} color={"#007bff"} />
    <p>{message}</p>
  </div>
);

const SuccessMessage = ({ message, onClose }: { message: string | null, onClose: () => void }) => (
  message ? (
    <div className="success-message-toast"> {/* Можно стилизовать как toast */}
      <span>{message}</span>
      <button onClick={onClose} className="toast-close-button">&times;</button>
    </div>
  ) : null
);

class SimpleErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) {
      return <div className="error-message">Что-то пошло не так. Пожалуйста, перезагрузите страницу.</div>;
    }
    return this.props.children;
  }
}

declare global {
  interface Window { Telegram?: any; }
}

try {
  if (window.Telegram?.WebApp) {
    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand(); // Разворачиваем приложение на весь экран
  }
} catch (e) {
  console.error('Ошибка при инициализации Telegram WebApp:', e);
}

// Определения типов
type ViewType = 'analyze' | 'suggestions' | 'plan' | 'details' | 'calendar' | 'edit' | 'posts';

interface AnalysisResult {
  message?: string;
  themes: string[];
  styles: string[];
  analyzed_posts_sample: string[];
  best_posting_time: string;
  analyzed_posts_count: number;
  error?: string;
  is_sample_data?: boolean;
}

interface SuggestedIdea {
  id: string;
  created_at: string;
  channel_name: string;
  topic_idea: string;
  format_style: string;
  day?: number;
  is_detailed?: boolean;
  user_id?: string;
  relative_day?: number; 
}

interface PostImage {
  url: string;
  id?: string;
  preview_url?: string;
  alt?: string;
  author?: string;
  author_url?: string;
  source?: string;
}

interface SavedPost {
  id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  target_date: string;
  topic_idea: string;
  format_style: string;
  final_text: string;
  image_url?: string; // Устаревшее, лучше использовать selected_image_data
  channel_name?: string;
  selected_image_data?: PostImage | null;
}

interface CalendarDay {
  date: Date;
  posts: SavedPost[];
  isCurrentMonth: boolean;
  isToday: boolean;
}

interface ApiUserSettings {
  channelName: string | null;
  selectedChannels: string[];
  allChannels: string[];
}

interface UserSettingsPayload {
  channelName?: string | null;
  selectedChannels?: string[];
  allChannels?: string[];
}

interface SuggestedIdeasResponse {
  ideas: SuggestedIdea[];
  message?: string;
}

interface PlanItem {
    day: number;
    topic_idea: string;
    format_style: string;
}

// Компонент ImageUploader
const ImageUploader = ({ onImageUploaded, userId }: { onImageUploaded: (imageUrl: string) => void, userId: string | null }) => {
  const [uploading, setUploading] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const file = files[0];
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Размер файла должен быть не более 5 МБ");
      return;
    }
    if (!file.type.startsWith('image/')) {
      toast.error("Разрешены только изображения");
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      // Убедитесь, что userId передается в заголовке, если API этого требует
      const headers: Record<string, string> = { 'Content-Type': 'multipart/form-data' };
      if (userId) {
        headers['X-Telegram-User-Id'] = userId;
      }
      const response = await axios.post(`${API_BASE_URL}/upload-image`, formData, { headers });
      if (response.data && response.data.url) {
        onImageUploaded(response.data.url);
        toast.success('Изображение успешно загружено!');
      } else {
        toast.error("Ошибка при загрузке. Нет URL в ответе.");
      }
    } catch (error: any) {
      console.error("Ошибка загрузки изображения:", error);
      toast.error(error.response?.data?.detail || "Ошибка при загрузке изображения");
    } finally {
      setUploading(false);
    }
  };
  
  return (
    <div className="image-uploader">
      <label className="upload-button-label">
        <input type="file" accept="image/*" onChange={handleFileChange} disabled={uploading} style={{ display: 'none' }} />
        <span className="action-button">{uploading ? <ClipLoader size={15} color={"#fff"} /> : "Загрузить свое"}</span>
      </label>
    </div>
  );
};

// Компонент CalendarDayComponent (ранее CalendarDay в JSX)
const CalendarDayComponent = ({ day, onEditPost, onDeletePost }: { day: CalendarDay; onEditPost: (post: SavedPost) => void; onDeletePost: (postId: string) => void; }) => {
  const { date, posts, isCurrentMonth, isToday } = day;
  const dayNumber = date.getDate();
  const cellClass = `calendar-day ${isCurrentMonth ? '' : 'other-month'} ${isToday ? 'today' : ''}`;
  return (
    <div className={cellClass}>
      <div className="day-number">{dayNumber}</div>
      {posts.length > 0 && (
        <div className="day-posts">
          {posts.map((post) => (
            <div key={post.id} className="post-item-calendar">
              <div className="post-title-calendar" title={post.topic_idea}>
                {post.topic_idea.length > 20 ? post.topic_idea.substring(0, 17) + '...' : post.topic_idea}
              </div>
              <div className="post-actions-calendar">
                <button onClick={() => onEditPost(post)} title="Редактировать">📝</button>
                <button onClick={() => onDeletePost(post.id)} title="Удалить">🗑️</button>
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
  const [appLoading, setAppLoading] = useState(true); 
  const [userId, setUserId] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<ViewType>('analyze');
  
  // Настройки пользователя, синхронизируемые с сервером
  const [channelName, setChannelName] = useState<string>(''); // Текущий выбранный канал для отображения
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]); // Для фильтрации (если используется)
  const [allChannelsState, setAllChannelsState] = useState<string[]>([]); // Список всех каналов пользователя
  const [initialSettingsLoaded, setInitialSettingsLoaded] = useState(false);

  // Данные приложения
  const [savedPosts, setSavedPosts] = useState<SavedPost[]>([]);
  const [loadingSavedPosts, setLoadingSavedPosts] = useState(false);
  const [suggestedIdeas, setSuggestedIdeas] = useState<SuggestedIdea[]>([]);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [isGeneratingIdeas, setIsGeneratingIdeas] = useState(false);
  const [planPeriod, setPlanPeriod] = useState<number>(7);
  const [generatedPlan, setGeneratedPlan] = useState<PlanItem[]>([]);

  // Календарь
  const [currentMonth, setCurrentMonth] = useState<Date>(new Date());
  const [calendarDays, setCalendarDays] = useState<CalendarDay[]>([]);
  
  // Редактирование/создание поста
  const [editingPost, setEditingPost] = useState<SavedPost | null>(null);
  const [isGeneratingPostDetails, setIsGeneratingPostDetails] = useState<boolean>(false);
  const [selectedIdeaForDetail, setSelectedIdeaForDetail] = useState<SuggestedIdea | null>(null);
  const [detailedPostText, setDetailedPostText] = useState(''); // Только текст из detailedPost
  const [suggestedImages, setSuggestedImages] = useState<PostImage[]>([]);
  const [selectedImage, setSelectedImage] = useState<PostImage | null>(null);
  const [isSavingPost, setIsSavingPost] = useState(false);
  const [currentPostDate, setCurrentPostDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [currentPostTopic, setCurrentPostTopic] = useState('');
  const [currentPostFormat, setCurrentPostFormat] = useState('');
  
  // UI состояния
  const [showSubscription, setShowSubscription] = useState<boolean>(false);
  const [analysisInput, setAnalysisInput] = useState<string>('');

  // --- Функции для работы с API --- 
  const fetchUserSettings = async (): Promise<ApiUserSettings | null> => {
    if (!userId) return null;
    try {
      const response = await axios.get<ApiUserSettings>(`${API_BASE_URL}/api/user/settings`);
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return null; // Настройки еще не созданы, это нормально
      }
      console.error('Failed to fetch user settings:', error);
      toast.error('Не удалось загрузить настройки пользователя.');
      return null; // Возвращаем null при других ошибках
    }
  };

  const saveUserSettings = async (settings: UserSettingsPayload) => {
    if (!userId || !initialSettingsLoaded) return; 
    try {
      await axios.put(`${API_BASE_URL}/api/user/settings`, settings);
    } catch (error) {
      console.error('Failed to save user settings:', error);
      toast.error('Ошибка сохранения настроек на сервере.');
    }
  };

  const fetchSavedPosts = async (currentChannel?: string | null) => {
    if (!userId) return;
    setLoadingSavedPosts(true);
    try {
      const params = currentChannel ? { channel_name: currentChannel } : {};
      const response = await axios.get<SavedPost[]>(`${API_BASE_URL}/posts`, { params });
      setSavedPosts(response.data || []);
    } catch (err: any) {
      console.error('Ошибка при загрузке постов:', err);
      toast.error(err.response?.data?.detail || err.message || 'Не удалось загрузить посты');
      setSavedPosts([]);
    } finally {
      setLoadingSavedPosts(false);
    }
  };

  const fetchSavedIdeas = async (currentChannel?: string | null) => {
    if (!userId) return;
    //setIsGeneratingIdeas(true); // Если нужен отдельный индикатор
    try {
      const params = currentChannel ? { channel_name: currentChannel } : {};
      const response = await axios.get<SuggestedIdeasResponse>(`${API_BASE_URL}/ideas`, { params });
      setSuggestedIdeas(response.data.ideas || []);
    } catch (err: any) {
      console.error('Ошибка при загрузке идей:', err);
      toast.error(err.response?.data?.message || err.response?.data?.detail || 'Не удалось загрузить идеи');
      setSuggestedIdeas([]);
    } finally {
      //setIsGeneratingIdeas(false);
    }
  };

  const fetchSavedAnalysis = async (currentChannel: string) => {
    if (!userId || !currentChannel) {
      setAnalysisResult(null);
      return;
    }
    setLoadingAnalysis(true);
    try {
      const response = await axios.get<AnalysisResult>(`${API_BASE_URL}/channel-analysis`, {
        params: { channel_name: currentChannel }
      });
      if (response.data && !response.data.error && !response.data.message?.includes("не найден")) {
        setAnalysisResult(response.data);
      } else {
        setAnalysisResult(null); // Если есть ошибка в ответе или анализ не найден
      }
    } catch (err: any) {
      console.error('Ошибка при загрузке сохраненного анализа:', err);
      if (!(axios.isAxiosError(err) && err.response?.status === 404)) {
        toast.error(err.response?.data?.detail || err.message || 'Ошибка загрузки анализа');
      }
      setAnalysisResult(null);
    } finally {
      setLoadingAnalysis(false);
    }
  };

  // --- useEffects для управления состоянием и данными ---

  // Загрузка начальных настроек пользователя
  useEffect(() => {
    const loadInitialUserSettings = async () => {
      if (isAuthenticated && userId) {
        // setAppLoading(true); // appLoading управляется в связке с initialSettingsLoaded
        try {
          const settings = await fetchUserSettings();
          if (settings) {
            setChannelName(settings.channelName || '');
            setSelectedChannels(settings.selectedChannels || []);
            setAllChannelsState(settings.allChannels || []);
          }
        } finally {
          setInitialSettingsLoaded(true);
        }
      } else {
        setChannelName('');
        setSelectedChannels([]);
        setAllChannelsState([]);
        setInitialSettingsLoaded(false); 
        setAppLoading(false); // Если не аутентифицирован, то нечего грузить
      }
    };
    loadInitialUserSettings();
  }, [isAuthenticated, userId]);

  // Загрузка данных, зависящих от канала (посты, идеи, анализ)
  useEffect(() => {
    const loadChannelDependentData = async () => {
      if (isAuthenticated && userId && initialSettingsLoaded) {
        setAppLoading(true);
        await fetchSavedPosts(channelName); 
        await fetchSavedIdeas(channelName);
        if (channelName) {
          await fetchSavedAnalysis(channelName);
        } else {
          setAnalysisResult(null); // Очищаем анализ, если не выбран конкретный канал
        }
        setAppLoading(false);
      }
    };
    if (initialSettingsLoaded) { // Важно: запускаем только после загрузки настроек
      loadChannelDependentData();
    } else if (!isAuthenticated) { // Если пользователь разлогинился, а initialSettingsLoaded еще true
        setAppLoading(false); // Убираем лоадер
    }
  }, [isAuthenticated, userId, initialSettingsLoaded, channelName]);

  // Сохранение настроек на сервере с debounce
  const debouncedSettingsToSave = useMemo(() => ({
    channelName,
    selectedChannels,
    allChannels: allChannelsState,
  }), [channelName, selectedChannels, allChannelsState]);

  useEffect(() => {
    if (isAuthenticated && userId && initialSettingsLoaded) {
      const handler = setTimeout(() => {
        saveUserSettings(debouncedSettingsToSave);
      }, 1500);
      return () => clearTimeout(handler);
    }
  }, [isAuthenticated, userId, initialSettingsLoaded, debouncedSettingsToSave]);
  
  // Генерация дней для календаря
  const generateCalendarDays = useCallback(() => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const firstDayOfMonth = new Date(year, month, 1);
    const lastDayOfMonth = new Date(year, month + 1, 0);
    let firstDayOfWeek = firstDayOfMonth.getDay();
    firstDayOfWeek = firstDayOfWeek === 0 ? 6 : firstDayOfWeek - 1; 
    const daysArray: CalendarDay[] = [];
    const prevMonthLastDay = new Date(year, month, 0).getDate();
    for (let i = firstDayOfWeek - 1; i >= 0; i--) {
      const date = new Date(year, month - 1, prevMonthLastDay - i);
      daysArray.push({ date, posts: savedPosts.filter(p => new Date(p.target_date).toDateString() === date.toDateString()), isCurrentMonth: false, isToday: date.toDateString() === new Date().toDateString() });
    }
    for (let i = 1; i <= lastDayOfMonth.getDate(); i++) {
      const date = new Date(year, month, i);
      daysArray.push({ date, posts: savedPosts.filter(p => new Date(p.target_date).toDateString() === date.toDateString()), isCurrentMonth: true, isToday: date.toDateString() === new Date().toDateString() });
    }
    const daysGenerated = daysArray.length;
    for (let i = 1; i <= 42 - daysGenerated; i++) { // 42 for 6 weeks grid
      const date = new Date(year, month + 1, i);
      daysArray.push({ date, posts: savedPosts.filter(p => new Date(p.target_date).toDateString() === date.toDateString()), isCurrentMonth: false, isToday: date.toDateString() === new Date().toDateString() });
    }
    setCalendarDays(daysArray);
  }, [currentMonth, savedPosts]); 

  useEffect(() => {
    if (isAuthenticated && initialSettingsLoaded) { // Генерируем календарь только после загрузки данных
        generateCalendarDays();
    }
  }, [currentMonth, savedPosts, isAuthenticated, initialSettingsLoaded, generateCalendarDays]);

  // --- Обработчики действий пользователя ---
  const handleAuthSuccess = (authUserId: string) => {
    setUserId(authUserId);
    axios.defaults.headers.common['X-Telegram-User-Id'] = authUserId;
    setIsAuthenticated(true);
    setAppLoading(false); // После успешной аутентификации, если нет других загрузок
  };
  
  const analyzeChannel = async () => {
    if (!analysisInput.trim()) {
      toast.error("Введите имя Telegram канала или URL.");
      return;
    }
    if (!userId) {
      toast.error("Ошибка аутентификации. Попробуйте перезагрузить.");
      return;
    }
    setLoadingAnalysis(true);
    setAnalysisResult(null);
    const currentChannelToAnalyze = analysisInput.replace("@", "").trim();
    try {
      const response = await axios.post<AnalysisResult>(`${API_BASE_URL}/analyze`, { username: currentChannelToAnalyze });
      setAnalysisResult(response.data);
      if (response.data.message && !response.data.error) {
        toast(response.data.message);
      } else if (!response.data.error) {
        toast.success(`Анализ для @${currentChannelToAnalyze} завершен!`);
      }
      // Устанавливаем проанализированный канал как текущий и добавляем в список всех каналов
      setChannelName(currentChannelToAnalyze); 
      if (!allChannelsState.includes(currentChannelToAnalyze)) {
        setAllChannelsState(prev => [...prev, currentChannelToAnalyze]);
      }
    } catch (err: any) {
      console.error('Ошибка при анализе канала:', err);
      toast.error(err.response?.data?.detail || err.message || 'Ошибка при анализе канала');
      setAnalysisResult(null);
    } finally {
      setLoadingAnalysis(false);
    }
  };
  
  const generateIdeas = async () => {
    if (!analysisResult || analysisResult.themes.length === 0 || analysisResult.styles.length === 0) {
      toast.error("Сначала проанализируйте канал, чтобы получить темы и стили.");
      return;
    }
    if (!userId || !channelName) {
        toast.error("Канал не выбран или ошибка пользователя.");
        return;
    }
    setIsGeneratingIdeas(true);
    try {
      const response = await axios.post<{ plan: PlanItem[], message?: string }>(`${API_BASE_URL}/generate-plan`, {
        themes: analysisResult.themes,
        styles: analysisResult.styles,
        period_days: planPeriod,
        channel_name: channelName
      });
      if (response.data.plan && response.data.plan.length > 0) {
        const newIdeas: SuggestedIdea[] = response.data.plan.map(item => ({
          id: uuidv4(),
          created_at: new Date().toISOString(),
          channel_name: channelName,
          topic_idea: item.topic_idea,
          format_style: item.format_style,
          relative_day: item.day,
          is_detailed: false,
          user_id: userId
        }));
        await axios.post(`${API_BASE_URL}/save-suggested-ideas`, { ideas: newIdeas, channel_name: channelName });
        setSuggestedIdeas(newIdeas);
        toast.success(response.data.message || "План идей успешно сгенерирован и сохранен!");
        setCurrentView('suggestions');
      } else {
        toast.error(response.data.message || "Не удалось сгенерировать идеи.");
      }
    } catch (err: any) {
      console.error('Ошибка при генерации идей:', err);
      toast.error(err.response?.data?.detail || err.message || 'Ошибка при генерации идей');
    } finally {
      setIsGeneratingIdeas(false);
    }
  };
  
  const handleDetailIdea = (idea: SuggestedIdea) => {
    setSelectedIdeaForDetail(idea);
    setCurrentView('details'); 
    setIsGeneratingPostDetails(true);
    setDetailedPostText(''); 
    setSuggestedImages([]);
    setSelectedImage(null);
    setEditingPost(null); // Сбрасываем редактирование, если детализируем новую идею

    axios.post(`${API_BASE_URL}/generate-post-details`, {
        topic_idea: idea.topic_idea,
        format_style: idea.format_style,
        channel_name: idea.channel_name,
    })
    .then(response => {
        setDetailedPostText(response.data.generated_text);
        setSuggestedImages(response.data.found_images || []);
        if (response.data.found_images && response.data.found_images.length > 0) {
            setSelectedImage(response.data.found_images[0]);
        } else {
            setSelectedImage(null);
        }
        // Заполняем поля для нового поста на основе идеи
        setCurrentPostTopic(idea.topic_idea);
        setCurrentPostFormat(idea.format_style);
        setCurrentPostDate(new Date().toISOString().split('T')[0]); // Сегодняшняя дата по умолчанию
    })
    .catch(err => {
        console.error("Ошибка при генерации деталей поста:", err);
        toast.error(err.response?.data?.detail || "Не удалось сгенерировать детали поста.");
    })
    .finally(() => setIsGeneratingPostDetails(false));
  };
  
  const handleSaveOrUpdatePost = async () => {
    const targetChannelName = editingPost?.channel_name || selectedIdeaForDetail?.channel_name || channelName;
    if (!userId || !targetChannelName) {
        toast.error("Ошибка: Канал не определен или нет данных пользователя.");
        return;
    }
    setIsSavingPost(true);
    const postPayload: Omit<SavedPost, 'id' | 'user_id' | 'created_at' | 'updated_at'> & { id?: string } = {
      target_date: currentPostDate,
      topic_idea: currentPostTopic,
      format_style: currentPostFormat,
      final_text: detailedPostText, // Используем detailedPostText
      channel_name: targetChannelName,
      selected_image_data: selectedImage,
    };

    try {
        if (editingPost && editingPost.id) {
            await axios.put<SavedPost>(`${API_BASE_URL}/posts/${editingPost.id}`, postPayload);
            toast.success("Пост успешно обновлен!");
        } else {
            await axios.post<SavedPost>(`${API_BASE_URL}/posts`, postPayload);
            toast.success("Пост успешно сохранен!");
            if (selectedIdeaForDetail) { // Помечаем идею как детализированную (опционально)
                 setSuggestedIdeas(prevIdeas => prevIdeas.map(i => 
                    i.id === selectedIdeaForDetail.id ? { ...i, is_detailed: true } : i
                ));
            }
        }
        fetchSavedPosts(channelName); // Обновляем список постов с учетом текущего фильтра
        setCurrentView('posts');
        setEditingPost(null); 
        setSelectedIdeaForDetail(null);
    } catch (err: any) {
        console.error("Ошибка при сохранении/обновлении поста:", err);
        toast.error(err.response?.data?.detail || "Не удалось сохранить пост.");
    } finally {
        setIsSavingPost(false);
    }
  };
  
  const startEditingPost = (post: SavedPost) => {
    setEditingPost(post);
    setSelectedIdeaForDetail(null); // Сбрасываем выбранную идею, т.к. редактируем пост
    setCurrentPostTopic(post.topic_idea);
    setCurrentPostFormat(post.format_style);
    setDetailedPostText(post.final_text);
    setCurrentPostDate(post.target_date);
    setSelectedImage(post.selected_image_data || null);
    setSuggestedImages(post.selected_image_data ? [post.selected_image_data] : []); // Показываем текущее изображение
    setCurrentView('details'); // Используем тот же view для редактирования
  };

  const deletePost = async (postId: string) => {
    if (!window.confirm("Вы уверены, что хотите удалить этот пост?")) return;
    try {
        await axios.delete(`${API_BASE_URL}/posts/${postId}`);
        toast.success("Пост успешно удален.");
        fetchSavedPosts(channelName); 
    } catch (err: any) {
        console.error("Ошибка при удалении поста:", err);
        toast.error(err.response?.data?.detail || "Не удалось удалить пост.");
    }
  };
  
  const handleImageSelection = (image: PostImage | undefined) => {
      setSelectedImage(image || null);
  };
  
  const handleCustomImageUpload = (imageUrl: string) => {
    const newImage: PostImage = {
        id: uuidv4(), 
        url: imageUrl,
        preview_url: imageUrl,
        alt: 'Загруженное изображение',
        source: 'upload',
        author: 'Пользователь (upload)'
    };
    setSuggestedImages(prev => [newImage, ...prev.filter(img => img.source !== 'upload')]);
    setSelectedImage(newImage);
  };

  const goToPrevMonth = () => setCurrentMonth(prev => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
  const goToNextMonth = () => setCurrentMonth(prev => new Date(prev.getFullYear(), prev.getMonth() + 1, 1));

  // Рендеринг
  if (appLoading && !initialSettingsLoaded && isAuthenticated) { 
    return (
      <div className="loading-container-full">
        <ClipLoader size={50} color={"#007bff"} />
        <p>Загрузка данных пользователя...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <TelegramAuth onAuthSuccess={handleAuthSuccess} />;
  }

  return (
    <SimpleErrorBoundary>
      <div className={`App view-${currentView}`}>
        <Toaster position="top-center" toastOptions={{duration: 3000}} />
        <header className="App-header">
          <h1>Smart Content Assistant</h1>
          <div className="channel-selector-header">
            <label htmlFor="channel-select-main">Канал:</label>
            <select id="channel-select-main" value={channelName} onChange={(e) => setChannelName(e.target.value)}>
              <option value="">Все каналы</option>
              {allChannelsState.map(cn => <option key={cn} value={cn}>{cn}</option>)}
            </select>
          </div>
          <DirectPremiumStatus userId={userId} />
        </header>
        
        <nav className="navigation">
          <button onClick={() => setCurrentView('analyze')} className={currentView === 'analyze' ? 'active' : ''}>Анализ</button>
          <button onClick={() => setCurrentView('suggestions')} className={currentView === 'suggestions' ? 'active' : ''} disabled={!channelName && suggestedIdeas.length === 0}>Идеи</button>
          <button onClick={() => setCurrentView('plan')} className={currentView === 'plan' ? 'active' : ''} disabled={!channelName || !analysisResult}>План</button>
          <button onClick={() => setCurrentView('posts')} className={currentView === 'posts' ? 'active' : ''}>Посты</button>
          <button onClick={() => setCurrentView('calendar')} className={currentView === 'calendar' ? 'active' : ''}>Календарь</button>
        </nav>

        <main className="content">
          {currentView === 'analyze' && (
            <section id="analyze-channel">
              <h2>Анализ Telegram Канала</h2>
              <div className="input-group">
                <input type="text" value={analysisInput} onChange={(e) => setAnalysisInput(e.target.value)} placeholder="Введите @имя_канала или URL"/>
                <button onClick={analyzeChannel} disabled={loadingAnalysis || !analysisInput.trim()}>
                  {loadingAnalysis ? <ClipLoader size={15} color={"#fff"} /> : "Анализ"}
                </button>
              </div>
              {loadingAnalysis && <Loading message="Идет анализ канала..."/>}
              {analysisResult && (
                <div className="analysis-results card">
                  <h3>Результаты анализа для: @{analysisResult.message?.includes("для @") ? analysisResult.message.split("@")[1] : channelName}</h3>
                  {analysisResult.is_sample_data && <p className="warning-text">Внимание: Реальные посты канала не были получены. Используются примеры.</p>}
                  <p><strong>Проанализировано постов:</strong> {analysisResult.analyzed_posts_count}</p>
                  <div className="result-section"><h4>Основные темы:</h4><ul>{analysisResult.themes.map((theme, i) => <li key={i}>{theme}</li>)}</ul></div>
                  <div className="result-section"><h4>Стили/форматы:</h4><ul>{analysisResult.styles.map((style, i) => <li key={i}>{style}</li>)}</ul></div>
                  {analysisResult.analyzed_posts_sample && analysisResult.analyzed_posts_sample.length > 0 && (
                    <div className="result-section"><h4>Примеры постов:</h4><div className="post-samples">{analysisResult.analyzed_posts_sample.map((post, i) => <div key={i} className="sample-post"><pre>{post}</pre></div>)}</div></div>
                  )}
                  <p><strong>Рекомендованное время для постинга:</strong> {analysisResult.best_posting_time}</p>
                </div>
              )}
            </section>
          )}

          {currentView === 'suggestions' && (
            <section id="suggested-ideas">
              <h2>Предложенные Идеи {channelName ? `для @${channelName}` : '(выберите канал)'}</h2>
              {(isGeneratingIdeas) && <Loading message="Генерация идей..."/>}
              {!(isGeneratingIdeas) && suggestedIdeas.length === 0 && <p>Идей пока нет. Выберите канал и сгенерируйте их на вкладке "План" или "Анализ".</p>}
              <div className="ideas-grid">
                {suggestedIdeas.map(idea => (
                  <div key={idea.id} className="idea-card card">
                    <h4>{idea.topic_idea}</h4>
                    <p><strong>Стиль:</strong> {idea.format_style}</p>
                    <p><strong>Канал:</strong> @{idea.channel_name}</p>
                    <button onClick={() => handleDetailIdea(idea)} className="action-button">Детализировать</button>
                  </div>
                ))}
              </div>
            </section>
          )}

          {currentView === 'plan' && (
             <section id="content-plan">
                <h2>Генерация Контент-Плана {channelName ? `для @${channelName}`: ''}</h2>
                {!channelName && <p className="warning-text">Для генерации плана выберите или проанализируйте канал.</p>}
                {channelName && !analysisResult && !loadingAnalysis && <p className="warning-text">Данные анализа для канала @{channelName} отсутствуют. <button onClick={() => {setAnalysisInput(channelName); analyzeChannel();}} className="action-button inline">Проанализировать</button></p>}
                {channelName && analysisResult && (
                  <>
                    <div className="input-group">
                        <label htmlFor="plan-period">Период (дней):</label>
                        <input type="number" id="plan-period" value={planPeriod} onChange={(e) => setPlanPeriod(Math.max(1, parseInt(e.target.value,10) || 7))} min="1" max="30"/>
                        <button onClick={generateIdeas} disabled={isGeneratingIdeas || !analysisResult.themes?.length || !analysisResult.styles?.length}>
                            {isGeneratingIdeas ? <ClipLoader size={15} color="#fff"/> : "Сгенерировать План"}
                        </button>
                    </div>
                    {generatedPlan.length > 0 && (
                        <div className="plan-results card">
                            <h3>Сгенерированный план:</h3>
                            <ul>{generatedPlan.map(item => (<li key={item.day}><strong>День {item.day}:</strong> {item.topic_idea} <em>({item.format_style})</em></li>))}</ul>
                        </div>
                    )}
                  </>
                )}
            </section>
          )}
          
          {(currentView === 'details' || currentView === 'edit') && (selectedIdeaForDetail || editingPost) && (
            <section id="post-details">
              <h2>{editingPost ? 'Редактирование Поста' : 'Детализация Идеи'} для @{editingPost?.channel_name || selectedIdeaForDetail?.channel_name}</h2>
              {isGeneratingPostDetails && <Loading message="Загрузка деталей поста..."/>}
              {!isGeneratingPostDetails && (
                <div className="post-editor-grid">
                    <div className="post-text-editor card">
                        <div className="form-group">
                            <label htmlFor="post-topic">Тема/Идея:</label>
                            <input id="post-topic" type="text" value={currentPostTopic} onChange={e => setCurrentPostTopic(e.target.value)} />
                        </div>
                        <div className="form-group">
                            <label htmlFor="post-format">Формат/Стиль:</label>
                            <input id="post-format" type="text" value={currentPostFormat} onChange={e => setCurrentPostFormat(e.target.value)} />
                        </div>
                        <div className="form-group">
                            <label htmlFor="post-date">Дата публикации:</label>
                            <input id="post-date" type="date" value={currentPostDate} onChange={e => setCurrentPostDate(e.target.value)} />
                        </div>
                        <div className="form-group">
                            <label htmlFor="post-text">Текст поста:</label>
                            <textarea id="post-text" value={detailedPostText} onChange={e => setDetailedPostText(e.target.value)} rows={15}></textarea>
                        </div>
                        <button onClick={handleSaveOrUpdatePost} className="action-button primary" disabled={isSavingPost}>
                            {isSavingPost ? <ClipLoader size={15} color="#fff"/> : (editingPost ? 'Обновить Пост' : 'Сохранить Пост')}
                        </button>
                    </div>
                    <div className="post-image-selector card">
                        <h4>Предложенные изображения:</h4>
                        <div className="suggested-images-grid">
                            {suggestedImages.map(img => (
                                <div key={img.id || img.url} 
                                     className={`suggested-image-item ${selectedImage?.url === img.url ? 'selected' : ''}`}
                                     onClick={() => handleImageSelection(img)}>
                                    <img src={img.preview_url || img.url} alt={img.alt || 'suggested'} />
                                </div>
                            ))}
                             {suggestedImages.length === 0 && !isGeneratingPostDetails && <p>Нет предложенных изображений.</p>}
                        </div>
                        <hr />
                        <h4>Выбранное изображение:</h4>
                        {selectedImage ? (
                            <div className="selected-image-preview">
                                <img src={selectedImage.url} alt={selectedImage.alt || 'selected'} />
                                <p>{selectedImage.alt}</p>
                                {selectedImage.author && <p>Автор: <a href={selectedImage.author_url || '#'} target="_blank" rel="noopener noreferrer">{selectedImage.author}</a> ({selectedImage.source})</p>}
                            </div>
                        ) : <p>Изображение не выбрано.</p>}
                        <ImageUploader userId={userId} onImageUploaded={handleCustomImageUpload} />
                    </div>
                </div>
              )}
            </section>
          )}

          {currentView === 'posts' && (
            <section id="saved-posts">
              <h2>Сохраненные Посты {channelName ? `для @${channelName}` : '(все каналы)'}</h2>
              {loadingSavedPosts && <Loading message="Загрузка постов..."/>}
              {!loadingSavedPosts && savedPosts.length === 0 && <p>Сохраненных постов пока нет.</p>}
              <div className="posts-grid">
                {savedPosts.map(post => (
                  <div key={post.id} className="post-card card">
                    <h3>{post.topic_idea}</h3>
                    <p><strong>Канал:</strong> @{post.channel_name || 'N/A'}</p>
                    <p><strong>Дата:</strong> {new Date(post.target_date).toLocaleDateString()}</p>
                    <p className="post-final-text-preview">{post.final_text.substring(0, 100)}...</p>
                    {post.selected_image_data?.url && (
                        <img src={post.selected_image_data.preview_url || post.selected_image_data.url} alt={post.selected_image_data.alt || "post image"} className="post-card-image-preview"/>
                    )}
                    <div className="post-actions">
                        <button onClick={() => startEditingPost(post)} className="action-button">Редактировать</button>
                        <button onClick={() => deletePost(post.id)} className="action-button danger">Удалить</button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {currentView === 'calendar' && (
            <section id="calendar-view">
              <h2>Календарь Публикаций {channelName ? `для @${channelName}` : '(все каналы)'}</h2>
              <div className="calendar-controls">
                <button onClick={goToPrevMonth} className="action-button">&lt; Пред.</button>
                <h3>{currentMonth.toLocaleString('default', { month: 'long', year: 'numeric' })}</h3>
                <button onClick={goToNextMonth} className="action-button">След. &gt;</button>
              </div>
              <div className="calendar-grid">
                 {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map(dayName => <div key={dayName} className="calendar-header">{dayName}</div>)}
                {calendarDays.map((day, index) => (
                  <CalendarDayComponent key={index} day={day} onEditPost={startEditingPost} onDeletePost={deletePost} />
                ))}
              </div>
            </section>
          )}
        </main>
        
        <footer>
          <button className="action-button" onClick={() => setShowSubscription(true)}>Управление подпиской</button>
        </footer>

        {showSubscription && <SubscriptionWidget userId={userId} onClose={() => setShowSubscription(false)} />}
      </div>
    </SimpleErrorBoundary>
  );
}

export default App;
