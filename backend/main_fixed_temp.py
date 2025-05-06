import os
import httpx
from fastapi import Request
from log import logger

async def telegram_webhook(request: Request):
    """Р’РµР±С…СѓРє РґР»СЏ РѕР±СЂР°Р±РѕС‚РєРё РѕР±РЅРѕРІР»РµРЅРёР№ РѕС‚ Р±РѕС‚Р° Telegram."""
    try:
        # РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ Р·Р°РїСЂРѕСЃР°
        data = await request.json()
        logger.info(f"РџРѕР»СѓС‡РµРЅ РІРµР±С…СѓРє РѕС‚ Telegram: {data}")
        
        # РџСЂРѕРІРµСЂСЏРµРј, РµСЃС‚СЊ Р»Рё СЃРѕРѕР±С‰РµРЅРёРµ
        message = data.get('message')
        if not message:
            return {"ok": True}
        
        # РџРѕР»СѓС‡Р°РµРј ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Рё С‚РµРєСЃС‚ СЃРѕРѕР±С‰РµРЅРёСЏ
        user_id = message.get('from', {}).get('id')
        text = message.get('text', '')
        
        # Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅРѕРµ Р»РѕРіРёСЂРѕРІР°РЅРёРµ
        logger.info(f"РћР±СЂР°Р±Р°С‚С‹РІР°РµРј СЃРѕРѕР±С‰РµРЅРёРµ РѕС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {user_id}: {text}")
        
        # Р•СЃР»Рё СЌС‚Рѕ РєРѕРјР°РЅРґР° /start СЃ РїР°СЂР°РјРµС‚СЂРѕРј check_premium РёР»Рё РєРѕРјР°РЅРґР° /check_premium
        if text.startswith('/start check_premium') or text == '/check_premium':
            logger.info(f"РџРѕР»СѓС‡РµРЅР° РєРѕРјР°РЅРґР° РїСЂРѕРІРµСЂРєРё РїСЂРµРјРёСѓРјР° РѕС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {user_id}")
            
            # РџСЂРѕРІРµСЂСЏРµРј РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ С‡РµСЂРµР· REST API РІРјРµСЃС‚Рѕ РїСЂСЏРјРѕРіРѕ РїРѕРґРєР»СЋС‡РµРЅРёСЏ Рє Р‘Р”
            try:
                # РџСЂРѕРІРµСЂСЏРµРј, РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ Р»Рё Supabase РєР»РёРµРЅС‚
                if not supabase:
                    logger.error("Supabase РєР»РёРµРЅС‚ РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
                    await send_telegram_message(user_id, "РћС€РёР±РєР° СЃРµСЂРІРµСЂР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…. РџРѕР¶Р°Р»СѓР№СЃС‚Р°, СЃРѕРѕР±С‰РёС‚Рµ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.")
                    return {"ok": True, "error": "Supabase client not initialized"}
                
                # Р—Р°РїСЂР°С€РёРІР°РµРј Р°РєС‚РёРІРЅС‹Рµ РїРѕРґРїРёСЃРєРё РґР»СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ С‡РµСЂРµР· REST API
                try:
                    subscription_query = supabase.table("user_subscription").select("*").eq("user_id", user_id).eq("is_active", True).execute()
                    
                    logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ Р·Р°РїСЂРѕСЃР° РїРѕРґРїРёСЃРєРё С‡РµСЂРµР· REST API: {subscription_query}")
                    
                    has_premium = False
                    end_date_str = 'РЅРµРёР·РІРµСЃС‚РЅРѕ'
                    
                    # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚С‹ Р·Р°РїСЂРѕСЃР°
                    if hasattr(subscription_query, 'data') and subscription_query.data:
                        from datetime import datetime, timezone
                        
                        # РџСЂРѕРІРµСЂСЏРµРј РїРѕРґРїРёСЃРєРё РЅР° Р°РєС‚РёРІРЅРѕСЃС‚СЊ Рё СЃСЂРѕРє
                        # РРЎРџР РђР’Р›Р•РќРћ: РЎРѕР·РґР°РµРј datetime СЃ UTC timezone
                        current_date = datetime.now(timezone.utc)
                        active_subscriptions = []
                        
                        for subscription in subscription_query.data:
                            end_date = subscription.get("end_date")
                            if end_date:
                                try:
                                    # РџСЂРµРѕР±СЂР°Р·СѓРµРј РґР°С‚Сѓ РёР· СЃС‚СЂРѕРєРё РІ РѕР±СЉРµРєС‚ datetime
                                    if isinstance(end_date, str):
                                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                    
                                    # Р•СЃР»Рё РґР°С‚Р° РѕРєРѕРЅС‡Р°РЅРёСЏ РІ Р±СѓРґСѓС‰РµРј, РґРѕР±Р°РІР»СЏРµРј РІ Р°РєС‚РёРІРЅС‹Рµ
                                    if end_date > current_date:
                                        active_subscriptions.append(subscription)
                                except Exception as e:
                                    logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ РґР°С‚С‹ РїРѕРґРїРёСЃРєРё {end_date}: {e}")
                        
                        # Р•СЃР»Рё РµСЃС‚СЊ Р°РєС‚РёРІРЅС‹Рµ РїРѕРґРїРёСЃРєРё, СѓСЃС‚Р°РЅР°РІР»РёРІР°РµРј has_premium = True
                        if active_subscriptions:
                            has_premium = True
                            # Р‘РµСЂРµРј СЃР°РјСѓСЋ РїРѕР·РґРЅСЋСЋ РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ
                            latest_subscription = max(active_subscriptions, key=lambda x: x.get("end_date"))
                            end_date = latest_subscription.get("end_date")
                            if isinstance(end_date, str):
                                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                            end_date_str = end_date.strftime('%d.%m.%Y %H:%M')
                    
                    logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ РїСЂРѕРІРµСЂРєРё РїРѕРґРїРёСЃРєРё РґР»СЏ {user_id}: has_premium={has_premium}, end_date={end_date_str}")
                    
                    # Р¤РѕСЂРјРёСЂСѓРµРј С‚РµРєСЃС‚ РѕС‚РІРµС‚Р°
                    if has_premium:
                        reply_text = f"вњ… РЈ РІР°СЃ Р°РєС‚РёРІРёСЂРѕРІР°РЅ РџР Р•РњРРЈРњ РґРѕСЃС‚СѓРї!\nР”РµР№СЃС‚РІСѓРµС‚ РґРѕ: {end_date_str}\nРћР±РЅРѕРІРёС‚Рµ СЃС‚СЂР°РЅРёС†Сѓ РїСЂРёР»РѕР¶РµРЅРёСЏ, С‡С‚РѕР±С‹ СѓРІРёРґРµС‚СЊ РёР·РјРµРЅРµРЅРёСЏ."
                    else:
                        reply_text = "вќЊ РЈ РІР°СЃ РЅРµС‚ Р°РєС‚РёРІРЅРѕР№ РџР Р•РњРРЈРњ РїРѕРґРїРёСЃРєРё.\nР”Р»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РїСЂРµРјРёСѓРј-РґРѕСЃС‚СѓРїР° РѕС„РѕСЂРјРёС‚Рµ РїРѕРґРїРёСЃРєСѓ РІ РїСЂРёР»РѕР¶РµРЅРёРё."
                    
                    # РћС‚РїСЂР°РІР»СЏРµРј РѕС‚РІРµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ
                    await send_telegram_message(user_id, reply_text)
                    
                    return {"ok": True, "has_premium": has_premium}
                    
                except Exception as api_error:
                    logger.error(f"РћС€РёР±РєР° РїСЂРё РїСЂРѕРІРµСЂРєРµ РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР° С‡РµСЂРµР· REST API: {api_error}")
                    # РџРѕРїСЂРѕР±СѓРµРј Р°Р»СЊС‚РµСЂРЅР°С‚РёРІРЅС‹Р№ СЃРїРѕСЃРѕР± РїСЂРѕРІРµСЂРєРё, РёСЃРїРѕР»СЊР·СѓСЏ REST API РЅР°РїСЂСЏРјСѓСЋ С‡РµСЂРµР· httpx
                    try:
                        supabase_url = os.getenv("SUPABASE_URL")
                        supabase_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
                        
                        if not supabase_url or not supabase_key:
                            raise ValueError("РћС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ SUPABASE_URL РёР»Рё SUPABASE_KEY")
                        
                        # Р¤РѕСЂРјРёСЂСѓРµРј Р·Р°РїСЂРѕСЃ Рє REST API Supabase
                        headers = {
                            "apikey": supabase_key,
                            "Authorization": f"Bearer {supabase_key}",
                            "Content-Type": "application/json"
                        }
                        
                        async with httpx.AsyncClient() as client:
                            response = await client.get(
                                f"{supabase_url}/rest/v1/user_subscription",
                                headers=headers,
                                params={
                                    "select": "*",
                                    "user_id": f"eq.{user_id}",
                                    "is_active": "eq.true"
                                }
                            )
                            
                            if response.status_code == 200:
                                subscriptions = response.json()
                                
                                # РџСЂРѕРІРµСЂСЏРµРј РїРѕРґРїРёСЃРєРё РЅР° Р°РєС‚РёРІРЅРѕСЃС‚СЊ Рё СЃСЂРѕРє
                                from datetime import datetime, timezone
                                # РРЎРџР РђР’Р›Р•РќРћ: РЎРѕР·РґР°РµРј datetime СЃ UTC timezone
                                current_date = datetime.now(timezone.utc)
                                active_subscriptions = []
                                
                                for subscription in subscriptions:
                                    end_date = subscription.get("end_date")
                                    if end_date:
                                        try:
                                            # РџСЂРµРѕР±СЂР°Р·СѓРµРј РґР°С‚Сѓ РёР· СЃС‚СЂРѕРєРё РІ РѕР±СЉРµРєС‚ datetime
                                            if isinstance(end_date, str):
                                                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                            
                                            # Р•СЃР»Рё РґР°С‚Р° РѕРєРѕРЅС‡Р°РЅРёСЏ РІ Р±СѓРґСѓС‰РµРј, РґРѕР±Р°РІР»СЏРµРј РІ Р°РєС‚РёРІРЅС‹Рµ
                                            if end_date > current_date:
                                                active_subscriptions.append(subscription)
                                        except Exception as e:
                                            logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ РґР°С‚С‹ РїРѕРґРїРёСЃРєРё {end_date}: {e}")
                                
                                # Р•СЃР»Рё РµСЃС‚СЊ Р°РєС‚РёРІРЅС‹Рµ РїРѕРґРїРёСЃРєРё, СѓСЃС‚Р°РЅР°РІР»РёРІР°РµРј has_premium = True
                                has_premium = bool(active_subscriptions)
                                end_date_str = 'РЅРµРёР·РІРµСЃС‚РЅРѕ'
                                
                                if active_subscriptions:
                                    # Р‘РµСЂРµРј СЃР°РјСѓСЋ РїРѕР·РґРЅСЋСЋ РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ
                                    latest_subscription = max(active_subscriptions, key=lambda x: x.get("end_date"))
                                    end_date = latest_subscription.get("end_date")
                                    if isinstance(end_date, str):
                                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                    end_date_str = end_date.strftime('%d.%m.%Y %H:%M')
                                
                                logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ РїСЂРѕРІРµСЂРєРё РїРѕРґРїРёСЃРєРё С‡РµСЂРµР· httpx РґР»СЏ {user_id}: has_premium={has_premium}, end_date={end_date_str}")
                                
                                # Р¤РѕСЂРјРёСЂСѓРµРј С‚РµРєСЃС‚ РѕС‚РІРµС‚Р°
                                if has_premium:
                                    reply_text = f"вњ… РЈ РІР°СЃ Р°РєС‚РёРІРёСЂРѕРІР°РЅ РџР Р•РњРРЈРњ РґРѕСЃС‚СѓРї!\nР”РµР№СЃС‚РІСѓРµС‚ РґРѕ: {end_date_str}\nРћР±РЅРѕРІРёС‚Рµ СЃС‚СЂР°РЅРёС†Сѓ РїСЂРёР»РѕР¶РµРЅРёСЏ, С‡С‚РѕР±С‹ СѓРІРёРґРµС‚СЊ РёР·РјРµРЅРµРЅРёСЏ."
                                else:
                                    reply_text = "вќЊ РЈ РІР°СЃ РЅРµС‚ Р°РєС‚РёРІРЅРѕР№ РџР Р•РњРРЈРњ РїРѕРґРїРёСЃРєРё.\nР”Р»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РїСЂРµРјРёСѓРј-РґРѕСЃС‚СѓРїР° РѕС„РѕСЂРјРёС‚Рµ РїРѕРґРїРёСЃРєСѓ РІ РїСЂРёР»РѕР¶РµРЅРёРё."
                                
                                # РћС‚РїСЂР°РІР»СЏРµРј РѕС‚РІРµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ
                                await send_telegram_message(user_id, reply_text)
                                
                                return {"ok": True, "has_premium": has_premium}
                            else:
                                logger.error(f"РћС€РёР±РєР° РїСЂРё Р·Р°РїСЂРѕСЃРµ Рє Supabase REST API: {response.status_code} - {response.text}")
                                raise Exception(f"HTTP Error: {response.status_code}")
                    
                    except Exception as httpx_error:
                        logger.error(f"РћС€РёР±РєР° РїСЂРё РїСЂРѕРІРµСЂРєРµ РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР° С‡РµСЂРµР· httpx: {httpx_error}")
                        await send_telegram_message(user_id, "РћС€РёР±РєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…. РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РїРѕРїСЂРѕР±СѓР№С‚Рµ РїРѕР·Р¶Рµ.")
                        return {"ok": False, "error": str(httpx_error)}
            
            except Exception as e:
                logger.error(f"РћС€РёР±РєР° РїСЂРё РїСЂРѕРІРµСЂРєРµ РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР°: {e}")
                await send_telegram_message(user_id, f"РџСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР° РїСЂРё РїСЂРѕРІРµСЂРєРµ СЃС‚Р°С‚СѓСЃР° РїРѕРґРїРёСЃРєРё. РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РїРѕРїСЂРѕР±СѓР№С‚Рµ РїРѕР·Р¶Рµ.")
                return {"ok": False, "error": str(e)}
        
        # ... РѕСЃС‚Р°Р»СЊРЅР°СЏ РѕР±СЂР°Р±РѕС‚РєР° РІРµР±С…СѓРєРѕРІ ...
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ РІРµР±С…СѓРєР° Telegram: {e}")
        return {"ok": False, "error": str(e)} 
