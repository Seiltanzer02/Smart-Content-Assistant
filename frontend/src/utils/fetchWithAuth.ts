/**
 * Выполняет fetch-запрос с добавлением заголовка авторизации Telegram
 * @param url - URL для запроса
 * @param options - Опции запроса (как в обычном fetch)
 * @returns Promise с результатом fetch
 */
export const fetchWithAuth = (url: string, options: RequestInit = {}): Promise<Response> => {
  // Получаем Telegram WebApp
  const tg = window.Telegram?.WebApp;
  
  // Получаем данные пользователя
  const user = tg?.initDataUnsafe?.user;
  const userId = user?.id;
  
  // Добавляем заголовок с ID пользователя
  const headers = new Headers(options.headers || {});
  if (userId) {
    headers.set('X-Telegram-User-Id', userId.toString());
  }
  
  // Возвращаем fetch с новыми заголовками
  return fetch(url, {
    ...options,
    headers
  });
}; 