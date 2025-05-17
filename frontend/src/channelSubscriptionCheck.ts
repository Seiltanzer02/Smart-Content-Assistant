export const TARGET_CHANNEL_USERNAME = import.meta.env.VITE_TARGET_CHANNEL_USERNAME || '';

export async function checkChannelSubscription(userId?: number): Promise<{subscribed: boolean, message: string}> {
  let realUserId = userId;
  if (!realUserId && window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
    realUserId = window.Telegram.WebApp.initDataUnsafe.user.id;
  }
  if (!realUserId) {
    throw new Error('Не удалось определить Telegram ID пользователя');
  }
  const response = await fetch(`/channel-subscription-check/${realUserId}`, {
    method: "GET"
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.message || "Ошибка проверки подписки");
  }

  return await response.json();
} 