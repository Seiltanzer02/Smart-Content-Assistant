export const TARGET_CHANNEL_USERNAME = import.meta.env.VITE_TARGET_CHANNEL_USERNAME || '';

export async function checkChannelSubscription(userId?: number): Promise<{subscribed: boolean, message: string}> {
  let realUserId = userId;
  if (!realUserId && window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
    realUserId = window.Telegram.WebApp.initDataUnsafe.user.id;
  }
  if (!realUserId) {
    throw new Error('Не удалось определить Telegram ID пользователя');
  }
  const response = await fetch("/check-channel-subscription", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ user_id: realUserId })
  });

  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.detail || "Ошибка проверки подписки");
  }

  return await response.json();
} 