import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Box, Grid, Card, CardMedia, CardContent, Typography, Button, CircularProgress, Alert } from '@mui/material';
import { API_BASE_URL } from '../utils/api';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

/**
 * Компонент для отображения галереи изображений, связанных с постом.
 * Позволяет выбирать изображения для включения в пост.
 */
const PostImageGallery = ({ 
  postId, 
  onImageSelect, 
  selectedImages = [], 
  maxImages = 5, 
  showSelected = true
}) => {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Загрузка изображений для конкретного поста или общих изображений для выбора
  const loadImages = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      let response;
      if (postId) {
        // Если есть postId, загружаем изображения этого поста
        response = await axios.get(`${API_BASE_URL}/posts/${postId}/images`, {
          headers: {
            'X-Telegram-User-Id': localStorage.getItem('telegramUserId')
          }
        });
        
        if (response.data && response.data.images) {
          setImages(response.data.images);
        }
      } else {
        // Иначе загружаем все доступные изображения пользователя
        response = await axios.get(`${API_BASE_URL}/images`, {
          headers: {
            'X-Telegram-User-Id': localStorage.getItem('telegramUserId')
          }
        });
        
        if (response.data && Array.isArray(response.data)) {
          setImages(response.data);
        }
      }
    } catch (err) {
      console.error('Ошибка при загрузке изображений:', err);
      setError('Не удалось загрузить изображения. Пожалуйста, попробуйте позже.');
    } finally {
      setLoading(false);
    }
  }, [postId]);
  
  useEffect(() => {
    loadImages();
  }, [loadImages]);
  
  // Обработчик выбора изображения
  const handleImageSelect = (image) => {
    if (!onImageSelect) return;
    
    const isSelected = selectedImages.some(img => img.id === image.id);
    
    // Если изображение уже выбрано, удаляем его из выбранных
    if (isSelected) {
      onImageSelect(selectedImages.filter(img => img.id !== image.id));
    } 
    // Иначе добавляем, если не превышен лимит
    else if (selectedImages.length < maxImages) {
      onImageSelect([...selectedImages, image]);
    }
  };
  
  // Проверка, выбрано ли изображение
  const isImageSelected = (imageId) => {
    return selectedImages.some(img => img.id === imageId);
  };
  
  // Рендер состояния загрузки
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }
  
  // Рендер ошибки
  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2, mb: 2 }}>
        {error}
      </Alert>
    );
  }
  
  // Рендер пустого состояния
  if (images.length === 0) {
    return (
      <Alert severity="info" sx={{ mt: 2, mb: 2 }}>
        {postId ? 'У этого поста нет изображений.' : 'Нет доступных изображений для выбора.'}
      </Alert>
    );
  }
  
  // Определяем, какие изображения показывать
  const displayImages = showSelected 
    ? images 
    : (selectedImages.length > 0 ? selectedImages : images);
  
  return (
    <Box sx={{ mt: 2, mb: 3 }}>
      {!postId && onImageSelect && (
        <Typography variant="body2" sx={{ mb: 1 }}>
          Выберите до {maxImages} изображений для поста (выбрано: {selectedImages.length})
        </Typography>
      )}
      
      <Grid container spacing={2}>
        {displayImages.map((image) => (
          <Grid item xs={12} sm={6} md={4} key={image.id}>
            <Card 
              sx={{ 
                position: 'relative',
                border: isImageSelected(image.id) ? '2px solid #2196f3' : 'none',
                cursor: onImageSelect ? 'pointer' : 'default',
                height: '100%'
              }}
              onClick={() => onImageSelect && handleImageSelect(image)}
            >
              {isImageSelected(image.id) && (
                <CheckCircleIcon 
                  sx={{ 
                    position: 'absolute', 
                    top: 8, 
                    right: 8, 
                    color: '#2196f3',
                    backgroundColor: 'white',
                    borderRadius: '50%',
                    zIndex: 2
                  }} 
                />
              )}
              
              <CardMedia
                component="img"
                sx={{ height: 140, objectFit: 'cover' }}
                image={image.preview_url || image.url}
                alt={image.alt || 'Изображение'}
                onError={(e) => {
                  e.target.onerror = null;
                  e.target.src = 'https://via.placeholder.com/140x140?text=Ошибка+загрузки';
                }}
              />
              
              <CardContent sx={{ pb: '8px !important' }}>
                <Typography variant="caption" color="text.secondary">
                  {image.alt || 'Изображение для поста'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
      
      {displayImages.length > 0 && !loading && (
        <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center' }}>
          <Button onClick={loadImages} variant="outlined">
            Обновить изображения
          </Button>
        </Box>
      )}
    </Box>
  );
};

export default PostImageGallery; 