import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../utils/api';
import '../styles/ImageSelector.css';

interface Image {
  id: string;
  url: string;
  preview_url?: string;
  alt?: string;
  author?: string;
  author_url?: string;
  created_at?: string;
}

interface ImageSelectorProps {
  onImageSelect: (image: Image | null) => void;
  selectedImageId?: string | null;
  userId: string;
}

const ImageSelector: React.FC<ImageSelectorProps> = ({ onImageSelect, selectedImageId, userId }) => {
  const [images, setImages] = useState<Image[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedImage, setSelectedImage] = useState<string | null>(selectedImageId || null);

  useEffect(() => {
    fetchUserImages();
  }, []);

  useEffect(() => {
    setSelectedImage(selectedImageId || null);
  }, [selectedImageId]);

  const fetchUserImages = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await axios.get(`${API_BASE_URL}/user-images`, {
        headers: {
          'x-telegram-user-id': userId ? Number(userId) : undefined
        }
      });

      if (response.data && Array.isArray(response.data)) {
        setImages(response.data);
      }
    } catch (err: any) {
      console.error('Ошибка при загрузке изображений:', err);
      setError(err.response?.data?.detail || err.message || 'Не удалось загрузить изображения');
    } finally {
      setLoading(false);
    }
  };

  const handleImageClick = (image: Image) => {
    const newSelectedId = selectedImage === image.id ? null : image.id;
    setSelectedImage(newSelectedId);
    
    // Находим выбранное изображение по ID или передаем null, если ничего не выбрано
    const selectedImgObject = newSelectedId 
      ? images.find(img => img.id === newSelectedId) || null 
      : null;
    
    onImageSelect(selectedImgObject);
  };

  if (loading) {
    return <div className="image-selector-loading">Загрузка изображений...</div>;
  }

  if (error) {
    return <div className="image-selector-error">{error}</div>;
  }

  if (images.length === 0) {
    return <div className="image-selector-empty">Нет доступных изображений</div>;
  }

  return (
    <div className="image-selector-container">
      <h3>Выберите изображение для поста</h3>
      <div className="image-selector-grid">
        {images.map((image) => (
          <div
            key={image.id}
            className={`image-item ${selectedImage === image.id ? 'selected' : ''}`}
            onClick={() => handleImageClick(image)}
          >
            <img 
              src={image.preview_url || image.url} 
              alt={image.alt || 'Изображение поста'} 
              className="image-preview"
            />
            {selectedImage === image.id && (
              <div className="selected-overlay">
                <span className="checkmark">✓</span>
              </div>
            )}
          </div>
        ))}
      </div>
      {selectedImage && (
        <button 
          className="clear-selection-button" 
          onClick={() => { 
            setSelectedImage(null); 
            onImageSelect(null); 
          }}
        >
          Отменить выбор
        </button>
      )}
    </div>
  );
};

export default ImageSelector; 