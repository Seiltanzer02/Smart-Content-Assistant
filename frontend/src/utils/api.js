// API конфигурация для приложения
export const API_BASE_URL = '';

// Получение заголовков авторизации
export const getAuthHeaders = () => {
  const telegramUserId = localStorage.getItem('telegramUserId');
  
  return {
    'X-Telegram-User-Id': telegramUserId || ''
  };
};

// Функция для сохранения изображения
export const saveImage = async (imageData) => {
  try {
    const response = await fetch(`${API_BASE_URL}/save-image`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify(imageData)
    });
    
    if (!response.ok) {
      throw new Error(`Ошибка HTTP: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Ошибка при сохранении изображения:', error);
    throw error;
  }
};

// Функция для получения сохраненных изображений
export const getSavedImages = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/images`, {
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      throw new Error(`Ошибка HTTP: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Ошибка при получении изображений:', error);
    throw error;
  }
};

// Функция для создания поста
export const createPost = async (postData) => {
  try {
    const response = await fetch(`${API_BASE_URL}/posts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify(postData)
    });
    
    if (!response.ok) {
      throw new Error(`Ошибка HTTP: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Ошибка при создании поста:', error);
    throw error;
  }
}; 