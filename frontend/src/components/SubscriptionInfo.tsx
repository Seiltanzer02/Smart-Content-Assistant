import React, { useEffect, useState } from 'react';
import { Box, Typography, CircularProgress, Button, Card, CardContent, Grid, Chip, Alert } from '@mui/material';
import { fetchWithAuth } from '../utils/fetchWithAuth';
import { API_URL } from '../config';
import { formatDate } from '../utils/formatters';

interface SubscriptionInfoProps {
  onSubscribe?: () => void;
}

interface SubscriptionData {
  has_subscription: boolean;
  subscription: {
    id: number;
    user_id: number;
    start_date: string;
    end_date: string;
    is_active: boolean;
    created_at: string;
    payment_id: string;
  } | null;
  usage: {
    analysis_count: number;
    post_generation_count: number;
    reset_at: string | null;
  };
  can_use: {
    analysis: boolean;
    post_generation: boolean;
  };
  free_limits: {
    analysis_limit: number;
    post_generation_limit: number;
  };
}

const SubscriptionInfo: React.FC<SubscriptionInfoProps> = ({ onSubscribe }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [subscriptionData, setSubscriptionData] = useState<SubscriptionData | null>(null);

  const fetchSubscriptionStatus = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetchWithAuth(`${API_URL}/subscription-status`);
      if (!response.ok) {
        throw new Error(`Ошибка при получении данных о подписке: ${response.statusText}`);
      }

      const data = await response.json();
      setSubscriptionData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка');
      console.error('Ошибка при получении данных о подписке:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubscriptionStatus();
  }, []);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" p={3}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!subscriptionData) {
    return (
      <Alert severity="warning" sx={{ mb: 2 }}>
        Не удалось загрузить информацию о подписке
      </Alert>
    );
  }

  const { has_subscription, subscription, usage, can_use, free_limits } = subscriptionData;

  return (
    <Card variant="outlined" sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {has_subscription ? 'Активная подписка' : 'Бесплатный план'}
        </Typography>

        {has_subscription && subscription ? (
          <Box mb={2}>
            <Typography variant="body1">
              Срок действия: {formatDate(subscription.start_date)} - {formatDate(subscription.end_date)}
            </Typography>
            <Chip 
              label="Активна" 
              color="success" 
              size="small" 
              sx={{ mt: 1 }} 
            />
          </Box>
        ) : (
          <Box mb={2}>
            <Typography variant="body2" color="text.secondary">
              Бесплатный план имеет ограничения на использование функций.
            </Typography>
            <Button 
              variant="contained" 
              color="primary" 
              size="small" 
              sx={{ mt: 2 }} 
              onClick={onSubscribe}
            >
              Оформить подписку
            </Button>
          </Box>
        )}

        <Typography variant="subtitle1" sx={{ mt: 2, mb: 1 }}>
          Использование
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <Card variant="outlined" sx={{ bgcolor: 'background.default' }}>
              <CardContent>
                <Typography variant="subtitle2">Анализ каналов</Typography>
                {has_subscription ? (
                  <Typography variant="body2" color="text.secondary">
                    Безлимитно
                  </Typography>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    {usage.analysis_count} из {free_limits.analysis_limit} использовано
                  </Typography>
                )}
                <Chip 
                  label={can_use.analysis ? "Доступно" : "Лимит исчерпан"} 
                  color={can_use.analysis ? "success" : "error"} 
                  size="small" 
                  sx={{ mt: 1 }} 
                />
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Card variant="outlined" sx={{ bgcolor: 'background.default' }}>
              <CardContent>
                <Typography variant="subtitle2">Генерация постов</Typography>
                {has_subscription ? (
                  <Typography variant="body2" color="text.secondary">
                    Безлимитно
                  </Typography>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    {usage.post_generation_count} из {free_limits.post_generation_limit} использовано
                  </Typography>
                )}
                <Chip 
                  label={can_use.post_generation ? "Доступно" : "Лимит исчерпан"} 
                  color={can_use.post_generation ? "success" : "error"} 
                  size="small" 
                  sx={{ mt: 1 }} 
                />
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {usage.reset_at && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Следующий сброс счетчиков: {formatDate(usage.reset_at)}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};

export default SubscriptionInfo; 