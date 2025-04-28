#!/usr/bin/env python
"""
Утилиты для работы с Telegram API через библиотеку Telethon.
"""

import logging
from typing import List, Dict, Optional, Tuple, Any, Union
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Channel, Message
import os
from dotenv import load_dotenv
import asyncio
import re
from datetime import datetime, timedelta
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon.tl.types import InputPeerChannel, PeerChannel
from telethon.errors import (
    ChannelPrivateError, ChannelInvalidError, 
    AuthKeyError, FloodWaitError, ApiIdInvalidError
)
import requests
import json
import telebot
import hmac
import hashlib
import time

# --- ПЕРЕМЕЩАЕМ Логгирование В НАЧАЛО --- 
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv(override=True)

# Получение конфигурации из переменных окружения
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SESSION_NAME = "telegram_session"

# Проверяем доступность Telethon
try:
    from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
    from telethon.tl.types import PeerChannel, InputPeerChannel
    TELETHON_AVAILABLE = True
except ImportError:
    logger.warning("Telethon не установлен. Функции, требующие Telethon, будут недоступны.")
    TELETHON_AVAILABLE = False

# Создание временного клиента Telegram
client = None

# Получение токена бота из переменных окружения
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения")

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

# Стоимость подписки в Stars
SUBSCRIPTION_PRICE = 70 * 100  # 70 Stars в копейках (1 Star = 100 копеек)
SUBSCRIPTION_PERIOD_DAYS = 30  # 30 дней

