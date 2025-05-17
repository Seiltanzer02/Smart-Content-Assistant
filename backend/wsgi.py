"""
WSGI модуль для запуска приложения через WSGI-совместимые серверы (gunicorn, uwsgi и т.д.).
"""

import os
import sys

# Добавляем текущую директорию в путь, чтобы импорты работали правильно
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app

# Добавляем роутер проверки подписки на канал
try:
    from backend.routers.channel_subscription import router as channel_subscription_router
    app.include_router(channel_subscription_router)
    print("=== Роутер проверки подписки на канал успешно подключен через wsgi.py ===")
except Exception as e:
    print(f"=== ОШИБКА при подключении роутера проверки подписки через wsgi.py: {e} ===")

# Для gunicorn используйте: gunicorn wsgi:app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False) 