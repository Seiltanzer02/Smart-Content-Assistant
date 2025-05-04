import React from 'react';
import { Box, Container, Typography, Paper, Divider } from '@mui/material';
import SubscriptionWidget from '../components/SubscriptionWidget';
import DirectPremiumStatus from '../components/DirectPremiumStatus';

interface SettingsPageProps {
  userId: string | null;
}

const SettingsPage: React.FC<SettingsPageProps> = ({ userId }) => {
  return (
    <Container maxWidth="md">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Настройки
        </Typography>
        
        <Paper sx={{ p: 3, mb: 4 }}>
          <SubscriptionWidget userId={userId} />
          <DirectPremiumStatus userId={userId} />
          <Divider sx={{ my: 3 }} />
          <Typography variant="body2" color="text.secondary">
            Подписка дает вам неограниченный доступ ко всем функциям сервиса.
            При наличии активной подписки вы можете делать неограниченное количество
            анализов каналов и генераций постов.
          </Typography>
        </Paper>
      </Box>
    </Container>
  );
};

export default SettingsPage; 