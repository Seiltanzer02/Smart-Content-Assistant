import React, { useState } from 'react';
import ImageSelector from './ImageSelector';
import axios from 'axios';
import { API_BASE_URL } from '../utils/api';
import '../styles/PostDetails.css';

interface Image {
  id: string;
  url: string;
  preview_url?: string;
  alt?: string;
  author?: string;
  author_url?: string;
}

interface PostDetailsProps {
  postText: string;
  images: Image[];
  topicIdea: string;
  formatStyle: string;
  channelName?: string;
  userId: string;
  onSave: (selectedImage: Image | null, postText: string) => Promise<void>;
  isSaving: boolean;
}

const PostDetails: React.FC<PostDetailsProps> = ({
  postText,
  images = [],
  topicIdea,
  formatStyle,
  channelName,
  userId,
  onSave,
  isSaving
}) => {
  const [selectedImage, setSelectedImage] = useState<Image | null>(null);
  const [editedText, setEditedText] = useState<string>(postText);
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());

  const handleSavePost = async () => {
    await onSave(selectedImage, editedText);
  };

  return (
    <div className="post-details-container">
      <h2 className="post-details-title">Детали поста</h2>
      
      <div className="post-meta">
        <div className="meta-item">
          <span className="meta-label">Тема:</span>
          <span className="meta-value">{topicIdea}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Формат:</span>
          <span className="meta-value">{formatStyle}</span>
        </div>
        {channelName && (
          <div className="meta-item">
            <span className="meta-label">Канал:</span>
            <span className="meta-value">{channelName}</span>
          </div>
        )}
      </div>
      
      <div className="post-content">
        <div className="post-text-section">
          <h3>Текст поста:</h3>
          <textarea
            className="post-text-editor"
            value={editedText}
            onChange={(e) => setEditedText(e.target.value)}
            rows={10}
          />
        </div>
        
        <div className="post-images-section">
          <h3>Изображения для поста:</h3>
          
          {images.length > 0 ? (
            <div className="suggested-images">
              <h4>Предложенные изображения:</h4>
              <div className="images-grid">
                {images.map((image, index) => (
                  <div
                    key={image.id || index}
                    className={`image-item ${selectedImage?.id === image.id ? 'selected' : ''}`}
                    onClick={() => setSelectedImage(selectedImage?.id === image.id ? null : image)}
                  >
                    <img
                      src={image.preview_url || image.url}
                      alt={image.alt || `Изображение ${index + 1}`}
                      className="image-preview"
                    />
                    {selectedImage?.id === image.id && (
                      <div className="selected-overlay">
                        <span className="checkmark">✓</span>
                      </div>
                    )}
                    {image.author && (
                      <div className="image-credit">
                        Автор: {image.author}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="no-images-message">Для этого поста нет предложенных изображений</p>
          )}
          
          <div className="user-images">
            <h4>Выберите изображение из вашей коллекции:</h4>
            <ImageSelector
              onImageSelect={setSelectedImage}
              selectedImageId={selectedImage?.id}
              userId={userId}
            />
          </div>
        </div>
      </div>
      
      <div className="post-actions">
        <div className="date-selector">
          <label htmlFor="post-date">Дата публикации:</label>
          <input
            type="date"
            id="post-date"
            value={selectedDate.toISOString().split('T')[0]}
            onChange={(e) => setSelectedDate(new Date(e.target.value))}
          />
        </div>
        
        <button
          className="save-post-button"
          onClick={handleSavePost}
          disabled={isSaving}
        >
          {isSaving ? 'Сохранение...' : 'Сохранить пост'}
        </button>
      </div>
    </div>
  );
};

export default PostDetails; 