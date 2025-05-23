import os
import httpx
from fastapi import Request
from backend.main import app, logger, supabase
from backend.telegram_utils import send_telegram_message

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Вебхук для обработки обновлений от бота Telegram."""
    try:
        data = await request.json()
        logger.info(f"Получен вебхук от Telegram: {data}")
        
        # Обработка pre_checkout_query
        pre_checkout_query = data.get("pre_checkout_query")
        if pre_checkout_query:
            query_id = pre_checkout_query.get("id")
            if query_id:
                bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
                logger.info(f"Обработка pre_checkout_query с ID: {query_id}")
                if not bot_token:
                    logger.error("TELEGRAM_BOT_TOKEN не найден")
                    return {"ok": False, "error": "Bot token not found"}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"https://api.telegram.org/bot{bot_token}/answerPreCheckoutQuery",
                        json={
                            "pre_checkout_query_id": query_id,
                            "ok": True
                        }
                    )
                    if response.status_code == 200:
                        logger.info(f"pre_checkout_query подтвержден: {response.json()}")
                        return {"ok": True}
                    else:
                        logger.error(f"Ошибка pre_checkout_query: {response.status_code}")
                        return {"ok": False, "error": "Failed to answer pre_checkout_query"}
        
        # Обработка сообщений
        message = data.get("message")
        if message:
            user_id = message.get("from", {}).get("id")
            text = message.get("text", "")
            
            # Проверка премиум-статуса
            if text and (text.startswith("/start check_premium") or text == "/check_premium"):
                logger.info(f"Проверка премиум-статуса для {user_id}")
                try:
                    if not supabase:
                        logger.error("Supabase не инициализирован")
                        return {"ok": False, "error": "Supabase client not initialized"}
                    subscription = supabase.table("user_subscription").select("*").eq("user_id", user_id).eq("is_active", True).execute()
                    has_premium = False
                    end_date_str = "неизвестно"
                    if hasattr(subscription, "data") and subscription.data:
                        from datetime import datetime, timezone
                        current_date = datetime.now(timezone.utc)
                        active_subs = []
                        for sub in subscription.data:
                            end_date = sub.get("end_date")
                            if end_date:
                                try:
                                    if isinstance(end_date, str):
                                        end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                                    if end_date > current_date:
                                        active_subs.append(sub)
                                except Exception as e:
                                    logger.error(f"Ошибка с датой: {e}")
                        if active_subs:
                            has_premium = True
                            latest_sub = max(active_subs, key=lambda x: x.get("end_date"))
                            end_date = latest_sub.get("end_date")
                            if isinstance(end_date, str):
                                end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                            end_date_str = end_date.strftime("%d.%m.%Y %H:%M")
                    reply_text = ""
                    if has_premium:
                        reply_text = f"✅ У вас активирован премиум-доступ!\nДействует до: {end_date_str}"
                    else:
                        reply_text = "❌ У вас нет активной подписки"
                    await send_telegram_message(user_id, reply_text)
                    return {"ok": True, "has_premium": has_premium}
                except Exception as e:
                    logger.error(f"Ошибка проверки премиума: {e}")
                    await send_telegram_message(user_id, "Произошла ошибка при проверке")
                    return {"ok": False, "error": str(e)}
            
            # Команда получения реферальной ссылки
            if text and text.strip().lower() in ["/getreferral", "getreferral", "/ref", "ref"]:
                try:
                    link = await get_star_referral_link()
                    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
                    reply_markup = {
                        "inline_keyboard": [[{"text": "Открыть реферальную ссылку", "url": link}]]
                    }
                    reply_text = f"Ваша официальная реферальная ссылка Stars:\n{link}\n\nИспользуйте её для продвижения и заработка Stars!"
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        await client.post(
                            f"https://api.telegram.org/bot{bot_token}/sendMessage",
                            json={
                                "chat_id": user_id,
                                "text": reply_text,
                                "reply_markup": reply_markup
                            }
                        )
                    return {"ok": True, "referral_link": link}
                except Exception as e:
                    logger.error(f"Ошибка при получении реферальной ссылки: {e}")
                    await send_telegram_message(user_id, f"Ошибка при получении ссылки: {e}")
                    return {"ok": False, "error": str(e)}
        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка в telegram_webhook: {e}")
        return {"ok": False, "error": str(e)}
