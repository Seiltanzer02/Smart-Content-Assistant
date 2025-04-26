# --- Маршрут для получения ранее сохраненных результатов анализа ---
@app.get("/ideas", response_model=SuggestedIdeasResponse)
async def get_saved_ideas(request: Request, channel_name: Optional[str] = None):
    """Получение ранее сохраненных результатов анализа."""
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос идей без идентификации пользователя Telegram")
            return SuggestedIdeasResponse(
                message="Для доступа к идеям необходимо авторизоваться через Telegram",
                ideas=[]
            )
        
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            return SuggestedIdeasResponse(
                message="Ошибка: не удалось подключиться к базе данных",
                ideas=[]
            )
        
        # Строим запрос к базе данных
        query = supabase.table("suggested_ideas").select("*").eq("user_id", telegram_user_id)
        
        # Если указано имя канала, фильтруем по нему
        if channel_name:
            query = query.eq("channel_name", channel_name)
            
        # Выполняем запрос
        result = query.order("created_at", desc=True).execute()
        
        # Обрабатываем результат
        if not hasattr(result, 'data'):
            logger.error(f"Ошибка при получении идей из БД: {result}")
            return SuggestedIdeasResponse(
                message="Не удалось получить сохраненные идеи",
                ideas=[]
            )
            
        # === СОЗДАЕМ СПИСОК ИДЕЙ С КОРРЕКТНЫМ ФОРМАТИРОВАНИЕМ ===
        ideas = []
        for item in result.data:
            # Проверяем наличие topic_idea
            topic_idea = item.get("topic_idea", "")
            if not topic_idea:
                logger.warning(f"Пропущена идея без topic_idea: ID={item.get('id', 'N/A')}")
                continue
                
            # Создаем объект идеи
            idea = {
                "id": item.get("id"),
                "channel_name": item.get("channel_name"),
                "topic_idea": topic_idea,
                "format_style": item.get("format_style"),
                "relative_day": item.get("relative_day"),
                "is_detailed": item.get("is_detailed"),
                "created_at": item.get("created_at")
            }
            ideas.append(idea)
        # === КОНЕЦ СОЗДАНИЯ СПИСКА ===
                
        logger.info(f"Получено {len(ideas)} идей для пользователя {telegram_user_id}")
        return SuggestedIdeasResponse(ideas=ideas)
        
    except Exception as e:
        logger.error(f"Ошибка при получении идей: {e}")
        return SuggestedIdeasResponse(
            message=f"Ошибка при получении идей: {str(e)}",
            ideas=[]
        )


