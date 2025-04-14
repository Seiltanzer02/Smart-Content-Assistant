import React from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import WebApp from '@twa-dev/sdk'

const container = document.getElementById('root')

console.log('main.tsx: Инициализация приложения');
console.log('main.tsx: WebApp объект:', WebApp);

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

console.log('main.tsx: Вызов WebApp.ready()');
WebApp.ready() // Сообщаем Telegram, что приложение готово
console.log('main.tsx: WebApp.ready() вызван');