def init_telegram_client() -> Optional[TelegramClient]:
    """Инициализация клиента Telegram."""
    # Проверка наличия API_ID и API_HASH
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        logger.error("TELEGRAM_API_ID или TELEGRAM_API_HASH не найдены в окружении")
        return None
    
    try:
        # Создание клиента
        client = TelegramClient(SESSION_NAME, int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
        logger.info("Клиент Telegram успешно инициализирован")
        return client
    except ValueError as e:
        logger.error(f"Ошибка при преобразовании TELEGRAM_API_ID в число: {e}")
        return None
    except Exception as e:
        logger.error(f"Ошибка при инициализации клиента Telegram: {e}")
        return None

async def get_telegram_posts_via_telethon(channel_username: str, limit: int = 20) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Получение последних постов из Telegram канала через Telethon API.
    
    Args:
        channel_username: Имя канала без символа '@'
        limit: Максимальное количество постов для получения
    
    Returns:
        Tuple[List[Dict[str, Any]], Optional[str]]: Список постов и сообщение об ошибке (если есть)
    """
    # Инициализация пустого списка постов и сообщения об ошибке
    posts = []
    error = None
    
    # Проверка имени канала
    if not channel_username:
        return [], "Имя канала не указано"
    
    # Удаление символа '@' из имени канала, если он есть
    if channel_username.startswith('@'):
        channel_username = channel_username[1:]
    
    # Инициализация клиента Telegram
    client = init_telegram_client()
    if not client:
        return [], "Не удалось инициализировать клиент Telegram. Проверьте API ключи."
    
    try:
        # Подключение к Telegram
        await client.connect()
        
        if not await client.is_user_authorized():
            # Попытка авторизации через бота (если есть токен)
            if TELEGRAM_BOT_TOKEN:
                await client.sign_in(bot_token=TELEGRAM_BOT_TOKEN)
                logger.info("Авторизация через бота успешна")
            else:
                error = "Требуется авторизация. Токен бота не найден."
                logger.warning(error)
                return [], error
        
        # Получение сущности канала
        try:
            entity = await client.get_entity(channel_username)
            logger.info(f"Сущность канала получена: {entity.id}")
        except (ChannelPrivateError, ChannelInvalidError) as e:
            error = f"Ошибка доступа к каналу {channel_username}: {str(e)}"
            logger.error(error)
            return [], error
        
        # Получение сообщений из канала
        messages = await client.get_messages(entity, limit=limit)
        logger.info(f"Получено {len(messages)} сообщений из канала {channel_username}")
        
        # Обработка сообщений
        for message in messages:
            if message.message:  # Если есть текст сообщения
                post = {"text": message.message, "date": message.date.isoformat()}
                
                # Обработка медиа (фото, документы и т.д.)
                if message.photo:
                    # Получение URL фото
                    post["photo"] = True
                    # Здесь можно добавить логику для получения URL фото
                
                if message.document:
                    # Обработка документов
                    post["document"] = True
                    # Здесь можно добавить логику для получения информации о документе
                
                posts.append(post)
        
        return posts, None
    
    except FloodWaitError as e:
        error = f"Слишком много запросов. Нужно подождать {e.seconds} секунд."
        logger.error(error)
    except ApiIdInvalidError:
        error = "Недействительный API ID или API Hash."
        logger.error(error)
    except AuthKeyError:
        error = "Ошибка авторизации. Возможно, сессия устарела."
        logger.error(error)
    except Exception as e:
        error = f"Непредвиденная ошибка при получении постов: {str(e)}"
        logger.error(error)
    
    finally:
        # Отключение от Telegram
        if client:
            await client.disconnect()
    
    return posts, error

def get_telegram_posts(channel_username: str, limit: int = 20) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Синхронная обертка для асинхронной функции get_telegram_posts_via_telethon.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(get_telegram_posts_via_telethon(channel_username, limit))
        return result
    finally:
        loop.close()

def get_mock_telegram_posts(username: str) -> List[Dict[str, Any]]:
    """
    Возвращает примеры постов, когда API недоступно.
    """
    # Примеры постов для тестирования
    return [
        {
            "text": "Пример поста 1 для канала " + username + ". Это демонстрационные данные, используемые когда API недоступно.",
            "date": "2023-01-01T12:00:00"
        },
        {
            "text": "Пример поста 2 для канала " + username + ". Содержит какую-то полезную информацию и #хэштеги.",
            "date": "2023-01-02T15:30:00"
        },
        {
            "text": "Пример поста 3 с более длинным текстом. Здесь может быть полезная информация, ссылки и т.д. Это демонстрационные данные.",
            "date": "2023-01-03T18:45:00"
        }
    ]

# --- Новые функции для работы с платежами и подписками ---

class TelegramBotPaymentAPI:
    """
    Класс для работы с платежами и подписками через Telegram Bot API.
    """
    
    def __init__(self, bot_token: str):
        """
        Инициализация API клиента для работы с Telegram Bot API.
        
        Args:
            bot_token: Токен бота Telegram
        """
        self.bot_token = bot_token
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        
    def _make_request(self, method: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Выполнение запроса к API Telegram.
        
        Args:
            method: Метод API
            data: Данные запроса
            
        Returns:
            Dict[str, Any]: Ответ API
        """
        url = f"{self.api_url}/{method}"
        
        try:
            response = requests.post(url, json=data if data else {})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при выполнении запроса к Telegram Bot API: {e}")
            return {"ok": False, "error": str(e)}
    
    def create_invoice_link(self, 
                           title: str, 
                           description: str, 
                           payload: str, 
                           currency: str, 
                           prices: List[Dict[str, Union[str, int]]], 
                           subscription_period_days: int = 30) -> Optional[str]:
        """
        Создание глубокой ссылки на инвойс для подписки через Stars.
        
        Args:
            title: Название товара/услуги
            description: Описание товара/услуги
            payload: Уникальная строка-идентификатор для отслеживания платежа
            currency: Валюта (XTR для Telegram Stars)
            prices: Список цен и их описаний
            subscription_period_days: Период подписки в днях
            
        Returns:
            Optional[str]: URL инвойса или None в случае ошибки
        """
        # Конвертируем период подписки в секунды (из дней)
        subscription_period = subscription_period_days * 24 * 60 * 60
        
        data = {
            "title": title,
            "description": description,
            "payload": payload,
            "currency": currency,
            "prices": prices,
            "max_tip_amount": 0,
            "suggested_tip_amounts": [],
            "provider_data": {"subscription": True},
            "photo_url": None,
            "photo_size": 0,
            "photo_width": 0,
            "photo_height": 0,
            "need_name": False,
            "need_phone_number": False,
            "need_email": False,
            "need_shipping_address": False,
            "send_phone_number_to_provider": False,
            "send_email_to_provider": False,
            "is_flexible": False,
            "subscription_period": subscription_period
        }
        
        result = self._make_request("createInvoiceLink", data)
        
        if result.get("ok") and "result" in result:
            return result["result"]
        else:
            logger.error(f"Ошибка при создании инвойса: {result.get('description', 'Неизвестная ошибка')}")
            return None
    
    def create_subscription_invoice(self, 
                                   title: str, 
                                   description: str, 
                                   chat_id: Union[int, str], 
                                   prices: List[Dict[str, Union[str, int]]], 
                                   payload: str = None) -> Optional[Dict[str, Any]]:
        """
        Создание инвойса для подписки и отправка его пользователю.
        
        Args:
            title: Название подписки
            description: Описание подписки
            chat_id: ID чата/пользователя
            prices: Список цен и их описаний
            payload: Уникальная строка-идентификатор для отслеживания платежа
            
        Returns:
            Optional[Dict[str, Any]]: Результат создания инвойса или None в случае ошибки
        """
        if payload is None:
            # Генерируем случайный payload, если не передан
            payload = f"sub_{datetime.now().strftime('%Y%m%d%H%M%S')}_{chat_id}"
        
        # Период подписки - 30 дней в секундах
        subscription_period = 30 * 24 * 60 * 60
        
        data = {
            "chat_id": chat_id,
            "title": title,
            "description": description,
            "payload": payload,
            "provider_token": "",  # Пустой для цифровых товаров через Stars
            "currency": "XTR",
            "prices": prices,
            "max_tip_amount": 0,
            "suggested_tip_amounts": [],
            "start_parameter": f"subscription_{chat_id}",
            "provider_data": None,
            "photo_url": None,
            "photo_size": 0,
            "photo_width": 0,
            "photo_height": 0,
            "need_name": False,
            "need_phone_number": False,
            "need_email": False,
            "need_shipping_address": False,
            "send_phone_number_to_provider": False,
            "send_email_to_provider": False,
            "is_flexible": False,
            "disable_notification": False,
            "protect_content": False,
            "reply_to_message_id": None,
            "allow_sending_without_reply": True,
            "reply_markup": None,
            "subscription_period": subscription_period
        }
        
        result = self._make_request("sendInvoice", data)
        
        if result.get("ok") and "result" in result:
            return result["result"]
        else:
            logger.error(f"Ошибка при отправке инвойса: {result.get('description', 'Неизвестная ошибка')}")
            return None
    
    def answer_pre_checkout_query(self, pre_checkout_query_id: str, ok: bool, error_message: str = None) -> bool:
        """
        Ответ на pre_checkout запрос для подтверждения/отклонения платежа.
        
        Args:
            pre_checkout_query_id: ID запроса
            ok: True для подтверждения, False для отклонения
            error_message: Сообщение об ошибке (если ok=False)
            
        Returns:
            bool: Успешность операции
        """
        data = {
            "pre_checkout_query_id": pre_checkout_query_id,
            "ok": ok
        }
        
        if not ok and error_message:
            data["error_message"] = error_message
            
        result = self._make_request("answerPreCheckoutQuery", data)
        
        return result.get("ok", False)
        
    def get_user_subscription_status(self, user_id: Union[int, str]) -> Dict[str, Any]:
        """
        Получение статуса подписки пользователя.
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            Dict[str, Any]: Информация о подписке
        """
        # В Bot API нет прямого метода для проверки подписки на бота
        # Эта информация должна храниться в вашей базе данных
        # Здесь мы просто возвращаем заглушку
        logger.warning("Метод get_user_subscription_status не имеет прямого аналога в Bot API и должен быть реализован через базу данных")
        return {
            "success": False,
            "message": "Для проверки статуса подписки необходимо использовать базу данных"
        }
    
    def cancel_subscription(self, user_id: Union[int, str], charge_id: str) -> bool:
        """
        Отмена подписки пользователя.
        
        Args:
            user_id: ID пользователя в Telegram
            charge_id: ID транзакции начальной оплаты подписки
            
        Returns:
            bool: Успешность операции
        """
        data = {
            "user_id": user_id,
            "charge_id": charge_id
        }
        
        result = self._make_request("botCancelStarsSubscription", data)
        
        return result.get("ok", False)

def create_subscription_payment_button(amount: int) -> Dict[str, Any]:
    """
    Создает данные для кнопки оплаты подписки, которые должны быть переданы в WebApp.
    
    Args:
        amount: Количество Stars для оплаты (например, 70)
        
    Returns:
        Dict[str, Any]: Данные для обработки в WebApp
    """
    return {
        "type": "subscribe",
        "amount": amount,
        "currency": "XTR",
        "period": "monthly",
        "title": "Подписка на Smart Content Assistant"
    }

def initialize_payment_bot() -> Optional[TelegramBotPaymentAPI]:
    """
    Инициализация API для работы с платежами.
    
    Returns:
        Optional[TelegramBotPaymentAPI]: Инстанс API для работы с платежами или None в случае ошибки
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN не найден в окружении")
        return None
    
    try:
        payment_api = TelegramBotPaymentAPI(bot_token)
        logger.info("API для работы с платежами инициализирован успешно")
        return payment_api
    except Exception as e:
        logger.error(f"Ошибка при инициализации API для работы с платежами: {e}")
        return None

def create_subscription_invoice(user_id: str) -> Optional[str]:
    """
    Создание счета на оплату подписки в Telegram
    
    Args:
        user_id: ID пользователя в Telegram
        
    Returns:
        Optional[str]: URL для оплаты или None в случае ошибки
    """
    if not BOT_TOKEN or not os.getenv("TELEGRAM_PAYMENT_PROVIDER_TOKEN"):
        logger.error("Отсутствуют токены для Telegram API")
        return None
    
    # Формируем данные для создания инвойса
    invoice_data = {
        "title": "Подписка на Смарт Контент Ассистент",
        "description": f"Доступ к полному функционалу на {SUBSCRIPTION_PERIOD_DAYS} дней",
        "payload": json.dumps({
            "user_id": user_id,
            "subscription_type": "monthly",
            "timestamp": int(time.time())
        }),
        "provider_token": os.getenv("TELEGRAM_PAYMENT_PROVIDER_TOKEN"),
        "currency": "STARS",
        "prices": [{"label": "Подписка", "amount": SUBSCRIPTION_PRICE}],
        "start_parameter": f"subscription_{user_id}",
        # Время жизни инвойса - 1 день
        "expires_in": 86400  
    }
    
    try:
        # Отправляем запрос на создание инвойса
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/createInvoiceLink",
            json=invoice_data
        )
        
        # Обрабатываем ответ
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("ok") and "result" in response_data:
                return response_data["result"]
            else:
                logger.error(f"Ошибка API Telegram: {response_data}")
                return None
        else:
            logger.error(f"Ошибка HTTP: {response.status_code}, {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Ошибка при создании инвойса: {e}")
        return None

def verify_payment_data(payment_data: Dict[str, Any]) -> Tuple[Optional[str], bool]:
    """
    Проверка данных о платеже от Telegram
    
    Args:
        payment_data: Данные о платеже от Telegram
        
    Returns:
        Tuple[Optional[str], bool]: ID пользователя и результат проверки
    """
    try:
        # Получаем данные из платежа
        if "pre_checkout_query" in payment_data:
            # Обработка pre_checkout запроса
            query_id = payment_data["pre_checkout_query"]["id"]
            payload = json.loads(payment_data["pre_checkout_query"]["invoice_payload"])
            user_id = payload.get("user_id")
            
            # Отправляем подтверждение pre_checkout
            confirm_pre_checkout(query_id)
            return user_id, False  # Пока не подтверждаем подписку, это только предварительная проверка
            
        elif "message" in payment_data and "successful_payment" in payment_data["message"]:
            # Обработка успешного платежа
            payment_info = payment_data["message"]["successful_payment"]
            payload = json.loads(payment_info["invoice_payload"])
            user_id = payload.get("user_id")
            
            # Проверяем сумму платежа
            if payment_info["total_amount"] == SUBSCRIPTION_PRICE:
                return user_id, True
            else:
                logger.warning(f"Неверная сумма платежа: {payment_info['total_amount']}, ожидалось: {SUBSCRIPTION_PRICE}")
                return user_id, False
        else:
            logger.warning("Неизвестный формат данных платежа")
            return None, False
            
    except Exception as e:
        logger.error(f"Ошибка при проверке данных платежа: {e}")
        return None, False

def confirm_pre_checkout(query_id: str) -> bool:
    """
    Подтверждение pre_checkout запроса
    
    Args:
        query_id: ID запроса pre_checkout
        
    Returns:
        bool: Успешность операции
    """
    if not BOT_TOKEN:
        logger.error("Отсутствует токен бота Telegram")
        return False
    
    try:
        # Отправляем запрос на подтверждение pre_checkout
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/answerPreCheckoutQuery",
            json={
                "pre_checkout_query_id": query_id,
                "ok": True
            }
        )
        
        # Обрабатываем ответ
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("ok"):
                return True
            else:
                logger.error(f"Ошибка API Telegram: {response_data}")
                return False
        else:
            logger.error(f"Ошибка HTTP: {response.status_code}, {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при подтверждении pre_checkout: {e}")
        return False

def get_subscription_expiry_date() -> datetime:
    """
    Получение даты окончания подписки
    
    Returns:
        datetime: Дата окончания подписки
    """
    return datetime.now() + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)

def setup_payment_webhook():
    """
    Настраивает вебхук для получения уведомлений о платежах
    """
    if not bot:
        logger.error("Бот не инициализирован, невозможно настроить вебхук")
        return
        
    try:
        webhook_url = os.getenv("WEBHOOK_URL")
        if webhook_url:
            bot.set_webhook(url=webhook_url)
            logger.info(f"Вебхук установлен на: {webhook_url}")
        else:
            logger.warning("WEBHOOK_URL не найден в переменных окружения")
    except Exception as e:
        logger.error(f"Ошибка при установке вебхука: {e}")

def calculate_subscription_expiry(current_expiry: Optional[str] = None) -> str:
    """
    Рассчитывает дату истечения подписки (30 дней от текущей даты или от текущей даты истечения)
    
    Args:
        current_expiry: Текущая дата истечения в ISO формате (опционально)
        
    Returns:
        str: Новая дата истечения в ISO формате
    """
    now = datetime.datetime.now()
    
    if current_expiry:
        try:
            expiry_date = datetime.datetime.fromisoformat(current_expiry)
            # Если подписка еще активна, добавляем 30 дней к текущей дате истечения
            if expiry_date > now:
                new_expiry = expiry_date + datetime.timedelta(days=30)
            else:  # Если подписка истекла, добавляем 30 дней к текущей дате
                new_expiry = now + datetime.timedelta(days=30)
        except ValueError:
            # Если не удалось распарсить дату, используем текущую дату + 30 дней
            new_expiry = now + datetime.timedelta(days=30)
    else:
        # Если нет текущей даты истечения, используем текущую дату + 30 дней
        new_expiry = now + datetime.timedelta(days=30)
    
    return new_expiry.isoformat() 