# --- Маршрут для обновления поста ---
@app.put("/posts/{post_id}", response_model=PostResponse)
async def update_post(post_id: UUID, updated_post: PostUpdate, request: Request):
    """Обновление существующего поста."""
    try:
        # Получаем идентификатор пользователя из заголовка
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning(f"Попытка обновления поста без идентификатора пользователя: post_id={post_id}")
            return PostResponse(
                message="Для обновления поста необходимо авторизоваться через Telegram",
                post=None
            )
        
        # Проверяем соединение с базой данных
        if not supabase:
            logger.error("Клиент Supabase не инициализирован")
            return PostResponse(
                message="Ошибка: не удалось подключиться к базе данных",
                post=None
            )
        
        # Сначала обновляем схему
        try:
            update_schema()
        except Exception as schema_error:
            logger.error(f"Ошибка при обновлении схемы: {schema_error}")
        
        # Получаем текущую версию поста
        result = supabase.table("posts").select("*").eq("id", str(post_id)).execute()
        if not result.data:
            logger.warning(f"Пост с ID={post_id} не найден")
            return PostResponse(
                message=f"Пост с ID={post_id} не найден",
                post=None
            )
        
        # Проверяем права доступа
        post = result.data[0]
        if post.get("user_id") != telegram_user_id:
            logger.warning(f"Отказано в доступе: user_id={telegram_user_id}, post_id={post_id}")
            return PostResponse(
                message="У вас нет прав на обновление этого поста",
                post=None
            )
        
        # === ОБРАБОТКА ИЗОБРАЖЕНИЯ ===
        # Флаги для отслеживания обработки изображения
        image_processed = False
        field_explicitly_provided = hasattr(updated_post, 'selected_image_data')
        saved_image_id = post.get("saved_image_id")
        
        # Проверяем, было ли предоставлено изображение
        if field_explicitly_provided:
            selected_image_data = getattr(updated_post, 'selected_image_data', None)
            
            # Если предоставлено новое изображение
            if selected_image_data:
                try:
                    # Обрабатываем новое изображение
                    image_data = selected_image_data.encode('utf-8') if isinstance(selected_image_data, str) else selected_image_data
                    image_mapping = process_image_data(image_data)
                    
                    # Если успешно обработано, обновляем идентификатор
                    if image_mapping:
                        saved_image_id = image_mapping.get("id")
                        image_processed = True
                    else:
                        logger.warning(f"Не удалось обработать изображение для поста {post_id}")
                except Exception as img_error:
                    logger.error(f"Ошибка при обработке изображения: {img_error}")
            else:
                # Если поле было указано как null или пустое, удаляем изображение
                saved_image_id = None
                image_processed = True
        # === КОНЕЦ ОБРАБОТКИ ИЗОБРАЖЕНИЯ ===
        
        # Подготавливаем данные для обновления
        update_data = {
            "title": updated_post.title,
            "content": updated_post.content,
            "status": updated_post.status,
            "updated_at": datetime.now().isoformat()
        }
        
        # Если изображение было обработано или явно указано как null, обновляем его ID
        if image_processed or (field_explicitly_provided and saved_image_id is None):
            update_data["saved_image_id"] = saved_image_id
        
        # Обновляем пост в базе данных
        result = supabase.table("posts").update(update_data).eq("id", str(post_id)).execute()
        
        if not result.data:
            logger.error(f"Ошибка при обновлении поста: {result}")
            return PostResponse(
                message="Не удалось обновить пост",
                post=None
            )
        
        updated_post_data = result.data[0]
        logger.info(f"Пост успешно обновлен: ID={post_id}")
        
        return PostResponse(
            message="Пост успешно обновлен",
            post=update_post_status(updated_post_data)
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении поста: {e}")
        return PostResponse(
            message=f"Ошибка при обновлении поста: {str(e)}",
            post=None
        )


# --- Endpoint для генерации деталей поста ---
@app.post("/generate-post-details", response_model=PostDetailsResponse)
async def generate_post_details(request: Request, req: GeneratePostDetailsRequest):
    """Генерация детального поста на основе идеи, с текстом и релевантными изображениями."""
    # === ИНИЦИАЛИЗАЦИЯ ===
    found_images = [] 
    channel_name = req.channel_name if hasattr(req, 'channel_name') else ""
    api_error_message = None # Переменная для хранения ошибки API
    try:
        # Получение telegram_user_id из заголовков
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Запрос генерации поста без идентификации пользователя Telegram")
            raise HTTPException(
                status_code=401, 
                detail="Для генерации постов необходимо авторизоваться через Telegram"
            )
            
        topic_idea = req.topic_idea
        format_style = req.format_style
        
        # Проверка наличия API ключа
        if not OPENROUTER_API_KEY:
            logger.warning("Генерация деталей поста невозможна: отсутствует OPENROUTER_API_KEY")
            raise HTTPException(
                status_code=503,
                detail="API ключ не настроен. Обратитесь к администратору."
            )
            
        # Получение примеров постов канала
        post_samples = []
        if channel_name:
            try:
                channel_data = await get_channel_analysis(request, channel_name)
                if channel_data and "analyzed_posts_sample" in channel_data:
                    post_samples = channel_data["analyzed_posts_sample"]
                    logger.info(f"Получено {len(post_samples)} примеров постов для канала @{channel_name}")
            except Exception as e:
                logger.warning(f"Не удалось получить примеры постов для канала @{channel_name}: {e}")
                # Продолжаем без примеров
                pass
                
        # Формируем системный промпт
        system_prompt = """Ты - опытный контент-маркетолог для Telegram-каналов.
Твоя задача - сгенерировать текст поста на основе идеи и формата, который будет готов к публикации.

Пост должен быть:
1. Хорошо структурированным и легко читаемым
2. Соответствовать указанной теме/идее
3. Соответствовать указанному формату/стилю
4. Иметь правильное форматирование для Telegram (если нужно - с эмодзи, абзацами, списками)

Не используй хэштеги, если это не является частью формата.
Сделай пост уникальным и интересным, учитывая специфику Telegram-аудитории.
Используй примеры постов канала, если они предоставлены, чтобы сохранить стиль."""

        # Формируем запрос пользователя
        user_prompt = f"""Создай пост для Telegram-канала "@{channel_name}" на тему:
"{topic_idea}"

Формат поста: {format_style}

Напиши полный текст поста, который будет готов к публикации.
"""

        # Если есть примеры постов канала, добавляем их
        if post_samples:
            sample_text = "\n\n".join(post_samples[:3])  # Берем до 3 примеров
            user_prompt += f"""
            
Вот несколько примеров постов из этого канала для сохранения стиля:

{sample_text}
"""

        # Настройка клиента для использования OpenRouter
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        
        # === ЗАПРОС К API С УМЕНЬШЕННЫМ ЗНАЧЕНИЕМ MAX_TOKENS ===
        post_text = ""
        try:
            logger.info(f"Отправка запроса на генерацию поста по идее: {topic_idea}")
            response = await client.chat.completions.create(
                model="deepseek/deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.75,
                max_tokens=850, # <--- ИСПРАВЛЕНО: Уменьшено с 1000 до 850 токенов
                timeout=120,
                extra_headers={
                    "HTTP-Referer": "https://content-manager.onrender.com",
                    "X-Title": "Smart Content Assistant"
                }
            )
            
            # Обработка ответа от API
            if response and hasattr(response, 'choices') and response.choices and response.choices[0].message:
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

        # === ПОИСК ИЗОБРАЖЕНИЙ ===
        image_keywords = await generate_image_keywords(post_text, topic_idea, format_style)
        logger.info(f"Сгенерированы ключевые слова для поиска изображений: {image_keywords}")
        
        # Поиск изображений по ключевым словам
        for keyword in image_keywords[:3]:
            try:
                image_count = min(5 - len(found_images), 3)
                if image_count <= 0:
                    break
                    
                images = await search_unsplash_images(
                    keyword, 
                    count=image_count,
                    topic=topic_idea,
                    format_style=format_style,
                    post_text=post_text
                )
                
                # Добавляем только уникальные изображения
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
        
        # Если изображения не найдены, повторяем поиск с общей идеей
        if not found_images:
            try:
                found_images = await search_unsplash_images(
                    topic_idea, 
                    count=5,
                    topic=topic_idea,
                    format_style=format_style
                )
                logger.info(f"Найдено {len(found_images)} изображений по основной теме")
            except Exception as e:
                logger.error(f"Ошибка при поиске изображений по основной теме: {e}")
                found_images = []
        
        logger.info(f"Подготовлено {len(found_images)} предложенных изображений")
        
        # === ФОРМИРОВАНИЕ ОТВЕТА ===
        response_message = f"Сгенерирован пост с {len(found_images[:IMAGE_RESULTS_COUNT])} предложенными изображениями"
        if api_error_message:
            response_message = f"Ошибка генерации текста: {api_error_message}. Изображений найдено: {len(found_images[:IMAGE_RESULTS_COUNT])}"
        
        return PostDetailsResponse(
            generated_text=post_text,
            found_images=found_images[:IMAGE_RESULTS_COUNT],
            message=response_message,
            channel_name=channel_name,
            selected_image_data=PostImage(
                url=found_images[0].regular_url if found_images else "",
                id=found_images[0].id if found_images else None,
                preview_url=found_images[0].preview_url if found_images else "",
                alt=found_images[0].description if found_images else "",
                author=found_images[0].author_name if found_images else "",
                author_url=found_images[0].author_url if found_images else ""
            ) if found_images else None
        )
                
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"Ошибка при генерации деталей поста: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка сервера при генерации деталей поста: {str(e)}"
        ) 