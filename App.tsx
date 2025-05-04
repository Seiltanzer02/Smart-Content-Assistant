import React, { useState, useEffect } from 'react';
import './App.css';
import SubscriptionWidget from './SubscriptionWidget';
import DirectPremiumStatus from './DirectPremiumStatus';

// Определяем типы для данных приложения
type ViewType = 'analyze' | 'suggestions' | 'plan' | 'details' | 'calendar' | 'edit' | 'posts';

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

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<ViewType>('analyze');
  const [showSubscription, setShowSubscription] = useState(false);
  
  // Получение ID пользователя при монтировании компонента
  useEffect(() => {
    // Проверяем Telegram WebApp для получения user_id
    if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
      const telegramUserId = String(window.Telegram.WebApp.initDataUnsafe.user.id);
      console.log(`[App] Получен user_id из Telegram WebApp: ${telegramUserId}`);
      setUserId(telegramUserId);
      setIsAuthenticated(true);
      setLoading(false);
    } else {
      console.log('[App] Не удалось получить user_id из Telegram WebApp');
      // Можно добавить запасной вариант получения ID, например из localStorage или URL-параметров
      setLoading(false);
    }
  }, []);
  
  // Компонент для пользователей, прошедших аутентификацию
  const AuthenticatedApp = () => {
    return (
      <div className="authenticated-app">
        {/* Показ статуса подписки вверху страницы */}
        <DirectPremiumStatus userId={userId} />
        
        {/* Основной контент приложения */}
        {/* ... остальное содержимое ... */}
      </div>
    );
  };

  // Основной интерфейс
  return (
    <div className="app-container">
      <header className="app-header">
        <div className="logo">Smart Content Assistant</div>
        
        {/* Компактное отображение статуса подписки */}
        {userId && <DirectPremiumStatus userId={userId} showDebug={false} />}
        
        <div className="header-icons">
          {/* Кнопка для управления подпиской */}
          <button
            className="icon-button"
            onClick={() => setShowSubscription(!showSubscription)}
            title="Управление подпиской"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
            </svg>
          </button>
          {/* ... остальные кнопки ... */}
        </div>
      </header>

      {/* Виджет управления подпиской */}
      {showSubscription && userId && (
        <SubscriptionWidget userId={userId} isActive={true} />
      )}
      
      {/* Основной контент */}
      <main className="app-main">
        {loading ? (
          <Loading message="Загрузка приложения..." />
        ) : isAuthenticated ? (
          <AuthenticatedApp />
        ) : (
          <div className="login-container">
            <p>Для использования приложения необходимо авторизоваться</p>
            <p>Откройте это приложение через Telegram</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App; 