import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
  },
  // Добавляем обработку env переменных
  define: {
    'process.env.VITE_DEBUG_TELEGRAM_WEBAPP': JSON.stringify(process.env.VITE_DEBUG_TELEGRAM_WEBAPP || 'false'),
    'process.env.VITE_TELEGRAM_WEB_APP_VERSION': JSON.stringify(process.env.VITE_TELEGRAM_WEB_APP_VERSION || '8.0'),
  },
  build: {
    sourcemap: true, // включаем для отладки
  },
})
