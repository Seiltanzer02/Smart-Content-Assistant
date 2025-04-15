import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import { TelegramAuth } from './components/TelegramAuth';

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
type ViewType = 'analyze' | 'suggestions' | 'plan' | 'details';

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

  // Быстрая инициализация без localStorage
  useEffect(() => {
    setTimeout(() => {
      setLoading(false);
    }, 500);
  }, []);

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
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при анализе канала');
      console.error('Ошибка при анализе:', err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Функция для генерации идей на основе анализа
  const generateIdeas = async () => {
    if (!analysisResult) {
      setError("Сначала выполните анализ канала");
      return;
    }

    setIsGeneratingIdeas(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await axios.post('/generate-plan', {
        themes: analysisResult.themes,
        styles: analysisResult.styles,
        period_days: 7,
        channel_name: channelName
      });
      
      // Обработка и очистка полученных данных от маркдаун форматирования
      const processedPlan = response.data.plan.map((item: any, index: number) => {
        // Извлекаем тему и формат из строки, удаляя markdown-форматирование и лишние символы
        let topic = item.topic_idea || '';
        let format = item.format_style || '';
        
        // Очищаем от маркдаун-разметки и других элементов форматирования
        topic = topic.replace(/\*\*/g, '').replace(/"/g, '').trim();
        format = format.replace(/\*\*/g, '').replace(/"/g, '').replace(/\(/g, '').replace(/\)/g, '').trim();
        
        return {
          id: `idea-${Date.now()}-${index}`,
          created_at: new Date().toISOString(),
          channel_name: channelName,
          topic_idea: topic,
          format_style: format,
          day: item.day || index + 1
        };
      });
      
      setSuggestedIdeas(processedPlan);
      setSuccess('Идеи успешно сгенерированы');
      setCurrentView('suggestions');
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при генерации идей');
      console.error('Ошибка при генерации идей:', err);
    } finally {
      setIsGeneratingIdeas(false);
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

  // Функция для детализации идеи
  const handleDetailIdea = async (idea: SuggestedIdea) => {
    setSelectedIdea(idea);
    setIsDetailGenerating(true);
    setDetailedPost(null);
    setError(null);
    setSuccess(null);
    setCurrentView('details');

    try {
      // Запрос на детализацию идеи через API
      const response = await axios.post('/generate-post-details', {
        topic_idea: idea.topic_idea,
        format_style: idea.format_style,
        channel_name: idea.channel_name
      });

      // Обработка полученных данных
      if (response.data) {
        setDetailedPost({
          post_text: response.data.generated_text || 'Не удалось сгенерировать текст поста.',
          images: response.data.found_images.map((img: any) => ({
            url: img.regular_url || img.preview_url,
            alt: img.description,
            author: img.author_name,
            author_url: img.author_url
          })) || []
        });
        setSuccess('Детализация успешно создана');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при детализации идеи');
      console.error('Ошибка при детализации:', err);
    } finally {
      setIsDetailGenerating(false);
    }
  };

  // Возврат к списку идей
  const backToIdeas = () => {
    setCurrentView('suggestions');
    setSelectedIdea(null);
    setDetailedPost(null);
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
            onClick={() => setCurrentView('plan')} 
            className={`action-button ${currentView === 'plan' ? 'active' : ''}`}
            disabled={!channelName}
          >
            План
          </button>
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
              {suggestedIdeas.length > 0 ? (
                <div className="plan-display">
                  <h3>План публикаций для канала @{channelName}</h3>
                  <ul className="plan-list">
                    {suggestedIdeas
                      .sort((a, b) => (a.day || 0) - (b.day || 0))
                      .map((idea) => (
                        <li key={idea.id} className="plan-list-item-clickable" onClick={() => handleDetailIdea(idea)}>
                          <strong>День {idea.day}:</strong> {idea.topic_idea} <em>({idea.format_style})</em>
                        </li>
                      ))}
                  </ul>
                </div>
              ) : (
                <p>Сначала сгенерируйте идеи на вкладке "Идеи"</p>
              )}
            </div>
          )}

          {/* Вид детализации */}
          {currentView === 'details' && selectedIdea && (
            <div className="view post-view">
              <button onClick={backToIdeas} className="back-button">
                ← Назад к идеям
              </button>
              
              <h2>Детализация идеи</h2>
              
              <div className="post-source-info">
                <p><strong>Тема:</strong> {selectedIdea.topic_idea}</p>
                <p><strong>Формат:</strong> {selectedIdea.format_style}</p>
                <p><strong>День:</strong> {selectedIdea.day}</p>
                <p><strong>Канал:</strong> @{selectedIdea.channel_name}</p>
              </div>
              
              {isDetailGenerating && (
                <div className="loading-indicator">
                  <div className="loading-spinner"></div>
                  <p>Генерация детализации...</p>
                </div>
              )}
              
              {detailedPost && !isDetailGenerating && (
                <div className="generated-content">
                  <div className="post-text-section">
                    <h3>Текст поста:</h3>
                    <textarea 
                      className="post-textarea" 
                      value={detailedPost.post_text} 
                      readOnly 
                    />
                  </div>
                  
                  {detailedPost.images && detailedPost.images.length > 0 && (
                    <div className="image-section">
                      <h3>Изображения:</h3>
                      <div className="image-thumbnails">
                        {detailedPost.images.map((img, index) => (
                          <div key={index} className="image-item">
                            <img 
                              src={img.url} 
                              alt={img.alt || "Изображение для поста"} 
                              className="thumbnail"
                            />
                            {img.author && (
                              <span className="image-author">{img.author}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
              
              {!detailedPost && !isDetailGenerating && (
                <button
                  onClick={() => handleDetailIdea(selectedIdea)}
                  className="action-button generate-button"
                >
                  Сгенерировать детализацию
                </button>
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
