from fastapi import Request, HTTPException
from typing import List, Dict, Any, Optional
from backend.telegram_utils import get_telegram_posts_via_http, get_telegram_posts_via_telethon, get_sample_posts
from backend.deepseek_utils import analyze_content_with_deepseek
from backend.main import supabase, logger, OPENROUTER_API_KEY
from backend.services.supabase_subscription_service import SupabaseSubscriptionService
from datetime import datetime
from pydantic import BaseModel

class AnalyzeRequest(BaseModel):
    username: str

class AnalyzeResponse(BaseModel):
    themes: List[str]
    styles: List[str]
    analyzed_posts_sample: List[str]
    best_posting_time: str
    analyzed_posts_count: int
    message: Optional[str] = None
    error: Optional[str] = None

async def analyze_channel(request: Request, req: AnalyzeRequest):
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    logger.info(f"Начинаем анализ канала от пользователя: {telegram_user_id}")
    if not telegram_user_id or not telegram_user_id.isdigit():
        raise HTTPException(status_code=401, detail="Ошибка авторизации: не удалось получить корректный Telegram ID. Откройте приложение внутри Telegram.")
    try:
        subscription_service = SupabaseSubscriptionService(supabase)
        can_analyze = await subscription_service.can_analyze_channel(int(telegram_user_id))
        if not can_analyze:
            usage = await subscription_service.get_user_usage(int(telegram_user_id))
            reset_at = usage.get("reset_at")
            raise HTTPException(status_code=403, detail=f"Достигнут лимит анализа каналов для бесплатной подписки. Следующая попытка будет доступна после: {reset_at}. Оформите подписку для снятия ограничений.")
        username = req.username.replace("@", "").strip()
        posts = []
        errors_list = []
        error_message = None
        # 1. HTTP парсер
        try:
            logger.info(f"Пытаемся получить посты канала @{username} через HTTP парсинг")
            http_posts = await get_telegram_posts_via_http(username)
            if http_posts and len(http_posts) > 0:
                posts = [{"text": post} for post in http_posts]
                logger.info(f"Успешно получено {len(posts)} постов через HTTP парсинг")
            else:
                logger.warning(f"HTTP парсинг не вернул постов для канала @{username}, пробуем Telethon")
                errors_list.append("HTTP: Не получены посты, пробуем Telethon")
        except Exception as http_error:
            logger.error(f"Ошибка при HTTP парсинге для канала @{username}: {http_error}")
            errors_list.append(f"HTTP: {str(http_error)}")
        # 2. Telethon
        if not posts:
            try:
                logger.info(f"Пытаемся получить посты канала @{username} через Telethon")
                telethon_posts, telethon_error = await get_telegram_posts_via_telethon(username)
                if telethon_error:
                    logger.warning(f"Ошибка Telethon для канала @{username}: {telethon_error}")
                    errors_list.append(f"Telethon: {telethon_error}")
                else:
                    posts = telethon_posts
                    logger.info(f"Успешно получено {len(posts)} постов через Telethon")
            except Exception as e:
                logger.error(f"Непредвиденная ошибка при получении постов канала @{username} через Telethon: {e}")
                errors_list.append(f"Ошибка Telethon: {str(e)}")
        # 3. Примеры
        sample_data_used = False
        if not posts:
            logger.warning(f"Используем примеры постов для канала {username}")
            sample_posts = get_sample_posts(username)
            posts = [{"text": post} for post in sample_posts]
            error_message = "Не удалось получить реальные посты. Используются примеры для демонстрации."
            errors_list.append(error_message)
            sample_data_used = True
            logger.info(f"Используем примеры постов для канала {username}")
        # 4. Анализируем первые 20 постов
        posts = posts[:20]
        logger.info(f"Анализируем {len(posts)} постов")
        texts = [post.get("text", "") for post in posts if post.get("text")]
        analysis_result = await analyze_content_with_deepseek(texts, OPENROUTER_API_KEY)
        themes = analysis_result.get("themes", [])
        styles = analysis_result.get("styles", [])
        # 5. Сохраняем результат анализа в БД
        try:
            analysis_data = {
                "user_id": int(telegram_user_id),
                "channel_name": username,
                "themes": themes,
                "styles": styles,
                "analyzed_posts_count": len(posts),
                "sample_posts": posts[:5],
                "best_posting_time": "18:00-20:00",  # Можно доработать
                "is_sample_data": sample_data_used,
                "updated_at": datetime.now().isoformat()
            }
            analysis_check = supabase.table("channel_analysis").select("id").eq("user_id", telegram_user_id).eq("channel_name", username).execute()
            if hasattr(analysis_check, 'data') and len(analysis_check.data) > 0:
                supabase.table("channel_analysis").update(analysis_data).eq("user_id", telegram_user_id).eq("channel_name", username).execute()
            else:
                supabase.table("channel_analysis").insert(analysis_data).execute()
            # --- Обновляем allChannels в user_settings ---
            user_settings_result = supabase.table("user_settings").select("allChannels").eq("user_id", telegram_user_id).maybe_single().execute()
            all_channels = []
            if hasattr(user_settings_result, 'data') and user_settings_result.data and user_settings_result.data.get("allChannels"):
                all_channels = user_settings_result.data["allChannels"]
            if username not in all_channels:
                all_channels.append(username)
                supabase.table("user_settings").update({"allChannels": all_channels, "updated_at": datetime.now().isoformat()}).eq("user_id", telegram_user_id).execute()
        except Exception as db_error:
            logger.error(f"Ошибка при сохранении результатов анализа в БД: {db_error}")
        # 6. Увеличиваем счетчик использования
        try:
            await subscription_service.increment_analysis_usage(int(telegram_user_id))
        except Exception as counter_error:
            logger.error(f"Ошибка при увеличении счетчика анализа: {counter_error}")
        # 7. Возвращаем результат
        return AnalyzeResponse(
            themes=themes,
            styles=styles,
            analyzed_posts_sample=[post.get("text", "") for post in posts[:5]],
            best_posting_time="18:00-20:00",
            analyzed_posts_count=len(posts),
            message=error_message
        )
    except Exception as e:
        logger.error(f"Ошибка при анализе канала для пользователя {telegram_user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}") 