# Сервис для работы с изображениями
from fastapi import Request, HTTPException, Response
from typing import Dict, Any, List, Optional
from backend.main import supabase, logger
import uuid

async def save_image(request: Request, image_data: Dict[str, Any]):
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос сохранения изображения без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для сохранения изображения необходимо авторизоваться через Telegram")
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        image_to_save = image_data.copy()
        image_to_save["user_id"] = int(telegram_user_id)
        image_to_save["id"] = str(uuid.uuid4())
        result = supabase.table("saved_images").insert(image_to_save).execute()
        if hasattr(result, 'data') and len(result.data) > 0:
            logger.info(f"Сохранено новое изображение для пользователя {telegram_user_id}")
            return {"success": True, "id": image_to_save["id"]}
        else:
            logger.error(f"Ошибка при сохранении изображения: {result}")
            raise HTTPException(status_code=500, detail="Ошибка при сохранении изображения")
    except Exception as e:
        logger.error(f"Ошибка при сохранении изображения: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении изображения: {str(e)}")

async def get_user_images(request: Request, limit: int = 20):
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос изображений без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для доступа к изображениям необходимо авторизоваться через Telegram")
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        result = supabase.table("saved_images").select("*").eq("user_id", int(telegram_user_id)).order("created_at", desc=True).limit(limit).execute()
        if not hasattr(result, 'data'):
            logger.error(f"Ошибка при получении изображений из БД: {result}")
            return []
        return result.data
    except Exception as e:
        logger.error(f"Ошибка при получении изображений: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при получении изображений: {str(e)}")

async def get_image_by_id(request: Request, image_id: str):
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос изображения по ID без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для доступа к изображению необходимо авторизоваться через Telegram")
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        result = supabase.table("saved_images").select("*").eq("id", image_id).eq("user_id", int(telegram_user_id)).maybe_single().execute()
        if not hasattr(result, 'data') or not result.data:
            logger.warning(f"Изображение {image_id} не найдено или не принадлежит пользователю {telegram_user_id}")
            raise HTTPException(status_code=404, detail="Изображение не найдено")
        return result.data
    except Exception as e:
        logger.error(f"Ошибка при получении изображения по ID: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при получении изображения: {str(e)}")

async def get_post_images(request: Request, post_id: str):
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос изображений поста без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для доступа к изображениям поста необходимо авторизоваться через Telegram")
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        result = supabase.table("post_images").select("*").eq("post_id", post_id).execute()
        if not hasattr(result, 'data'):
            logger.error(f"Ошибка при получении изображений поста из БД: {result}")
            return []
        return result.data
    except Exception as e:
        logger.error(f"Ошибка при получении изображений поста: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при получении изображений поста: {str(e)}")

async def proxy_image(request: Request, image_id: str, size: Optional[str] = None):
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос проксирования изображения без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для доступа к изображению необходимо авторизоваться через Telegram")
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        result = supabase.table("saved_images").select("*").eq("id", image_id).eq("user_id", int(telegram_user_id)).maybe_single().execute()
        if not hasattr(result, 'data') or not result.data:
            logger.warning(f"Изображение {image_id} не найдено или не принадлежит пользователю {telegram_user_id}")
            raise HTTPException(status_code=404, detail="Изображение не найдено")
        image_url = result.data.get("url")
        if not image_url:
            logger.error(f"URL изображения отсутствует для изображения {image_id}")
            raise HTTPException(status_code=404, detail="URL изображения отсутствует")
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            if response.status_code == 200:
                return Response(content=response.content, media_type="image/jpeg")
            else:
                logger.error(f"Ошибка при проксировании изображения: {response.status_code}")
                raise HTTPException(status_code=500, detail="Ошибка при получении изображения с внешнего источника")
    except Exception as e:
        logger.error(f"Ошибка при проксировании изображения: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при проксировании изображения: {str(e)}") 