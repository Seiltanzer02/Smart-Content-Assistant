import React, { useState } from 'react';
import { Box, Typography, Button, Card, CardContent, CircularProgress } from '@mui/material';
import { API_URL } from '../config';
import { fetchWithAuth } from '../utils/fetchWithAuth';
import SubscriptionInfo from './SubscriptionInfo';

const SubscriptionWidget: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [invoiceUrl, setInvoiceUrl] = useState<string | null>(null);

  const handleSubscribe = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetchWithAuth(`${API_URL}/generate-stars-invoice-link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({})
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Ошибка при создании ссылки на оплату');
      }

      if (data && data.invoice_url) {
        setInvoiceUrl(data.invoice_url);
        // Можно открыть ссылку автоматически
        window.open(data.invoice_url, '_blank');
      } else {
        throw new Error('Не удалось получить ссылку на оплату');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка');
      console.error('Ошибка при создании ссылки на оплату:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h5" component="h2" gutterBottom>
        Подписка
      </Typography>

      <SubscriptionInfo onSubscribe={handleSubscribe} />

      <Card variant="outlined">
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Premium-подписка
          </Typography>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Получите неограниченный доступ ко всем функциям сервиса.
          </Typography>
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2">
              • Неограниченное количество анализов каналов
            </Typography>
            <Typography variant="body2">
              • Неограниченное количество генераций постов
            </Typography>
            <Typography variant="body2">
              • Приоритетная техническая поддержка
            </Typography>
          </Box>
          <Typography variant="h6" color="primary" gutterBottom>
            349 ₽ / месяц
          </Typography>
          <Button
            variant="contained"
            color="primary"
            onClick={handleSubscribe}
            disabled={loading}
            sx={{ mt: 1 }}
            fullWidth
          >
            {loading ? <CircularProgress size={24} color="inherit" /> : 'Оформить подписку'}
          </Button>
          {error && (
            <Typography color="error" variant="body2" sx={{ mt: 1 }}>
              {error}
            </Typography>
          )}
          {invoiceUrl && (
            <Typography variant="body2" sx={{ mt: 1 }}>
              Оплата через Telegram. Если страница не открылась автоматически,{' '}
              <a href={invoiceUrl} target="_blank" rel="noopener noreferrer">
                нажмите здесь
              </a>
              .
            </Typography>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default SubscriptionWidget; 