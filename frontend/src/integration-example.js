/**
 * Пример интеграции проверки подписки на канал в основной файл приложения
 * 
 * Импортируйте и используйте этот код в основном файле вашего приложения
 * (например, в App.js или index.js)
 */

// Вариант 1: Автоматическая инициализация (рекомендуется)
// При таком импорте проверка начнется автоматически при загрузке
import './channelSubscriptionCheck';

// Вариант 2: Ручная инициализация
// Импортируем функции
import { checkChannelSubscription, initSubscriptionCheck } from './channelSubscriptionCheck';

// Пример интеграции в компонент React
function App() {
  // Используем React useEffect для запуска проверки при монтировании компонента
  React.useEffect(() => {
    // Проверка подписки при загрузке компонента
    async function checkAccess() {
      const hasAccess = await checkChannelSubscription();
      if (hasAccess) {
        console.log('Пользователь имеет доступ к приложению');
      } else {
        console.log('Пользователь не имеет доступа к приложению');
      }
    }
    
    checkAccess();
    
    // Альтернативный вариант: просто вызываем функцию инициализации
    // initSubscriptionCheck();
  }, []);
  
  return (
    <div className="app">
      {/* Ваше приложение */}
    </div>
  );
}

// Пример для Vue.js
/*
export default {
  name: 'App',
  mounted() {
    // Проверяем подписку при монтировании компонента
    checkChannelSubscription().then(hasAccess => {
      if (hasAccess) {
        console.log('Пользователь имеет доступ к приложению');
      } else {
        console.log('Пользователь не имеет доступ к приложению');
      }
    });
  }
}
*/

// Для JavaScript (без фреймворка)
document.addEventListener('DOMContentLoaded', () => {
  // Либо используем нашу функцию инициализации
  initSubscriptionCheck();
  
  // Либо вызываем проверку напрямую
  // checkChannelSubscription();
}); 