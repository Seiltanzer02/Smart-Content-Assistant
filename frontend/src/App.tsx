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
type ViewType = 'analyze' | 'suggestions' | 'plan';

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
      
      setSuggestedIdeas(response.data.plan.map((item: PlanItem) => ({
        id: `idea-${Date.now()}-${Math.random()}`,
        created_at: new Date().toISOString(),
        channel_name: channelName,
        topic_idea: item.topic_idea,
        format_style: item.format_style,
        day: item.day
      })));
      
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
                      <button className="action-button small">Детализировать</button>
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

          {currentView === 'plan' && (
            <div className="view plan-view">
              <h2>План публикаций</h2>
              <p>Здесь будет отображаться календарь с планом публикаций для канала @{channelName || 'Не выбран'}</p>
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
