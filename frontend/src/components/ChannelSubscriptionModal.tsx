import React from 'react';

interface ChannelSubscriptionModalProps {
  open: boolean;
  onCheck: () => void;
  channelUrl: string;
}

const ChannelSubscriptionModal: React.FC<ChannelSubscriptionModalProps> = ({ open, onCheck, channelUrl }) => {
  console.log('Рендер ChannelSubscriptionModal, состояние open:', open);
  if (!open) return null;
  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,0,0,0.85)', zIndex: 2000,
      display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', color: '#fff',
    }}>
      <div style={{ background: '#222', padding: 32, borderRadius: 16, maxWidth: 400, textAlign: 'center', boxShadow: '0 2px 16px #0008' }}>
        <h2 style={{ marginBottom: 16 }}>Подпишитесь на наш канал</h2>
        <p style={{ marginBottom: 24 }}>
          Чтобы пользоваться приложением, подпишитесь на наш Telegram-канал.<br />
          <a href={channelUrl} target="_blank" rel="noopener noreferrer" style={{ color: '#ffd600', fontWeight: 600, fontSize: 18, textDecoration: 'underline' }}>
            Перейти в канал
          </a>
        </p>
        <button className="action-button" onClick={onCheck} style={{ fontSize: 18, padding: '10px 28px', marginBottom: 8 }}>
          Проверить подписку
        </button>
        <p style={{ fontSize: 13, color: '#bbb', marginTop: 12 }}>После подписки вернитесь и нажмите кнопку</p>
      </div>
    </div>
  );
};

export default ChannelSubscriptionModal; 