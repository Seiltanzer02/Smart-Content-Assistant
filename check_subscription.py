import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# ID пользователя из скриншота базы данных
USER_ID = 427032240

async def check_subscription():
    # Подключение к базе данных
    conn_string = os.getenv("DATABASE_URL")
    if not conn_string:
        print("Ошибка: переменная окружения DATABASE_URL не установлена")
        return
    
    conn = await asyncpg.connect(conn_string)
    
    try:
        print(f"Проверка подписки для user_id: {USER_ID}")
        
        # 1. Получить все записи для пользователя
        all_subscriptions = await conn.fetch(
            "SELECT * FROM user_subscription WHERE user_id = $1",
            USER_ID
        )
        print(f"\nВсе подписки пользователя ({len(all_subscriptions)}):")
        for sub in all_subscriptions:
            print(f"ID: {sub['id']}, active: {sub['is_active']}, start: {sub['start_date']}, end: {sub['end_date']}")
        
        # 2. Получить текущее время на сервере
        server_time = await conn.fetchval("SELECT NOW()")
        print(f"\nТекущее время на сервере: {server_time}")
        
        # 3. Проверить активные подписки
        active_subs = await conn.fetch(
            "SELECT * FROM user_subscription WHERE user_id = $1 AND is_active = TRUE AND end_date > NOW()",
            USER_ID
        )
        print(f"\nАктивные подписки ({len(active_subs)}):")
        for sub in active_subs:
            print(f"ID: {sub['id']}, end_date: {sub['end_date']}")
        
        # 4. Проверить, почему подписка может быть неактивна
        inactive_reasons = await conn.fetch(
            """
            SELECT id, 
                is_active,
                end_date,
                NOW() as current_time,
                CASE 
                    WHEN NOT is_active THEN 'Флаг is_active установлен в FALSE'
                    WHEN end_date <= NOW() THEN 'Срок подписки истек'
                    ELSE 'Подписка должна быть активна'
                END as reason
            FROM user_subscription 
            WHERE user_id = $1
            """,
            USER_ID
        )
        print("\nПричины неактивности подписок:")
        for row in inactive_reasons:
            print(f"ID: {row['id']}, Причина: {row['reason']}, is_active: {row['is_active']}, end_date: {row['end_date']}")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_subscription()) 