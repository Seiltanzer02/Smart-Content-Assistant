# РЎРµСЂРІРёСЃ РґР»СЏ СЂР°Р±РѕС‚С‹ СЃ РїРѕСЃС‚Р°РјРё
from fastapi import Request, HTTPException
from typing import Dict, Any, List, Optional
from backend.main import supabase, logger
from pydantic import BaseModel
import uuid
import asyncio
from datetime import datetime
import traceback

# РРјРїРѕСЂС‚ РјРѕРґРµР»РµР№ PostImage, PostData, SavedPostResponse, PostDetailsResponse РёР· main.py РёР»Рё РѕС‚РґРµР»СЊРЅРѕРіРѕ С„Р°Р№Р»Р° РјРѕРґРµР»РµР№
# from backend.models import PostImage, PostData, SavedPostResponse, PostDetailsResponse

async def get_posts(request: Request, channel_name: Optional[str] = None):
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ РїРѕСЃС‚РѕРІ Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ РґРѕСЃС‚СѓРїР° Рє РїРѕСЃС‚Р°Рј РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")
        query = supabase.table("saved_posts").select("*, saved_images(*)").eq("user_id", int(telegram_user_id))
        if channel_name:
            query = query.eq("channel_name", channel_name)
        result = query.order("target_date", desc=True).execute()
        if not hasattr(result, 'data'):
            logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РїРѕСЃС‚РѕРІ РёР· Р‘Р”: {result}")
            return []
        posts_with_images = []
        for post_data in result.data:
            response_item = post_data  # Р—РґРµСЃСЊ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ SavedPostResponse(**post_data), РµСЃР»Рё РјРѕРґРµР»СЊ РёРјРїРѕСЂС‚РёСЂРѕРІР°РЅР°
            image_relation_data = post_data.get("saved_images")
            logger.info(f"РћР±СЂР°Р±РѕС‚РєР° РїРѕСЃС‚Р° ID: {post_data.get('id')}. РЎРІСЏР·Р°РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {image_relation_data}")
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
                    logger.info(f"РЈСЃРїРµС€РЅРѕ СЃРѕР·РґР°РЅРѕ selected_image_data РґР»СЏ РїРѕСЃС‚Р° {post_data.get('id')} СЃ РёР·РѕР±СЂР°Р¶РµРЅРёРµРј ID: {image_relation_data.get('id')}")
                except Exception as mapping_error:
                    logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё PostImage РґР»СЏ РїРѕСЃС‚Р° {post_data.get('id')}: {mapping_error}")
                    logger.error(f"Р”Р°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {image_relation_data}")
                    response_item["selected_image_data"] = None
            else:
                response_item["selected_image_data"] = None
                if post_data.get("saved_image_id"):
                    logger.warning(f"Р”Р»СЏ РїРѕСЃС‚Р° {post_data['id']} РµСЃС‚СЊ saved_image_id, РЅРѕ СЃРІСЏР·Р°РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РЅРµ Р±С‹Р»Рё РїРѕР»СѓС‡РµРЅС‹ РёР»Рё РїСѓСЃС‚С‹. РЎРІСЏР·Р°РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ: {image_relation_data}")
            posts_with_images.append(response_item)
        return posts_with_images
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РїРѕСЃС‚РѕРІ: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def create_post(request: Request, post_data):
    try:
        from backend.main import fix_schema, download_and_save_external_image
        try:
            logger.info("Р’С‹Р·РѕРІ fix_schema РїРµСЂРµРґ СЃРѕР·РґР°РЅРёРµРј РїРѕСЃС‚Р°...")
            fix_result = await fix_schema()
            if not fix_result.get("success"):
                logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ/РїСЂРѕРІРµСЂРёС‚СЊ СЃС…РµРјСѓ РїРµСЂРµРґ СЃРѕР·РґР°РЅРёРµРј РїРѕСЃС‚Р°: {fix_result}")
            else:
                logger.info("РџСЂРѕРІРµСЂРєР°/РѕР±РЅРѕРІР»РµРЅРёРµ СЃС…РµРјС‹ РїРµСЂРµРґ СЃРѕР·РґР°РЅРёРµРј РїРѕСЃС‚Р° Р·Р°РІРµСЂС€РµРЅР° СѓСЃРїРµС€РЅРѕ.")
        except Exception as pre_save_fix_err:
            logger.error(f"РћС€РёР±РєР° РїСЂРё РІС‹Р·РѕРІРµ fix_schema РїРµСЂРµРґ СЃРѕР·РґР°РЅРёРµРј РїРѕСЃС‚Р°: {pre_save_fix_err}", exc_info=True)
        logger.info("РќРµР±РѕР»СЊС€Р°СЏ РїР°СѓР·Р° РїРѕСЃР»Рµ fix_schema, С‡С‚РѕР±С‹ РґР°С‚СЊ PostgREST РІСЂРµРјСЏ...")
        await asyncio.sleep(0.7)
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ СЃРѕР·РґР°РЅРёСЏ РїРѕСЃС‚Р° Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ СЃРѕР·РґР°РЅРёСЏ РїРѕСЃС‚Р° РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")
        selected_image = post_data.selected_image_data
        post_to_save = post_data.dict(exclude={"selected_image_data"})
        post_to_save["user_id"] = int(telegram_user_id)
        post_to_save["id"] = str(uuid.uuid4())
        if not post_to_save.get("target_date"):
            logger.warning(f"РџРѕР»СѓС‡РµРЅР° РїСѓСЃС‚Р°СЏ target_date РґР»СЏ РЅРѕРІРѕРіРѕ РїРѕСЃС‚Р° {post_to_save['id']}, СѓСЃС‚Р°РЅР°РІР»РёРІР°РµРј РІ NULL.")
            post_to_save["target_date"] = None
        else:
            try:
                datetime.strptime(post_to_save["target_date"], '%Y-%m-%d')
            except ValueError:
                logger.error(f"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ С„РѕСЂРјР°С‚ target_date: {post_to_save['target_date']} РґР»СЏ РїРѕСЃС‚Р° {post_to_save['id']}. РЈСЃС‚Р°РЅР°РІР»РёРІР°РµРј РІ NULL.")
                post_to_save["target_date"] = None
        saved_image_id = None
        if selected_image:
            try:
                logger.info(f"РћР±СЂР°Р±РѕС‚РєР° РІС‹Р±СЂР°РЅРЅРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {selected_image.dict() if hasattr(selected_image, 'dict') else selected_image}")
                is_external_image = selected_image.source in ["unsplash", "pexels", "openverse"]
                if is_external_image:
                    logger.info(f"РћР±РЅР°СЂСѓР¶РµРЅРѕ РІРЅРµС€РЅРµРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ СЃ РёСЃС‚РѕС‡РЅРёРєРѕРј {selected_image.source}")
                    try:
                        external_image_result = await download_and_save_external_image(selected_image, int(telegram_user_id))
                        saved_image_id = external_image_result["id"]
                        if external_image_result.get("is_new", False) and external_image_result.get("url"):
                            selected_image.url = external_image_result["url"]
                            if external_image_result.get("preview_url"):
                                selected_image.preview_url = external_image_result["preview_url"]
                            selected_image.source = f"{selected_image.source}_saved"
                        logger.info(f"Р’РЅРµС€РЅРµРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ СѓСЃРїРµС€РЅРѕ РѕР±СЂР°Р±РѕС‚Р°РЅРѕ, saved_image_id: {saved_image_id}")
                    except Exception as ext_img_err:
                        logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ РІРЅРµС€РЅРµРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {ext_img_err}")
                        raise HTTPException(status_code=500, detail=f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±СЂР°Р±РѕС‚Р°С‚СЊ РІРЅРµС€РЅРµРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ: {str(ext_img_err)}")
                else:
                    image_check = None
                    if selected_image.url:
                        image_check_result = supabase.table("saved_images").select("id").eq("url", selected_image.url).limit(1).execute()
                        if hasattr(image_check_result, 'data') and len(image_check_result.data) > 0:
                            image_check = image_check_result.data[0]
                    if image_check:
                        saved_image_id = image_check["id"]
                        logger.info(f"РСЃРїРѕР»СЊР·СѓРµРј СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ {saved_image_id} (URL: {selected_image.url}) РґР»СЏ РїРѕСЃС‚Р°")
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
                            logger.info(f"РЎРѕС…СЂР°РЅРµРЅРѕ РЅРѕРІРѕРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ {saved_image_id} РґР»СЏ РїРѕСЃС‚Р°")
                        else:
                            logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РЅРѕРІРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {image_result}")
                            raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РЅРѕРІРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {getattr(image_result, 'error', 'Unknown error')}")
            except Exception as img_err:
                logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ/СЃРѕС…СЂР°РЅРµРЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {img_err}")
                raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ/СЃРѕС…СЂР°РЅРµРЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {str(img_err)}")
        post_to_save.pop('image_url', None)
        post_to_save.pop('images_ids', None)
        post_to_save["saved_image_id"] = saved_image_id
        logger.info(f"РџРѕРґРіРѕС‚РѕРІР»РµРЅС‹ РґР°РЅРЅС‹Рµ РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ РІ saved_posts: {post_to_save}")
        try:
            logger.info(f"Р’С‹РїРѕР»РЅСЏРµРј insert РІ saved_posts РґР»СЏ ID {post_to_save['id']}...")
            result = supabase.table("saved_posts").insert(post_to_save).execute()
            if hasattr(result, 'data') and len(result.data) > 0:
                logger.info(f"РџРѕСЃС‚ СѓСЃРїРµС€РЅРѕ СЃРѕР·РґР°РЅ: {post_to_save['id']}")
                return result.data[0]
            else:
                logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РїРѕСЃС‚Р°: {result}")
                raise HTTPException(status_code=500, detail="РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РїРѕСЃС‚Р°")
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РїРѕСЃС‚Р°: {e}")
            raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РїРѕСЃС‚Р°: {str(e)}")
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё РїРѕСЃС‚Р°: {e}")
        raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё РїРѕСЃС‚Р°: {str(e)}")

async def update_post(post_id: str, request: Request, post_data):
    try:
        from backend.main import fix_schema, download_and_save_external_image
        try:
            logger.info(f"Р’С‹Р·РѕРІ fix_schema РїРµСЂРµРґ РѕР±РЅРѕРІР»РµРЅРёРµРј РїРѕСЃС‚Р° {post_id}...")
            fix_result = await fix_schema()
            if not fix_result.get("success"):
                logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ/РїСЂРѕРІРµСЂРёС‚СЊ СЃС…РµРјСѓ РїРµСЂРµРґ РѕР±РЅРѕРІР»РµРЅРёРµРј РїРѕСЃС‚Р° {post_id}: {fix_result}")
            else:
                logger.info(f"РџСЂРѕРІРµСЂРєР°/РѕР±РЅРѕРІР»РµРЅРёРµ СЃС…РµРјС‹ РїРµСЂРµРґ РѕР±РЅРѕРІР»РµРЅРёРµРј РїРѕСЃС‚Р° {post_id} Р·Р°РІРµСЂС€РµРЅР° СѓСЃРїРµС€РЅРѕ.")
        except Exception as pre_update_fix_err:
            logger.error(f"РћС€РёР±РєР° РїСЂРё РІС‹Р·РѕРІРµ fix_schema РїРµСЂРµРґ РѕР±РЅРѕРІР»РµРЅРёРµРј РїРѕСЃС‚Р° {post_id}: {pre_update_fix_err}", exc_info=True)
        logger.info(f"РќРµР±РѕР»СЊС€Р°СЏ РїР°СѓР·Р° РїРѕСЃР»Рµ fix_schema РґР»СЏ РїРѕСЃС‚Р° {post_id}, С‡С‚РѕР±С‹ РґР°С‚СЊ PostgREST РІСЂРµРјСЏ...")
        await asyncio.sleep(0.7)
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ РѕР±РЅРѕРІР»РµРЅРёСЏ РїРѕСЃС‚Р° Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ РїРѕСЃС‚Р° РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")
        post_check = supabase.table("saved_posts").select("id").eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
        if not hasattr(post_check, 'data') or len(post_check.data) == 0:
            logger.warning(f"РџРѕРїС‹С‚РєР° РѕР±РЅРѕРІРёС‚СЊ С‡СѓР¶РѕР№ РёР»Рё РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РёР№ РїРѕСЃС‚: {post_id}")
            raise HTTPException(status_code=404, detail="РџРѕСЃС‚ РЅРµ РЅР°Р№РґРµРЅ РёР»Рё РЅРµС‚ РїСЂР°РІ РЅР° РµРіРѕ СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ")
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
                        logger.info(f"РћР±РЅР°СЂСѓР¶РµРЅРѕ РІРЅРµС€РЅРµРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ СЃ РёСЃС‚РѕС‡РЅРёРєРѕРј {selected_image.source} РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р° {post_id}")
                        try:
                            external_image_result = await download_and_save_external_image(selected_image, int(telegram_user_id))
                            image_id_to_set_in_post = external_image_result["id"]
                            if external_image_result.get("is_new", False) and external_image_result.get("url"):
                                selected_image.url = external_image_result["url"]
                                if external_image_result.get("preview_url"):
                                    selected_image.preview_url = external_image_result["preview_url"]
                                selected_image.source = f"{selected_image.source}_saved"
                            logger.info(f"Р’РЅРµС€РЅРµРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ СѓСЃРїРµС€РЅРѕ РѕР±СЂР°Р±РѕС‚Р°РЅРѕ РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р° {post_id}, saved_image_id: {image_id_to_set_in_post}")
                        except Exception as ext_img_err:
                            logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ РІРЅРµС€РЅРµРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р° {post_id}: {ext_img_err}")
                            raise HTTPException(status_code=500, detail=f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±СЂР°Р±РѕС‚Р°С‚СЊ РІРЅРµС€РЅРµРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ: {str(ext_img_err)}")
                    else:
                        image_check = None
                        if selected_image.url:
                            image_check_result = supabase.table("saved_images").select("id").eq("url", selected_image.url).limit(1).execute()
                            if hasattr(image_check_result, 'data') and len(image_check_result.data) > 0:
                                image_check = image_check_result.data[0]
                        if image_check:
                            image_id_to_set_in_post = image_check["id"]
                            logger.info(f"РСЃРїРѕР»СЊР·СѓРµРј СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ {image_id_to_set_in_post} РґР»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ РїРѕСЃС‚Р° {post_id}")
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
                                logger.info(f"РЎРѕС…СЂР°РЅРµРЅРѕ РЅРѕРІРѕРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ {image_id_to_set_in_post} РґР»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ РїРѕСЃС‚Р° {post_id}")
                            else:
                                logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РЅРѕРІРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р°: {image_result}")
                                raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РЅРѕРІРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {getattr(image_result, 'error', 'Unknown error')}")
                except Exception as img_err:
                    logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ/СЃРѕС…СЂР°РЅРµРЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р°: {img_err}")
                    raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ/СЃРѕС…СЂР°РЅРµРЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {str(img_err)}")
            else:
                image_id_to_set_in_post = None
                logger.info(f"Р’ Р·Р°РїСЂРѕСЃРµ РЅР° РѕР±РЅРѕРІР»РµРЅРёРµ РїРѕСЃС‚Р° {post_id} РїРµСЂРµРґР°РЅРѕ РїСѓСЃС‚РѕРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ (None/null). РЎРІСЏР·СЊ Р±СѓРґРµС‚ РѕС‡РёС‰РµРЅР°.")
        post_to_update = post_data.dict(exclude={"selected_image_data", "image_url", "images_ids"})
        post_to_update["updated_at"] = datetime.now().isoformat()
        if "target_date" in post_to_update and not post_to_update.get("target_date"):
            logger.warning(f"РџРѕР»СѓС‡РµРЅР° РїСѓСЃС‚Р°СЏ target_date РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р° {post_id}, СѓСЃС‚Р°РЅР°РІР»РёРІР°РµРј РІ NULL.")
            post_to_update["target_date"] = None
        elif post_to_update.get("target_date"):
            try:
                datetime.strptime(post_to_update["target_date"], '%Y-%m-%d')
            except ValueError:
                logger.error(f"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ С„РѕСЂРјР°С‚ target_date: {post_to_update['target_date']} РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р° {post_id}. РЈСЃС‚Р°РЅР°РІР»РёРІР°РµРј РІ NULL.")
                post_to_update["target_date"] = None
        if image_processed:
            post_to_update["saved_image_id"] = image_id_to_set_in_post
            logger.info(f"РџРѕР»Рµ saved_image_id РґР»СЏ РїРѕСЃС‚Р° {post_id} Р±СѓРґРµС‚ РѕР±РЅРѕРІР»РµРЅРѕ РЅР°: {image_id_to_set_in_post}")
        else:
            post_to_update.pop("saved_image_id", None)
            logger.info(f"РџРѕР»Рµ selected_image_data РЅРµ РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅРѕ РІ Р·Р°РїСЂРѕСЃРµ РЅР° РѕР±РЅРѕРІР»РµРЅРёРµ РїРѕСЃС‚Р° {post_id}. РџРѕР»Рµ saved_image_id РЅРµ Р±СѓРґРµС‚ РёР·РјРµРЅРµРЅРѕ.")
        logger.info(f"РџРѕРґРіРѕС‚РѕРІР»РµРЅС‹ РґР°РЅРЅС‹Рµ РґР»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ РІ saved_posts: {post_to_update}")
        try:
            logger.info(f"Р’С‹РїРѕР»РЅСЏРµРј update РІ saved_posts РґР»СЏ ID {post_id}...")
            result = supabase.table("saved_posts").update(post_to_update).eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
            logger.info(f"Update РІС‹РїРѕР»РЅРµРЅ. Status: {result.status_code if hasattr(result, 'status_code') else 'N/A'}")
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РїСЂРё update РІ saved_posts РґР»СЏ ID {post_id}: {e}")
            raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° Р‘Р” РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р°: {str(e)}")
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р° {post_id}: РћС‚РІРµС‚ Supabase РїСѓСЃС‚ РёР»Рё РЅРµ СЃРѕРґРµСЂР¶РёС‚ РґР°РЅРЅС‹С….")
            last_error_details = f"Status: {result.status_code if hasattr(result, 'status_code') else 'N/A'}"
            raise HTTPException(status_code=500, detail=f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ РїРѕСЃС‚. {last_error_details}")
        updated_post = result.data[0]
        logger.info(f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {telegram_user_id} РѕР±РЅРѕРІРёР» РїРѕСЃС‚: {post_id}")
        response_data = updated_post  # Р—РґРµСЃСЊ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ SavedPostResponse(**updated_post), РµСЃР»Рё РјРѕРґРµР»СЊ РёРјРїРѕСЂС‚РёСЂРѕРІР°РЅР°
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
                    logger.error(f"РћС€РёР±РєР° РїСЂРё РјР°РїРїРёРЅРіРµ РґР°РЅРЅС‹С… РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РёР· Р‘Р” РґР»СЏ РѕР±РЅРѕРІР»РµРЅРЅРѕРіРѕ РїРѕСЃС‚Р° {post_id}: {mapping_err}")
                    response_data["selected_image_data"] = None
            else:
                logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ {final_image_id} РёР· Р‘Р” РґР»СЏ РѕС‚РІРµС‚Р° РЅР° РѕР±РЅРѕРІР»РµРЅРёРµ РїРѕСЃС‚Р° {post_id}")
                response_data["selected_image_data"] = None
        else:
            response_data["selected_image_data"] = None
        return response_data
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р° {post_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Р’РЅСѓС‚СЂРµРЅРЅСЏСЏ РѕС€РёР±РєР° СЃРµСЂРІРµСЂР° РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р°: {str(e)}")

async def delete_post(post_id: str, request: Request):
    try:
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ СѓРґР°Р»РµРЅРёСЏ РїРѕСЃС‚Р° Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ СѓРґР°Р»РµРЅРёСЏ РїРѕСЃС‚Р° РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")
        post_check = supabase.table("saved_posts").select("id").eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
        if not hasattr(post_check, 'data') or len(post_check.data) == 0:
            logger.warning(f"РџРѕРїС‹С‚РєР° СѓРґР°Р»РёС‚СЊ С‡СѓР¶РѕР№ РёР»Рё РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РёР№ РїРѕСЃС‚: {post_id}")
            raise HTTPException(status_code=404, detail="РџРѕСЃС‚ РЅРµ РЅР°Р№РґРµРЅ РёР»Рё РЅРµС‚ РїСЂР°РІ РЅР° РµРіРѕ СѓРґР°Р»РµРЅРёРµ")
        try:
            delete_links_res = supabase.table("post_images").delete().eq("post_id", post_id).execute()
            logger.info(f"РЈРґР°Р»РµРЅРѕ {len(delete_links_res.data) if hasattr(delete_links_res, 'data') else 0} СЃРІСЏР·РµР№ РґР»СЏ СѓРґР°Р»СЏРµРјРѕРіРѕ РїРѕСЃС‚Р° {post_id}")
        except Exception as del_link_err:
            logger.error(f"РћС€РёР±РєР° РїСЂРё СѓРґР°Р»РµРЅРёРё СЃРІСЏР·РµР№ post_images РґР»СЏ РїРѕСЃС‚Р° {post_id} РїРµСЂРµРґ СѓРґР°Р»РµРЅРёРµРј РїРѕСЃС‚Р°: {del_link_err}")
        result = supabase.table("saved_posts").delete().eq("id", post_id).execute()
        if not hasattr(result, 'data'):
            logger.error(f"РћС€РёР±РєР° РїСЂРё СѓРґР°Р»РµРЅРёРё РїРѕСЃС‚Р°: {result}")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР° РїСЂРё СѓРґР°Р»РµРЅРёРё РїРѕСЃС‚Р°")
        logger.info(f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {telegram_user_id} СѓРґР°Р»РёР» РїРѕСЃС‚ {post_id}")
        return {"success": True, "message": "РџРѕСЃС‚ СѓСЃРїРµС€РЅРѕ СѓРґР°Р»РµРЅ"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё СѓРґР°Р»РµРЅРёРё РїРѕСЃС‚Р° {post_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Р’РЅСѓС‚СЂРµРЅРЅСЏСЏ РѕС€РёР±РєР° СЃРµСЂРІРµСЂР° РїСЂРё СѓРґР°Р»РµРЅРёРё РїРѕСЃС‚Р°: {str(e)}")

async def generate_post_details(request: Request, req):
    import traceback
    from backend.main import generate_image_keywords, search_unsplash_images, get_channel_analysis, IMAGE_RESULTS_COUNT, PostImage, OPENROUTER_API_KEY, OPENAI_API_KEY, logger
    from openai import AsyncOpenAI
    found_images = []
    api_error_message = None
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if telegram_user_id:
            from backend.services.supabase_subscription_service import SupabaseSubscriptionService
            subscription_service = SupabaseSubscriptionService(supabase)
            can_generate = await subscription_service.can_generate_post(int(telegram_user_id))
            if not can_generate:
                usage = await subscription_service.get_user_usage(int(telegram_user_id))
                reset_at = usage.get("reset_at")
                raise HTTPException(status_code=403, detail=f"Р”РѕСЃС‚РёРіРЅСѓС‚ Р»РёРјРёС‚ РІ 2 РіРµРЅРµСЂР°С†РёРё РїРѕСЃС‚РѕРІ РґР»СЏ Р±РµСЃРїР»Р°С‚РЅРѕР№ РїРѕРґРїРёСЃРєРё. РЎР»РµРґСѓСЋС‰Р°СЏ РїРѕРїС‹С‚РєР° Р±СѓРґРµС‚ РґРѕСЃС‚СѓРїРЅР° РїРѕСЃР»Рµ: {reset_at}. Р›РёРјРёС‚С‹ РѕР±РЅРѕРІР»СЏСЋС‚СЃСЏ РєР°Р¶РґС‹Рµ 3 РґРЅСЏ. РћС„РѕСЂРјРёС‚Рµ РїРѕРґРїРёСЃРєСѓ РґР»СЏ СЃРЅСЏС‚РёСЏ РѕРіСЂР°РЅРёС‡РµРЅРёР№.")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ РіРµРЅРµСЂР°С†РёРё РїРѕСЃС‚Р° Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ РіРµРЅРµСЂР°С†РёРё РїРѕСЃС‚РѕРІ РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")
        topic_idea = req.get("topic_idea")
        format_style = req.get("format_style")
        channel_name = req.get("channel_name", "")
        post_samples = req.get("post_samples") or []
        if not post_samples and channel_name:
            try:
                channel_data = await get_channel_analysis(request, channel_name)
                if channel_data and "analyzed_posts_sample" in channel_data:
                    post_samples = channel_data["analyzed_posts_sample"]
                    logger.info(f"РџРѕР»СѓС‡РµРЅРѕ {len(post_samples)} РїСЂРёРјРµСЂРѕРІ РїРѕСЃС‚РѕРІ РґР»СЏ РєР°РЅР°Р»Р° @{channel_name}")
            except Exception as e:
                logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ РїСЂРёРјРµСЂС‹ РїРѕСЃС‚РѕРІ РґР»СЏ РєР°РЅР°Р»Р° @{channel_name}: {e}")
        
        # РџСЂРѕРІРµСЂРєР° РЅР°Р»РёС‡РёСЏ С…РѕС‚СЏ Р±С‹ РѕРґРЅРѕРіРѕ API РєР»СЋС‡Р°
        if not OPENROUTER_API_KEY and not OPENAI_API_KEY:
            logger.warning("Р“РµРЅРµСЂР°С†РёСЏ РґРµС‚Р°Р»РµР№ РїРѕСЃС‚Р° РЅРµРІРѕР·РјРѕР¶РЅР°: РѕС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ OPENROUTER_API_KEY Рё OPENAI_API_KEY")
            raise HTTPException(status_code=503, detail="API РґР»СЏ РіРµРЅРµСЂР°С†РёРё С‚РµРєСЃС‚Р° РЅРµРґРѕСЃС‚СѓРїРµРЅ")
            
        system_prompt = """РўС‹ вЂ” РѕРїС‹С‚РЅС‹Р№ РєРѕРЅС‚РµРЅС‚-РјР°СЂРєРµС‚РѕР»РѕРі РґР»СЏ Telegram-РєР°РЅР°Р»РѕРІ.
РўРІРѕСЏ Р·РґР°С‡Р° вЂ” СЃРіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ С‚РµРєСЃС‚ РїРѕСЃС‚Р° РЅР° РѕСЃРЅРѕРІРµ РёРґРµРё Рё С„РѕСЂРјР°С‚Р°, РєРѕС‚РѕСЂС‹Р№ Р±СѓРґРµС‚ РіРѕС‚РѕРІ Рє РїСѓР±Р»РёРєР°С†РёРё.

РџРѕСЃС‚ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ:
1. РҐРѕСЂРѕС€Рѕ СЃС‚СЂСѓРєС‚СѓСЂРёСЂРѕРІР°РЅРЅС‹Рј Рё Р»РµРіРєРѕ С‡РёС‚Р°РµРјС‹Рј.
2. РЎРѕРѕС‚РІРµС‚СЃС‚РІРѕРІР°С‚СЊ СѓРєР°Р·Р°РЅРЅРѕР№ С‚РµРјРµ/РёРґРµРµ.
3. РЎРѕРѕС‚РІРµС‚СЃС‚РІРѕРІР°С‚СЊ СѓРєР°Р·Р°РЅРЅРѕРјСѓ С„РѕСЂРјР°С‚Сѓ/СЃС‚РёР»СЋ.
4. РРјРµС‚СЊ РїСЂР°РІРёР»СЊРЅРѕРµ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ РґР»СЏ Telegram (РµСЃР»Рё РЅСѓР¶РЅРѕ вЂ” СЃ СЌРјРѕРґР·Рё, Р°Р±Р·Р°С†Р°РјРё, СЃРїРёСЃРєР°РјРё).
5. РќР• РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ РЅРёРєР°РєРёС… С€Р°Р±Р»РѕРЅРѕРІ, placeholder-РѕРІ ([РќР°Р·РІР°РЅРёРµ], [РЎСЃС‹Р»РєР°], [РќР°С‡Р°С‚СЊ СЃРµР№С‡Р°СЃ], "...", "[С‚РµРєСЃС‚]" Рё С‚.Рґ.) вЂ” С‚РµРєСЃС‚ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РїРѕР»РЅРѕСЃС‚СЊСЋ РіРѕС‚РѕРІ Рє РїСѓР±Р»РёРєР°С†РёРё, Р±РµР· РјРµСЃС‚ РґР»СЏ СЂСѓС‡РЅРѕРіРѕ Р·Р°РїРѕР»РЅРµРЅРёСЏ.
6. **РљСЂРёС‚РёС‡РµСЃРєРё РІР°Р¶РЅРѕ**: РњР°РєСЃРёРјР°Р»СЊРЅРѕ С‚РѕС‡РЅРѕ РєРѕРїРёСЂСѓР№ СЃС‚РёР»СЊ, С‚РѕРЅ, РјР°РЅРµСЂСѓ РёР·Р»РѕР¶РµРЅРёСЏ, РёСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ СЌРјРѕРґР·Рё (РІРєР»СЋС‡Р°СЏ РёС… РєРѕР»РёС‡РµСЃС‚РІРѕ Рё СЂР°СЃРїРѕР»РѕР¶РµРЅРёРµ), РґР»РёРЅСѓ РїСЂРµРґР»РѕР¶РµРЅРёР№ Рё Р°Р±Р·Р°С†РµРІ, РёСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ Р·Р°РіР»Р°РІРЅС‹С… Р±СѓРєРІ, РїСѓРЅРєС‚СѓР°С†РёСЋ Рё РґСЂСѓРіРёРµ С…Р°СЂР°РєС‚РµСЂРЅС‹Рµ РѕСЃРѕР±РµРЅРЅРѕСЃС‚Рё РёР· РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅРЅС‹С… РїСЂРёРјРµСЂРѕРІ РїРѕСЃС‚РѕРІ. РўРµРєСЃС‚ РґРѕР»Р¶РµРЅ РІС‹РіР»СЏРґРµС‚СЊ С‚Р°Рє, РєР°Рє Р±СѓРґС‚Рѕ РµРіРѕ РЅР°РїРёСЃР°Р» Р°РІС‚РѕСЂ РѕСЂРёРіРёРЅР°Р»СЊРЅРѕРіРѕ РєР°РЅР°Р»Р°. РћР±СЂР°С‚Рё РІРЅРёРјР°РЅРёРµ РЅР° С‡Р°СЃС‚РѕС‚Сѓ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ РѕРїСЂРµРґРµР»РµРЅРЅС‹С… СЃР»РѕРІ РёР»Рё С„СЂР°Р·.

РќРµ РёСЃРїРѕР»СЊР·СѓР№ С…СЌС€С‚РµРіРё, РµСЃР»Рё СЌС‚Рѕ РЅРµ СЏРІР»СЏРµС‚СЃСЏ С‡Р°СЃС‚СЊСЋ С„РѕСЂРјР°С‚Р° РёР»Рё РёС… РЅРµС‚ РІ РїСЂРёРјРµСЂР°С….
РЎРґРµР»Р°Р№ РїРѕСЃС‚ СѓРЅРёРєР°Р»СЊРЅС‹Рј Рё РёРЅС‚РµСЂРµСЃРЅС‹Рј, РЅРѕ РїСЂРёРѕСЂРёС‚РµС‚ вЂ” РЅР° С‚РѕС‡РЅРѕРј СЃР»РµРґРѕРІР°РЅРёРё СЃС‚РёР»СЋ РєР°РЅР°Р»Р°.
РСЃРїРѕР»СЊР·СѓР№ РїСЂРёРјРµСЂС‹ РїРѕСЃС‚РѕРІ РєР°РЅР°Р»Р°, РµСЃР»Рё РѕРЅРё РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅС‹, С‡С‚РѕР±С‹ СЃРѕС…СЂР°РЅРёС‚СЊ СЃС‚РёР»СЊ. Р•СЃР»Рё РїСЂРёРјРµСЂС‹ РЅРµ РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅС‹, СЃРѕР·РґР°Р№ РєР°С‡РµСЃС‚РІРµРЅРЅС‹Р№ РїРѕСЃС‚ РІ СѓРєР°Р·Р°РЅРЅРѕРј С„РѕСЂРјР°С‚Рµ."""
        user_prompt = f"""РЎРѕР·РґР°Р№ РїРѕСЃС‚ РґР»СЏ Telegram-РєР°РЅР°Р»Р° \\\"@{channel_name}\\\" РЅР° С‚РµРјСѓ:\\n\\\"{topic_idea}\\\"\\n\\nР¤РѕСЂРјР°С‚ РїРѕСЃС‚Р°: {format_style}\\n\\nРќР°РїРёС€Рё РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚ РїРѕСЃС‚Р°, РєРѕС‚РѕСЂС‹Р№ Р±СѓРґРµС‚ РіРѕС‚РѕРІ Рє РїСѓР±Р»РёРєР°С†РёРё.\\n"""
        if post_samples:
            sample_text = "\\n\\n---\\n\\n".join(post_samples[:10]) # РЈРІРµР»РёС‡РµРЅРѕ РєРѕР»РёС‡РµСЃС‚РІРѕ РїСЂРёРјРµСЂРѕРІ РґРѕ 10
            user_prompt += f"""\\n\\nР’РѕС‚ РЅРµСЃРєРѕР»СЊРєРѕ РїСЂРёРјРµСЂРѕРІ РїРѕСЃС‚РѕРІ РёР· СЌС‚РѕРіРѕ РєР°РЅР°Р»Р° РґР»СЏ С‚РѕС‡РЅРѕРіРѕ РєРѕРїРёСЂРѕРІР°РЅРёСЏ СЃС‚РёР»СЏ Рё РїРѕРґР°С‡Рё (РїСЂРѕР°РЅР°Р»РёР·РёСЂСѓР№ РёС… РѕС‡РµРЅСЊ РІРЅРёРјР°С‚РµР»СЊРЅРѕ):\\n\\n{sample_text}\\n\\nРЈР±РµРґРёСЃСЊ, С‡С‚Рѕ С‚РІРѕР№ РѕС‚РІРµС‚ СЃС‚СЂРѕРіРѕ СЃР»РµРґСѓРµС‚ РёС… РјР°РЅРµСЂРµ."""
        
        # РЎРЅР°С‡Р°Р»Р° РїСЂРѕР±СѓРµРј OpenRouter API, РµСЃР»Рё РѕРЅ РґРѕСЃС‚СѓРїРµРЅ
        post_text = ""
        used_backup_api = False
        api_error_message = None
        found_images = []
        
        if OPENROUTER_API_KEY:
            try:
                logger.info(f"РћС‚РїСЂР°РІРєР° Р·Р°РїСЂРѕСЃР° РЅР° РіРµРЅРµСЂР°С†РёСЋ РїРѕСЃС‚Р° РїРѕ РёРґРµРµ С‡РµСЂРµР· OpenRouter API: {topic_idea}")
                client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=OPENROUTER_API_KEY
                )
                
                response = await client.chat.completions.create(
                    model="meta-llama/llama-4-maverick:free",
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
                    logger.info(f"РџРѕР»СѓС‡РµРЅ С‚РµРєСЃС‚ РїРѕСЃС‚Р° С‡РµСЂРµР· OpenRouter API ({len(post_text)} СЃРёРјРІРѕР»РѕРІ)")
                elif response and hasattr(response, 'error') and response.error:
                    err_details = response.error
                    api_error_message = getattr(err_details, 'message', str(err_details))
                    logger.error(f"OpenRouter API РІРµСЂРЅСѓР» РѕС€РёР±РєСѓ: {api_error_message}")
                    # РћС€РёР±РєР° OpenRouter API - РїСЂРѕР±СѓРµРј Р·Р°РїР°СЃРЅРѕР№ РІР°СЂРёР°РЅС‚
                    raise Exception(f"OpenRouter API РІРµСЂРЅСѓР» РѕС€РёР±РєСѓ: {api_error_message}")
                else:
                    api_error_message = "OpenRouter API РІРµСЂРЅСѓР» РЅРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РёР»Рё РїСѓСЃС‚РѕР№ РѕС‚РІРµС‚"
                    logger.error(f"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РёР»Рё РїСѓСЃС‚РѕР№ РѕС‚РІРµС‚ РѕС‚ OpenRouter API. РћС‚РІРµС‚: {response}")
                    # РћС€РёР±РєР° OpenRouter API - РїСЂРѕР±СѓРµРј Р·Р°РїР°СЃРЅРѕР№ РІР°СЂРёР°РЅС‚
                    raise Exception("РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РёР»Рё РїСѓСЃС‚РѕР№ РѕС‚РІРµС‚ РѕС‚ OpenRouter API")
                    
            except Exception as api_error:
                # Р' СЃР»СѓС‡Р°Рµ РѕС€РёР±РєРё СЃ OpenRouter API, РїСЂРѕРІРµСЂСЏРµРј РЅР°Р»РёС‡РёРµ Р·Р°РїР°СЃРЅРѕРіРѕ РєР»СЋС‡Р°
                api_error_message = f"РћС€РёР±РєР° СЃРѕРµРґРёРЅРµРЅРёСЏ СЃ OpenRouter API: {str(api_error)}"
                logger.error(f"РћС€РёР±РєР° РїСЂРё Р·Р°РїСЂРѕСЃРµ Рє OpenRouter API: {api_error}", exc_info=True)
                
                # РџСЂРѕР±СѓРµРј РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ OpenAI API РєР°Рє Р·Р°РїР°СЃРЅРѕР№ РІР°СЂРёР°РЅС‚
                if OPENAI_API_KEY:
                    used_backup_api = True
                    logger.info(f"РџРѕРїС‹С‚РєР° РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ OpenAI API РєР°Рє Р·Р°РїР°СЃРЅРѕРіРѕ РІР°СЂРёР°РЅС‚Р° РґР»СЏ РёРґРµРё: {topic_idea}")
                    try:
                        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
                        
                        openai_response = await openai_client.chat.completions.create(
                            model="gpt-3.5-turbo",  # РСЃРїРѕР»СЊР·СѓРµРј GPT-3.5 Turbo РєР°Рє Р·Р°РїР°СЃРЅРѕР№ РІР°СЂРёР°РЅС‚
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            temperature=0.7,
                            max_tokens=850
                        )
                        
                        if openai_response and openai_response.choices and len(openai_response.choices) > 0 and openai_response.choices[0].message:
                            post_text = openai_response.choices[0].message.content.strip()
                            logger.info(f"РџРѕР»СѓС‡РµРЅ С‚РµРєСЃС‚ РїРѕСЃС‚Р° С‡РµСЂРµР· Р·Р°РїР°СЃРЅРѕР№ OpenAI API ({len(post_text)} СЃРёРјРІРѕР»РѕРІ)")
                        else:
                            logger.error(f"Некорректный или пустой ответ от OpenAI API")
                            post_text = "[Текст не сгенерирован из-за ошибки API]"
                    except Exception as openai_error:
                        logger.error(f"РћС€РёР±РєР° РїСЂРё РёСЃРїРѕР»СЊР·РѕРІР°РЅРёРё Р·Р°РїР°СЃРЅРѕРіРѕ OpenAI API: {openai_error}", exc_info=True)
                        post_text = "[Текст не сгенерирован из-за ошибки API]"
                else:
                    logger.error("Р—Р°РїР°СЃРЅРѕР№ OPENAI_API_KEY РЅРµ РЅР°СЃС‚СЂРѕРµРЅ, РЅРµРІРѕР·РјРѕР¶РЅРѕ РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ Р°Р»СЊС‚РµСЂРЅР°С‚РёРІРЅС‹Р№ API")
                    post_text = "[Текст не сгенерирован из-за ошибки API]"
        
        # Р•СЃР»Рё РЅРµС‚ OPENROUTER_API_KEY, РЅРѕ РµСЃС‚СЊ OPENAI_API_KEY, РёСЃРїРѕР»СЊР·СѓРµРј РµРіРѕ РЅР°РїСЂСЏРјСѓСЋ
        elif OPENAI_API_KEY:
            used_backup_api = True
            logger.info(f"OPENROUTER_API_KEY РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚, РёСЃРїРѕР»СЊР·СѓРµРј OpenAI API РЅР°РїСЂСЏРјСѓСЋ РґР»СЏ РёРґРµРё: {topic_idea}")
            try:
                openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
                
                openai_response = await openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",  # РСЃРїРѕР»СЊР·СѓРµРј GPT-3.5 Turbo
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=850
                )
                
                if openai_response and openai_response.choices and len(openai_response.choices) > 0 and openai_response.choices[0].message:
                    post_text = openai_response.choices[0].message.content.strip()
                    logger.info(f"РџРѕР»СѓС‡РµРЅ С‚РµРєСЃС‚ РїРѕСЃС‚Р° С‡РµСЂРµР· OpenAI API ({len(post_text)} СЃРёРјРІРѕР»РѕРІ)")
                else:
                    logger.error(f"Некорректный или пустой ответ от OpenAI API")
                    post_text = "[Текст не сгенерирован из-за ошибки API]"
            except Exception as openai_error:
                api_error_message = f"РћС€РёР±РєР° СЃРѕРµРґРёРЅРµРЅРёСЏ СЃ OpenAI API: {str(openai_error)}"
                logger.error(f"РћС€РёР±РєР° РїСЂРё Р·Р°РїСЂРѕСЃРµ Рє OpenAI API: {openai_error}", exc_info=True)
                post_text = "[Текст не сгенерирован из-за ошибки API]"
        
        # Р“РµРЅРµСЂР°С†РёСЏ РєР»СЋС‡РµРІС‹С… СЃР»РѕРІ РґР»СЏ РїРѕРёСЃРєР° РёР·РѕР±СЂР°Р¶РµРЅРёР№
        image_keywords = await generate_image_keywords(post_text, topic_idea, format_style)
        logger.info(f"РЎРіРµРЅРµСЂРёСЂРѕРІР°РЅС‹ РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР° РґР»СЏ РїРѕРёСЃРєР° РёР·РѕР±СЂР°Р¶РµРЅРёР№: {image_keywords}")
        
        # РџРѕРёСЃРє РёР·РѕР±СЂР°Р¶РµРЅРёР№
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
                logger.info(f"РќР°Р№РґРµРЅРѕ {len(unique_images)} СѓРЅРёРєР°Р»СЊРЅС‹С… РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕ РєР»СЋС‡РµРІРѕРјСѓ СЃР»РѕРІСѓ '{keyword}'")
            except Exception as e:
                logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕРёСЃРєРµ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РґР»СЏ РєР»СЋС‡РµРІРѕРіРѕ СЃР»РѕРІР° '{keyword}': {e}")
                continue
                
        if not found_images:
            try:
                found_images = await search_unsplash_images(topic_idea, count=5, topic=topic_idea, format_style=format_style)
                logger.info(f"РќР°Р№РґРµРЅРѕ {len(found_images)} РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕ РѕСЃРЅРѕРІРЅРѕР№ С‚РµРјРµ")
            except Exception as e:
                logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕРёСЃРєРµ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕ РѕСЃРЅРѕРІРЅРѕР№ С‚РµРјРµ: {e}")
                found_images = []
                
        logger.info(f"РџРѕРґРіРѕС‚РѕРІР»РµРЅРѕ {len(found_images)} РїСЂРµРґР»РѕР¶РµРЅРЅС‹С… РёР·РѕР±СЂР°Р¶РµРЅРёР№")
        
        # Р¤РѕСЂРјРёСЂРѕРІР°РЅРёРµ СЃРѕРѕР±С‰РµРЅРёСЏ РѕС‚РІРµС‚Р° СЃ СѓС‡РµС‚РѕРј РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ Р·Р°РїР°СЃРЅРѕРіРѕ API
        response_message = f"РЎРіРµРЅРµСЂРёСЂРѕРІР°РЅ РїРѕСЃС‚ СЃ {len(found_images[:IMAGE_RESULTS_COUNT])} РїСЂРµРґР»РѕР¶РµРЅРЅС‹РјРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏРјРё"
        if used_backup_api:
            response_message = f"РСЃРїРѕР»СЊР·РѕРІР°РЅ СЂРµР·РµСЂРІРЅС‹Р№ API (OpenAI). РЎРіРµРЅРµСЂРёСЂРѕРІР°РЅ РїРѕСЃС‚ СЃ {len(found_images[:IMAGE_RESULTS_COUNT])} РїСЂРµРґР»РѕР¶РµРЅРЅС‹РјРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏРјРё"
        if api_error_message:
            response_message = f"РћС€РёР±РєР° РіРµРЅРµСЂР°С†РёРё С‚РµРєСЃС‚Р°: {api_error_message}. РР·РѕР±СЂР°Р¶РµРЅРёР№ РЅР°Р№РґРµРЅРѕ: {len(found_images[:IMAGE_RESULTS_COUNT])}"
            
        # РџРѕСЃР»Рµ СѓСЃРїРµС€РЅРѕР№ РіРµРЅРµСЂР°С†РёРё РїРѕСЃС‚Р° СѓРІРµР»РёС‡РёРІР°РµРј СЃС‡РµС‚С‡РёРє РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ
        if telegram_user_id:
            has_subscription = await subscription_service.has_active_subscription(int(telegram_user_id))
            if not has_subscription:
                await subscription_service.increment_post_usage(int(telegram_user_id))
                
        return {
            "generated_text": post_text,
            "found_images": [img.dict() if hasattr(img, 'dict') else img for img in found_images[:IMAGE_RESULTS_COUNT]],
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
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РіРµРЅРµСЂР°С†РёРё РґРµС‚Р°Р»РµР№ РїРѕСЃС‚Р°: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Р’РЅСѓС‚СЂРµРЅРЅСЏСЏ РѕС€РёР±РєР° СЃРµСЂРІРµСЂР° РїСЂРё РіРµРЅРµСЂР°С†РёРё РґРµС‚Р°Р»РµР№ РїРѕСЃС‚Р°: {str(e)}") 
