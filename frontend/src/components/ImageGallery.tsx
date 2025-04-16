import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Box, 
  CircularProgress, 
  Grid, 
  Typography, 
  Card, 
  CardMedia, 
  CardContent, 
  Checkbox,
  IconButton,
  Alert
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { API_BASE_URL, getAuthHeaders } from '../utils/api';

// Интерфейс для типа изображения
interface Image {
  id: string;
  url: string;
  preview_url?: string;
  alt?: string;
  author?: string;
  author_url?: string;
  source: string;
}

// Пропсы компонента галереи
interface ImageGalleryProps {
  postId?: string;
  selectedImages: Image[];
  onSelectImages: (images: Image[]) => void;
  maxSelections?: number;
}

const ImageGallery: React.FC<ImageGalleryProps> = ({
  postId,
  selectedImages,
  onSelectImages,
  maxSelections = 5
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [images, setImages] = useState<Image[]>([]);

  // Загрузка изображений, связанных с постом
  const loadPostImages = async () => {
    if (!postId) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.get(`${API_BASE_URL}/posts/${postId}/images`, {
        headers: getAuthHeaders()
      });
      
      if (response.data && response.data.images) {
        setImages(response.data.images);
        // Если есть изображения в посте, выбираем их автоматически
        onSelectImages(response.data.images);
      }
    } catch (err) {
      console.error('Ошибка при загрузке изображений поста:', err);
      setError('Не удалось загрузить изображения поста');
    } finally {
      setLoading(false);
    }
  };

  // Загрузка пользовательских изображений
  const loadUserImages = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.get(`${API_BASE_URL}/images`, {
        headers: getAuthHeaders()
      });
      
      if (response.data) {
        setImages(response.data);
      }
    } catch (err) {
      console.error('Ошибка при загрузке изображений пользователя:', err);
      setError('Не удалось загрузить изображения');
    } finally {
      setLoading(false);
    }
  };

  // Загрузка изображений при монтировании компонента
  useEffect(() => {
    if (postId) {
      loadPostImages();
    } else {
      loadUserImages();
    }
  }, [postId]);

  // Выбор/отмена выбора изображения
  const handleSelectImage = (image: Image) => {
    const isSelected = selectedImages.some(img => img.id === image.id);
    
    if (isSelected) {
      // Если изображение уже выбрано, удаляем его из выбранных
      onSelectImages(selectedImages.filter(img => img.id !== image.id));
    } else {
      // Если изображение не выбрано и не превышен лимит, добавляем
      if (selectedImages.length < maxSelections) {
        onSelectImages([...selectedImages, image]);
      }
    }
  };

  // Обновление списка изображений
  const handleRefresh = () => {
    if (postId) {
      loadPostImages();
    } else {
      loadUserImages();
    }
  };

  return (
    <Box sx={{ mt: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">
          {postId ? 'Изображения поста' : 'Мои изображения'}
        </Typography>
        <IconButton onClick={handleRefresh} disabled={loading}>
          <RefreshIcon />
        </IconButton>
      </Box>
      
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      ) : images.length === 0 ? (
        <Typography variant="body1" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
          Изображения не найдены
        </Typography>
      ) : (
        <Grid container spacing={2}>
          {images.map((image) => {
            const isSelected = selectedImages.some(img => img.id === image.id);
            return (
              <Grid item xs={6} sm={4} md={3} key={image.id}>
                <Card 
                  sx={{ 
                    position: 'relative',
                    border: isSelected ? '2px solid #1976d2' : 'none',
                    cursor: 'pointer',
                    height: '100%'
                  }}
                  onClick={() => handleSelectImage(image)}
                >
                  <CardMedia
                    component="img"
                    height="140"
                    image={image.preview_url || image.url}
                    alt={image.alt || 'Изображение'}
                  />
                  <Checkbox
                    checked={isSelected}
                    sx={{
                      position: 'absolute',
                      top: 0,
                      right: 0,
                      backgroundColor: 'rgba(255, 255, 255, 0.7)',
                      m: 0.5
                    }}
                  />
                  {image.author && (
                    <CardContent sx={{ p: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        Автор: {image.author}
                      </Typography>
                    </CardContent>
                  )}
                </Card>
              </Grid>
            );
          })}
        </Grid>
      )}
      
      {selectedImages.length > 0 && (
        <Typography variant="body2" sx={{ mt: 2 }}>
          Выбрано {selectedImages.length} из {maxSelections} изображений
        </Typography>
      )}
    </Box>
  );
};

export default ImageGallery; 