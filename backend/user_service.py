import os
import json
import logging
import datetime
from typing import Dict, Any, Optional, Tuple
from supabase import create_client, Client
from dotenv import load_dotenv
from telegram_utils import calculate_subscription_expiry

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Инициализация Supabase клиента
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    logger.error("SUPABASE_URL или SUPABASE_KEY не найдены в переменных окружения")
    supabase = None
else:
    supabase = create_client(supabase_url, supabase_key)

class UserService:
    @staticmethod
    def get_user(user_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о пользователе из базы данных
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            Optional[Dict[str, Any]]: Данные пользователя или None, если пользователь не найден
        """
        if not supabase:
            logger.error("Supabase клиент не инициализирован")
            return None
            
        try:
            response = supabase.table("app_users").select("*").eq("user_id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            else:
                logger.info(f"Пользователь {user_id} не найден")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя: {e}")
            return None
    
    @staticmethod
    def create_user(user_id: str) -> Optional[Dict[str, Any]]:
        """
        Создает нового пользователя в базе данных
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            Optional[Dict[str, Any]]: Созданные данные пользователя или None в случае ошибки
        """
        if not supabase:
            logger.error("Supabase клиент не инициализирован")
            return None
            
        try:
            # Установка начальных значений для нового пользователя
            user_data = {
                "user_id": user_id,
                "subscription_expires_at": None,
                "free_analysis_count": 2,
                "free_post_details_count": 2,
                "created_at": datetime.datetime.now().isoformat(),
                "updated_at": datetime.datetime.now().isoformat()
            }
            
            response = supabase.table("app_users").insert(user_data).execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"Пользователь {user_id} успешно создан")
                return response.data[0]
            else:
                logger.error(f"Ошибка при создании пользователя {user_id}: пустой ответ")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при создании пользователя: {e}")
            return None
    
    @staticmethod
    def get_or_create_user(user_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о пользователе или создает нового, если не существует
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            Optional[Dict[str, Any]]: Данные пользователя или None в случае ошибки
        """
        user = UserService.get_user(user_id)
        if not user:
            user = UserService.create_user(user_id)
        return user
    
    @staticmethod
    def update_user(user_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Обновляет данные пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            data: Данные для обновления
            
        Returns:
            Optional[Dict[str, Any]]: Обновленные данные пользователя или None в случае ошибки
        """
        if not supabase:
            logger.error("Supabase клиент не инициализирован")
            return None
            
        try:
            # Добавляем updated_at к обновляемым данным
            update_data = {**data, "updated_at": datetime.datetime.now().isoformat()}
            
            response = supabase.table("app_users").update(update_data).eq("user_id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"Пользователь {user_id} успешно обновлен")
                return response.data[0]
            else:
                logger.error(f"Ошибка при обновлении пользователя {user_id}: пустой ответ")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении пользователя: {e}")
            return None
    
    @staticmethod
    def update_subscription(user_id: str) -> Tuple[bool, str]:
        """
        Обновляет информацию о подписке пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        user = UserService.get_or_create_user(user_id)
        if not user:
            return False, "Не удалось получить информацию о пользователе"
            
        try:
            # Рассчитываем новую дату истечения подписки
            current_expiry = user.get("subscription_expires_at")
            new_expiry = calculate_subscription_expiry(current_expiry)
            
            # Обновляем данные пользователя
            update_data = {"subscription_expires_at": new_expiry}
            updated_user = UserService.update_user(user_id, update_data)
            
            if updated_user:
                return True, f"Подписка успешно обновлена до {new_expiry}"
            else:
                return False, "Не удалось обновить информацию о подписке"
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении подписки: {e}")
            return False, f"Ошибка при обновлении подписки: {str(e)}"
    
    @staticmethod
    def check_subscription_status(user_id: str) -> Dict[str, Any]:
        """
        Проверяет статус подписки пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            Dict[str, Any]: Информация о статусе подписки
        """
        user = UserService.get_or_create_user(user_id)
        result = {
            "has_subscription": False,
            "free_analysis_count": 0,
            "free_post_details_count": 0,
            "subscription_expires_at": None,
            "days_left": 0
        }
        
        if not user:
            return result
            
        # Заполняем доступные бесплатные попытки
        result["free_analysis_count"] = user.get("free_analysis_count", 0)
        result["free_post_details_count"] = user.get("free_post_details_count", 0)
        
        # Проверяем активность подписки
        expiry_str = user.get("subscription_expires_at")
        result["subscription_expires_at"] = expiry_str
        
        if expiry_str:
            try:
                expiry_date = datetime.datetime.fromisoformat(expiry_str)
                now = datetime.datetime.now()
                
                if expiry_date > now:
                    result["has_subscription"] = True
                    delta = expiry_date - now
                    result["days_left"] = delta.days
            except ValueError:
                logger.error(f"Некорректный формат даты истечения подписки: {expiry_str}")
                
        return result
    
    @staticmethod
    def use_free_analysis(user_id: str) -> bool:
        """
        Использует одну бесплатную попытку анализа
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            bool: True, если успешно использована, False в противном случае
        """
        user = UserService.get_or_create_user(user_id)
        if not user:
            return False
            
        free_count = user.get("free_analysis_count", 0)
        if free_count <= 0:
            return False
            
        update_data = {"free_analysis_count": free_count - 1}
        updated_user = UserService.update_user(user_id, update_data)
        
        return updated_user is not None
    
    @staticmethod
    def use_free_post_details(user_id: str) -> bool:
        """
        Использует одну бесплатную попытку получения деталей поста
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            bool: True, если успешно использована, False в противном случае
        """
        user = UserService.get_or_create_user(user_id)
        if not user:
            return False
            
        free_count = user.get("free_post_details_count", 0)
        if free_count <= 0:
            return False
            
        update_data = {"free_post_details_count": free_count - 1}
        updated_user = UserService.update_user(user_id, update_data)
        
        return updated_user is not None 