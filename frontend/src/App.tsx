import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './App.css';
import { TelegramAuth } from './components/TelegramAuth';
import { v4 as uuidv4 } from 'uuid';
import { Toaster, toast } from 'react-hot-toast';
import { ClipLoader } from 'react-spinners';

// Определяем базовый URL API
// Так как фронтенд и API находятся на одном хостинге, используем пустой путь
const API_BASE_URL = '';

// Настраиваем базовый URL для axios
axios.defaults.baseURL = API_BASE_URL;

// Конфигурация axios для запросов API
axios.interceptors.request.use(config => {
  // Получаем ID пользователя из localStorage
  const telegramUserId = localStorage.getItem('telegramUserId');
  
  // Добавляем заголовок с ID пользователя ко всем запросам
  if (telegramUserId) {
    config.headers['X-Telegram-User-Id'] = telegramUserId;
  }
  
  // Логирование запросов в консоль при разработке
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    console.log('API Request:', {
      url: config.url,
      method: config.method,
      data: config.data,
      headers: config.headers
    });
  }
  
  return config;
}, error => Promise.reject(error));

// Добавляем перехватчик ответов для отладки
axios.interceptors.response.use(response => {
  // Логирование ответов в консоль при разработке
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    console.log('API Response:', {
      status: response.status,
      data: response.data,
      headers: response.headers
    });
  }
  return response;
}, error => {
  // Логирование ошибок
  console.error('API Error:', error.response || error.message);
  return Promise.reject(error);
});

// --- ДОБАВЛЕНО: Вспомогательная функция для ключей localStorage ---
const getUserSpecificKey = (baseKey: string, userId: string | null): string | null => {
  if (!userId) return null; // Не работаем с localStorage без ID пользователя
  return `${userId}_${baseKey}`;
};
// --- КОНЕЦ ДОБАВЛЕНИЯ ---

// --- ДАЛЕЕ ПРОДОЛЖАЕТСЯ СУЩЕСТВУЮЩИЙ КОД ---

function App() {
  // ... existing code ...

  return (
    <div className="App">
      {/* ... existing JSX ... */}
      <footer>
        {/* ... existing footer content ... */}
      </footer>
    </div>
  );
}

export default App;
