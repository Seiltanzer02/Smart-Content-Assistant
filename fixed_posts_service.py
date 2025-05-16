"""
Этот файл содержит исправленную версию блока кода из posts_service.py.
Нужно заменить проблемный блок в оригинальном файле на этот код.
"""

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