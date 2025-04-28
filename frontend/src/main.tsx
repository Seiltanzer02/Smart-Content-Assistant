import React from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import WebApp from '@twa-dev/sdk'

// Добавляем определение типов для Telegram
declare global {
  interface Window {
    Telegram?: {
      WebApp?: any;
    };
  }
}

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
} else if (WebApp) {
  console.log('main.tsx: Используем WebApp из @twa-dev/sdk');
console.log('main.tsx: WebApp объект:', WebApp);
  console.log('main.tsx: Вызываем WebApp.ready()');
  WebApp.ready(); // Сообщаем Telegram, что приложение готово
  console.log('main.tsx: WebApp.ready() вызван');
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
