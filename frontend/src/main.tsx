import React from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import WebApp from '@twa-dev/sdk'
import axios from 'axios'

// Устанавливаем заголовок csrf для всех запросов axios
axios.defaults.withCredentials = true;
axios.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

// Определяем типы для Telegram для TypeScript
declare global {
  interface Window {
    Telegram?: {
      WebApp?: any; // Используем any для избежания проблем с типизацией
    };
    INJECTED_USER_ID?: string;
  }
}

// Инициализация Telegram WebApp
console.log('Инициализация Telegram WebApp...');

try {
  // Проверяем доступность Telegram WebApp
  const telegramWebApp = window.Telegram?.WebApp;
  
  if (telegramWebApp) {
    console.log('Найден window.Telegram.WebApp - используем нативный WebApp');
    telegramWebApp.ready();
    telegramWebApp.expand();
    
    // Используем приведение типов для вызова методов
    const anyWebApp = telegramWebApp as any;
    if (typeof anyWebApp.setHeaderColor === 'function') {
      anyWebApp.setHeaderColor('#2481cc');
    }
  } 
  // Резервный вариант с использованием SDK
  else if (WebApp) {
    console.log('Используем полифилл WebApp из @twa-dev/sdk');
    WebApp.ready();
    WebApp.expand();
    WebApp.setHeaderColor('#2481cc');
  } 
  else {
    console.warn('Telegram WebApp не найден. Приложение может работать некорректно в браузере.');
  }
} catch (error) {
  console.error('Ошибка при инициализации Telegram WebApp:', error);
}

// Инициализация React приложения
const rootElement = document.getElementById('root');
if (rootElement) {
  const root = createRoot(rootElement);
  
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
} else {
  console.error('Элемент с id "root" не найден!');
}
