from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import requests
import os

router = APIRouter()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_API_URL = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}' if TELEGRAM_BOT_TOKEN else None

@router.post('/send-image-to-chat')
async def send_image_to_chat(request: Request):
    try:
        data = await request.json()
        image_url = data.get('imageUrl')
        alt = data.get('alt', '')
        telegram_user_id = request.headers.get('x-telegram-user-id')
        if not telegram_user_id:
            raise HTTPException(status_code=401, detail='Не передан идентификатор пользователя Telegram')
        if not TELEGRAM_BOT_TOKEN:
            raise HTTPException(status_code=500, detail='TELEGRAM_BOT_TOKEN не задан в окружении')
        if not image_url:
            raise HTTPException(status_code=400, detail='Не передан URL изображения')
        # Отправляем изображение через Telegram Bot API
        payload = {
            'chat_id': telegram_user_id,
            'photo': image_url,
            'caption': alt or 'Ваше изображение',
            'parse_mode': 'HTML'
        }
        resp = requests.post(f'{TELEGRAM_API_URL}/sendPhoto', data=payload)
        if resp.status_code == 200:
            return JSONResponse({'success': True})
        else:
            return JSONResponse({'success': False, 'error': resp.text}, status_code=500)
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500) 