import asyncio
import asyncpg
import os
from dotenv import load_dotenv
import sys

# Загрузка переменных окружения
load_dotenv()

# ID пользователя из скриншота базы данных
USER_ID = 427032240

async def fix_subscription():
    # Подключение к базе данных
    conn_string = os.getenv("DATABASE_URL")
    if not conn_string:
        print("Ошибка: переменная окружения DATABASE_URL не установлена")
        return
    
    conn = await asyncpg.connect(conn_string)
    
    try:
        # Дополнительный аргумент command_line - проверить подписку без исправления
        check_only = len(sys.argv) > 1 and sys.argv[1] == '--check'
        
        print(f"{'Проверка' if check_only else 'Исправление'} подписки для user_id: {USER_ID}")
        
        # Получить текущее время на сервере
        server_time = await conn.fetchval("SELECT NOW()")
        print(f"Текущее время на сервере: {server_time}")
        
        # Проверить все подписки для данного пользователя
        all_subscriptions = await conn.fetch(
            "SELECT * FROM user_subscription WHERE user_id = $1",
            USER_ID
        )
        
        print(f"Найдено {len(all_subscriptions)} подписок для пользователя {USER_ID}")
        
        if not all_subscriptions:
            print("Подписки не найдены. Создаем новую подписку...")
            if not check_only:
                # Создать новую подписку на 1 месяц
                result = await conn.fetchrow("""
                INSERT INTO user_subscription
                (user_id, start_date, end_date, is_active, payment_id)
                VALUES 
                ($1, NOW(), NOW() + INTERVAL '1 month', TRUE, 'manual_fix_' || extract(epoch from now())::int)
                RETURNING id, start_date, end_date, is_active
                """, USER_ID)
                
                print(f"Создана новая подписка: ID={result['id']}, начало={result['start_date']}, окончание={result['end_date']}, активна={result['is_active']}")
            else:
                print("Режим проверки - новая подписка не создается")
            return
        
        # Проверить, есть ли активные подписки
        valid_subscription = None
        for sub in all_subscriptions:
            end_date = sub['end_date']
            is_active = sub['is_active']
            
            if end_date > server_time:
                print(f"Найдена подписка (ID={sub['id']}) с end_date в будущем: {end_date}")
                valid_subscription = sub
                
                if not is_active:
                    print(f"Подписка (ID={sub['id']}) имеет is_active=FALSE, но срок не истек")
                    if not check_only:
                        # Активировать подписку
                        await conn.execute(
                            "UPDATE user_subscription SET is_active = TRUE, updated_at = NOW() WHERE id = $1",
                            sub['id']
                        )
                        print(f"Подписка ID={sub['id']} активирована")
                else:
                    print(f"Подписка (ID={sub['id']}) активна и действительна")
                    
                # Нашли действительную подписку, можно останавливаться
                break
        
        # Если нет действительных подписок, но есть записи в таблице
        if not valid_subscription:
            print("Не найдено действующих подписок (с end_date в будущем)")
            
            # Находим самую последнюю подписку
            latest_subscription = sorted(all_subscriptions, key=lambda x: x['end_date'], reverse=True)[0]
            
            if not check_only:
                # Продлеваем эту подписку на 1 месяц от текущей даты
                new_end_date = await conn.fetchval("SELECT NOW() + INTERVAL '1 month'")
                
                await conn.execute(
                    """
                    UPDATE user_subscription 
                    SET end_date = $1, is_active = TRUE, updated_at = NOW() 
                    WHERE id = $2
                    """,
                    new_end_date, latest_subscription['id']
                )
                
                print(f"Подписка ID={latest_subscription['id']} продлена до {new_end_date}")
            else:
                print(f"Режим проверки - подписка ID={latest_subscription['id']} не продлевается")
    
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_subscription()) 