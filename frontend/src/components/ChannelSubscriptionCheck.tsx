import React, { useEffect, useState } from 'react';
import { Button, Box, Typography, Alert, CircularProgress, Paper } from '@mui/material';
import { checkChannelSubscription, openChannelSubscription } from '../api/channel_subscription';

interface ChannelSubscriptionCheckProps {
  userId: string | null;
  onSubscriptionVerified?: (isSubscribed: boolean) => void;
}

const ChannelSubscriptionCheck: React.FC<ChannelSubscriptionCheckProps> = ({ 
  userId, 
  onSubscriptionVerified 
}) => {
  const [isSubscribed, setIsSubscribed] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [channelName, setChannelName] = useState<string>('');

  // Проверка подписки при загрузке компонента
  useEffect(() => {
    checkSubscription();
  }, [userId]);

  // Функция для проверки подписки
  const checkSubscription = async () => {
    if (!userId) {
      setError('Не удалось определить ID пользователя');
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await checkChannelSubscription(userId);
      setIsSubscribed(result.is_subscribed);
      setChannelName(result.channel);
      
      // Вызываем callback, если он предоставлен
      if (onSubscriptionVerified) {
        onSubscriptionVerified(result.is_subscribed);
      }
    } catch (err) {
      console.error('Ошибка при проверке подписки:', err);
      setError('Не удалось проверить подписку. Пожалуйста, попробуйте позже.');
    } finally {
      setIsLoading(false);
    }
  };

  // Открытие канала для подписки
  const handleSubscribe = async () => {
    await openChannelSubscription();
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
        <CircularProgress />
      </Box>
    );
  }

  // Если пользователь уже подписан, не показываем ничего
  if (isSubscribed === true) {
    return null;
  }

  return (
    <Paper 
      elevation={3} 
      sx={{ 
        p: 3, 
        my: 2, 
        maxWidth: '100%', 
        backgroundColor: '#f5f5f5',
        border: '1px solid #e0e0e0',
        borderRadius: '8px'
      }}
    >
      <Typography variant="h5" component="h2" gutterBottom>
        Требуется подписка на канал
      </Typography>
      
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      <Typography variant="body1" paragraph>
        Для использования приложения необходимо подписаться на наш канал{' '}
        {channelName && <strong>@{channelName}</strong>}.
      </Typography>
      
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 2 }}>
        <Button 
          variant="contained" 
          color="primary" 
          onClick={handleSubscribe}
        >
          Подписаться на канал
        </Button>
        
        <Button 
          variant="outlined"
          onClick={checkSubscription}
        >
          Проверить подписку
        </Button>
      </Box>
    </Paper>
  );
};

export default ChannelSubscriptionCheck; 