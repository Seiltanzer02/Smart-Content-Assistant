/**
 * Функции для работы с аутентификацией пользователя
 */

/**
 * Получает ID пользователя из localStorage
 * @returns ID пользователя или null, если пользователь не авторизован
 */
export const getUserId = (): string | null => {
  return localStorage.getItem('telegramUserId');
};

/**
 * Сохраняет ID пользователя в localStorage
 * @param userId ID пользователя
 */
export const setUserId = (userId: string): void => {
  localStorage.setItem('telegramUserId', userId);
};

/**
 * Очищает данные аутентификации пользователя
 */
export const clearAuthData = (): void => {
  localStorage.removeItem('telegramUserId');
};

/**
 * Проверяет, авторизован ли пользователь
 * @returns true, если пользователь авторизован, иначе false
 */
export const isAuthenticated = (): boolean => {
  return !!getUserId();
}; 