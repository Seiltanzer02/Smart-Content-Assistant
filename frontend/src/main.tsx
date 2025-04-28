import React from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import WebApp from '@twa-dev/sdk'
import axios from 'axios'

// Добавляем определение типов для Telegram
declare global {
  interface Window {
    Telegram?: {
      WebApp?: any;
    };
  }
}

// Инициализация обработчика данных для получения платежей
const initDataHandler = async (data: string) => {
  try {
    // Предполагаем, что data - это JSON-строка, переданная от Telegram WebApp
    const parsedData = JSON.parse(data);
    
    if (parsedData.type === 'subscribe') {
      // Получаем данные пользователя из WebApp
      const user = window.Telegram?.WebApp?.initDataUnsafe?.user || {};
      
      // Отправляем запрос на создание подписки
      await axios.post('/telegram/webhook', {
        data: data,
        user: user
      });
      
      // Обновляем статус подписки - обновит UI автоматически при следующем запросе
      console.log('Подписка успешно обработана');
      
      // Показываем уведомление пользователю (если доступно)
      if (window.Telegram?.WebApp?.showPopup) {
        window.Telegram.WebApp.showPopup({
          title: 'Успех',
          message: 'Ваша подписка успешно активирована!',
          buttons: [{type: 'ok'}]
        });
      }
    }
  } catch (error) {
    console.error('Ошибка при обработке данных от Telegram:', error);
    
    // Показываем уведомление об ошибке (если доступно)
    if (window.Telegram?.WebApp?.showPopup) {
      window.Telegram.WebApp.showPopup({
        title: 'Ошибка',
        message: 'Не удалось обработать платеж. Пожалуйста, попробуйте позже.',
        buttons: [{type: 'ok'}]
      });
    }
  }
};

const container = document.getElementById('root')

console.log('main.tsx: Инициализация приложения');

// Проверяем доступность Telegram WebApp - сначала нативный, потом SDK
if (window.Telegram && window.Telegram.WebApp) {
  console.log('main.tsx: Найден window.Telegram.WebApp - используем нативный WebApp');
  
  // Если есть нативный WebApp, вызываем его метод ready
  if (typeof window.Telegram.WebApp.ready === 'function') {
    console.log('main.tsx: Вызываем window.Telegram.WebApp.ready()');
    window.Telegram.WebApp.ready();
  }
  
  // Устанавливаем обработчик получения данных от Telegram
  if (typeof window.Telegram.WebApp.onEvent === 'function') {
    window.Telegram.WebApp.onEvent('viewportChanged', () => {
      console.log('Viewport изменился');
    });
    
    // Слушаем событие mainButtonClicked для обработки платежей
    window.Telegram.WebApp.onEvent('mainButtonClicked', () => {
      console.log('Клик по главной кнопке');
    });
    
    // Важно: добавляем слушателя для обработки данных от Telegram
    window.Telegram.WebApp.onEvent('data', (data: string) => {
      console.log('Получены данные от Telegram:', data);
      initDataHandler(data);
    });
  }
} else if (WebApp) {
  console.log('main.tsx: Используем WebApp из @twa-dev/sdk');
  console.log('main.tsx: WebApp объект:', WebApp);
  console.log('main.tsx: Вызываем WebApp.ready()');
  WebApp.ready(); // Сообщаем Telegram, что приложение готово
  console.log('main.tsx: WebApp.ready() вызван');
  
  // Устанавливаем обработчик событий для SDK версии
  WebApp.onEvent('viewportChanged', () => {
    console.log('Viewport изменился (SDK)');
  });
  
  WebApp.onEvent('mainButtonClicked', () => {
    console.log('Клик по главной кнопке (SDK)');
  });
  
  // Слушаем событие data для SDK версии
  // @ts-ignore - событие data может быть недоступно в типах, но поддерживается в SDK
  WebApp.onEvent('data', (data: string) => {
    console.log('Получены данные от Telegram (SDK):', data);
    initDataHandler(data);
  });
} else {
  console.warn('main.tsx: WebApp не найден ни в window.Telegram, ни в @twa-dev/sdk');
}

if (container) {
  const root = createRoot(container)
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
} else {
  console.error('Failed to find the root element')
}
