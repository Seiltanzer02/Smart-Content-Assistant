# Smart Content Assistant

Это бэкенд для Telegram Mini App "Smart Content Assistant".

## Установка

1.  Клонируйте репозиторий.
2.  Создайте и активируйте виртуальное окружение:
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```
3.  Установите зависимости:
    ```bash
    pip install -r requirements.txt
    ```
4.  Создайте файл `.env` на основе `.env.example` и заполните его вашими API-ключами и настройками.
5.  Запустите приложение:
    ```bash
    uvicorn main:app --reload
    ```

Приложение будет доступно по адресу `http://127.0.0.1:8000`. 