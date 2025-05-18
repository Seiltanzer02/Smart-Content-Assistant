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
  const [debugInfo, setDebugInfo] = useState<string>('Инициализация...');

  // Проверка подписки при загрузке компонента
  useEffect(() => {
    console.log('ChannelSubscriptionCheck: initializing with userId:', userId);
    setDebugInfo(`Проверка подписки для пользователя: ${userId}`);
    checkSubscription();
  }, [userId]);

  // Функция для проверки подписки
  const checkSubscription = async () => {
    if (!userId) {
      console.error('ChannelSubscriptionCheck: userId is null');
      setError('Не удалось определить ID пользователя');
      setDebugInfo('Ошибка: userId is null');
      setIsLoading(false);
      return;
    }

    console.log('ChannelSubscriptionCheck: начинаем проверку подписки для', userId);
    setIsLoading(true);
    setError(null);
    setDebugInfo(`Отправка запроса на /channel/subscription/status?user_id=${userId}`);

    try {
      const result = await checkChannelSubscription(userId);
      console.log('ChannelSubscriptionCheck: результат проверки:', result);
      setIsSubscribed(result.is_subscribed);
      setChannelName(result.channel);
      setDebugInfo(`Получен ответ: is_subscribed=${result.is_subscribed}, channel=${result.channel}`);
      
      // Вызываем callback, если он предоставлен
      if (onSubscriptionVerified) {
        console.log('ChannelSubscriptionCheck: вызываем onSubscriptionVerified с', result.is_subscribed);
        onSubscriptionVerified(result.is_subscribed);
      }
    } catch (err) {
      console.error('Ошибка при проверке подписки:', err);
      setError('Не удалось проверить подписку. Пожалуйста, попробуйте позже.');
      setDebugInfo(`Ошибка: ${err}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Открытие канала для подписки
  const handleSubscribe = async () => {
    setDebugInfo('Открытие канала для подписки...');
    await openChannelSubscription();
    setDebugInfo('Канал для подписки открыт. Ожидание проверки...');
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
        <CircularProgress />
        <Typography variant="body2" sx={{ mt: 2, color: '#666' }}>
          Проверка подписки...
        </Typography>
        <Typography variant="caption" sx={{ mt: 1, color: '#999', fontSize: '10px' }}>
          Отладка: {debugInfo}
        </Typography>
      </Box>
    );
  }

  // Всегда показываем компонент при первоначальной загрузке
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
        {isSubscribed 
          ? "Подписка активна" 
          : "Требуется подписка на канал"}
      </Typography>
      
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      <Typography variant="body1" paragraph>
        {isSubscribed 
          ? `Вы успешно подписаны на канал @${channelName}` 
          : `Для использования приложения необходимо подписаться на канал ${channelName && <strong>@{channelName}</strong>}.`}
      </Typography>
      
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 2 }}>
        {!isSubscribed && (
          <Button 
            variant="contained" 
            color="primary" 
            onClick={handleSubscribe}
          >
            Подписаться на канал
          </Button>
        )}
        
        <Button 
          variant="outlined"
          onClick={checkSubscription}
        >
          Проверить подписку
        </Button>
      </Box>
      
      {/* Отладочная информация */}
      <Typography variant="caption" sx={{ mt: 2, display: 'block', color: '#999', fontSize: '10px' }}>
        Отладка: {debugInfo}
      </Typography>
    </Paper>
  );
};

export default ChannelSubscriptionCheck; 