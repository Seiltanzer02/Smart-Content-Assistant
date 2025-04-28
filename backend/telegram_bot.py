#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Telegram бот для обработки донатов Stars и активации подписки
"""

import os
import logging
import telebot
import requests
from telebot import types
from dotenv import load_dotenv
from user_service import UserService

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Получение токена бота
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
    raise ValueError("TELEGRAM_BOT_TOKEN не указан")

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Настройка вебхука при запуске
def setup_webhook_on_startup():
    """Настраивает вебхук для бота при запуске приложения на Render"""
    webhook_url = os.environ.get("WEBHOOK_URL")
    if not webhook_url:
        logger.warning("WEBHOOK_URL не найден в переменных окружения. Вебхук не будет настроен.")
        return False
    
    try:
        # URL для настройки webhook
        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        
        # Параметры webhook
        params = {
            "url": webhook_url,
            "allowed_updates": ["message", "pre_checkout_query", "successful_payment"]
        }
        
        # Отправляем запрос на настройку webhook
        response = requests.post(api_url, json=params)
        data = response.json()
        
        if response.status_code == 200 and data.get("ok"):
            logger.info(f"Webhook успешно настроен: {webhook_url}")
            return True
        else:
            logger.error(f"Ошибка при настройке webhook: {data}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при настройке webhook: {e}")
        return False

# Настройка платежей Stars
SUBSCRIPTION_PRICE = 7000  # 70 Stars в копейках (1 Star = 100 копеек)
SUBSCRIPTION_CURRENCY = "STARS"  # Валюта - Stars
SUBSCRIPTION_TITLE = "Подписка на Smart Content Assistant"
SUBSCRIPTION_DESCRIPTION = "Подписка на 30 дней с неограниченным доступом ко всем функциям сервиса"

# Команда старт
@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обработчик команды /start"""
    user_id = str(message.from_user.id)
    chat_id = message.chat.id
    username = message.from_user.username or "пользователь"
    
    # Проверяем параметр /start
    if message.text.startswith('/start subscribe'):
        # Пользователь пришел из мини-приложения для подписки
        send_subscription_message(chat_id, user_id)
    else:
        # Обычное приветствие
        bot.send_message(
            chat_id,
            f"Привет, {username}! Я бот для управления подпиской на сервис Smart Content Assistant.\n\n"
            f"Используйте команду /subscribe для оформления подписки."
        )

# Команда подписки
@bot.message_handler(commands=['subscribe', 'donate'])
def handle_subscribe_command(message):
    """Обработчик команд /subscribe и /donate"""
    user_id = str(message.from_user.id)
    chat_id = message.chat.id
    
    send_subscription_message(chat_id, user_id)

def send_subscription_message(chat_id, user_id):
    """Отправляет сообщение с кнопкой для оформления подписки"""
    # Проверяем текущий статус подписки
    status = UserService.check_subscription_status(user_id)
    
    if status["has_subscription"]:
        # У пользователя уже есть активная подписка
        expiry_date = status["subscription_expires_at"]
        bot.send_message(
            chat_id,
            f"У вас уже есть активная подписка до {expiry_date}.\n\n"
            f"Осталось дней: {status['days_left']}"
        )
        return
    
    # Создаем инвойс для оплаты подписки
    prices = [
        types.LabeledPrice(label=SUBSCRIPTION_TITLE, amount=SUBSCRIPTION_PRICE)
    ]
    
    # Формируем description с лимитами
    description = (
        f"{SUBSCRIPTION_DESCRIPTION}\n\n"
        f"• Неограниченное число анализов каналов\n"
        f"• Неограниченное число генераций постов\n"
        f"• Приоритетная поддержка"
    )
    
    # Отправляем инвойс для оплаты
    try:
        bot.send_invoice(
            chat_id=chat_id,
            title=SUBSCRIPTION_TITLE,
            description=description,
            invoice_payload=f"subscription:{user_id}",
            provider_token="",  # Пустой токен для Stars
            currency=SUBSCRIPTION_CURRENCY,
            prices=prices,
            start_parameter="subscribe",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
        
        # Для дополнительной информации отправляем еще сообщение
        bot.send_message(
            chat_id,
            "📱 *Smart Content Assistant*\n\n"
            "После оплаты подписки, перейдите в мини-приложение и нажмите кнопку 'Обновить статус' "
            "для применения изменений.\n\n"
            "_Подписка активируется автоматически и действует 30 дней._",
            parse_mode="Markdown"
        )
        
        # Сохраняем в базе информацию о запросе на подписку
        UserService.register_subscription_request(user_id)
        
    except Exception as e:
        logger.error(f"Ошибка при отправке инвойса: {e}")
        bot.send_message(
            chat_id,
            f"Произошла ошибка при создании платежа. Пожалуйста, попробуйте позже или обратитесь в поддержку.\n\nТехническая информация: {str(e)}"
        )

# Обработчик предварительной проверки платежа
@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout_query(pre_checkout_query):
    """Обработчик предварительной проверки платежа"""
    # Всегда подтверждаем возможность платежа
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# Обработчик успешного платежа
@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    """Обработчик успешного платежа"""
    user_id = str(message.from_user.id)
    chat_id = message.chat.id
    payment_info = message.successful_payment
    
    # Проверяем сумму доната (минимум 70 Stars)
    total_stars = payment_info.total_amount / 100  # Конвертация в Stars (1 Star = 100 копеек)
    logger.info(f"Получен платеж от пользователя {user_id}: {total_stars} Stars")
    
    if total_stars >= 70:
        # Активируем подписку
        success, message_text = UserService.update_subscription(user_id)
        
        if success:
            # Получаем обновленный статус подписки
            status = UserService.check_subscription_status(user_id)
            expiry_date = status.get("subscription_expires_at", "неизвестно")
            
            bot.send_message(
                chat_id,
                f"🎉 Спасибо за подписку!\n\n"
                f"Ваша подписка активирована до {expiry_date}.\n"
                f"Теперь вам доступны все функции Smart Content Assistant без ограничений."
            )
            
            # Можно добавить уведомление администратора о новой подписке
            try:
                admin_id = os.getenv("ADMIN_TELEGRAM_ID")
                if admin_id:
                    bot.send_message(
                        admin_id,
                        f"Новая подписка:\n"
                        f"Пользователь: {user_id}\n"
                        f"Сумма: {total_stars} Stars\n"
                        f"Подписка до: {expiry_date}"
                    )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления администратору: {e}")
        else:
            bot.send_message(
                chat_id,
                f"⚠️ Возникла проблема при активации подписки: {message_text}\n\n"
                f"Пожалуйста, обратитесь в поддержку."
            )
    else:
        bot.send_message(
            chat_id,
            f"⚠️ Для активации подписки необходимо минимум 70 Stars.\n"
            f"Вы отправили {total_stars} Stars.\n\n"
            f"Пожалуйста, используйте команду /subscribe для повторной попытки."
        )

# Запуск бота в режиме polling (для отладки)
if __name__ == "__main__":
    logger.info("Запуск бота в режиме polling")
    bot.polling(none_stop=True, interval=0) 