import React from 'react';
import { useParams } from 'react-router-dom';

const PostEditorPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  
  return (
    <div className="post-editor-page">
      <h1>{id ? `Редактирование поста #${id}` : 'Создание нового поста'}</h1>
      <p>Страница находится в разработке</p>
    </div>
  );
};

export default PostEditorPage; 