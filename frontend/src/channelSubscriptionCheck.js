/**
 * Модуль для проверки подписки пользователя на Telegram-канал
 * 
 * Используется в Mini App для проверки подписки пользователя на указанный канал
 * перед предоставлением доступа к функционалу приложения.
 */

// Импортируем WebApp из SDK для случаев, когда он не доступен в window.Telegram
import WebAppSDK from '@twa-dev/sdk';

/**
 * Проверяет подписку на канал и закрывает приложение, если пользователь не подписан
 * @returns {Promise<boolean>} true если пользователь имеет доступ, false в противном случае
 */
export async function checkChannelSubscription() {
  try {
    // Определяем источник WebApp
    const telegramWebApp = window.Telegram?.WebApp;
    const webAppSDK = window.WebApp || WebAppSDK;
    
    // Получаем данные пользователя
    let userId = '';
    let chatId = '';
    
    if (telegramWebApp) {
      // Вариант 1: Используем window.Telegram.WebApp
      const initData = telegramWebApp.initData || '';
      const initDataURI = decodeURIComponent(initData);
      
      // Парсим initData для получения user_id и chat_id
      const params = new URLSearchParams(initDataURI);
      const user = params.get('user') ? JSON.parse(params.get('user')) : null;
      userId = user?.id || '';
      chatId = params.get('chat_id') || userId; // Если chat_id отсутствует, используем user_id
    } else if (webAppSDK) {
      // Вариант 2: Используем WebApp из @twa-dev/sdk
      try {
        const initDataObj = webAppSDK.initDataUnsafe || {};
        userId = initDataObj.user?.id || '';
        chatId = initDataObj.chat_instance || initDataObj.chat?.id || userId;
      } catch (e) {
        console.error('Ошибка при получении данных из WebApp SDK:', e);
      }
    }
    
    if (!userId) {
      console.error('Не удалось получить идентификатор пользователя Telegram');
      return false;
    }
    
    console.log(`Проверка подписки для пользователя ${userId} в чате ${chatId}`);
    
    // Запрос на проверку подписки
    const response = await fetch('/api/check-app-access', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-User-Id': userId,
        'X-Telegram-Chat-Id': chatId
      },
      body: JSON.stringify({
        user_id: userId,
        chat_id: chatId
      })
    });
    
    if (!response.ok) {
      console.error('Ошибка при проверке подписки на канал:', response.status);
      return true; // В случае ошибки лучше не блокировать доступ
    }
    
    const result = await response.json();
    
    if (!result.access_granted) {
      console.log('Доступ не предоставлен: пользователь не подписан на канал');
      
      // Закрываем мини-приложение
      if (telegramWebApp?.close) {
        telegramWebApp.close();
      } else if (webAppSDK?.close) {
        webAppSDK.close();
      }
      
      return false;
    }
    
    console.log('Доступ предоставлен: пользователь подписан на канал');
    return true;
  } catch (error) {
    console.error('Ошибка при проверке подписки на канал:', error);
    return true; // В случае ошибки лучше не блокировать доступ
  }
}

/**
 * Инициализация проверки подписки при загрузке приложения
 */
export function initSubscriptionCheck() {
  // Проверяем, что мы в Telegram Web App
  if (window.Telegram?.WebApp) {
    console.log('Инициализация проверки подписки на канал через window.Telegram.WebApp');
    // Дожидаемся полной инициализации Telegram Web App
    if (document.readyState === 'complete') {
      checkChannelSubscription();
    } else {
      window.addEventListener('load', checkChannelSubscription);
    }
  } else if (typeof window.WebApp !== 'undefined' || typeof WebAppSDK !== 'undefined') {
    // Используем WebApp из @twa-dev/sdk
    console.log('Инициализация проверки подписки на канал через @twa-dev/sdk');
    if (document.readyState === 'complete') {
      checkChannelSubscription();
    } else {
      window.addEventListener('load', checkChannelSubscription);
    }
  } else {
    console.warn('Telegram Web App не обнаружен, проверка подписки не будет выполнена');
  }
}

// Устанавливаем задержку для проверки подписки, чтобы дать время приложению загрузиться
setTimeout(() => {
  console.log('Запуск проверки подписки на канал с задержкой');
  initSubscriptionCheck();
}, 1000);

// Также выполняем проверку после полной загрузки страницы
window.addEventListener('load', () => {
  console.log('Страница загружена, проверяем подписку на канал');
  initSubscriptionCheck();
}); 