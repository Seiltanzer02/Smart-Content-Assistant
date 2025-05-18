import os
import logging
import asyncpg
from telethon import TelegramClient, functions
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('partner_referral.log')
    ]
)
logger = logging.getLogger('partner_referral')

# Загрузка переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = int(os.getenv("TELEGRAM_API_ID", 0))  # Замените на ваш API ID из my.telegram.org
API_HASH = os.getenv("TELEGRAM_API_HASH", "")  # Замените на ваш API Hash из my.telegram.org

class PartnerReferralService:
    def __init__(self, db_pool: asyncpg.Pool):
        """
        Инициализация сервиса для работы с партнерскими ссылками
        
        :param db_pool: Пул соединений с базой данных
        """
        self.db_pool = db_pool
        self.telegram_client = None
        
    async def init_telegram_client(self, session_name='partner_session'):
        """
        Инициализирует клиент Telethon для работы с API Telegram
        
        :param session_name: Имя файла сессии
        """
        if not API_ID or not API_HASH:
            raise ValueError("API_ID и API_HASH должны быть указаны в переменных окружения")
            
        self.telegram_client = TelegramClient(session_name, API_ID, API_HASH)
        await self.telegram_client.start()
        logger.info("Telegram клиент инициализирован успешно")
        
    async def get_partner_link(self, user_id: int) -> str:
        """
        Получает партнерскую ссылку для пользователя из базы данных
        или создает новую, если она отсутствует
        
        :param user_id: ID пользователя Telegram
        :return: Партнерская ссылка
        """
        # Проверяем, есть ли уже партнерская ссылка в БД
        async with self.db_pool.acquire() as conn:
            partner_link = await conn.fetchval(
                "SELECT partner_link FROM user_settings WHERE user_id = $1",
                user_id
            )
            
            # Если ссылка уже существует, возвращаем её
            if partner_link:
                logger.info(f"Найдена существующая партнерская ссылка для пользователя {user_id}")
                return partner_link
                
            # Если ссылки нет, генерируем новую
            try:
                if not self.telegram_client:
                    await self.init_telegram_client()
                    
                # Извлекаем username бота из токена
                bot_username = None
                if TELEGRAM_BOT_TOKEN:
                    bot_username = f"@{TELEGRAM_BOT_TOKEN.split(':')[0]}"
                    
                if not bot_username:
                    raise ValueError("Не удалось определить username бота из TELEGRAM_BOT_TOKEN")
                    
                # Вызываем метод API для получения партнерской ссылки
                result = await self.telegram_client(functions.payments.ConnectStarRefBotRequest(
                    bot=bot_username  # Используем username бота
                ))
                
                # Получаем ссылку из результата
                new_link = result.link
                logger.info(f"Сгенерирована новая партнерская ссылка для пользователя {user_id}: {new_link}")
                
                # Сохраняем ссылку в базе данных
                await conn.execute(
                    """
                    INSERT INTO user_settings (user_id, partner_link) 
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET partner_link = $2, updated_at = NOW()
                    """,
                    user_id, new_link
                )
                
                # Добавляем запись в таблицу user_referrals, если еще не существует
                await self._ensure_referral_record(user_id, conn)
                
                return new_link
                
            except Exception as e:
                logger.error(f"Ошибка при получении партнерской ссылки для пользователя {user_id}: {e}")
                raise
                
    async def _ensure_referral_record(self, referrer_id: int, conn=None):
        """
        Убеждаемся, что у пользователя есть запись в таблице user_referrals
        
        :param referrer_id: ID пользователя-реферера
        :param conn: Соединение с БД или None
        """
        should_release = False
        if not conn:
            conn = await self.db_pool.acquire()
            should_release = True
            
        try:
            # Проверяем наличие записи
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM user_referrals WHERE referrer_id = $1)",
                referrer_id
            )
            
            if not exists:
                # Создаем запись, если не существует
                await conn.execute(
                    """
                    INSERT INTO user_referrals (referrer_id, referred_id, created_at, reward_given)
                    VALUES ($1, NULL, NOW(), FALSE)
                    """,
                    referrer_id
                )
                logger.info(f"Создана запись в user_referrals для пользователя {referrer_id}")
                
        finally:
            if should_release and conn:
                await self.db_pool.release(conn)
                
    async def track_referral(self, referrer_id: int, referred_id: int):
        """
        Отслеживает реферальную активность: когда новый пользователь 
        регистрируется по партнерской ссылке
        
        :param referrer_id: ID пользователя-реферера
        :param referred_id: ID привлеченного пользователя
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Проверяем, была ли уже учтена эта связь
                exists = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM user_referrals 
                        WHERE referrer_id = $1 AND referred_id = $2
                    )
                    """,
                    referrer_id, referred_id
                )
                
                if not exists:
                    # Создаем новую запись
                    await conn.execute(
                        """
                        INSERT INTO user_referrals 
                        (referrer_id, referred_id, created_at, reward_given)
                        VALUES ($1, $2, NOW(), FALSE)
                        """,
                        referrer_id, referred_id
                    )
                    logger.info(f"Отслежена новая реферальная активность: {referrer_id} → {referred_id}")
                    
                    # Здесь могла бы быть логика для начисления вознаграждения партнеру
                    
        except Exception as e:
            logger.error(f"Ошибка при отслеживании реферальной активности: {e}")
            raise
            
    async def get_referral_stats(self, user_id: int):
        """
        Получает статистику по реферальной программе для пользователя
        
        :param user_id: ID пользователя
        :return: Словарь со статистикой
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Получаем количество привлеченных пользователей
                referred_count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM user_referrals 
                    WHERE referrer_id = $1 AND referred_id IS NOT NULL
                    """,
                    user_id
                )
                
                # Получаем количество вознаграждений
                rewards_count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM user_referrals 
                    WHERE referrer_id = $1 AND referred_id IS NOT NULL AND reward_given = TRUE
                    """,
                    user_id
                )
                
                # Получаем партнерскую ссылку
                partner_link = await conn.fetchval(
                    "SELECT partner_link FROM user_settings WHERE user_id = $1",
                    user_id
                )
                
                return {
                    "user_id": user_id,
                    "referred_users": referred_count,
                    "rewards_received": rewards_count,
                    "partner_link": partner_link
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики рефералов для пользователя {user_id}: {e}")
            raise
            
# Функция для получения экземпляра сервиса
async def get_partner_referral_service(db_pool=None):
    """
    Создает и возвращает экземпляр PartnerReferralService
    
    :param db_pool: Пул соединений с базой данных или None
    :return: Экземпляр PartnerReferralService
    """
    if not db_pool:
        # Если пул не передан, создаем новый
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL не указан в переменных окружения")
            
        db_pool = await asyncpg.create_pool(db_url)
        
    service = PartnerReferralService(db_pool)
    return service 