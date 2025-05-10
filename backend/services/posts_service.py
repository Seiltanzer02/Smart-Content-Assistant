# Сервис для работы с постами
from fastapi import Request, HTTPException
from typing import Dict, Any, List, Optional
from backend.main import supabase, logger
from pydantic import BaseModel
import uuid
import asyncio
from datetime import datetime
import traceback

# Импорт моделей PostImage, PostData, SavedPostResponse, PostDetailsResponse из main.py или отдельного файла моделей
# from backend.models import PostImage, PostData, SavedPostResponse, PostDetailsResponse

async def get_posts(request: Request, channel_name: Optional[str] = None):
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос постов без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для доступа к постам необходимо авторизоваться через Telegram")
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        query = supabase.table("saved_posts").select("*, saved_images(*)").eq("user_id", int(telegram_user_id))
        if channel_name:
            query = query.eq("channel_name", channel_name)
        result = query.order("target_date", desc=True).execute()
        if not hasattr(result, 'data'):
            logger.error(f"Ошибка при получении постов из БД: {result}")
            return []
        posts_with_images = []
        for post_data in result.data:
            response_item = post_data  # Здесь должен быть SavedPostResponse(**post_data), если модель импортирована
            image_relation_data = post_data.get("saved_images")
            logger.info(f"Обработка поста ID: {post_data.get('id')}. Связанные данные изображения: {image_relation_data}")
            if image_relation_data and isinstance(image_relation_data, dict):
                try:
                    alt_text = image_relation_data.get("alt_description") or image_relation_data.get("alt")
                    response_item["selected_image_data"] = {
                        "id": image_relation_data.get("id"),
                        "url": image_relation_data.get("url"),
                        "preview_url": image_relation_data.get("preview_url"),
                        "alt": alt_text,
                        "author": image_relation_data.get("author"),
                        "author_url": image_relation_data.get("author_url"),
                        "source": image_relation_data.get("source")
                    }
                    logger.info(f"Успешно создано selected_image_data для поста {post_data.get('id')} с изображением ID: {image_relation_data.get('id')}")
                except Exception as mapping_error:
                    logger.error(f"Ошибка при создании PostImage для поста {post_data.get('id')}: {mapping_error}")
                    logger.error(f"Данные изображения: {image_relation_data}")
                    response_item["selected_image_data"] = None
            else:
                response_item["selected_image_data"] = None
                if post_data.get("saved_image_id"):
                    logger.warning(f"Для поста {post_data['id']} есть saved_image_id, но связанные данные изображения не были получены или пусты. Связанные данные: {image_relation_data}")
            posts_with_images.append(response_item)
        return posts_with_images
    except Exception as e:
        logger.error(f"Ошибка при получении постов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def create_post(request: Request, post_data):
    try:
        from backend.main import fix_schema, download_and_save_external_image
        try:
            logger.info("Вызов fix_schema перед созданием поста...")
            fix_result = await fix_schema()
            if not fix_result.get("success"):
                logger.warning(f"Не удалось обновить/проверить схему перед созданием поста: {fix_result}")
            else:
                logger.info("Проверка/обновление схемы перед созданием поста завершена успешно.")
        except Exception as pre_save_fix_err:
            logger.error(f"Ошибка при вызове fix_schema перед созданием поста: {pre_save_fix_err}", exc_info=True)
        logger.info("Небольшая пауза после fix_schema, чтобы дать PostgREST время...")
        await asyncio.sleep(0.7)
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос создания поста без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для создания поста необходимо авторизоваться через Telegram")
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        selected_image = post_data.selected_image_data
        post_to_save = post_data.dict(exclude={"selected_image_data"})
        post_to_save["user_id"] = int(telegram_user_id)
        post_to_save["id"] = str(uuid.uuid4())
        if not post_to_save.get("target_date"):
            logger.warning(f"Получена пустая target_date для нового поста {post_to_save['id']}, устанавливаем в NULL.")
            post_to_save["target_date"] = None
        else:
            try:
                datetime.strptime(post_to_save["target_date"], '%Y-%m-%d')
            except ValueError:
                logger.error(f"Некорректный формат target_date: {post_to_save['target_date']} для поста {post_to_save['id']}. Устанавливаем в NULL.")
                post_to_save["target_date"] = None
        saved_image_id = None
        if selected_image:
            try:
                logger.info(f"Обработка выбранного изображения: {selected_image.dict() if hasattr(selected_image, 'dict') else selected_image}")
                is_external_image = selected_image.source in ["unsplash", "pexels", "openverse"]
                if is_external_image:
                    logger.info(f"Обнаружено внешнее изображение с источником {selected_image.source}")
                    try:
                        external_image_result = await download_and_save_external_image(selected_image, int(telegram_user_id))
                        saved_image_id = external_image_result["id"]
                        if external_image_result.get("is_new", False) and external_image_result.get("url"):
                            selected_image.url = external_image_result["url"]
                            if external_image_result.get("preview_url"):
                                selected_image.preview_url = external_image_result["preview_url"]
                            selected_image.source = f"{selected_image.source}_saved"
                        logger.info(f"Внешнее изображение успешно обработано, saved_image_id: {saved_image_id}")
                    except Exception as ext_img_err:
                        logger.error(f"Ошибка при обработке внешнего изображения: {ext_img_err}")
                        raise HTTPException(status_code=500, detail=f"Не удалось обработать внешнее изображение: {str(ext_img_err)}")
                else:
                    image_check = None
                    if selected_image.url:
                        image_check_result = supabase.table("saved_images").select("id").eq("url", selected_image.url).limit(1).execute()
                        if hasattr(image_check_result, 'data') and len(image_check_result.data) > 0:
                            image_check = image_check_result.data[0]
                    if image_check:
                        saved_image_id = image_check["id"]
                        logger.info(f"Используем существующее изображение {saved_image_id} (URL: {selected_image.url}) для поста")
                    else:
                        new_internal_id = str(uuid.uuid4())
                        image_data_to_save = {
                            "id": new_internal_id,
                            "url": selected_image.url,
                            "preview_url": selected_image.preview_url or selected_image.url,
                            "alt": selected_image.alt or "",
                            "author": selected_image.author or "",
                            "author_url": selected_image.author_url or "",
                            "source": selected_image.source or "frontend_selection",
                            "user_id": int(telegram_user_id),
                        }
                        image_result = supabase.table("saved_images").insert(image_data_to_save).execute()
                        if hasattr(image_result, 'data') and len(image_result.data) > 0:
                            saved_image_id = new_internal_id
                            logger.info(f"Сохранено новое изображение {saved_image_id} для поста")
                        else:
                            logger.error(f"Ошибка при сохранении нового изображения: {image_result}")
                            raise HTTPException(status_code=500, detail=f"Ошибка при сохранении нового изображения: {getattr(image_result, 'error', 'Unknown error')}")
            except Exception as img_err:
                logger.error(f"Ошибка при обработке/сохранении изображения: {img_err}")
                raise HTTPException(status_code=500, detail=f"Ошибка при обработке/сохранении изображения: {str(img_err)}")
        post_to_save.pop('image_url', None)
        post_to_save.pop('images_ids', None)
        post_to_save["saved_image_id"] = saved_image_id
        logger.info(f"Подготовлены данные для сохранения в saved_posts: {post_to_save}")
        try:
            logger.info(f"Выполняем insert в saved_posts для ID {post_to_save['id']}...")
            result = supabase.table("saved_posts").insert(post_to_save).execute()
            if hasattr(result, 'data') and len(result.data) > 0:
                logger.info(f"Пост успешно создан: {post_to_save['id']}")
                return result.data[0]
            else:
                logger.error(f"Ошибка при сохранении поста: {result}")
                raise HTTPException(status_code=500, detail="Ошибка при сохранении поста")
        except Exception as e:
            logger.error(f"Ошибка при сохранении поста: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка при сохранении поста: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка при создании поста: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при создании поста: {str(e)}")

async def update_post(post_id: str, request: Request, post_data):
    try:
        from backend.main import fix_schema, download_and_save_external_image
        try:
            logger.info(f"Вызов fix_schema перед обновлением поста {post_id}...")
            fix_result = await fix_schema()
            if not fix_result.get("success"):
                logger.warning(f"Не удалось обновить/проверить схему перед обновлением поста {post_id}: {fix_result}")
            else:
                logger.info(f"Проверка/обновление схемы перед обновлением поста {post_id} завершена успешно.")
        except Exception as pre_update_fix_err:
            logger.error(f"Ошибка при вызове fix_schema перед обновлением поста {post_id}: {pre_update_fix_err}", exc_info=True)
        logger.info(f"Небольшая пауза после fix_schema для поста {post_id}, чтобы дать PostgREST время...")
        await asyncio.sleep(0.7)
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос обновления поста без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для обновления поста необходимо авторизоваться через Telegram")
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        post_check = supabase.table("saved_posts").select("id").eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
        if not hasattr(post_check, 'data') or len(post_check.data) == 0:
            logger.warning(f"Попытка обновить чужой или несуществующий пост: {post_id}")
            raise HTTPException(status_code=404, detail="Пост не найден или нет прав на его редактирование")
        selected_image = getattr(post_data, 'selected_image_data', None)
        image_field_provided_in_request = hasattr(post_data, 'selected_image_data')
        image_id_to_set_in_post = None
        image_processed = False
        if image_field_provided_in_request:
            image_processed = True
            if selected_image:
                try:
                    is_external_image = selected_image.source in ["unsplash", "pexels", "openverse"]
                    if is_external_image:
                        logger.info(f"Обнаружено внешнее изображение с источником {selected_image.source} при обновлении поста {post_id}")
                        try:
                            external_image_result = await download_and_save_external_image(selected_image, int(telegram_user_id))
                            image_id_to_set_in_post = external_image_result["id"]
                            if external_image_result.get("is_new", False) and external_image_result.get("url"):
                                selected_image.url = external_image_result["url"]
                                if external_image_result.get("preview_url"):
                                    selected_image.preview_url = external_image_result["preview_url"]
                                selected_image.source = f"{selected_image.source}_saved"
                            logger.info(f"Внешнее изображение успешно обработано при обновлении поста {post_id}, saved_image_id: {image_id_to_set_in_post}")
                        except Exception as ext_img_err:
                            logger.error(f"Ошибка при обработке внешнего изображения при обновлении поста {post_id}: {ext_img_err}")
                            raise HTTPException(status_code=500, detail=f"Не удалось обработать внешнее изображение: {str(ext_img_err)}")
                    else:
                        image_check = None
                        if selected_image.url:
                            image_check_result = supabase.table("saved_images").select("id").eq("url", selected_image.url).limit(1).execute()
                            if hasattr(image_check_result, 'data') and len(image_check_result.data) > 0:
                                image_check = image_check_result.data[0]
                        if image_check:
                            image_id_to_set_in_post = image_check["id"]
                            logger.info(f"Используем существующее изображение {image_id_to_set_in_post} для обновления поста {post_id}")
                        else:
                            new_internal_id = str(uuid.uuid4())
                            image_data_to_save = {
                                "id": new_internal_id,
                                "url": selected_image.url,
                                "preview_url": selected_image.preview_url or selected_image.url,
                                "alt": selected_image.alt or "",
                                "author": selected_image.author or "",
                                "author_url": selected_image.author_url or "",
                                "source": selected_image.source or "frontend_selection",
                                "user_id": int(telegram_user_id),
                            }
                            image_result = supabase.table("saved_images").insert(image_data_to_save).execute()
                            if hasattr(image_result, 'data') and len(image_result.data) > 0:
                                image_id_to_set_in_post = new_internal_id
                                logger.info(f"Сохранено новое изображение {image_id_to_set_in_post} для обновления поста {post_id}")
                            else:
                                logger.error(f"Ошибка при сохранении нового изображения при обновлении поста: {image_result}")
                                raise HTTPException(status_code=500, detail=f"Ошибка при сохранении нового изображения: {getattr(image_result, 'error', 'Unknown error')}")
                except Exception as img_err:
                    logger.error(f"Ошибка при обработке/сохранении изображения при обновлении поста: {img_err}")
                    raise HTTPException(status_code=500, detail=f"Ошибка при обработке/сохранении изображения: {str(img_err)}")
            else:
                image_id_to_set_in_post = None
                logger.info(f"В запросе на обновление поста {post_id} передано пустое изображение (None/null). Связь будет очищена.")
        post_to_update = post_data.dict(exclude={"selected_image_data", "image_url", "images_ids"})
        post_to_update["updated_at"] = datetime.now().isoformat()
        if "target_date" in post_to_update and not post_to_update.get("target_date"):
            logger.warning(f"Получена пустая target_date при обновлении поста {post_id}, устанавливаем в NULL.")
            post_to_update["target_date"] = None
        elif post_to_update.get("target_date"):
            try:
                datetime.strptime(post_to_update["target_date"], '%Y-%m-%d')
            except ValueError:
                logger.error(f"Некорректный формат target_date: {post_to_update['target_date']} при обновлении поста {post_id}. Устанавливаем в NULL.")
                post_to_update["target_date"] = None
        if image_processed:
            post_to_update["saved_image_id"] = image_id_to_set_in_post
            logger.info(f"Поле saved_image_id для поста {post_id} будет обновлено на: {image_id_to_set_in_post}")
        else:
            post_to_update.pop("saved_image_id", None)
            logger.info(f"Поле selected_image_data не предоставлено в запросе на обновление поста {post_id}. Поле saved_image_id не будет изменено.")
        logger.info(f"Подготовлены данные для обновления в saved_posts: {post_to_update}")
        try:
            logger.info(f"Выполняем update в saved_posts для ID {post_id}...")
            result = supabase.table("saved_posts").update(post_to_update).eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
            logger.info(f"Update выполнен. Status: {result.status_code if hasattr(result, 'status_code') else 'N/A'}")
        except Exception as e:
            logger.error(f"Ошибка при update в saved_posts для ID {post_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка БД при обновлении поста: {str(e)}")
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.error(f"Ошибка при обновлении поста {post_id}: Ответ Supabase пуст или не содержит данных.")
            last_error_details = f"Status: {result.status_code if hasattr(result, 'status_code') else 'N/A'}"
            raise HTTPException(status_code=500, detail=f"Не удалось обновить пост. {last_error_details}")
        updated_post = result.data[0]
        logger.info(f"Пользователь {telegram_user_id} обновил пост: {post_id}")
        response_data = updated_post  # Здесь должен быть SavedPostResponse(**updated_post), если модель импортирована
        final_image_id = updated_post.get("saved_image_id")
        if final_image_id:
            img_data_res = supabase.table("saved_images").select("id, url, preview_url, alt, author, author_url, source").eq("id", final_image_id).maybe_single().execute()
            if img_data_res.data:
                try:
                    alt_text = img_data_res.data.get("alt_description") or img_data_res.data.get("alt")
                    response_data["selected_image_data"] = {
                        "id": img_data_res.data.get("id"),
                        "url": img_data_res.data.get("url"),
                        "preview_url": img_data_res.data.get("preview_url"),
                        "alt": alt_text,
                        "author": img_data_res.data.get("author"),
                        "author_url": img_data_res.data.get("author_url"),
                        "source": img_data_res.data.get("source")
                    }
                except Exception as mapping_err:
                    logger.error(f"Ошибка при маппинге данных изображения из БД для обновленного поста {post_id}: {mapping_err}")
                    response_data["selected_image_data"] = None
            else:
                logger.warning(f"Не удалось получить данные изображения {final_image_id} из БД для ответа на обновление поста {post_id}")
                response_data["selected_image_data"] = None
        else:
            response_data["selected_image_data"] = None
        return response_data
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"Ошибка при обновлении поста {post_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера при обновлении поста: {str(e)}")

