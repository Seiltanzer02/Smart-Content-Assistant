import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, PreCheckoutQuery, LabeledPrice
from aiogram.utils.keyboard import InlineKeyboardBuilder
import httpx
from datetime import datetime, timedelta

# Получаем переменные окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# --- Клавиатура с кнопкой оплаты ---
def payment_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить 70 ⭐️", pay=True)
    return builder.as_markup()

# --- Инициализация бота и диспетчера ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# --- Обработчик команды /buy ---
@dp.message(F.text == "/buy")
async def send_invoice_handler(message: Message):
    prices = [LabeledPrice(label="XTR", amount=70)]  # 70 Stars
    await message.answer_invoice(
        title="Подписка Premium",
        description="Подписка Premium на 1 месяц",
        prices=prices,
        provider_token="",  # Для Stars — пустая строка!
        payload=f"premium_sub_{message.from_user.id}",
        currency="XTR",
        reply_markup=payment_keyboard(),
    )

# --- Подтверждение оплаты (обязательно!) ---
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

# --- Обработка успешной оплаты ---
@dp.message(F.successful_payment)
async def success_payment_handler(message: Message):
    user_id = message.from_user.id
    payment_id = message.successful_payment.telegram_payment_charge_id
    now = datetime.utcnow().isoformat()
    end_date = (datetime.utcnow() + timedelta(days=31)).isoformat()
    # --- Активируем подписку в user_subscription ---
    try:
        async with httpx.AsyncClient() as client:
            url = f"{SUPABASE_URL}/rest/v1/user_subscription"
            headers = {
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "user_id": user_id,
                "start_date": now,
                "end_date": end_date,
                "payment_id": payment_id,
                "is_active": True,
                "created_at": now,
                "updated_at": now
            }
            # Вставляем новую подписку (можно добавить upsert по user_id, если нужно продлевать)
            response = await client.post(url, headers=headers, json=data)
            if response.status_code not in (200, 201):
                await message.answer(f"Подписка оплачена, но возникла ошибка при активации: {response.text}")
                return
    except Exception as e:
        await message.answer(f"Подписка оплачена, но возникла ошибка при активации: {e}")
        return
    await message.answer("🥳 Спасибо за покупку подписки! Ваш Premium активирован.")

# --- Запуск long polling ---
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))

# ---
# Требуемая зависимость:
# В requirements.txt добавить:
# aiogram==3.7.0
# aiohttp
# httpx
# ---
# После добавления этого файла и зависимостей:
# 1. Перезапустите сервер (Render)
# 2. В Telegram напишите своему боту /buy — появится кнопка оплаты
# 3. После оплаты подписка активируется автоматически
# --- 