import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import axios from 'axios';
import Calendar from 'react-calendar';
import 'react-calendar/dist/Calendar.css';
import './App.css';
import WebApp from '@twa-dev/sdk'; // <-- РАСКОММЕНТИРОВАЛИ

// --- ТИПЫ --- 

// Переносим SuggestedIdeaResponse в начало
interface SuggestedIdeaResponse {
    id: string;
    created_at: string;
    topic_idea: string;
    format_style: string;
    relative_day: number | null;
    is_detailed: boolean;
}

// Типы для переключения видов
type View = 'analyze' | 'suggestions' | 'plan' | 'editor';

// Тип для значения календаря
type ValuePiece = Date | null;
type CalendarValue = ValuePiece | [ValuePiece, ValuePiece];

// --- Определяем тип для результата анализа --- 
interface AnalysisResult {
  message: string;
  themes: string[]; // Массив строк
  styles: string[]; // Массив строк
  analyzed_posts_sample: string[]; // <--- Добавлено: Примеры постов
  best_posting_time: string; // Пока строка
  analyzed_posts_count: number;
}

// Добавляем тип для элемента плана (дублируем с бэкенда для удобства)
interface PlanItem {
  day: number;
  topic_idea: string;
  format_style: string;
}

// --- ОБНОВЛЕННЫЙ ТИП для найденного изображения (из бэкенда) --- 
interface FoundImage {
  id: string;
  source: string; 
  preview_url: string; 
  regular_url: string;
  description?: string | null;
  author_name?: string | null;
  author_url?: string | null;
}

// --- ОБНОВЛЕННЫЙ ТИП ответа детализации --- 
interface PostDetailsResponse {
  generated_text: string;
  found_images: FoundImage[]; // Используем новый тип
  message: string;
}

// --- ОБНОВЛЕННЫЙ ТИП для сохраненного поста (совпадает с SavedPostResponse из бэка) ---
interface SavedPost {
  id: string; 
  target_date: string; 
  topic_idea: string;
  format_style: string;
  final_text: string; 
  image_url: string | null;
  created_at: string; 
  updated_at: string;
  channel_name: string;
  user_id?: number; // <-- ДОБАВИЛИ user_id (опционально, т.к. старые посты могут его не иметь)
}

// --- ОБНОВЛЕННЫЙ ТИП для создания нового поста ---
interface PostToSave {
  target_date: string;
  topic_idea: string;
  format_style: string;
  final_text: string;
  image_url: string | null;
  channel_name: string;
  // user_id будет добавлен на бэкенде из заголовка
}

// Тип для данных в редакторе
type EditorData = SuggestedIdeaResponse | SavedPost;

// --- КЛЮЧИ для localStorage --- 
const LOCAL_STORAGE_KEYS = {
    VIEW: 'contentApp_currentView',
    CHANNEL: 'contentApp_channelName',
    ANALYSIS: 'contentApp_analysisResult',
    IDEAS: 'contentApp_savedIdeas',
    POSTS: 'contentApp_savedPosts',
};

// Базовый URL API
const API_BASE_URL = 'http://127.0.0.1:8000';

// Тип ответа /upload-image
interface UploadResponse {
    image_url: string;
}

