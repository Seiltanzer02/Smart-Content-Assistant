import React from 'react';

// Интерфейс для типа изображения
interface PostImage {
  id?: string;
  url: string;
  preview_url?: string;
  alt?: string;
  author?: string;
  author_url?: string;
  source?: string;
  external_id?: string;
  alt_description?: string;
}

// Пропсы компонента галереи
interface ImageGalleryProps {
  images: PostImage[];
  selectedImage: PostImage | null;
  onSelectImage: (image: PostImage | null) => void;
}

const ImageGallery: React.FC<ImageGalleryProps> = ({ images, selectedImage, onSelectImage }) => {
  return (
    <div className="suggested-images-section">
      <h3>Предложенные изображения:</h3>
      <div className="image-gallery suggested">
        {images.map((image, index) => {
          const isSelected = selectedImage && selectedImage.url === image.url;
          
          return (
            <div 
              key={image.id || `image-${index}`} 
              className={`image-item ${isSelected ? 'selected' : ''}`}
              onClick={() => {
                if (isSelected) {
                  onSelectImage(null);
                } else {
                  onSelectImage(image);
                }
              }}
            >
              <img 
                src={image.preview_url || image.url} 
                alt={image.alt || 'Изображение'} 
                onError={(e) => {
                  const target = e.target as HTMLImageElement;
                  target.src = 'https://via.placeholder.com/150?text=Ошибка'; 
                  console.error('Image load error:', image.preview_url || image.url);
                }}
              />
              <div className="checkmark">✓</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ImageGallery; 