async def delete_post(post_id: str, request: Request):
    try:
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            raise HTTPException(status_code=500, detail="Ошибка: не удалось подключиться к базе данных")
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос удаления поста без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для удаления поста необходимо авторизоваться через Telegram")
        post_check = supabase.table("saved_posts").select("id").eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
        if not hasattr(post_check, 'data') or len(post_check.data) == 0:
            logger.warning(f"Попытка удалить чужой или несуществующий пост: {post_id}")
            raise HTTPException(status_code=404, detail="Пост не найден или нет прав на его удаление")
        try:
            delete_links_res = supabase.table("post_images").delete().eq("post_id", post_id).execute()
            logger.info(f"Удалено {len(delete_links_res.data) if hasattr(delete_links_res, 'data') else 0} связей для удаляемого поста {post_id}")
        except Exception as del_link_err:
            logger.error(f"Ошибка при удалении связей post_images для поста {post_id} перед удалением поста: {del_link_err}")
        result = supabase.table("saved_posts").delete().eq("id", post_id).execute()
        if not hasattr(result, 'data'):
            logger.error(f"Ошибка при удалении поста: {result}")
            raise HTTPException(status_code=500, detail="Ошибка при удалении поста")
        logger.info(f"Пользователь {telegram_user_id} удалил пост {post_id}")
        return {"success": True, "message": "Пост успешно удален"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"Ошибка при удалении поста {post_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера при удалении поста: {str(e)}")