function App() {
  // --- СОСТОЯНИЯ --- 

  // Глобальные
  // Читаем из localStorage при инициализации
  const [currentView, setCurrentView] = useState<View>(() => {
     const savedView = localStorage.getItem(LOCAL_STORAGE_KEYS.VIEW);
     return (savedView as View) || 'analyze'; // По умолчанию 'analyze'
  });
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null); 
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  // НОВОЕ СОСТОЯНИЕ для ID пользователя Telegram
  const [telegramUserId, setTelegramUserId] = useState<number | null>(null);

  // Анализ
  // Читаем из localStorage при инициализации
  const [channelName, setChannelName] = useState<string>(() => 
      localStorage.getItem(LOCAL_STORAGE_KEYS.CHANNEL) || ''
  );
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(() => {
     const savedAnalysis = localStorage.getItem(LOCAL_STORAGE_KEYS.ANALYSIS);
     try {
       return savedAnalysis ? JSON.parse(savedAnalysis) : null;
     } catch (e) {
       console.error("Ошибка парсинга analysisResult из localStorage", e);
       localStorage.removeItem(LOCAL_STORAGE_KEYS.ANALYSIS); // Удаляем некорректные данные
       return null;
     }
  });

  // Генерация Идей (ДОБАВЛЯЕМ localStorage)
  const [savedIdeas, setSavedIdeas] = useState<SuggestedIdeaResponse[]>(() => {
    const saved = localStorage.getItem(LOCAL_STORAGE_KEYS.IDEAS);
    try {
      return saved ? JSON.parse(saved) : [];
    } catch (e) {
      console.error("Ошибка парсинга savedIdeas из localStorage", e);
      localStorage.removeItem(LOCAL_STORAGE_KEYS.IDEAS);
      return [];
    }
  });
  const [isLoadingIdeas, setIsLoadingIdeas] = useState<boolean>(false);

  // План (ДОБАВЛЯЕМ localStorage)
  const [savedPosts, setSavedPosts] = useState<SavedPost[]>(() => {
    const saved = localStorage.getItem(LOCAL_STORAGE_KEYS.POSTS);
    try {
      // Доп. проверка: убедимся, что это массив (на случай некорректных данных)
      const parsed = saved ? JSON.parse(saved) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      console.error("Ошибка парсинга savedPosts из localStorage", e);
      localStorage.removeItem(LOCAL_STORAGE_KEYS.POSTS);
      return [];
    }
  });
  const [isLoadingPosts, setIsLoadingPosts] = useState<boolean>(false);
  const [calendarValue, setCalendarValue] = useState<CalendarValue>(new Date());
  // НОВОЕ СОСТОЯНИЕ для поста, выбранного в календаре
  const [selectedDatePost, setSelectedDatePost] = useState<SavedPost | null>(null);

  // Редактор Поста
  const [currentDataForEditor, setCurrentDataForEditor] = useState<EditorData | null>(null);
  const [isEditingMode, setIsEditingMode] = useState<boolean>(false); // true - редактируем SavedPost, false - новая идея PlanItem
  const [editorFormData, setEditorFormData] = useState<Partial<SavedPost>>({}); // Данные формы редактора
  const [foundImages, setFoundImages] = useState<FoundImage[]>([]); // Найденные картинки для редактора
  const [isGeneratingDetails, setIsGeneratingDetails] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false); // Для блокировки кнопок Save/Update/Delete
  // Добавляем состояние для индикатора загрузки изображения
  const [isUploadingImage, setIsUploadingImage] = useState<boolean>(false);
  // Добавляем ref для скрытого инпута файла
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const [selectedPreviewIndex, setSelectedPreviewIndex] = useState<number>(0); // Индекс выбранного превью

  // --- ЭФФЕКТЫ --- 

  // Инициализация Telegram WebApp и получение User ID
  useEffect(() => {
    try {
      WebApp.ready(); // Сообщаем Telegram, что приложение готово
      const user = WebApp.initDataUnsafe?.user;
      if (user?.id) {
        console.log('Telegram User ID:', user.id);
        setTelegramUserId(user.id);

        // Настраиваем глобальные заголовки axios
        axios.defaults.headers.common['X-Telegram-User-Id'] = user.id.toString();

      } else {
        console.warn('Не удалось получить Telegram User ID.');
        setError("Не удалось идентифицировать пользователя Telegram. Функционал может быть ограничен.");
        // Удаляем заголовок, если ID не получен
        delete axios.defaults.headers.common['X-Telegram-User-Id'];
      }
      // Дополнительные настройки WebApp (цвет хедера, кнопка назад и т.д.) - можно добавить позже
      // WebApp.setHeaderColor('secondary_bg_color');
      // WebApp.BackButton.show();
      // WebApp.BackButton.onClick(() => { /* обработка нажатия кнопки назад */ });
    } catch (e) {
      console.error('Ошибка инициализации Telegram WebApp SDK:', e);
      setError("Ошибка при инициализации интерфейса Telegram.");
      // Удаляем заголовок в случае ошибки
      delete axios.defaults.headers.common['X-Telegram-User-Id'];
    }

    // Очистка при размонтировании (если нужно)
    // return () => {
    //   WebApp.BackButton.offClick(/* ... */);
    // };
  }, []); // Пустой массив зависимостей - выполнить один раз при монтировании

  // Сохранение currentView в localStorage при изменении
  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEYS.VIEW, currentView);
  }, [currentView]);

  // Сохранение channelName в localStorage при изменении
  useEffect(() => {
     localStorage.setItem(LOCAL_STORAGE_KEYS.CHANNEL, channelName);
  }, [channelName]);

  // Сохранение analysisResult в localStorage при изменении
  useEffect(() => {
     if (analysisResult) {
         localStorage.setItem(LOCAL_STORAGE_KEYS.ANALYSIS, JSON.stringify(analysisResult));
      } else {
         localStorage.removeItem(LOCAL_STORAGE_KEYS.ANALYSIS);
     }
  }, [analysisResult]);

  // ДОБАВЛЯЕМ: Сохранение savedIdeas в localStorage при изменении
  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEYS.IDEAS, JSON.stringify(savedIdeas));
  }, [savedIdeas]);

  // ДОБАВЛЯЕМ: Сохранение savedPosts в localStorage при изменении
  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEYS.POSTS, JSON.stringify(savedPosts));
  }, [savedPosts]);

  // Загрузка сохраненных постов при переключении на 'plan' ИЛИ изменении channelName
  useEffect(() => {
    if (currentView === 'plan' && channelName) { // <-- Добавили && channelName
      fetchSavedPosts(channelName); // <-- Передаем channelName
    }
  }, [currentView, channelName]); // <-- Добавили channelName в зависимости

  // Загрузка сохраненных идей при переключении на 'suggestions' ИЛИ изменении channelName
  useEffect(() => {
    if (currentView === 'suggestions' && channelName) { // <-- Добавили && channelName
      fetchSavedIdeas(channelName); // <-- Передаем channelName
    }
     // Сбрасываем идеи, если ушли с вкладки или очистили канал
     if (currentView !== 'suggestions' || !channelName) {
        setSavedIdeas([]);
     } 
  }, [currentView, channelName]); // <-- Добавили channelName в зависимости

  // Заполнение формы редактора при изменении currentDataForEditor
  useEffect(() => {
    if (currentDataForEditor) {
      // Проверяем, есть ли поле final_text, чтобы отличить SavedPost от SuggestedIdeaResponse
      if ('final_text' in currentDataForEditor && typeof currentDataForEditor.final_text === 'string') { // Редактируем SavedPost
        setIsEditingMode(true);
        setEditorFormData({
          id: currentDataForEditor.id,
          target_date: currentDataForEditor.target_date,
          topic_idea: currentDataForEditor.topic_idea,
          format_style: currentDataForEditor.format_style,
          final_text: currentDataForEditor.final_text,
          image_url: currentDataForEditor.image_url || '',
          channel_name: currentDataForEditor.channel_name, // Берем из редактируемого поста
        });
        setFoundImages([]);
      } else { // Новая идея SuggestedIdeaResponse
        setIsEditingMode(false);
        const idea = currentDataForEditor as SuggestedIdeaResponse; // Утверждаем тип
        const initialDate = new Date();
        // Используем relative_day из типа SuggestedIdeaResponse
        if (idea.relative_day) {
          initialDate.setDate(initialDate.getDate() + idea.relative_day - 1);
        }
        setEditorFormData({
          target_date: initialDate.toISOString().split('T')[0],
          topic_idea: idea.topic_idea,
          format_style: idea.format_style,
          final_text: '', 
          image_url: '', 
          channel_name: channelName, // Берем текущий канал из состояния
        });
        setFoundImages([]);
      }
    } else {
      setEditorFormData({});
      setIsEditingMode(false);
      setFoundImages([]);
    }
  }, [currentDataForEditor, channelName]); // Добавили channelName в зависимости!

  // Сброс сообщений об успехе/ошибке через некоторое время
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    if (successMessage || error) {
      timer = setTimeout(() => {
        setSuccessMessage(null);
        setError(null);
      }, 5000); // Скрывать через 5 секунд
    }
    return () => clearTimeout(timer);
  }, [successMessage, error]);


  // --- ВЫНОСИМ ХУКИ из renderPlanView --- 

  // Мемоизированный набор дат с постами для календаря
  const savedPostDatesSet = useMemo(() => {
      return new Set(savedPosts.map(p => p.target_date));
  }, [savedPosts]);

  // Контент для ячеек календаря (теперь в основном скоупе компонента)
  const tileContent = useCallback(({ date, view }: { date: Date; view: string }) => {
      if (view === 'month') {
          // --- ИСПРАВЛЕНИЕ: Форматируем дату в ЛОКАЛЬНОМ времени --- 
          const year = date.getFullYear();
          // getMonth() возвращает 0-11, добавляем 1
          const month = (date.getMonth() + 1).toString().padStart(2, '0'); 
          const day = date.getDate().toString().padStart(2, '0');
          const dateString = `${year}-${month}-${day}`;
          // --- КОНЕЦ ИСПРАВЛЕНИЯ ---
          
          // Старая версия с UTC:
          // const dateString = date.toISOString().split('T')[0]; 
          
          if (savedPostDatesSet.has(dateString)) {
              // Добавляем title к элементу-точке
              return <div key={dateString} className="calendar-dot" title="На эту дату запланирован пост"></div>; 
          }
      }
      return null;
  }, [savedPostDatesSet]); // Зависимость от мемоизированного Set

  // --- ФУНКЦИИ API --- 

  // Запрос анализа
  const handleAnalyze = async () => {
    if (!channelName) return setError('Введите имя канала');
    setIsLoading(true); setError(null); setSuccessMessage(null);
    // При новом анализе сбрасываем старые идеи и результат
    setAnalysisResult(null); 
    setSavedIdeas([]); // Сброс идей при новом анализе
    try {
      const response = await axios.post<AnalysisResult>(`${API_BASE_URL}/analyze`, { username: channelName });
      setAnalysisResult(response.data);
      setSuccessMessage('Анализ завершен. Теперь можно генерировать идеи.');
    } catch (err: any) { handleError(err, 'Анализ канала') } 
    finally { setIsLoading(false); }
  };

  // ОБНОВЛЕНО: Запрос генерации и сохранения идей с ПРЕДУПРЕЖДЕНИЕМ и каналом
  const handleGenerateAndSaveIdeas = async (period: number = 7) => {
    if (!analysisResult || !channelName) { // Добавляем проверку channelName
       setError('Сначала выполните анализ канала.');
       return;
    }

    const userConfirmed = window.confirm(
        "Это действие перезапишет все существующие предложенные идеи. Продолжить?"
    );
    if (!userConfirmed) {
        setSuccessMessage("Генерация идей отменена.");
        return; // Прерываем, если пользователь нажал "Отмена"
    }

    setIsLoading(true); setError(null); setSuccessMessage(null);
    try {
      const response = await axios.post<SuggestedIdeaResponse[]>(`${API_BASE_URL}/generate-plan`, {
        themes: analysisResult.themes,
        styles: analysisResult.styles,
        period_days: period,
        channel_name: channelName // <-- ПЕРЕДАЕМ ИМЯ КАНАЛА
      });
      setSavedIdeas(response.data);
      setSuccessMessage(`Сгенерировано и сохранено ${response.data.length} идей.`);
      setCurrentView('suggestions'); // Переключаем на вкладку Идеи после генерации
    } catch (err: any) { handleError(err, 'Генерация и сохранение идей') } 
    finally { setIsLoading(false); }
  };

  // ОБНОВЛЕНО: Загрузка идей с фильтром по каналу (принимает channelName)
  const fetchSavedIdeas = async (channelNameToFetch: string) => { // <-- Принимаем аргумент
    if (!channelNameToFetch) {
        setSavedIdeas([]);
        return; 
    }
    setIsLoadingIdeas(true); setError(null);
    try {
      const response = await axios.get<SuggestedIdeaResponse[]>(`${API_BASE_URL}/ideas`, {
          params: { channel_name: channelNameToFetch } // <-- Используем аргумент
      });
      setSavedIdeas(response.data); 
    } catch (err: any) { handleError(err, 'Загрузка предложенных идей') } 
    finally { setIsLoadingIdeas(false); }
  };

  // Запрос генерации деталей (текст + картинки)
  const handleGenerateDetailsClick = async () => {
    if (!editorFormData.topic_idea || !editorFormData.format_style) return setError('Нет данных для генерации деталей');
    if (!analysisResult?.analyzed_posts_sample) return setError('Примеры постов не найдены. Выполните анализ заново.');
    
    setIsLoading(true); setError(null); setSuccessMessage(null);
    setIsGeneratingDetails(true); setFoundImages([]);
    setEditorFormData(prev => ({ ...prev, final_text: '', image_url: '' })); // Сброс текста и картинки

    try {
      const response = await axios.post<PostDetailsResponse>(`${API_BASE_URL}/generate-post-details`, {
        topic_idea: editorFormData.topic_idea,
        format_style: editorFormData.format_style,
        post_samples: analysisResult.analyzed_posts_sample,
      }, {
        params: { 
          channel_name: channelName 
        }
      });
      setEditorFormData(prev => ({ 
          ...prev, 
          final_text: response.data.generated_text || "",
          // Автовыбор первой картинки, если есть
          image_url: response.data.found_images?.[0]?.regular_url || '' 
      }));
      setFoundImages(response.data.found_images || []);
      if (response.data.message) setSuccessMessage(response.data.message); // Показываем доп. сообщение

    } catch (err: any) { handleError(err, 'Генерация деталей поста') } 
    finally { setIsLoading(false); setIsGeneratingDetails(false); }
  };

  // Загрузка сохраненных постов (принимает channelName)
  const fetchSavedPosts = async (channelNameToFetch: string) => { // <-- Принимаем аргумент
    if (!channelNameToFetch) {
      setSavedPosts([]); // Очищаем посты если канала нет
      return;
    }
    setIsLoadingPosts(true); setError(null);
    try {
      // Предполагаем, что бэкенд поддерживает фильтрацию постов по channel_name
      const response = await axios.get<SavedPost[]>(`${API_BASE_URL}/posts`, {
        params: { channel_name: channelNameToFetch } // <-- Передаем параметр
      });
      setSavedPosts(response.data);
    } catch (err: any) { handleError(err, 'Загрузка сохраненных постов') }
    finally { setIsLoadingPosts(false); }
  };

  // Сохранение НОВОГО поста
  const handleSavePost = async () => {
    // Добавляем проверку на наличие target_date в данных формы
    if (isEditingMode || !editorFormData.final_text || !editorFormData.target_date) {
        setError('Недостаточно данных для сохранения поста.');
        return; 
    }

    // --- ПРЕДУПРЕЖДЕНИЕ О ЗАНЯТОЙ ДАТЕ --- 
    const targetDate = editorFormData.target_date;
    if (savedPostDatesSet.has(targetDate)) {
        const userConfirmed = window.confirm(
            `На дату ${formatDate(targetDate)} уже запланирован пост. Вы уверены, что хотите добавить еще один?`
        );
        if (!userConfirmed) {
            setSuccessMessage("Сохранение отменено."); // Информируем пользователя
            return; // Прерываем сохранение
        }
    }
    // --- КОНЕЦ ПРОВЕРКИ --- 

    setIsLoading(true); setError(null); setSuccessMessage(null); setIsSaving(true);

    const postToSave: PostToSave = {
      target_date: targetDate,
      topic_idea: editorFormData.topic_idea || 'Без темы',
      format_style: editorFormData.format_style || 'Без стиля',
      final_text: editorFormData.final_text,
      image_url: editorFormData.image_url || null,
      channel_name: channelName, // <-- ДОБАВЛЕНО: Передаем текущее имя канала
    };

    try {
      const response = await axios.post<SavedPost>(`${API_BASE_URL}/posts`, postToSave);
      // Обновляем Set дат ПОСЛЕ успешного сохранения
      setSavedPosts(prev => [...prev, response.data].sort((a, b) => a.target_date.localeCompare(b.target_date)));
      setSuccessMessage('Пост успешно сохранен!');
      setCurrentView('plan');
      setCurrentDataForEditor(null);
    } catch (err: any) { 
        handleError(err, 'Сохранение поста'); 
        // Важно сбросить флаги загрузки/сохранения даже в случае ошибки
        setIsLoading(false); 
        setIsSaving(false);
    } 
  };

  // Обновление СУЩЕСТВУЮЩЕГО поста
  const handleUpdatePost = async () => {
    if (!isEditingMode || !editorFormData.id || !editorFormData.target_date) return setError('Нет данных для обновления');

    setIsLoading(true); setError(null); setSuccessMessage(null); setIsSaving(true);

    const postToUpdate: Partial<SavedPost> = {
      target_date: editorFormData.target_date,
      topic_idea: editorFormData.topic_idea,
      format_style: editorFormData.format_style,
      final_text: editorFormData.final_text,
      image_url: editorFormData.image_url || null,
      channel_name: channelName, // <-- ДОБАВЛЕНО: Передаем текущее имя канала
    };

    try {
      const response = await axios.put<SavedPost>(`${API_BASE_URL}/posts/${editorFormData.id}`, postToUpdate);
      setSavedPosts(prev => 
        prev.map(p => p.id === editorFormData.id ? response.data : p)
          .sort((a, b) => a.target_date.localeCompare(b.target_date))
      );
      // Обновляем выбранный пост в деталях календаря, если он был выбран
      if(selectedDatePost && selectedDatePost.id === editorFormData.id) {
        setSelectedDatePost(response.data);
      }
      setSuccessMessage('Пост успешно обновлен!');
      setCurrentView('plan');
      setCurrentDataForEditor(null);
    } catch (err: any) { handleError(err, 'Обновление поста') } 
    finally { setIsLoading(false); setIsSaving(false); }
  };

  // Удаление поста (изменяем аргумент на объект поста для консистентности)
  const handleDeletePost = async (postToDelete: SavedPost) => { // <-- Принимаем SavedPost
    if (!postToDelete.id) return setError('ID поста не найден для удаления');
    
    if (!window.confirm("Вы уверены, что хотите удалить этот пост?")) {
      return;
    }

    setIsLoading(true); setError(null); setSuccessMessage(null); setIsSaving(true);
    
    try {
      await axios.delete(`${API_BASE_URL}/posts/${postToDelete.id}`);
      setSavedPosts(prev => prev.filter(p => p.id !== postToDelete.id));
      setSuccessMessage('Пост успешно удален!');
      // Если удаляли из редактора, то закрываем его
      if (currentDataForEditor && currentDataForEditor.id === postToDelete.id) {
          setCurrentView('plan');
          setCurrentDataForEditor(null);
      }
      // Если удаляли из деталей календаря, сбрасываем детали
      if (selectedDatePost && selectedDatePost.id === postToDelete.id) {
        setSelectedDatePost(null);
      }
    } catch (err: any) { handleError(err, 'Удаление поста') } 
    finally { setIsLoading(false); setIsSaving(false); }
  };

  // --- ОБРАБОТЧИКИ ИНТЕРФЕЙСА --- 

  // Навигация
  const navigateTo = (view: View) => {
    // Сбрасываем ошибки/сообщения при переходе
    // setError(null);
    // setSuccessMessage(null);
    
    // Сбрасываем редактор при уходе с него
    if (currentView === 'editor' && view !== 'editor') {
        setCurrentDataForEditor(null);
    }
      setCurrentView(view);
  };

  // Клик "Детализировать" в списке идей (тип параметра изменен)
  const handleDetailSuggestion = (idea: SuggestedIdeaResponse) => {
    setCurrentDataForEditor(idea);
    navigateTo('editor');
  };

  // Клик "Редактировать" в списке сохраненных постов
  const handleEditSavedPost = (post: SavedPost) => {
    setCurrentDataForEditor(post);
    navigateTo('editor');
  };

  // Изменение данных в форме редактора
  const handleEditorFormChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setEditorFormData(prev => ({ ...prev, [name]: value }));
  };
  
  // Обработчик выбора изображения
  const handleSelectImage = (imageUrl: string, index?: number) => {
    setEditorFormData(prev => ({ ...prev, image_url: imageUrl }));
    if (index !== undefined) {
      setSelectedPreviewIndex(index);
    } else {
      // Находим индекс изображения с указанным URL
      const newIndex = foundImages.findIndex(img => img.regular_url === imageUrl);
      if (newIndex !== -1) {
        setSelectedPreviewIndex(newIndex);
      }
    }
  };

  // Обработчики для навигации по галерее
  const handlePrevImage = () => {
    if (foundImages.length > 0) {
      const newIndex = selectedPreviewIndex > 0 ? selectedPreviewIndex - 1 : foundImages.length - 1;
      setSelectedPreviewIndex(newIndex);
      setEditorFormData(prev => ({ ...prev, image_url: foundImages[newIndex].regular_url }));
    }
  };

  const handleNextImage = () => {
    if (foundImages.length > 0) {
      const newIndex = selectedPreviewIndex < foundImages.length - 1 ? selectedPreviewIndex + 1 : 0;
      setSelectedPreviewIndex(newIndex);
      setEditorFormData(prev => ({ ...prev, image_url: foundImages[newIndex].regular_url }));
    }
  };

  // Обработка ошибок
  const handleError = (err: any, context: string) => {
    console.error(`Ошибка (${context}):`, err);
    const message = err.response?.data?.detail || err.message || `Произошла ошибка: ${context}`;
    setError(message);
    // WebApp.showAlert(`Ошибка: ${message}`); // Если используем TWA SDK
  };

  // --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ --- 
  const formatDate = (dateString: string | Date | undefined): string => {
    if (!dateString) return "";
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) return "Неверная дата";
        return date.toLocaleDateString('ru-RU');
    } catch { return "Ошибка даты"}
  };
  const getDayAbbreviation = (locale: string | undefined, date: Date): string => {
    return date.toLocaleDateString(locale, { weekday: 'short' }).substring(0, 2).toUpperCase();
  };

  // --- КОМПОНЕНТЫ РЕНДЕРИНГА --- 

  // Навигация
  const renderNavigation = () => (
    <div className="navigation-buttons">
      <button onClick={() => navigateTo('analyze')} className={`action-button ${currentView === 'analyze' ? 'active' : ''}`}>Анализ</button>
      {/* Кнопка Идей доступна, если есть имя канала */}
      <button onClick={() => navigateTo('suggestions')} className={`action-button ${currentView === 'suggestions' ? 'active' : ''}`} disabled={!channelName}>Идеи</button>
      {/* Кнопка План доступна, если есть имя канала */} 
      <button onClick={() => navigateTo('plan')} className={`action-button ${currentView === 'plan' ? 'active' : ''}`} disabled={!channelName}>План</button>
    </div>
  );

  // Сообщения об успехе/ошибке
  const renderFeedbackMessages = () => (
    <>
      {error && <p className="error-message">Ошибка: {error}</p>}
      {successMessage && <p className="success-message">{successMessage}</p>}
    </>
  );

  // 1. Вид "Анализ"
  const renderAnalyzeView = () => (
    <div className="view analyze-view view-container-animated">
      <h2>Анализ Telegram-канала</h2>
      <div className="input-container">
        <input
          type="text"
          className="channel-input"
          value={channelName}
          onChange={(e) => setChannelName(e.target.value.replace(/^@/, ''))}
          placeholder="Введите username канала (без @)"
          disabled={isLoading}
          title="Введите username Telegram-канала (например, durov)"
        />
        <button onClick={handleAnalyze} disabled={isLoading} className="action-button analyze-button-in-view" title="Запустить анализ тем, стилей и постов канала">
          {isLoading ? 'Анализ...' : 'Анализировать'}
        </button>
      </div>
      {isLoading && <div className="loading-indicator"><div className="loading-spinner"></div><p>Идет анализ...</p></div>}
      {analysisResult && (
          <div className="results-container">
              <h3>Результаты анализа:</h3>
              <p><strong>Темы:</strong> {analysisResult.themes.join(', ')}</p>
              <p><strong>Стили:</strong> {analysisResult.styles.join(', ')}</p>
              {/* Кнопка для перехода к генерации */} 
              <button 
                onClick={() => handleGenerateAndSaveIdeas()} 
                disabled={isLoading || isLoadingIdeas}
                className="action-button generate-ideas-button"
                title="Сгенерировать и сохранить список идей для постов на основе результатов анализа"
              >
                 {isLoadingIdeas ? 'Генерация идей...' : 'Сгенерировать и Сохранить Идеи'}
              </button>
          </div>
      )}
    </div>
  );

  // 2. Вид "Идеи"
  const renderSuggestionsView = () => (
    <div className="view suggestions-view view-container-animated">
      <h2>Предложенные Идеи</h2>
      {channelName && <p className="current-channel">Канал: <strong>@{channelName}</strong></p>}
      
      {/* Кнопка обновления УБРАНА */} 
      
      {isLoadingIdeas ? (
        <div className="loading-indicator"><div className="loading-spinner"></div><p>Загрузка идей...</p></div>
      ) : !channelName ? (
         <p>Введите имя канала на вкладке "Анализ", чтобы увидеть сохраненные или сгенерировать новые идеи.</p>
      ) : savedIdeas.length > 0 ? (
        <ul className="ideas-list">
          {savedIdeas.map((idea) => (
            <li key={idea.id} className="idea-item">
              <div className="idea-text">
                <span className="idea-topic">{idea.topic_idea}</span>
                <span className="idea-style">({idea.format_style})</span>
              </div>
              <button onClick={() => handleDetailSuggestion(idea)} className="action-button detail-button" title="Перейти к созданию поста на основе этой идеи">Детализировать</button>
            </li>
          ))}
        </ul>
      ) : (
        <p>Для канала @{channelName} еще нет сохраненных идей. Вы можете сгенерировать их на вкладке "Анализ" после выполнения анализа.</p>
      )}
    </div>
  );

  // 3. Вид "План" (Календарь + Список) - Использует хуки извне
  const renderPlanView = () => (
    <div className="view plan-view view-container-animated">
        <h2>План контента</h2>
        <div className="plan-content">
            <div className="calendar-section">
                <h3>Календарь</h3>
                <Calendar
                    value={calendarValue}
                    locale="ru-RU"
                    tileContent={tileContent}
                    formatShortWeekday={getDayAbbreviation}
                    onClickDay={handleCalendarDayClick}
                />
            </div>

            {/* === ПЕРЕМЕЩЕННЫЙ БЛОК: Детали выбранного поста === */}
            {selectedDatePost && (
                <div id="calendar-post-details" className="calendar-post-details-section">
                    <h3>Детали поста на {formatDate(selectedDatePost.target_date)}</h3>
                    <div className="post-details-content">
                        <p><strong>Тема:</strong> {selectedDatePost.topic_idea}</p>
                        <p><strong>Стиль:</strong> {selectedDatePost.format_style}</p>
                        
                        {/* --- ИЗМЕНЕНИЕ: Логика отображения картинки --- */}
                        {(() => {
                            // Определяем, какой URL использовать
                            let imageUrlToShow = selectedDatePost.image_url;
                            // Если мы в режиме редактирования, и редактируемый пост совпадает с выбранным в календаре
                            if (isEditingMode && currentDataForEditor && 'id' in currentDataForEditor && currentDataForEditor.id === selectedDatePost.id) {
                                // Берем URL из данных формы редактора (может быть пустым, если картинку убрали)
                                imageUrlToShow = editorFormData.image_url || null;
                            }
                            
                            // Рендерим блок только если есть URL для показа
                            return imageUrlToShow ? (
                                <div className="post-details-image-preview">
                                    <img src={imageUrlToShow} alt="Изображение поста" />
                                </div>
                            ) : null;
                        })()}
                        {/* --- КОНЕЦ ИЗМЕНЕНИЯ --- */}

                        <div className="post-actions">
                            <button onClick={() => handleEditSavedPost(selectedDatePost)} className="edit-button" title="Редактировать этот пост">Редактировать</button>
                            <button 
                                // Используем новый обработчик, передавая весь объект поста
                                onClick={() => handleDeletePostClick(selectedDatePost)} 
                                className="delete-button"
                                disabled={isSaving} 
                                title="Удалить этот пост"
                            >
                                Удалить
                            </button>
                        </div>
                    </div>
                </div>
            )}
            {/* === КОНЕЦ ПЕРЕМЕЩЕННОГО БЛОКА === */}

            <div className="posts-section">
                <h3>Сохраненные посты</h3>
                {isLoadingPosts ? (
                    <div className="loading-indicator"><div className="loading-spinner"></div><p>Загрузка постов...</p></div>
                ) : savedPosts.length > 0 ? (
                    <ul className="posts-list">
                        {savedPosts.map((post) => (
                            <li key={post.id} className="post-item">
                                <span className="post-date">{formatDate(post.target_date)}:</span>
                                <span className="post-topic"> [{post.format_style}] {post.topic_idea}</span>
                                <div className="post-actions">
                                    <button onClick={() => handleEditSavedPost(post)} className="edit-button" title="Редактировать этот пост">Ред.</button>
                                    {/* Используем новый обработчик */} 
                                    <button 
                                       onClick={() => handleDeletePostClick(post)} 
                                       className="delete-button"
                                       disabled={isSaving} 
                                       title="Удалить этот пост"
                                    >
                                        Удал.
                                    </button>
                                </div>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p>Нет сохраненных постов.</p>
                )}
            </div>
        </div>
    </div>
  );

  // 4. Вид "Редактор"
  const renderEditorView = () => {
    if (!currentDataForEditor) {
      return <div className="view editor-view"><p>Нет данных для отображения в редакторе.</p></div>;
    }

    const postTitle = isEditingMode ? "Редактирование поста" : "Создание поста из идеи";

    // Обработчик кнопки "Убрать картинку"
    const handleRemoveImage = () => {
        setEditorFormData(prev => ({ ...prev, image_url: '' })); // Ставим пустую строку
    };

    return (
      <div className="view editor-view view-container-animated">
        <h2>{postTitle}</h2>

        {/* Добавляем кнопку Отмена/Назад */} 
        <button 
          onClick={() => {
            setCurrentDataForEditor(null); // Сброс редактора
            // Возвращаемся на предыдущий осмысленный вид
            navigateTo(isEditingMode ? 'plan' : 'suggestions'); 
          }}
          className="back-button"
          disabled={isLoading || isSaving || isGeneratingDetails}
        >
          &larr; Отмена / Назад
        </button>

        <div className="editor-form">
          {/* Поля формы */} 
          <div className="form-row">
             <div className="form-group">
                <label htmlFor="target_date">Дата:</label>
                <input
                  type="date"
                  id="target_date"
                  name="target_date"
                  value={editorFormData.target_date || ''}
                  onChange={handleEditorFormChange}
                  required
                  disabled={isLoading}
                />
             </div>
             {/* Можно добавить отображение/редактирование Идеи и Стиля, но пока оставим как есть */}
              <div className="form-group display-only">
                   <span>Идея: {editorFormData.topic_idea}</span>
               </div>
               <div className="form-group display-only">
                   <span>Стиль: {editorFormData.format_style}</span>
               </div>
          </div>

          {/* Кнопка генерации деталей (только для новых) */} 
          {!isEditingMode && !editorFormData.final_text && (
              <button onClick={handleGenerateDetailsClick} disabled={isLoading || isGeneratingDetails} className='action-button' title="Сгенерировать текст поста и найти подходящие изображения с помощью ИИ">
                  {isGeneratingDetails ? 'Генерация...' : 'Сгенерировать текст и картинки'}
              </button>
          )}
          {isGeneratingDetails && <div className="loading-indicator"><div className="loading-spinner"></div><p>Идет генерация...</p></div>}

          {/* Текст поста */} 
          {(editorFormData.final_text || isGeneratingDetails) && (
            <div className="form-group">
              <label htmlFor="final_text">Текст поста:</label>
              <textarea
                id="final_text"
                name="final_text"
                value={editorFormData.final_text || ''}
                onChange={handleEditorFormChange}
                rows={10}
                required
                disabled={isLoading}
              />
            </div>
          )}

          {/* --- БЛОК РАБОТЫ С ИЗОБРАЖЕНИЯМИ --- */} 
          <div className="form-group image-section">
            <label>Изображение:</label>
            
            {/* 1. Выбор из найденных (если есть и картинка еще не выбрана) */} 
            {foundImages.length > 0 && !editorFormData.image_url && (
              <div className="image-gallery">
                <div className="image-thumbnails">
                  {foundImages.map((img, index) => (
                    <div key={img.id} className="image-item">
                      <img
                        src={img.preview_url}
                        alt="Изображение" 
                        className={`thumbnail ${editorFormData.image_url === img.regular_url ? 'selected' : ''}`}
                        onClick={() => handleSelectImage(img.regular_url, index)}
                      />
                    </div>
                  ))}
                </div>
                <div className="image-preview-gallery">
                  {foundImages.length > 0 && (
                    <div className="selected-image-preview">
                      <img 
                        src={editorFormData.image_url || foundImages[selectedPreviewIndex].regular_url} 
                        alt="Изображение" 
                        className="preview-image" 
                      />
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 2. Предпросмотр и кнопка "Убрать" (если есть URL) */} 
            {editorFormData.image_url && (
              <div className="image-preview">
                <label style={{ display: 'block', marginBottom: '5px' }}>Выбрано:</label>
                <div className="image-preview-container">
                  <div className="preview-controls">
                    <button type="button" onClick={handlePrevImage} className="nav-button prev-button">◀</button>
                    <img src={editorFormData.image_url} alt="Изображение" className="selected-image" />
                    <button type="button" onClick={handleNextImage} className="nav-button next-button">▶</button>
                  </div>
                  <div className="image-actions">
                    <button onClick={handleRemoveImage} className="remove-image-button" title="Убрать изображение" disabled={isUploadingImage}>
                      &times;
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* 3. Кнопка "Загрузить свое" (если картинка НЕ выбрана) */} 
            {!editorFormData.image_url && (
               <div className="upload-section">
                    <input 
                        type="file"
                        accept="image/*" 
                        ref={fileInputRef}
                        onChange={handleFileInputChange}
                        style={{ display: 'none' }} // Скрываем стандартный инпут
                        disabled={isUploadingImage} 
                    />
                    <button 
                        onClick={handleUploadButtonClick}
                        disabled={isUploadingImage}
                        className='action-button upload-button'
                        title="Загрузить собственное изображение с устройства"
                    >
                        {isUploadingImage ? <div className="loading-spinner" style={{ width: '20px', height: '20px', borderColor: 'white', borderLeftColor: 'transparent', display:'inline-block', verticalAlign: 'middle' }}></div> : 'Загрузить свое изображение'}
                    </button>
               </div>
            )}
            
          </div>
          {/* --- КОНЕЦ БЛОКА РАБОТЫ С ИЗОБРАЖЕНИЯМИ --- */} 

          {/* Кнопки действий */} 
          <div className="editor-actions">
            {isEditingMode ? (
              <>
                <button onClick={handleUpdatePost} disabled={isLoading || isSaving || !editorFormData.final_text} className='action-button update' title="Сохранить изменения в этом посте">
                  {isSaving ? 'Обновление...' : 'Обновить пост'}
                </button>
                <button 
                    onClick={() => {
                         // --- ИСПРАВЛЕНИЕ LINTER ERROR ---
                         // Передаем currentDataForEditor (тип SavedPost), а не editorFormData (тип Partial<SavedPost>)
                         if (currentDataForEditor && 'id' in currentDataForEditor) {
                             handleDeletePost(currentDataForEditor as SavedPost); // Утверждаем тип для уверенности
                         } else {
                             setError("Не удалось получить данные поста для удаления из редактора");
                         }
                         // --- КОНЕЦ ИСПРАВЛЕНИЯ ---
                     }}
                    disabled={isLoading || isSaving} 
                    className='action-button delete'
                 >
                  {isSaving ? 'Удаление...' : 'Удалить пост'}
                </button>
              </>
            ) : (
              // Кнопка "Сохранить" активна только если есть текст
              editorFormData.final_text && (
                <button onClick={handleSavePost} disabled={isLoading || isSaving} className='action-button save' title="Сохранить новый пост в плане">
                  {isSaving ? 'Сохранение...' : 'Сохранить новый пост'}
                </button>
              )
            )}
          </div>
      </div>
      </div>
  );
  };

  // Обработчик клика по кнопке "Редактировать" сохраненный пост
  const handleEditPost = (post: SavedPost) => {
    setCurrentDataForEditor(post);
    setCurrentView('editor');
  };

  // Обработчик клика по кнопке "Создать пост" для идеи
  const handleCreatePostFromIdea = (idea: SuggestedIdeaResponse) => {
    setCurrentDataForEditor(idea);
    setCurrentView('editor');
  };
  
  // НОВЫЙ ОБРАБОТЧИК для кнопки удаления поста из списка/деталей календаря
  const handleDeletePostClick = (post: SavedPost) => {
      if (post.id) {
          // --- ИСПРАВЛЕНИЕ LINTER ERROR ---
          handleDeletePost(post); // Передаем весь объект post
          // --- КОНЕЦ ИСПРАВЛЕНИЯ ---
      } else {
          setError('Не удалось получить ID поста для удаления');
      }
  };

  // НОВЫЙ: Обработчик клика по кнопке "Загрузить изображение"
  const handleUploadButtonClick = () => {
    // Имитируем клик по скрытому инпуту файла
    fileInputRef.current?.click();
  };

  // НОВЫЙ: Обработчик изменения в инпуте файла
  const handleFileInputChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Сбрасываем значение инпута, чтобы можно было выбрать тот же файл снова
    event.target.value = ''; 

    setIsUploadingImage(true);
    setError(null);
    setSuccessMessage(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post<UploadResponse>(`${API_BASE_URL}/upload-image`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      // Обновляем URL картинки в форме редактора
      setEditorFormData(prev => ({ ...prev, image_url: response.data.image_url }));
      setSuccessMessage('Изображение успешно загружено!');
    } catch (err: any) {
      handleError(err, 'Загрузка изображения');
    } finally {
      setIsUploadingImage(false);
    }
  };

  // --- ОБРАБОТЧИКИ ИНТЕРФЕЙСА --- 

  // НОВЫЙ ОБРАБОТЧИК клика по дню в календаре
  const handleCalendarDayClick = (value: Date) => {
    // Форматируем кликнутую дату так же, как в tileContent и target_date
    const year = value.getFullYear();
    const month = (value.getMonth() + 1).toString().padStart(2, '0');
    const day = value.getDate().toString().padStart(2, '0');
    const clickedDateString = `${year}-${month}-${day}`;

    // Ищем пост на эту дату
    const postOnDate = savedPosts.find(post => post.target_date === clickedDateString);

    // Обновляем состояние:
    // - Если нашли пост и он не тот, что уже выбран -> выбираем его
    // - Если нашли пост и он УЖЕ выбран -> снимаем выбор (null)
    // - Если не нашли пост -> снимаем выбор (null)
    setSelectedDatePost(prevSelected => 
        postOnDate && prevSelected?.id !== postOnDate.id ? postOnDate : null
    );

    // Опционально: можно скроллить к деталям поста, если они появились
    // const detailsElement = document.getElementById('calendar-post-details');
    // if (postOnDate && detailsElement) {
    //   detailsElement.scrollIntoView({ behavior: 'smooth' });
    // }
  };

  // --- ОСНОВНОЙ РЕНДЕР --- 
  const renderCurrentView = () => {
    // Добавим проверку на наличие telegramUserId перед рендерингом основного контента
    if (telegramUserId === null && !error) {
      // Можно показать индикатор загрузки или сообщение, пока получаем ID
      return <div className="loading-indicator"><div className="loading-spinner"></div><p>Инициализация пользователя...</p></div>;
    } 
    // Если есть ошибка (включая ошибку получения ID), отображаем её
    // if (error) {
    //   return <p className="error-message">Ошибка: {error}</p>; // Сообщение об ошибке уже рендерится отдельно
    // }

    // Если ID получен (или произошла ошибка, но мы все равно показываем интерфейс)
    switch (currentView) {
      case 'analyze': return renderAnalyzeView();
      case 'suggestions': return renderSuggestionsView();
      case 'plan': return renderPlanView();
      case 'editor': return renderEditorView();
      default: return renderAnalyzeView(); // По умолчанию
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
      <h1>Smart Content Assistant</h1>
      </header>
      
      {/* Сообщения */} 
      {renderFeedbackMessages()}

      <main className="app-main">
        {/* Показываем навигацию только если пользователь идентифицирован (или если решили показывать всегда) */} 
        {telegramUserId !== null && renderNavigation()}
        <div className="view-container">
          {renderCurrentView()} 
        </div>
      </main>
      <footer className="app-footer">
        {(isLoading || isLoadingPosts || isLoadingIdeas || isSaving || isGeneratingDetails) && <div className="loading-indicator">Загрузка...</div>}
      </footer>
    </div>
  );
}

export default App;
