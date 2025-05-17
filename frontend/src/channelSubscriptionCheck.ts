export async function checkChannelSubscription(userId: number): Promise<{subscribed: boolean, message: string}> {
  const response = await fetch("/check-channel-subscription", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ user_id: userId })
  });

  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.detail || "Ошибка проверки подписки");
  }

  return await response.json();
} 