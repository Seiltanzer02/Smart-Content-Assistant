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

// Определяем тип для представления
type ViewType = 'analyze' | 'suggestions' | 'plan';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<ViewType>('analyze');
  const [channelName, setChannelName] = useState<string>('');

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
        {/* Навигация */}
        <div className="navigation-buttons">
          <button 
            onClick={() => setCurrentView('analyze')} 
            className={`action-button ${currentView === 'analyze' ? 'active' : ''}`}
          >
            Анализ
          </button>
          <button 
            onClick={() => setCurrentView('suggestions')} 
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
                />
                <button 
                  onClick={() => alert('Функция временно отключена')} 
                  className="action-button"
                >
                  Анализировать
                </button>
              </div>
              <p>Введите имя канала для начала работы.</p>
            </div>
          )}

          {currentView === 'suggestions' && (
            <div className="view suggestions-view">
              <h2>Идеи контента</h2>
              <p>Здесь будут отображаться идеи для канала @{channelName || 'Не выбран'}</p>
            </div>
          )}

          {currentView === 'plan' && (
            <div className="view plan-view">
              <h2>План публикаций</h2>
              <p>Здесь будет отображаться план публикаций для канала @{channelName || 'Не выбран'}</p>
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