async def generate_post_details(request: Request, req):
    from backend.main import generate_image_keywords, search_unsplash_images, get_channel_analysis, IMAGE_RESULTS_COUNT, PostImage
    from openai import AsyncOpenAI
    found_images = []
    channel_name = req.channel_name if hasattr(req, 'channel_name') else ""
    api_error_message = None
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if telegram_user_id:
            from backend.services.supabase_subscription_service import SupabaseSubscriptionService
            subscription_service = SupabaseSubscriptionService(supabase)
            can_generate = await subscription_service.can_generate_post(int(telegram_user_id))
            if not can_generate:
                raise HTTPException(status_code=403, detail="Достигнут лимит генерации идей для бесплатной подписки. Оформите подписку для снятия ограничений.")
        if not telegram_user_id:
            logger.warning("Запрос генерации поста без идентификации пользователя Telegram")
            raise HTTPException(status_code=401, detail="Для генерации постов необходимо авторизоваться через Telegram")
        topic_idea = req.topic_idea
        format_style = req.format_style
        post_samples = []
        if channel_name:
            try:
                channel_data = await get_channel_analysis(request, channel_name)
                if channel_data and "analyzed_posts_sample" in channel_data:
                    post_samples = channel_data["analyzed_posts_sample"]
                    logger.info(f"Получено {len(post_samples)} примеров постов для канала @{channel_name}")
            except Exception as e:
                logger.warning(f"Не удалось получить примеры постов для канала @{channel_name}: {e}")
        from backend.main import OPENROUTER_API_KEY
        if not OPENROUTER_API_KEY:
            logger.warning("Генерация деталей поста невозможна: отсутствует OPENROUTER_API_KEY")
            raise HTTPException(status_code=503, detail="API для генерации текста недоступен")
        system_prompt = """Ты - опытный контент-маркетолог для Telegram-каналов.\nТвоя задача - сгенерировать текст поста на основе идеи и формата, который будет готов к публикации.\n\nПост должен быть:\n1. Хорошо структурированным и легко читаемым\n2. Соответствовать указанной теме/идее\n3. Соответствовать указанному формату/стилю\n4. Иметь правильное форматирование для Telegram (если нужно - с эмодзи, абзацами, списками)\n\nНе используй хэштеги, если это не является частью формата.\nСделай пост уникальным и интересным, учитывая специфику Telegram-аудитории.\nИспользуй примеры постов канала, если они предоставлены, чтобы сохранить стиль."""
        user_prompt = f"""Создай пост для Telegram-канала "@{channel_name}" на тему:\n"{topic_idea}"\n\nФормат поста: {format_style}\n\nНапиши полный текст поста, который будет готов к публикации.\n"""
        if post_samples:
            sample_text = "\n\n".join(post_samples[:3])
            user_prompt += f"""\n\nВот несколько примеров постов из этого канала для сохранения стиля:\n\n{sample_text}\n"""
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        post_text = ""
        try:
            logger.info(f"Отправка запроса на генерацию поста по идее: {topic_idea}")
            response = await client.chat.completions.create(
                model="deepseek/deepseek-chat-v3-0324:free",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=850,
                timeout=60,
                extra_headers={
                    "HTTP-Referer": "https://content-manager.onrender.com",
                    "X-Title": "Smart Content Assistant"
                }
            )
            if response and response.choices and len(response.choices) > 0 and response.choices[0].message and response.choices[0].message.content:
                post_text = response.choices[0].message.content.strip()
                logger.info(f"Получен текст поста ({len(post_text)} символов)")
            elif response and hasattr(response, 'error') and response.error:
                err_details = response.error
                api_error_message = getattr(err_details, 'message', str(err_details))
                logger.error(f"OpenRouter API вернул ошибку: {api_error_message}")
                post_text = "[Текст не сгенерирован из-за ошибки API]"
            else:
                api_error_message = "API вернул некорректный или пустой ответ"
                logger.error(f"Некорректный или пустой ответ от OpenRouter API. Ответ: {response}")
                post_text = "[Текст не сгенерирован из-за ошибки API]"
        except Exception as api_error:
            api_error_message = f"Ошибка соединения с API: {str(api_error)}"
            logger.error(f"Ошибка при запросе к OpenRouter API: {api_error}", exc_info=True)
            post_text = "[Текст не сгенерирован из-за ошибки API]"
        image_keywords = await generate_image_keywords(post_text, topic_idea, format_style)
        logger.info(f"Сгенерированы ключевые слова для поиска изображений: {image_keywords}")
        for keyword in image_keywords[:3]:
            try:
                image_count = min(5 - len(found_images), 3)
                if image_count <= 0:
                    break
                images = await search_unsplash_images(keyword, count=image_count, topic=topic_idea, format_style=format_style, post_text=post_text)
                existing_ids = {img.id for img in found_images}
                unique_images = [img for img in images if img.id not in existing_ids]
                found_images.extend(unique_images)
                if len(found_images) >= 5:
                    found_images = found_images[:5]
                    break
                logger.info(f"Найдено {len(unique_images)} уникальных изображений по ключевому слову '{keyword}'")
            except Exception as e:
                logger.error(f"Ошибка при поиске изображений для ключевого слова '{keyword}': {e}")
                continue
        if not found_images:
            try:
                found_images = await search_unsplash_images(topic_idea, count=5, topic=topic_idea, format_style=format_style)
                logger.info(f"Найдено {len(found_images)} изображений по основной теме")
            except Exception as e:
                logger.error(f"Ошибка при поиске изображений по основной теме: {e}")
                found_images = []
        logger.info(f"Подготовлено {len(found_images)} предложенных изображений")
        response_message = f"Сгенерирован пост с {len(found_images[:IMAGE_RESULTS_COUNT])} предложенными изображениями"
        if api_error_message:
            response_message = f"Ошибка генерации текста: {api_error_message}. Изображений найдено: {len(found_images[:IMAGE_RESULTS_COUNT])}"
        return {
            "generated_text": post_text,
            "found_images": found_images[:IMAGE_RESULTS_COUNT],
            "message": response_message,
            "channel_name": channel_name,
            "selected_image_data": {
                "url": found_images[0].regular_url if found_images else "",
                "id": found_images[0].id if found_images else None,
                "preview_url": found_images[0].preview_url if found_images else "",
                "alt": found_images[0].description if found_images else "",
                "author": found_images[0].author_name if found_images else "",
                "author_url": found_images[0].author_url if found_images else ""
            } if found_images else None
        }
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"Ошибка при генерации деталей поста: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера при генерации деталей поста: {str(e)}") 