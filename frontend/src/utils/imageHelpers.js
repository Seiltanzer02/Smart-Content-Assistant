/**
 * Функции-помощники для работы с изображениями
 */

/**
 * Подготавливает объект изображения для API, добавляя недостающие поля
 * @param {Object} image - Исходный объект изображения
 * @returns {Object} - Обработанный объект изображения
 */
export const prepareImageForAPI = (image) => {
  if (!image) return null;
  
  // Генерируем уникальный ID, если он отсутствует
  const timestamp = Date.now();
  const randomId = Math.random().toString(36).substring(2, 10);
  
  return {
    ...image,
    id: image.id || `img-${timestamp}-${randomId}`,
    url: image.url,
    preview_url: image.preview_url || image.url,
    alt: image.alt || 'Изображение для поста',
    author: image.author || '',
    source: image.source || 'suggested',
    created_at: image.created_at || new Date().toISOString()
  };
};

/**
 * Проверяет, совпадают ли URL двух изображений
 * @param {Object} image1 - Первое изображение
 * @param {Object} image2 - Второе изображение
 * @returns {boolean} - true, если URL изображений совпадают
 */
export const isSameImage = (image1, image2) => {
  if (!image1 || !image2) return false;
  return image1.url === image2.url;
};

/**
 * Проверяет, содержит ли изображение все необходимые поля для API
 * @param {Object} image - Изображение для проверки
 * @returns {boolean} - true, если все необходимые поля присутствуют
 */
export const isValidImage = (image) => {
  if (!image) return false;
  
  // Минимальный набор полей, необходимых для работы с API
  const requiredFields = ['url'];
  
  // Проверяем наличие всех обязательных полей
  return requiredFields.every(field => 
    image[field] !== undefined && image[field] !== null && image[field] !== ''
  );
}; 