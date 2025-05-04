import os
import json
import hashlib
import hmac
import urllib.parse
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def validate_telegram_init_data(init_data: str, bot_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Проверяет подпись Telegram initData и возвращает разобранные данные.
    Если проверка не пройдена, возвращает None.
    
    Args:
        init_data: строка initData от Telegram WebApp
        bot_token: токен бота Telegram (если не указан, берется из переменной окружения)
        
    Returns:
        Словарь с данными или None при ошибке
    """
    if not init_data:
        return None
    
    # Получаем токен бота
    if not bot_token:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            logger.error("Не найден TELEGRAM_BOT_TOKEN для валидации initData")
            return None
    
    try:
        # Разбор строки запроса в словарь
        data_dict = dict(urllib.parse.parse_qsl(init_data))
        
        # Извлекаем hash из данных
        received_hash = data_dict.pop('hash', None)
        if not received_hash:
            logger.error("Hash отсутствует в initData")
            return None
        
        # Создание списка пар ключ=значение, отсортированных по ключу
        data_check_list = []
        for key in sorted(data_dict.keys()):
            data_check_list.append(f"{key}={data_dict[key]}")
        
        # Соединение в строку с разделителем \n
        data_check_string = '\n'.join(data_check_list)
        
        # Создание SHA-256 HMAC хеша с секретным ключом
        secret_key = hashlib.sha256(bot_token.encode()).digest()
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Сравнение полученного хеша с вычисленным
        if received_hash != calculated_hash:
            logger.warning(f"Неверная подпись initData: {received_hash} != {calculated_hash}")
            return None
        
        # Если проверка успешна, возвращаем данные с дополнительной обработкой user данных
        if 'user' in data_dict:
            try:
                data_dict['user'] = json.loads(data_dict['user'])
            except json.JSONDecodeError:
                logger.warning("Не удалось разобрать JSON данных пользователя")
        
        return data_dict
    
    except Exception as e:
        logger.error(f"Ошибка при валидации initData: {e}")
        return None

def get_user_id_from_init_data(init_data: str) -> Optional[int]:
    """
    Извлекает ID пользователя из Telegram initData
    
    Args:
        init_data: строка initData от Telegram WebApp
        
    Returns:
        ID пользователя или None при ошибке
    """
    data = validate_telegram_init_data(init_data)
    if data and isinstance(data.get('user'), dict):
        user_id = data['user'].get('id')
        if user_id:
            try:
                return int(user_id)
            except (ValueError, TypeError):
                logger.error(f"Некорректный ID пользователя в initData: {user_id}")
    
    return None 