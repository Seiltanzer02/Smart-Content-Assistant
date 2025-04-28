import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import WebApp from '@twa-dev/sdk'

const container = document.getElementById('root')

console.log('main.tsx: Инициализация приложения');

// Инициализация Telegram WebApp
const initTelegramApp = () => {
  try {
    // Проверяем, есть ли объект Telegram в window
    if (window.Telegram?.WebApp) {
      console.log('Telegram WebApp API доступен глобально, инициализируем...');
      window.Telegram.WebApp.ready();
    } 
    // Иначе проверяем доступность WebApp из @twa-dev/sdk
    else if (typeof (window as any).WebApp?.ready === 'function') {
      console.log('WebApp API доступен через SDK, инициализируем...');
      (window as any).WebApp.ready();
    } 
    // На случай, если @twa-dev/sdk был загружен, но объект размещен по-другому
    else if (typeof (window as any).TelegramWebApp !== 'undefined') {
      console.log('TelegramWebApp из SDK доступен, инициализируем...');
      (window as any).TelegramWebApp.ready();
    } 
    else {
      console.warn('Telegram WebApp API не обнаружен. Приложение будет работать в автономном режиме.');
    }
  } catch (e) {
    console.error('Ошибка при инициализации Telegram WebApp:', e);
  }
};

// Загрузка SDK Telegram Mini App
const loadTelegramSdk = (): Promise<void> => {
  return new Promise((resolve) => {
    // Если SDK уже загружен, просто возвращаем resolve
    if (window.Telegram?.WebApp || (window as any).WebApp) {
      console.log('Telegram SDK уже загружен');
      resolve();
      return;
    }

    try {
      // Динамическая загрузка SDK
      import('@twa-dev/sdk').then(() => {
        console.log('Telegram SDK загружен динамически');
        resolve();
      }).catch(error => {
        console.error('Ошибка при динамической загрузке Telegram SDK:', error);
        resolve(); // Продолжаем даже при ошибке
      });
    } catch (e) {
      console.error('Ошибка при импорте Telegram SDK:', e);
      resolve(); // Продолжаем даже при ошибке
    }
  });
};

// Запуск приложения после инициализации Telegram
const startApp = () => {
  const rootElement = document.getElementById('root');
  if (rootElement) {
    ReactDOM.createRoot(rootElement).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    );
  } else {
    console.error('Элемент с id "root" не найден!');
  }
};

// Основная функция запуска
async function bootstrapApp() {
  // Загружаем SDK и инициализируем Telegram
  await loadTelegramSdk();
  initTelegramApp();
  
  // Запускаем приложение
  startApp();
}

// Запускаем приложение
bootstrapApp().catch(e => {
  console.error('Ошибка при запуске приложения:', e);
  // Всё равно пытаемся запустить приложение при ошибке
  startApp();
});
