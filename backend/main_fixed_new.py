# РћСЃРЅРѕРІРЅС‹Рµ Р±РёР±Р»РёРѕС‚РµРєРё
import os
import sys
import json
import logging
import asyncio
import httpx
import tempfile
import shutil
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

# FastAPI РєРѕРјРїРѕРЅРµРЅС‚С‹
from fastapi import FastAPI, Request, File, UploadFile, HTTPException, Query, Path, Response, Header, Depends, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

# Telethon
from telethon import TelegramClient
from telethon.errors import ChannelInvalidError, ChannelPrivateError, UsernameNotOccupiedError
from dotenv import load_dotenv

# Supabase
from supabase import create_client, Client, AClient
from postgrest.exceptions import APIError
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PhoneNumberInvalidError, AuthKeyError, ApiIdInvalidError
import uuid
import mimetypes
from telethon.errors import RPCError
import getpass
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import time
import requests
from bs4 import BeautifulSoup
import telethon
import aiohttp
from telegram_utils import get_telegram_posts, get_mock_telegram_posts
import move_temp_files
from datetime import datetime, timedelta
import traceback

# Unsplash
from unsplash import Api as UnsplashApi
from unsplash import Auth as UnsplashAuth

# DeepSeek
from openai import AsyncOpenAI, OpenAIError

# PostgreSQL
import asyncpg

# --- Р”РћР‘РђР’Р›РЇР•Рњ РРњРџРћР РўР« РґР»СЏ Unsplash --- 
# from pyunsplash import PyUnsplash # <-- РЈР”РђР›РЇР•Рњ РќР•РџР РђР’РР›Р¬РќР«Р™ РРњРџРћР Рў
from unsplash import Api as UnsplashApi # <-- РРњРџРћР РўРР РЈР•Рњ РР— РџР РђР’РР›Р¬РќРћР“Рћ РњРћР”РЈР›РЇ
from unsplash import Auth as UnsplashAuth # <-- РРњРџРћР РўРР РЈР•Рњ РР— РџР РђР’РР›Р¬РќРћР“Рћ РњРћР”РЈР›РЇ
# ---------------------------------------

# --- РџР•Р Р•РњР•Р©РђР•Рњ Р›РѕРіРіРёСЂРѕРІР°РЅРёРµ Р’ РќРђР§РђР›Рћ --- 
# === РР—РњР•РќР•РќРћ: РЈСЂРѕРІРµРЅСЊ Р»РѕРіРёСЂРѕРІР°РЅРёСЏ РЅР° DEBUG ===
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
# === РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ===
logger = logging.getLogger(__name__)
# --- РљРћРќР•Р¦ РџР•Р Р•РњР•Р©Р•РќРРЇ --- 

# --- Р—Р°РіСЂСѓР·РєР° РїРµСЂРµРјРµРЅРЅС‹С… РѕРєСЂСѓР¶РµРЅРёСЏ (РѕСЃС‚Р°РІР»СЏРµРј РґР»СЏ РґСЂСѓРіРёС… РєР»СЋС‡РµР№) --- 
# РЈР±РёСЂР°РµРј РѕС‚Р»Р°РґРѕС‡РЅС‹Рµ print РґР»СЏ load_dotenv
dotenv_loaded = load_dotenv(override=True)

# РџРµСЂРµРјРµРЅРЅС‹Рµ РёР· Render РёРјРµСЋС‚ РїСЂРёРѕСЂРёС‚РµС‚ РЅР°Рґ .env С„Р°Р№Р»РѕРј
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL") 
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") 

# --- РљРѕРЅСЃС‚Р°РЅС‚С‹ (РІРєР»СЋС‡Р°СЏ РёРјСЏ СЃРµСЃСЃРёРё Telegram) --- 
SESSION_NAME = "telegram_session" # <-- РћРїСЂРµРґРµР»СЏРµРј РёРјСЏ С„Р°Р№Р»Р° СЃРµСЃСЃРёРё
IMAGE_SEARCH_COUNT = 15 # РЎРєРѕР»СЊРєРѕ РёР·РѕР±СЂР°Р¶РµРЅРёР№ Р·Р°РїСЂР°С€РёРІР°С‚СЊ Сѓ Unsplash
IMAGE_RESULTS_COUNT = 5 # РЎРєРѕР»СЊРєРѕ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕРєР°Р·С‹РІР°С‚СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ

# --- Р’Р°Р»РёРґР°С†РёСЏ РїРµСЂРµРјРµРЅРЅС‹С… РѕРєСЂСѓР¶РµРЅРёСЏ Р±РµР· Р°РІР°СЂРёР№РЅРѕРіРѕ Р·Р°РІРµСЂС€РµРЅРёСЏ --- 
missing_keys = []
if not OPENROUTER_API_KEY:
    logger.warning("РљР»СЋС‡ OPENROUTER_API_KEY РЅРµ РЅР°Р№РґРµРЅ! Р¤СѓРЅРєС†РёРё Р°РЅР°Р»РёР·Р° РєРѕРЅС‚РµРЅС‚Р° Р±СѓРґСѓС‚ РЅРµРґРѕСЃС‚СѓРїРЅС‹.")
    missing_keys.append("OPENROUTER_API_KEY")

if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
    logger.warning("TELEGRAM_API_ID РёР»Рё TELEGRAM_API_HASH РЅРµ РЅР°Р№РґРµРЅС‹! Р¤СѓРЅРєС†РёРё СЂР°Р±РѕС‚С‹ СЃ Telegram API Р±СѓРґСѓС‚ РЅРµРґРѕСЃС‚СѓРїРЅС‹.")
    if not TELEGRAM_API_ID:
        missing_keys.append("TELEGRAM_API_ID")
    if not TELEGRAM_API_HASH:
        missing_keys.append("TELEGRAM_API_HASH")

if not UNSPLASH_ACCESS_KEY:
    logger.warning("РљР»СЋС‡ UNSPLASH_ACCESS_KEY РЅРµ РЅР°Р№РґРµРЅ! РџРѕРёСЃРє РёР·РѕР±СЂР°Р¶РµРЅРёР№ С‡РµСЂРµР· Unsplash Р±СѓРґРµС‚ РЅРµРґРѕСЃС‚СѓРїРµРЅ.")
    missing_keys.append("UNSPLASH_ACCESS_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    logger.warning("SUPABASE_URL РёР»Рё SUPABASE_ANON_KEY РЅРµ РЅР°Р№РґРµРЅС‹! Р¤СѓРЅРєС†РёРё СЃРѕС…СЂР°РЅРµРЅРёСЏ РґР°РЅРЅС‹С… Р±СѓРґСѓС‚ РЅРµРґРѕСЃС‚СѓРїРЅС‹.")
    if not SUPABASE_URL:
        missing_keys.append("SUPABASE_URL")
    if not SUPABASE_ANON_KEY:
        missing_keys.append("SUPABASE_ANON_KEY")

# Р’С‹РІРѕРґ РёРЅС„РѕСЂРјР°С†РёРё Рѕ СЃРѕСЃС‚РѕСЏРЅРёРё РїРµСЂРµРјРµРЅРЅС‹С… РѕРєСЂСѓР¶РµРЅРёСЏ
if missing_keys:
    logger.warning(f"РћС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ СЃР»РµРґСѓСЋС‰РёРµ РїРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ: {', '.join(missing_keys)}")
    logger.warning("РќРµРєРѕС‚РѕСЂС‹Рµ С„СѓРЅРєС†РёРё РїСЂРёР»РѕР¶РµРЅРёСЏ РјРѕРіСѓС‚ Р±С‹С‚СЊ РЅРµРґРѕСЃС‚СѓРїРЅС‹.")
else:
    logger.info("Р’СЃРµ РЅРµРѕР±С…РѕРґРёРјС‹Рµ РїРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ РЅР°Р№РґРµРЅС‹.")

# --- РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ Supabase client ---
logger.info("РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ Supabase...")
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")

if not supabase_url or not supabase_key:
    logger.warning("SUPABASE_URL РёР»Рё SUPABASE_ANON_KEY РЅРµ РЅР°Р№РґРµРЅС‹ РІ РѕРєСЂСѓР¶РµРЅРёРё.")
    supabase = None
else:
    try:
        # РЎРѕР·РґР°РµРј РєР»РёРµРЅС‚ Supabase
        supabase = create_client(supabase_url, supabase_key)
        logger.info("Supabase СѓСЃРїРµС€РЅРѕ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ.")
        
        # РџСЂРѕРІРµСЂСЏРµРј РґРѕСЃС‚СѓРїРЅРѕСЃС‚СЊ С‚Р°Р±Р»РёС†
        try:
            # РџРѕРїС‹С‚РєР° РїРѕР»СѓС‡РёС‚СЊ Р·Р°РїРёСЃСЊ РёР· С‚Р°Р±Р»РёС†С‹ suggested_ideas РґР»СЏ РїСЂРѕРІРµСЂРєРё
            result = supabase.table("suggested_ideas").select("id").limit(1).execute()
            logger.info("РўР°Р±Р»РёС†Р° suggested_ideas СЃСѓС‰РµСЃС‚РІСѓРµС‚ Рё РґРѕСЃС‚СѓРїРЅР°.")
        except Exception as table_err:
            logger.warning(f"РўР°Р±Р»РёС†Р° suggested_ideas РЅРµРґРѕСЃС‚СѓРїРЅР°: {table_err}. Р’РѕР·РјРѕР¶РЅРѕ, РјРёРіСЂР°С†РёРё РЅРµ Р±С‹Р»Рё РІС‹РїРѕР»РЅРµРЅС‹.")
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РёРЅРёС†РёР°Р»РёР·Р°С†РёРё Supabase: {e}")
        supabase = None
# ---------------------------------------

# --- Р’СЃРїРѕРјРѕРіР°С‚РµР»СЊРЅР°СЏ С„СѓРЅРєС†РёСЏ РґР»СЏ РїСЂСЏРјС‹С… SQL-Р·Р°РїСЂРѕСЃРѕРІ С‡РµСЂРµР· API Supabase ---
async def _execute_sql_direct(sql_query: str) -> Dict[str, Any]:
    """Р’С‹РїРѕР»РЅСЏРµС‚ РїСЂСЏРјРѕР№ SQL Р·Р°РїСЂРѕСЃ С‡РµСЂРµР· Supabase API."""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not supabase_key:
        logger.error("РќРµ РЅР°Р№РґРµРЅС‹ РїРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ SUPABASE_URL РёР»Рё SUPABASE_ANON_KEY РґР»СЏ РїСЂСЏРјРѕРіРѕ SQL")
        return {"status_code": 500, "error": "Missing Supabase credentials"}
        
    url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json" # РСЃРїРѕР»СЊР·СѓРµРј РЅР°С€Сѓ RPC С„СѓРЅРєС†РёСЋ
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json={"query": sql_query}, headers=headers)
        
        if response.status_code in [200, 204]:
            try:
                return {"status_code": response.status_code, "data": response.json()}
            except json.JSONDecodeError:
                # Р”Р»СЏ 204 РѕС‚РІРµС‚Р° С‚РµР»Р° РјРѕР¶РµС‚ РЅРµ Р±С‹С‚СЊ
                return {"status_code": response.status_code, "data": None}
        else:
            logger.error(f"РћС€РёР±РєР° РїСЂРё РІС‹РїРѕР»РЅРµРЅРёРё РїСЂСЏРјРѕРіРѕ SQL Р·Р°РїСЂРѕСЃР°: {response.status_code} - {response.text}")
            return {"status_code": response.status_code, "error": response.text}
            
    except httpx.RequestError as e:
        logger.error(f"РћС€РёР±РєР° HTTP Р·Р°РїСЂРѕСЃР° РїСЂРё РІС‹РїРѕР»РЅРµРЅРёРё РїСЂСЏРјРѕРіРѕ SQL: {e}")
        return {"status_code": 500, "error": str(e)}
    except Exception as e:
        logger.error(f"РќРµРїСЂРµРґРІРёРґРµРЅРЅР°СЏ РѕС€РёР±РєР° РїСЂРё РІС‹РїРѕР»РЅРµРЅРёРё РїСЂСЏРјРѕРіРѕ SQL: {e}")
        return {"status_code": 500, "error": str(e)}
# -------------------------------------------------------------------

# --- РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ FastAPI --- 
app = FastAPI(
    title="Smart Content Assistant API",
    description="API РґР»СЏ Р°РЅР°Р»РёР·Р° Telegram РєР°РЅР°Р»РѕРІ Рё РіРµРЅРµСЂР°С†РёРё РєРѕРЅС‚РµРЅС‚-РїР»Р°РЅРѕРІ."
)

# РќР°СЃС‚СЂРѕР№РєР° CORS
origins = [
    "http://localhost", 
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "https://*.onrender.com",  # Р”Р»СЏ Render
    "https://t.me",            # Р”Р»СЏ Telegram
    "*"                        # Р’СЂРµРјРµРЅРЅРѕ СЂР°Р·СЂРµС€Р°РµРј РІСЃРµ
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Telegram-User-Id"]  # РџРѕР·РІРѕР»СЏРµРј С‡РёС‚Р°С‚СЊ СЌС‚РѕС‚ Р·Р°РіРѕР»РѕРІРѕРє
)

@app.post("/generate-invoice", response_model=Dict[str, Any])
async def generate_invoice(request: Request):
    """Р“РµРЅРµСЂРёСЂСѓРµС‚ invoice_url С‡РµСЂРµР· Telegram Bot API createInvoiceLink"""
    try:
        data = await request.json()
        if not data.get("user_id") or not data.get("amount"):
            raise HTTPException(status_code=400, detail="РћС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ РѕР±СЏР·Р°С‚РµР»СЊРЅС‹Рµ РїР°СЂР°РјРµС‚СЂС‹")
        user_id = data["user_id"]
        amount = int(data["amount"])
        payment_id = f"stars_invoice_{int(time.time())}_{user_id}"
        title = "РџРѕРґРїРёСЃРєР° Premium"
        description = "РџРѕРґРїРёСЃРєР° Premium РЅР° Smart Content Assistant РЅР° 1 РјРµСЃСЏС†"
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        provider_token = os.getenv("PROVIDER_TOKEN")
        if not bot_token or not provider_token:
            raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN РёР»Рё PROVIDER_TOKEN РЅРµ Р·Р°РґР°РЅС‹ РІ РѕРєСЂСѓР¶РµРЅРёРё")
        url = f"https://api.telegram.org/bot{bot_token}/createInvoiceLink"
        payload = {
            "title": title,
            "description": description,
            "payload": payment_id,
            "provider_token": provider_token,
            "currency": "RUB",
            "prices": [{"label": "РџРѕРґРїРёСЃРєР°", "amount": amount * 100}],
            "photo_url": "https://smart-content-assistant.onrender.com/static/premium_sub.jpg"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            tg_data = response.json()
            if not tg_data.get("ok"):
                logger.error(f"РћС€РёР±РєР° Telegram API: {tg_data}")
                raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° Telegram API: {tg_data}")
            invoice_url = tg_data["result"]
        return {"invoice_url": invoice_url, "payment_id": payment_id}
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РіРµРЅРµСЂР°С†РёРё РёРЅРІРѕР№СЃР°: {e}")
        raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° РїСЂРё РіРµРЅРµСЂР°С†РёРё РёРЅРІРѕР№СЃР°: {str(e)}")

@app.post("/send-stars-invoice", response_model=Dict[str, Any])
async def send_stars_invoice(request: Request):
    """РћС‚РїСЂР°РІР»СЏРµС‚ invoice РЅР° РѕРїР»Р°С‚Сѓ Stars С‡РµСЂРµР· Telegram Bot API sendInvoice (provider_token='', currency='XTR'). amount вЂ” СЌС‚Рѕ РєРѕР»РёС‡РµСЃС‚РІРѕ Stars (С†РµР»РѕРµ С‡РёСЃР»Рѕ)."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        amount = data.get("amount")
        if not user_id or not amount:
            raise HTTPException(status_code=400, detail="user_id Рё amount РѕР±СЏР·Р°С‚РµР»СЊРЅС‹")
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN РЅРµ Р·Р°РґР°РЅ РІ РѕРєСЂСѓР¶РµРЅРёРё")
        # amount вЂ” СЌС‚Рѕ РєРѕР»РёС‡РµСЃС‚РІРѕ Stars, Telegram С‚СЂРµР±СѓРµС‚ amount*100
        stars_amount = int(amount)
        url = f"https://api.telegram.org/bot{bot_token}/sendInvoice"
        payload = {
            "chat_id": user_id,
            "title": "РџРѕРґРїРёСЃРєР° Premium",
            "description": "РџРѕРґРїРёСЃРєР° Premium РЅР° 1 РјРµСЃСЏС†",
            "payload": f"stars_invoice_{user_id}_{int(time.time())}",
            "provider_token": "",  # РџРЈРЎРўРћР™ РґР»СЏ Stars
            "currency": "XTR",
            "prices": [{"label": "XTR", "amount": stars_amount}],  # <--- Р‘Р•Р— *100!
            "need_name": False,
            "need_email": False,
            "is_flexible": False,
            "photo_url": "https://smart-content-assistant.onrender.com/static/premium_sub.jpg"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            tg_data = response.json()
            if not tg_data.get("ok"):
                logger.error(f"РћС€РёР±РєР° Telegram API sendInvoice: {tg_data}")
                return {"success": False, "message": f"РћС€РёР±РєР° Telegram API: {tg_data}"}
        return {"success": True, "message": "РРЅРІРѕР№СЃ РѕС‚РїСЂР°РІР»РµРЅ РІ С‡Р°С‚ СЃ Р±РѕС‚РѕРј. РџСЂРѕРІРµСЂСЊС‚Рµ Telegram Рё РѕРїР»Р°С‚РёС‚Рµ СЃС‡С‘С‚."}
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РѕС‚РїСЂР°РІРєРµ Stars-РёРЅРІРѕР№СЃР°: {e}")
        return {"success": False, "message": f"РћС€РёР±РєР°: {str(e)}"}

@app.post("/generate-stars-invoice-link", response_model=Dict[str, Any])
async def generate_stars_invoice_link(request: Request):
    """Р“РµРЅРµСЂРёСЂСѓРµС‚ invoice_link РґР»СЏ РѕРїР»Р°С‚С‹ Stars С‡РµСЂРµР· Telegram Bot API createInvoiceLink (provider_token='', currency='XTR')."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        amount = 1 # <--- РЈРЎРўРђРќРћР’Р›Р•РќРћ Р’ 1 Star
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id РѕР±СЏР·Р°С‚РµР»РµРЅ")
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN РЅРµ Р·Р°РґР°РЅ РІ РѕРєСЂСѓР¶РµРЅРёРё")
        url = f"https://api.telegram.org/bot{bot_token}/createInvoiceLink"
        payload = {
            "title": "РџРѕРґРїРёСЃРєР° Premium",
            "description": "РџРѕРґРїРёСЃРєР° Premium РЅР° 1 РјРµСЃСЏС†",
            "payload": f"stars_invoice_{user_id}_{int(time.time())}",
            "provider_token": "",
            "currency": "XTR",
            "prices": [{"label": "XTR", "amount": amount}], # <--- Р¦РµРЅР° С‚РµРїРµСЂСЊ 1
            "photo_url": "https://smart-content-assistant.onrender.com/static/premium_sub.jpg"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            tg_data = response.json()
            if not tg_data.get("ok"):
                logger.error(f"РћС€РёР±РєР° Telegram API createInvoiceLink: {tg_data}")
                return {"success": False, "error": tg_data}
            invoice_link = tg_data["result"]
        return {"success": True, "invoice_link": invoice_link}
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РіРµРЅРµСЂР°С†РёРё Stars invoice link: {e}")
        return {"success": False, "error": str(e)}

def normalize_db_url(url: str) -> str:
    """
    РџСЂРµРѕР±СЂР°Р·СѓРµС‚ URL Р±Р°Р·С‹ РґР°РЅРЅС‹С… РІ С„РѕСЂРјР°С‚, СЃРѕРІРјРµСЃС‚РёРјС‹Р№ СЃ PostgreSQL.
    Р•СЃР»Рё URL РЅР°С‡РёРЅР°РµС‚СЃСЏ СЃ https://, РїСЂРµРѕР±СЂР°Р·СѓРµС‚ РµРіРѕ РІ С„РѕСЂРјР°С‚ postgresql://.
    """
    if not url:
        logger.warning("URL Р±Р°Р·С‹ РґР°РЅРЅС‹С… РїСѓСЃС‚РѕР№!")
        return url
        
    logger.info(f"РСЃС…РѕРґРЅС‹Р№ URL Р±Р°Р·С‹ РґР°РЅРЅС‹С… РЅР°С‡РёРЅР°РµС‚СЃСЏ СЃ: {url[:10]}...")
    
    # Р•СЃР»Рё URL - СЌС‚Рѕ СЃС‚СЂРѕРєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ Postgres, РєРѕС‚РѕСЂСѓСЋ РїСЂРµРґРѕСЃС‚Р°РІР»СЏРµС‚ Supabase
    # РџСЂРёРјРµСЂ: postgres://postgres:[YOUR-PASSWORD]@db.vgffoerxbaqvzqgkaabq.supabase.co:5432/postgres
    if url.startswith('postgres://') and 'supabase.co' in url:
        logger.info("РћР±РЅР°СЂСѓР¶РµРЅ URL РїРѕРґРєР»СЋС‡РµРЅРёСЏ Рє Supabase PostgreSQL - URL РєРѕСЂСЂРµРєС‚РЅС‹Р№")
        return url
    
    # Р•СЃР»Рё URL РЅР°С‡РёРЅР°РµС‚СЃСЏ СЃ https://, Р·Р°РјРµРЅСЏРµРј РЅР° postgresql://
    if url.startswith('https://'):
        # РР·РІР»РµРєР°РµРј С…РѕСЃС‚ Рё РїСѓС‚СЊ
        parts = url.replace('https://', '').split('/')
        host = parts[0]
        
        # Р”Р»СЏ Supabase РЅСѓР¶РµРЅ СЃРїРµС†РёР°Р»СЊРЅС‹Р№ С„РѕСЂРјР°С‚
        if 'supabase.co' in host:
            try:
                # РџС‹С‚Р°РµРјСЃСЏ РЅР°Р№С‚Рё ID РїСЂРѕРµРєС‚Р°
                project_id = host.split('.')[0]
                # Р¤РѕСЂРјРёСЂСѓРµРј РїСЂР°РІРёР»СЊРЅС‹Р№ URL РґР»СЏ PostgreSQL СЃ РїР°СЂРѕР»РµРј РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ
                # Р­С‚Рѕ РїСЂРёРјРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚, РµРіРѕ РЅСѓР¶РЅРѕ СѓС‚РѕС‡РЅРёС‚СЊ РґР»СЏ РєРѕРЅРєСЂРµС‚РЅРѕР№ РёРЅСЃС‚Р°Р»Р»СЏС†РёРё
                postgresql_url = f"postgresql://postgres:postgres@db.{project_id}.supabase.co:5432/postgres"
                logger.info(f"URL Supabase РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅ РІ PostgreSQL С„РѕСЂРјР°С‚: {postgresql_url[:20]}...")
                return postgresql_url
            except Exception as e:
                logger.error(f"РћС€РёР±РєР° РїСЂРё РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅРёРё URL Supabase: {e}")
                # РџСЂРѕСЃС‚РѕРµ РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅРёРµ РєР°Рє СЂРµР·РµСЂРІРЅС‹Р№ РІР°СЂРёР°РЅС‚
                postgresql_url = url.replace('https://', 'postgresql://')
                logger.info(f"URL Р±Р°Р·С‹ РґР°РЅРЅС‹С… РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅ РёР· https:// РІ postgresql:// С„РѕСЂРјР°С‚ (СЂРµР·РµСЂРІРЅС‹Р№ РІР°СЂРёР°РЅС‚): {postgresql_url[:20]}...")
                return postgresql_url
        else:
            # Р”Р»СЏ РґСЂСѓРіРёС… СЃР»СѓС‡Р°РµРІ РїСЂРѕСЃС‚Рѕ Р·Р°РјРµРЅСЏРµРј РїСЂРѕС‚РѕРєРѕР»
            postgresql_url = url.replace('https://', 'postgresql://')
            logger.info(f"URL Р±Р°Р·С‹ РґР°РЅРЅС‹С… РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅ РёР· https:// РІ postgresql:// С„РѕСЂРјР°С‚: {postgresql_url[:20]}...")
            return postgresql_url
    
    # Р•СЃР»Рё URL РЅР°С‡РёРЅР°РµС‚СЃСЏ СЃ http://, С‚РѕР¶Рµ Р·Р°РјРµРЅСЏРµРј РЅР° postgresql://
    if url.startswith('http://'):
        postgresql_url = url.replace('http://', 'postgresql://')
        logger.info(f"URL Р±Р°Р·С‹ РґР°РЅРЅС‹С… РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅ РёР· http:// РІ postgresql:// С„РѕСЂРјР°С‚: {postgresql_url[:20]}...")
        return postgresql_url
    
    # Р•СЃР»Рё URL СѓР¶Рµ РёРјРµРµС‚ РїСЂР°РІРёР»СЊРЅС‹Р№ С„РѕСЂРјР°С‚ postgresql://
    if url.startswith('postgresql://') or url.startswith('postgres://'):
        logger.info(f"URL Р±Р°Р·С‹ РґР°РЅРЅС‹С… СѓР¶Рµ РІ РїСЂР°РІРёР»СЊРЅРѕРј С„РѕСЂРјР°С‚Рµ: {url[:20]}...")
        return url
    
    # Р’ РґСЂСѓРіРёС… СЃР»СѓС‡Р°СЏС… РІРѕР·РІСЂР°С‰Р°РµРј URL Р±РµР· РёР·РјРµРЅРµРЅРёР№, РЅРѕ СЃ РїСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµРј
    logger.warning(f"URL Р±Р°Р·С‹ РґР°РЅРЅС‹С… РёРјРµРµС‚ РЅРµРёР·РІРµСЃС‚РЅС‹Р№ С„РѕСЂРјР°С‚. РќР°С‡Р°Р»Рѕ URL: {url[:10]}...")
    return url

@app.post("/telegram/webhook")
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
        
        # ... РѕСЃС‚Р°Р»СЊРЅР°СЏ РѕР±СЂР°Р±РѕС‚РєР° РІРµР±С…СѓРєРѕРІ ...
        
    return {"ok": True}
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ РІРµР±С…СѓРєР° Telegram: {e}")
        return {"ok": False, "error": str(e)}

# Р’С‹РґРµР»РёРј РѕС‚РїСЂР°РІРєСѓ СЃРѕРѕР±С‰РµРЅРёР№ РІ РѕС‚РґРµР»СЊРЅСѓСЋ С„СѓРЅРєС†РёСЋ РґР»СЏ РїРµСЂРµРёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ
async def send_telegram_message(chat_id, text, parse_mode="HTML"):
    """РћС‚РїСЂР°РІР»СЏРµС‚ СЃРѕРѕР±С‰РµРЅРёРµ С‡РµСЂРµР· Telegram API"""
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        logger.error("РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ TELEGRAM_BOT_TOKEN РїСЂРё РѕС‚РїСЂР°РІРєРµ СЃРѕРѕР±С‰РµРЅРёСЏ")
        return False
        
    telegram_api_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(telegram_api_url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            })
            if response.status_code == 200:
                logger.info(f"РЎРѕРѕР±С‰РµРЅРёРµ СѓСЃРїРµС€РЅРѕ РѕС‚РїСЂР°РІР»РµРЅРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ {chat_id}")
                return True
            else:
                logger.error(f"РћС€РёР±РєР° РїСЂРё РѕС‚РїСЂР°РІРєРµ СЃРѕРѕР±С‰РµРЅРёСЏ: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"РСЃРєР»СЋС‡РµРЅРёРµ РїСЂРё РѕС‚РїСЂР°РІРєРµ СЃРѕРѕР±С‰РµРЅРёСЏ РІ Telegram: {e}")
            return False

# Р”РѕР±Р°РІР»СЏРµРј РїСЂСЏРјРѕР№ СЌРЅРґРїРѕРёРЅС‚ РґР»СЏ РїСЂРѕРІРµСЂРєРё Рё РѕР±РЅРѕРІР»РµРЅРёСЏ СЃС‚Р°С‚СѓСЃР° РїРѕРґРїРёСЃРєРё
@app.get("/manual-check-premium/{user_id}")
async def manual_check_premium(user_id: int, request: Request, force_update: bool = False):
    """
    Р СѓС‡РЅР°СЏ РїСЂРѕРІРµСЂРєР° РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР° Рё РѕР±РЅРѕРІР»РµРЅРёРµ РєСЌС€Р°.
    РџР°СЂР°РјРµС‚СЂ force_update=true РїРѕР·РІРѕР»СЏРµС‚ РїСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕ РѕР±РЅРѕРІРёС‚СЊ РєСЌС€ РґР»СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ.
    """
    try:
        db_url = os.getenv("SUPABASE_URL") or os.getenv("DATABASE_URL") or os.getenv("RENDER_DATABASE_URL")
        if not db_url:
            logger.error("РћС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ SUPABASE_URL, DATABASE_URL Рё RENDER_DATABASE_URL РїСЂРё СЂСѓС‡РЅРѕР№ РїСЂРѕРІРµСЂРєРµ РїСЂРµРјРёСѓРјР°")
            return {"success": False, "error": "РћС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ SUPABASE_URL, DATABASE_URL Рё RENDER_DATABASE_URL РІ РїРµСЂРµРјРµРЅРЅС‹С… РѕРєСЂСѓР¶РµРЅРёСЏ"}
            
        # РќРѕСЂРјР°Р»РёР·СѓРµРј URL Р±Р°Р·С‹ РґР°РЅРЅС‹С…
        db_url = normalize_db_url(db_url)
            
        # РџРѕРґРєР»СЋС‡Р°РµРјСЃСЏ Рє Р‘Р”
        conn = await asyncpg.connect(db_url)
        try:
            # РџСЂРѕРІРµСЂСЏРµРј РЅР°Р»РёС‡РёРµ Р°РєС‚РёРІРЅРѕР№ РїРѕРґРїРёСЃРєРё
            query = """
            SELECT COUNT(*) 
            FROM user_subscription 
            WHERE user_id = $1 
              AND is_active = TRUE 
              AND end_date > NOW()
            """
            count = await conn.fetchval(query, user_id)
            has_premium = count > 0
            
            # РџРѕР»СѓС‡Р°РµРј РґРµС‚Р°Р»Рё РїРѕРґРїРёСЃРєРё
            subscription_details = {}
            if has_premium:
                details_query = """
                SELECT 
                    end_date,
                    payment_id,
                    created_at,
                    updated_at
                FROM user_subscription 
                WHERE user_id = $1 
                  AND is_active = TRUE
                ORDER BY end_date DESC 
                LIMIT 1
                """
                record = await conn.fetchrow(details_query, user_id)
                if record:
                    subscription_details = {
                        "end_date": record["end_date"].strftime('%Y-%m-%d %H:%M:%S'),
                        "payment_id": record["payment_id"],
                        "created_at": record["created_at"].strftime('%Y-%m-%d %H:%M:%S'),
                        "updated_at": record["updated_at"].strftime('%Y-%m-%d %H:%M:%S')
                    }
            
            # Р•СЃР»Рё force_update = true, РїСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕ РѕР±РЅРѕРІР»СЏРµРј СЃС‚Р°С‚СѓСЃ РІРѕ РІСЃРµС… РєСЌС€Р°С…
            if force_update and has_premium:
                # Р—РґРµСЃСЊ РјРѕР¶РЅРѕ РґРѕР±Р°РІРёС‚СЊ Р»РѕРіРёРєСѓ РѕР±РЅРѕРІР»РµРЅРёСЏ РєСЌС€Р° РёР»Рё РґСЂСѓРіРёС… РјРµС…Р°РЅРёР·РјРѕРІ
                # Р’ СЌС‚РѕРј РїСЂРёРјРµСЂРµ РјС‹ РїСЂРѕСЃС‚Рѕ Р»РѕРіРёСЂСѓРµРј СЃРѕР±С‹С‚РёРµ
                logger.info(f"РџСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕРµ РѕР±РЅРѕРІР»РµРЅРёРµ РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР° РґР»СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {user_id}")
            
            return {
                "success": True, 
                "user_id": user_id,
                "has_premium": has_premium,
                "subscription_details": subscription_details
            }
            
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё СЂСѓС‡РЅРѕР№ РїСЂРѕРІРµСЂРєРµ РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР°: {e}")
        return {"success": False, "error": str(e)}

# --- РќР°СЃС‚СЂРѕР№РєР° РѕР±СЃР»СѓР¶РёРІР°РЅРёСЏ СЃС‚Р°С‚РёС‡РµСЃРєРёС… С„Р°Р№Р»РѕРІ ---
import os
from fastapi.staticfiles import StaticFiles

# РџСѓС‚СЊ Рє РїР°РїРєРµ СЃРѕ СЃС‚Р°С‚РёС‡РµСЃРєРёРјРё С„Р°Р№Р»Р°РјРё
static_folder = os.path.join(os.path.dirname(__file__), "static")

# Р¤Р›РђР“ РґР»СЏ РјРѕРЅС‚РёСЂРѕРІР°РЅРёСЏ СЃС‚Р°С‚РёРєРё РІ РєРѕРЅС†Рµ С„Р°Р№Р»Р°
SHOULD_MOUNT_STATIC = os.path.exists(static_folder)
# РќРћР’Р«Р™ Р¤Р›РђР“, СѓРєР°Р·С‹РІР°СЋС‰РёР№, С‡С‚Рѕ РјС‹ СѓР¶Рµ РЅР°СЃС‚СЂРѕРёР»Рё РјР°СЂС€СЂСѓС‚С‹ SPA
SPA_ROUTES_CONFIGURED = False

if SHOULD_MOUNT_STATIC:
    logger.info(f"РЎС‚Р°С‚РёС‡РµСЃРєРёРµ С„Р°Р№Р»С‹ Р±СѓРґСѓС‚ РѕР±СЃР»СѓР¶РёРІР°С‚СЊСЃСЏ РёР· РїР°РїРєРё: {static_folder} (РјРѕРЅС‚РёСЂРѕРІР°РЅРёРµ РІ РєРѕРЅС†Рµ С„Р°Р№Р»Р°)")
else:
    logger.warning(f"РџР°РїРєР° СЃС‚Р°С‚РёС‡РµСЃРєРёС… С„Р°Р№Р»РѕРІ РЅРµ РЅР°Р№РґРµРЅР°: {static_folder}")
    logger.warning("РЎС‚Р°С‚РёС‡РµСЃРєРёРµ С„Р°Р№Р»С‹ РЅРµ Р±СѓРґСѓС‚ РѕР±СЃР»СѓР¶РёРІР°С‚СЊСЃСЏ. РўРѕР»СЊРєРѕ API endpoints РґРѕСЃС‚СѓРїРЅС‹.")

class AnalyzeRequest(BaseModel):
    username: str

class AnalysisResult(BaseModel):
    themes: List[str]
    styles: List[str]
    analyzed_posts_sample: List[str]
    best_posting_time: str # РџРѕРєР° СЃС‚СЂРѕРєР°
    analyzed_posts_count: int
    
# Р”РѕР±Р°РІР»СЏРµРј РїСЂРѕРїСѓС‰РµРЅРЅРѕРµ РѕРїСЂРµРґРµР»РµРЅРёРµ РєР»Р°СЃСЃР° AnalyzeResponse
class AnalyzeResponse(BaseModel):
    themes: List[str]
    styles: List[str]
    analyzed_posts_sample: List[str] 
    best_posting_time: str
    analyzed_posts_count: int
    message: Optional[str] = None
    error: Optional[str] = None
    
# --- Р”РћР‘РђР’Р›РЇР•Рњ РћРџР Р•Р”Р•Р›Р•РќРР• РњРћР”Р•Р›Р PlanGenerationRequest ---
class PlanGenerationRequest(BaseModel):
    themes: List[str]
    styles: List[str]
    period_days: int = Field(7, gt=0, le=30) # РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ 7 РґРЅРµР№, СЃ РѕРіСЂР°РЅРёС‡РµРЅРёСЏРјРё
    channel_name: str # Р”РѕР±Р°РІР»СЏРµРј РѕР±СЏР·Р°С‚РµР»СЊРЅРѕРµ РёРјСЏ РєР°РЅР°Р»Р°

# РњРѕРґРµР»СЊ РґР»СЏ РѕРґРЅРѕРіРѕ СЌР»РµРјРµРЅС‚Р° РїР»Р°РЅР° (РґР»СЏ СЃС‚СЂСѓРєС‚СѓСЂРёСЂРѕРІР°РЅРЅРѕРіРѕ РѕС‚РІРµС‚Р°)
class PlanItem(BaseModel):
    day: int # Р”РµРЅСЊ РѕС‚ РЅР°С‡Р°Р»Р° РїРµСЂРёРѕРґР° (1, 2, ...)
    topic_idea: str # РџСЂРµРґР»РѕР¶РµРЅРЅР°СЏ С‚РµРјР°/РёРґРµСЏ РїРѕСЃС‚Р°
    format_style: str # РџСЂРµРґР»РѕР¶РµРЅРЅС‹Р№ С„РѕСЂРјР°С‚/СЃС‚РёР»СЊ

# --- РќРћР’Р«Р• РњРћР”Р•Р›Р РґР»СЏ РґРµС‚Р°Р»РёР·Р°С†РёРё РїРѕСЃС‚Р° --- 
class GeneratePostDetailsRequest(BaseModel):
    topic_idea: str = Field(..., description="РРґРµСЏ РїРѕСЃС‚Р° РёР· РїР»Р°РЅР°")
    format_style: str = Field(..., description="Р¤РѕСЂРјР°С‚/СЃС‚РёР»СЊ РїРѕСЃС‚Р° РёР· РїР»Р°РЅР°")
    keywords: Optional[List[str]] = Field(None, description="(РћРїС†РёРѕРЅР°Р»СЊРЅРѕ) РљР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР° РґР»СЏ РїРѕРёСЃРєР° РёР·РѕР±СЂР°Р¶РµРЅРёР№ Рё СѓС‚РѕС‡РЅРµРЅРёСЏ С‚РµРєСЃС‚Р°") 
    post_samples: Optional[List[str]] = Field(None, description="РџСЂРёРјРµСЂС‹ РїРѕСЃС‚РѕРІ РєР°РЅР°Р»Р° РґР»СЏ РёРјРёС‚Р°С†РёРё СЃС‚РёР»СЏ")

# --- РћР‘Р©РР™ РўРРџ РґР»СЏ РЅР°Р№РґРµРЅРЅРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ --- 
class FoundImage(BaseModel):
    id: str
    source: str # РСЃС‚РѕС‡РЅРёРє (unsplash, pexels, openverse)
    preview_url: str # URL РјРёРЅРёР°С‚СЋСЂС‹
    regular_url: str # URL РѕСЃРЅРѕРІРЅРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
    description: Optional[str] = None
    author_name: Optional[str] = None
    author_url: Optional[str] = None

# --- РћРїСЂРµРґРµР»РµРЅРёРµ PostImage РџР•Р Р•Р” РµРіРѕ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёРµРј --- 
class PostImage(BaseModel):
    url: str
    id: Optional[str] = None
    preview_url: Optional[str] = None
    alt: Optional[str] = None
    author: Optional[str] = None # РЎРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚ author_name РІ Р‘Р”
    author_url: Optional[str] = None
    source: Optional[str] = None

# --- РњРѕРґРµР»СЊ РѕС‚РІРµС‚Р° РґР»СЏ РґРµС‚Р°Р»РёР·Р°С†РёРё РїРѕСЃС‚Р° --- 
class PostDetailsResponse(BaseModel):
    generated_text: str = Field(..., description="РЎРіРµРЅРµСЂРёСЂРѕРІР°РЅРЅС‹Р№ С‚РµРєСЃС‚ РїРѕСЃС‚Р°")
    found_images: List[FoundImage] = Field([], description="РЎРїРёСЃРѕРє РЅР°Р№РґРµРЅРЅС‹С… РёР·РѕР±СЂР°Р¶РµРЅРёР№ РёР· СЂР°Р·РЅС‹С… РёСЃС‚РѕС‡РЅРёРєРѕРІ") 
    message: str = Field("", description="Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅРѕРµ СЃРѕРѕР±С‰РµРЅРёРµ")
    channel_name: Optional[str] = Field(None, description="РРјСЏ РєР°РЅР°Р»Р°, Рє РєРѕС‚РѕСЂРѕРјСѓ РѕС‚РЅРѕСЃРёС‚СЃСЏ РїРѕСЃС‚")
    # РўРµРїРµСЂСЊ PostImage РѕРїСЂРµРґРµР»РµРЅ РІС‹С€Рµ
    selected_image_data: Optional[PostImage] = Field(None, description="Р”Р°РЅРЅС‹Рµ РІС‹Р±СЂР°РЅРЅРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ")

# --- РњРѕРґРµР»СЊ РґР»СЏ РЎРћР—Р”РђРќРРЇ/РћР‘РќРћР’Р›Р•РќРРЇ РїРѕСЃС‚Р° --- 
class PostData(BaseModel):
    target_date: str = Field(..., description="Р”Р°С‚Р° РїРѕСЃС‚Р° YYYY-MM-DD")
    topic_idea: str
    format_style: str
    final_text: str
    image_url: Optional[str] = Field(None, description="URL РёР·РѕР±СЂР°Р¶РµРЅРёСЏ (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)") # РћСЃС‚Р°РІР»СЏРµРј РґР»СЏ СЃС‚Р°СЂС‹С… РІРµСЂСЃРёР№? РњРѕР¶РЅРѕ СѓРґР°Р»РёС‚СЊ РїРѕР·Р¶Рµ.
    images_ids: Optional[List[str]] = Field(None, description="РЎРїРёСЃРѕРє ID РёР·РѕР±СЂР°Р¶РµРЅРёР№ (СѓСЃС‚Р°СЂРµР»Рѕ)") # РџРѕРјРµС‡Р°РµРј РєР°Рє СѓСЃС‚Р°СЂРµРІС€РµРµ
    channel_name: Optional[str] = Field(None, description="РРјСЏ РєР°РЅР°Р»Р°, Рє РєРѕС‚РѕСЂРѕРјСѓ РѕС‚РЅРѕСЃРёС‚СЃСЏ РїРѕСЃС‚")
    # PostImage РѕРїСЂРµРґРµР»РµРЅ РІС‹С€Рµ
    selected_image_data: Optional[PostImage] = Field(None, description="Р”Р°РЅРЅС‹Рµ РІС‹Р±СЂР°РЅРЅРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ")

# --- РњРѕРґРµР»СЊ РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРЅРѕРіРѕ РїРѕСЃС‚Р° (РґР»СЏ РѕС‚РІРµС‚Р° GET /posts) --- 
class SavedPostResponse(PostData):
    id: str 
    # РЈР±РёСЂР°РµРј РґСѓР±Р»РёСЂСѓСЋС‰РёРµ РїРѕР»СЏ РёР· PostData
    # created_at: str 
    # updated_at: str
    # image_url: Optional[str] = Field(None, description="URL РёР·РѕР±СЂР°Р¶РµРЅРёСЏ (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)")
    # images_ids: Optional[List[str]] = Field(None, description="РЎРїРёСЃРѕРє ID РёР·РѕР±СЂР°Р¶РµРЅРёР№")
    # channel_name: Optional[str] = Field(None, description="РРјСЏ РєР°РЅР°Р»Р°, Рє РєРѕС‚РѕСЂРѕРјСѓ РѕС‚РЅРѕСЃРёС‚СЃСЏ РїРѕСЃС‚")
    # Р”РѕР±Р°РІР»СЏРµРј РїРѕР»СЏ, СЃРїРµС†РёС„РёС‡РЅС‹Рµ РґР»СЏ РѕС‚РІРµС‚Р°
    created_at: str = Field(..., description="Р’СЂРµРјСЏ СЃРѕР·РґР°РЅРёСЏ РїРѕСЃС‚Р°")
    updated_at: str = Field(..., description="Р’СЂРµРјСЏ РїРѕСЃР»РµРґРЅРµРіРѕ РѕР±РЅРѕРІР»РµРЅРёСЏ РїРѕСЃС‚Р°")

# --- Р¤СѓРЅРєС†РёСЏ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РїРѕСЃС‚РѕРІ Telegram С‡РµСЂРµР· HTTP РїР°СЂСЃРёРЅРі ---
async def get_telegram_posts_via_http(username: str) -> List[str]:
    """РџРѕР»СѓС‡РµРЅРёРµ РїРѕСЃС‚РѕРІ РєР°РЅР°Р»Р° Telegram С‡РµСЂРµР· HTTP РїР°СЂСЃРёРЅРі."""
    try:
        url = f"https://t.me/s/{username}"
        logger.info(f"Р—Р°РїСЂРѕСЃ HTTP РїР°СЂСЃРёРЅРіР° РґР»СЏ РєР°РЅР°Р»Р° @{username}: {url}")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            
        if response.status_code != 200:
            logger.warning(f"HTTP СЃС‚Р°С‚СѓСЃ-РєРѕРґ РґР»СЏ @{username}: {response.status_code}")
            return []
            
        # РСЃРїРѕР»СЊР·СѓРµРј BeautifulSoup РґР»СЏ РїР°СЂСЃРёРЅРіР° HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # РС‰РµРј Р±Р»РѕРєРё СЃ СЃРѕРѕР±С‰РµРЅРёСЏРјРё
        message_blocks = soup.select('div.tgme_widget_message_bubble')
        
        if not message_blocks:
            logger.warning(f"РќРµ РЅР°Р№РґРµРЅС‹ Р±Р»РѕРєРё СЃРѕРѕР±С‰РµРЅРёР№ РґР»СЏ @{username}")
            return []
            
        # РР·РІР»РµРєР°РµРј С‚РµРєСЃС‚ СЃРѕРѕР±С‰РµРЅРёР№
        posts = []
        for block in message_blocks:
            text_block = block.select_one('div.tgme_widget_message_text')
            if text_block and text_block.text.strip():
                posts.append(text_block.text.strip())
        
        logger.info(f"РќР°Р№РґРµРЅРѕ {len(posts)} РїРѕСЃС‚РѕРІ С‡РµСЂРµР· HTTP РїР°СЂСЃРёРЅРі РґР»СЏ @{username}")
        return posts
        
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё HTTP РїР°СЂСЃРёРЅРіРµ РєР°РЅР°Р»Р° @{username}: {e}")
        raise

# --- Р¤СѓРЅРєС†РёСЏ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РїСЂРёРјРµСЂРѕРІ РїРѕСЃС‚РѕРІ ---
def get_sample_posts(channel_name: str) -> List[str]:
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ РїСЂРёРјРµСЂ РїРѕСЃС‚РѕРІ РґР»СЏ РґРµРјРѕРЅСЃС‚СЂР°С†РёРё РІ СЃР»СѓС‡Р°Рµ, РµСЃР»Рё РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ СЂРµР°Р»СЊРЅС‹Рµ РїРѕСЃС‚С‹."""
    # Р‘Р°Р·РѕРІС‹Рµ РїСЂРёРјРµСЂС‹ РїРѕСЃС‚РѕРІ
    generic_posts = [
        "Р”РѕР±СЂС‹Р№ РґРµРЅСЊ, СѓРІР°Р¶Р°РµРјС‹Рµ РїРѕРґРїРёСЃС‡РёРєРё! РЎРµРіРѕРґРЅСЏ РјС‹ РѕР±СЃСѓРґРёРј РІР°Р¶РЅСѓСЋ С‚РµРјСѓ, РєРѕС‚РѕСЂР°СЏ РєР°СЃР°РµС‚СЃСЏ РєР°Р¶РґРѕРіРѕ.",
        "РџСЂРµРґСЃС‚Р°РІР»СЏРµРј РІР°Рј РЅРѕРІС‹Р№ РѕР±Р·РѕСЂ Р°РєС‚СѓР°Р»СЊРЅС‹С… СЃРѕР±С‹С‚РёР№. РћСЃС‚Р°РІР»СЏР№С‚Рµ СЃРІРѕРё РєРѕРјРјРµРЅС‚Р°СЂРёРё Рё РґРµР»РёС‚РµСЃСЊ РјРЅРµРЅРёРµРј.",
        "РРЅС‚РµСЂРµСЃРЅС‹Р№ С„Р°РєС‚: Р·РЅР°РµС‚Рµ Р»Рё РІС‹, С‡С‚Рѕ СЃС‚Р°С‚РёСЃС‚РёРєР° РїРѕРєР°Р·С‹РІР°РµС‚, С‡С‚Рѕ 90% Р»СЋРґРµР№...",
        "Р’ СЌС‚РѕРј РїРѕСЃС‚Рµ РјС‹ СЂР°Р·Р±РµСЂРµРј СЃР°РјС‹Рµ РїРѕРїСѓР»СЏСЂРЅС‹Рµ РІРѕРїСЂРѕСЃС‹ РѕС‚ РЅР°С€РёС… РїРѕРґРїРёСЃС‡РёРєРѕРІ.",
        "РџРѕРґРІРѕРґРёРј РёС‚РѕРіРё РЅРµРґРµР»Рё: С‡С‚Рѕ РІР°Р¶РЅРѕРіРѕ РїСЂРѕРёР·РѕС€Р»Рѕ Рё С‡С‚Рѕ РЅР°СЃ Р¶РґРµС‚ РІРїРµСЂРµРґРё."
    ]
    
    # РњРѕР¶РЅРѕ РґРѕР±Р°РІРёС‚СЊ СЃРїРµС†РёС„РёС‡РЅС‹Рµ РїСЂРёРјРµСЂС‹ РґР»СЏ СЂР°Р·РЅС‹С… РєР°РЅР°Р»РѕРІ
    tech_posts = [
        "РќРѕРІС‹Р№ iPhone СѓР¶Рµ РІ РїСЂРѕРґР°Р¶Рµ. РџРµСЂРІС‹Рµ РІРїРµС‡Р°С‚Р»РµРЅРёСЏ Рё РѕР±Р·РѕСЂ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРє.",
        "РћР±Р·РѕСЂ РїРѕСЃР»РµРґРЅРёС… РёР·РјРµРЅРµРЅРёР№ РІ Android. Р§С‚Рѕ РЅР°СЃ Р¶РґРµС‚ РІ РЅРѕРІРѕР№ РІРµСЂСЃРёРё?",
        "РР Рё РµРіРѕ РІР»РёСЏРЅРёРµ РЅР° СЃРѕРІСЂРµРјРµРЅРЅРѕРµ РїСЂРѕРіСЂР°РјРјРёСЂРѕРІР°РЅРёРµ: РїРѕР»РµР·РЅС‹Рµ РёРЅСЃС‚СЂСѓРјРµРЅС‚С‹ РґР»СЏ СЂР°Р·СЂР°Р±РѕС‚С‡РёРєРѕРІ.",
        "РљР°РєРѕР№ СЏР·С‹Рє РїСЂРѕРіСЂР°РјРјРёСЂРѕРІР°РЅРёСЏ РІС‹Р±СЂР°С‚СЊ РІ 2024 РіРѕРґСѓ? РћР±Р·РѕСЂ РїРѕРїСѓР»СЏСЂРЅС‹С… С‚РµС…РЅРѕР»РѕРіРёР№.",
        "РќРѕРІС‹Рµ РёРЅСЃС‚СЂСѓРјРµРЅС‚С‹ РґР»СЏ РІРµР±-СЂР°Р·СЂР°Р±РѕС‚РєРё, РєРѕС‚РѕСЂС‹Рµ СЃС‚РѕРёС‚ РїРѕРїСЂРѕР±РѕРІР°С‚СЊ РєР°Р¶РґРѕРјСѓ."
    ]
    
    business_posts = [
        "5 СЃС‚СЂР°С‚РµРіРёР№, РєРѕС‚РѕСЂС‹Рµ РїРѕРјРѕРіСѓС‚ РІР°С€РµРјСѓ Р±РёР·РЅРµСЃСѓ РІС‹Р№С‚Рё РЅР° РЅРѕРІС‹Р№ СѓСЂРѕРІРµРЅСЊ.",
        "РљР°Рє РїСЂР°РІРёР»СЊРЅРѕ РёРЅРІРµСЃС‚РёСЂРѕРІР°С‚СЊ РІ 2024 РіРѕРґСѓ? РЎРѕРІРµС‚С‹ СЌРєСЃРїРµСЂС‚РѕРІ.",
        "РўР°Р№Рј-РјРµРЅРµРґР¶РјРµРЅС‚ РґР»СЏ СЂСѓРєРѕРІРѕРґРёС‚РµР»СЏ: РєР°Рє РІСЃРµ СѓСЃРїРµРІР°С‚СЊ Рё РЅРµ РІС‹РіРѕСЂР°С‚СЊ.",
        "РђРЅР°Р»РёР· СЂС‹РЅРєР°: РіР»Р°РІРЅС‹Рµ С‚СЂРµРЅРґС‹ Рё РїСЂРѕРіРЅРѕР·С‹ РЅР° Р±Р»РёР¶Р°Р№С€РµРµ Р±СѓРґСѓС‰РµРµ.",
        "РСЃС‚РѕСЂРёСЏ СѓСЃРїРµС…Р°: РєР°Рє РЅРµР±РѕР»СЊС€РѕР№ СЃС‚Р°СЂС‚Р°Рї РїСЂРµРІСЂР°С‚РёР»СЃСЏ РІ РјРёР»Р»РёРѕРЅРЅС‹Р№ Р±РёР·РЅРµСЃ."
    ]
    
    # Р’С‹Р±РёСЂР°РµРј РїРѕРґС…РѕРґСЏС‰РёР№ РЅР°Р±РѕСЂ РїСЂРёРјРµСЂРѕРІ РІ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё РѕС‚ РёРјРµРЅРё РєР°РЅР°Р»Р°
    channel_lower = channel_name.lower()
    if any(keyword in channel_lower for keyword in ["tech", "code", "programming", "dev", "it"]):
        return tech_posts
    elif any(keyword in channel_lower for keyword in ["business", "finance", "money", "startup"]):
        return business_posts
    else:
        return generic_posts

# --- Р¤СѓРЅРєС†РёСЏ РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ Р°РЅР°Р»РёР·Р° РІ Р±Р°Р·Сѓ РґР°РЅРЅС‹С… ---
async def save_suggested_idea(idea_data: Dict[str, Any]) -> str:
    """РЎРѕС…СЂР°РЅСЏРµС‚ РїСЂРµРґР»РѕР¶РµРЅРЅСѓСЋ РёРґРµСЋ РІ Р±Р°Р·Сѓ РґР°РЅРЅС‹С…."""
    try:
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            return "РћС€РёР±РєР°: РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ"
        
        # РџРѕРґРіРѕС‚Р°РІР»РёРІР°РµРј РґР°РЅРЅС‹Рµ РІ СЃРѕРѕС‚РІРµС‚СЃС‚РІРёРё СЃРѕ СЃС‚СЂСѓРєС‚СѓСЂРѕР№ С‚Р°Р±Р»РёС†С‹ suggested_ideas
        idea_to_save = {
            "id": str(uuid.uuid4()),  # Р“РµРЅРµСЂРёСЂСѓРµРј UUID
            "channel_name": idea_data.get("channel_name", ""),
            "user_id": idea_data.get("user_id"),
            "topic_idea": idea_data.get("topic_idea", ""),
            "format_style": idea_data.get("format_style", ""),
            "relative_day": idea_data.get("day", 0),
            "is_detailed": False  # РР·РЅР°С‡Р°Р»СЊРЅРѕ РёРґРµСЏ РЅРµ РґРµС‚Р°Р»РёР·РёСЂРѕРІР°РЅР°
        }
        
        # РЎРѕС…СЂР°РЅРµРЅРёРµ РІ Supabase
        result = supabase.table("suggested_ideas").insert(idea_to_save).execute()
        
        # РџСЂРѕРІРµСЂРєР° СЂРµР·СѓР»СЊС‚Р°С‚Р°
        if hasattr(result, 'data') and len(result.data) > 0:
            logger.info(f"РЈСЃРїРµС€РЅРѕ СЃРѕС…СЂР°РЅРµРЅР° РёРґРµСЏ РґР»СЏ РєР°РЅР°Р»Р° {idea_data.get('channel_name')}")
            return "success"
        else:
            logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РёРґРµРё: {result}")
            return "error"
            
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РёРґРµРё: {e}")
        return f"РћС€РёР±РєР°: {str(e)}"

# --- Р¤СѓРЅРєС†РёСЏ РґР»СЏ Р°РЅР°Р»РёР·Р° РєРѕРЅС‚РµРЅС‚Р° СЃ РїРѕРјРѕС‰СЊСЋ DeepSeek ---
async def analyze_content_with_deepseek(texts: List[str], api_key: str) -> Dict[str, List[str]]:
    """РђРЅР°Р»РёР· РєРѕРЅС‚РµРЅС‚Р° СЃ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёРµРј РјРѕРґРµР»Рё DeepSeek С‡РµСЂРµР· OpenRouter API."""
    
    # РџСЂРѕРІРµСЂСЏРµРј РЅР°Р»РёС‡РёРµ API РєР»СЋС‡Р°
    if not api_key:
        logger.warning("РђРЅР°Р»РёР· РєРѕРЅС‚РµРЅС‚Р° СЃ DeepSeek РЅРµРІРѕР·РјРѕР¶РµРЅ: РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ OPENROUTER_API_KEY")
        return {
            "themes": ["РўРµРјР° 1", "РўРµРјР° 2", "РўРµРјР° 3", "РўРµРјР° 4", "РўРµРјР° 5"],
            "styles": ["Р¤РѕСЂРјР°С‚ 1", "Р¤РѕСЂРјР°С‚ 2", "Р¤РѕСЂРјР°С‚ 3", "Р¤РѕСЂРјР°С‚ 4", "Р¤РѕСЂРјР°С‚ 5"]
        }
    
    # Р•СЃР»Рё РЅРµС‚ С‚РµРєСЃС‚РѕРІ РёР»Рё API РєР»СЋС‡Р°, РІРѕР·РІСЂР°С‰Р°РµРј РїСѓСЃС‚РѕР№ СЂРµР·СѓР»СЊС‚Р°С‚
    if not texts or not api_key:
        logger.error("РћС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ С‚РµРєСЃС‚С‹ РёР»Рё API РєР»СЋС‡ РґР»СЏ Р°РЅР°Р»РёР·Р°")
        return {"themes": [], "styles": []}
    
    # РћР±СЉРµРґРёРЅСЏРµРј С‚РµРєСЃС‚С‹ РґР»СЏ Р°РЅР°Р»РёР·Р°
    combined_text = "\n\n".join([f"РџРѕСЃС‚ {i+1}: {text}" for i, text in enumerate(texts)])
    logger.info(f"РџРѕРґРіРѕС‚РѕРІР»РµРЅРѕ {len(texts)} С‚РµРєСЃС‚РѕРІ РґР»СЏ Р°РЅР°Р»РёР·Р° С‡РµСЂРµР· DeepSeek")
    
    # --- РР—РњР•РќР•РќРР•: РЈС‚РѕС‡РЅРµРЅРЅС‹Рµ РїСЂРѕРјРїС‚С‹ РґР»СЏ Р°РЅР°Р»РёР·Р° --- 
    system_prompt = """РўС‹ - СЌРєСЃРїРµСЂС‚ РїРѕ Р°РЅР°Р»РёР·Сѓ РєРѕРЅС‚РµРЅС‚Р° Telegram-РєР°РЅР°Р»РѕРІ. 
РўРІРѕСЏ Р·Р°РґР°С‡Р° - РіР»СѓР±РѕРєРѕ РїСЂРѕР°РЅР°Р»РёР·РёСЂРѕРІР°С‚СЊ РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅРЅС‹Рµ РїРѕСЃС‚С‹ Рё РІС‹СЏРІРёС‚СЊ РЎРђРњР«Р• РҐРђР РђРљРўР•Р РќР«Р•, Р”РћРњРРќРР РЈР®Р©РР• С‚РµРјС‹ Рё СЃС‚РёР»Рё/С„РѕСЂРјР°С‚С‹, РѕС‚СЂР°Р¶Р°СЋС‰РёРµ РЎРЈРўР¬ Рё РЈРќРРљРђР›Р¬РќРћРЎРўР¬ РєР°РЅР°Р»Р°. 
РР·Р±РµРіР°Р№ СЃР»РёС€РєРѕРј РѕР±С‰РёС… С„РѕСЂРјСѓР»РёСЂРѕРІРѕРє, РµСЃР»Рё РѕРЅРё РЅРµ СЏРІР»СЏСЋС‚СЃСЏ РєР»СЋС‡РµРІС‹РјРё. РЎРѕСЃСЂРµРґРѕС‚РѕС‡СЊСЃСЏ РЅР° РєР°С‡РµСЃС‚РІРµ, Р° РЅРµ РЅР° РєРѕР»РёС‡РµСЃС‚РІРµ.

Р’С‹РґР°Р№ СЂРµР·СѓР»СЊС‚Р°С‚ РЎРўР РћР“Рћ РІ С„РѕСЂРјР°С‚Рµ JSON СЃ РґРІСѓРјСЏ РєР»СЋС‡Р°РјРё: "themes" Рё "styles". РљР°Р¶РґС‹Р№ РєР»СЋС‡ РґРѕР»Р¶РµРЅ СЃРѕРґРµСЂР¶Р°С‚СЊ РјР°СЃСЃРёРІ РёР· 3-5 РЅР°РёР±РѕР»РµРµ Р Р•Р›Р•Р’РђРќРўРќР«РҐ СЃС‚СЂРѕРє."""
    
    user_prompt = f"""РџСЂРѕР°РЅР°Р»РёР·РёСЂСѓР№ РЎРўР РћР“Рћ СЃР»РµРґСѓСЋС‰РёРµ РїРѕСЃС‚С‹ РёР· Telegram-РєР°РЅР°Р»Р°:
{combined_text}

РћРїСЂРµРґРµР»Рё 3-5 РЎРђРњР«РҐ РҐРђР РђРљРўР•Р РќР«РҐ С‚РµРј Рё 3-5 РЎРђРњР«РҐ Р РђРЎРџР РћРЎРўР РђРќР•РќРќР«РҐ СЃС‚РёР»РµР№/С„РѕСЂРјР°С‚РѕРІ РїРѕРґР°С‡Рё РєРѕРЅС‚РµРЅС‚Р°, РєРѕС‚РѕСЂС‹Рµ РЅР°РёР»СѓС‡С€РёРј РѕР±СЂР°Р·РѕРј РѕС‚СЂР°Р¶Р°СЋС‚ СЃРїРµС†РёС„РёРєСѓ РРњР•РќРќРћ Р­РўРћР“Рћ РєР°РЅР°Р»Р°. 
РћСЃРЅРѕРІС‹РІР°Р№СЃСЏ РўРћР›Р¬РљРћ РЅР° РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅРЅС‹С… С‚РµРєСЃС‚Р°С…. 

РџСЂРµРґСЃС‚Р°РІСЊ СЂРµР·СѓР»СЊС‚Р°С‚ РўРћР›Р¬РљРћ РІ РІРёРґРµ JSON РѕР±СЉРµРєС‚Р° СЃ РєР»СЋС‡Р°РјРё "themes" Рё "styles". РќРёРєР°РєРѕРіРѕ РґСЂСѓРіРѕРіРѕ С‚РµРєСЃС‚Р°."""
    # --- РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ --- 
    
    # Р”РµР»Р°РµРј Р·Р°РїСЂРѕСЃ Рє API
    analysis_result = {"themes": [], "styles": []}
    
    try:
        # РРЅРёС†РёР°Р»РёР·РёСЂСѓРµРј РєР»РёРµРЅС‚
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        
        # Р—Р°РїСЂР°С€РёРІР°РµРј РѕС‚РІРµС‚ РѕС‚ API
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free", # <--- РР—РњР•РќР•РќРћ РќРђ РќРћР’РЈР® Р‘Р•РЎРџР›РђРўРќРЈР® РњРћР”Р•Р›Р¬
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=600,
            timeout=60,
            extra_headers={
                "HTTP-Referer": "https://content-manager.onrender.com",
                "X-Title": "Smart Content Assistant"
            }
        )
        
        # РџРѕР»СѓС‡Р°РµРј С‚РµРєСЃС‚ РѕС‚РІРµС‚Р°
        analysis_text = response.choices[0].message.content.strip()
        logger.info(f"РџРѕР»СѓС‡РµРЅ РѕС‚РІРµС‚ РѕС‚ DeepSeek: {analysis_text[:100]}...")
        
        # РР·РІР»РµРєР°РµРј JSON РёР· РѕС‚РІРµС‚Р°
        json_match = re.search(r'(\{.*\})', analysis_text, re.DOTALL)
        if json_match:
            analysis_text = json_match.group(1)
        
        # РџР°СЂСЃРёРј JSON
        analysis_json = json.loads(analysis_text)
        
        # --- РР—РњР•РќР•РќРР•: РћР±СЂР°Р±РѕС‚РєР° РєР»СЋС‡РµР№ themes Рё styles/style --- 
        themes = analysis_json.get("themes", [])
        # РџС‹С‚Р°РµРјСЃСЏ РїРѕР»СѓС‡РёС‚СЊ СЃС‚РёР»Рё РїРѕ РєР»СЋС‡Сѓ "styles" РёР»Рё "style"
        styles = analysis_json.get("styles", analysis_json.get("style", [])) 
        
        if isinstance(themes, list) and isinstance(styles, list):
            analysis_result = {"themes": themes, "styles": styles}
            logger.info(f"РЈСЃРїРµС€РЅРѕ РёР·РІР»РµС‡РµРЅС‹ С‚РµРјС‹ ({len(themes)}) Рё СЃС‚РёР»Рё ({len(styles)}) РёР· JSON.")
        else:
            logger.warning(f"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ С‚РёРї РґР°РЅРЅС‹С… РґР»СЏ С‚РµРј РёР»Рё СЃС‚РёР»РµР№ РІ JSON: {analysis_json}")
            # РћСЃС‚Р°РІР»СЏРµРј analysis_result РїСѓСЃС‚С‹Рј РёР»Рё СЃР±СЂР°СЃС‹РІР°РµРј РІ РґРµС„РѕР»С‚РЅРѕРµ Р·РЅР°С‡РµРЅРёРµ
            analysis_result = {"themes": [], "styles": []}
        # --- РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ --- 
    
    except json.JSONDecodeError as e:
        # Р•СЃР»Рё РЅРµ СѓРґР°Р»РѕСЃСЊ СЂР°СЃРїР°СЂСЃРёС‚СЊ JSON, РёСЃРїРѕР»СЊР·СѓРµРј СЂРµРіСѓР»СЏСЂРЅС‹Рµ РІС‹СЂР°Р¶РµРЅРёСЏ
        logger.error(f"РћС€РёР±РєР° РїР°СЂСЃРёРЅРіР° JSON: {e}, С‚РµРєСЃС‚: {analysis_text}")
        
        themes_match = re.findall(r'"themes":\s*\[(.*?)\]', analysis_text, re.DOTALL)
        if themes_match:
            theme_items = re.findall(r'"([^"]+)"', themes_match[0])
            analysis_result["themes"] = theme_items
        
        styles_match = re.findall(r'"styles":\s*\[(.*?)\]', analysis_text, re.DOTALL)
        if styles_match:
            style_items = re.findall(r'"([^"]+)"', styles_match[0])
            analysis_result["styles"] = style_items
    
    except Exception as e:
        # РћР±СЂР°Р±Р°С‚С‹РІР°РµРј Р»СЋР±С‹Рµ РґСЂСѓРіРёРµ РѕС€РёР±РєРё
        logger.error(f"РћС€РёР±РєР° РїСЂРё Р°РЅР°Р»РёР·Рµ РєРѕРЅС‚РµРЅС‚Р° С‡РµСЂРµР· DeepSeek: {e}")
    
    return analysis_result

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_channel(request: Request, req: AnalyzeRequest):
    """РђРЅР°Р»РёР· РєР°РЅР°Р»Р° Telegram РЅР° РѕСЃРЅРѕРІРµ Р·Р°РїСЂРѕСЃР°."""
    # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if telegram_user_id:
        logger.info(f"РђРЅР°Р»РёР· РґР»СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram ID: {telegram_user_id}")
    
    # РћР±СЂР°Р±РѕС‚РєР° РёРјРµРЅРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
    username = req.username.replace("@", "").strip()
    logger.info(f"РџРѕР»СѓС‡РµРЅ Р·Р°РїСЂРѕСЃ РЅР° Р°РЅР°Р»РёР· РєР°РЅР°Р»Р° @{username}")
    
    posts = []
    errors_list = []
    error_message = None
    
    # --- РќРђР§РђР›Рћ: РџРћРџР«РўРљРђ РџРћР›РЈР§Р•РќРРЇ Р§Р•Р Р•Р— HTTP (РџР•Р Р’Р«Р™ РџР РРћР РРўР•Рў) ---
    try:
        logger.info(f"РџС‹С‚Р°РµРјСЃСЏ РїРѕР»СѓС‡РёС‚СЊ РїРѕСЃС‚С‹ РєР°РЅР°Р»Р° @{username} С‡РµСЂРµР· HTTP РїР°СЂСЃРёРЅРі")
        http_posts = await get_telegram_posts_via_http(username)
        
        if http_posts and len(http_posts) > 0:
            posts = [{"text": post} for post in http_posts]
            logger.info(f"РЈСЃРїРµС€РЅРѕ РїРѕР»СѓС‡РµРЅРѕ {len(posts)} РїРѕСЃС‚РѕРІ С‡РµСЂРµР· HTTP РїР°СЂСЃРёРЅРі")
        else:
            logger.warning(f"HTTP РїР°СЂСЃРёРЅРі РЅРµ РІРµСЂРЅСѓР» РїРѕСЃС‚РѕРІ РґР»СЏ РєР°РЅР°Р»Р° @{username}, РїСЂРѕР±СѓРµРј Telethon")
            errors_list.append("HTTP: РќРµ РїРѕР»СѓС‡РµРЅС‹ РїРѕСЃС‚С‹, РїСЂРѕР±СѓРµРј Telethon")
    except Exception as http_error:
        logger.error(f"РћС€РёР±РєР° РїСЂРё HTTP РїР°СЂСЃРёРЅРіРµ РґР»СЏ РєР°РЅР°Р»Р° @{username}: {http_error}")
        errors_list.append(f"HTTP: {str(http_error)}")
        logger.info("РџРµСЂРµРєР»СЋС‡Р°РµРјСЃСЏ РЅР° РјРµС‚РѕРґ Telethon")
    
    # --- РќРђР§РђР›Рћ: РџРћРџР«РўРљРђ РџРћР›РЈР§Р•РќРРЇ Р§Р•Р Р•Р— TELETHON (Р’РўРћР РћР™ РџР РРћР РРўР•Рў) ---
    # РўРѕР»СЊРєРѕ РµСЃР»Рё HTTP РјРµС‚РѕРґ РЅРµ РґР°Р» СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ
    if not posts:
        try:
            logger.info(f"РџС‹С‚Р°РµРјСЃСЏ РїРѕР»СѓС‡РёС‚СЊ РїРѕСЃС‚С‹ РєР°РЅР°Р»Р° @{username} С‡РµСЂРµР· Telethon")
            telethon_posts, telethon_error = get_telegram_posts(username)
            
            if telethon_error:
                logger.warning(f"РћС€РёР±РєР° Telethon РґР»СЏ РєР°РЅР°Р»Р° @{username}: {telethon_error}")
                errors_list.append(f"Telethon: {telethon_error}")
            else:
                # Р•СЃР»Рё Telethon СѓСЃРїРµС€РЅРѕ РїРѕР»СѓС‡РёР» РїРѕСЃС‚С‹
                posts = telethon_posts
                logger.info(f"РЈСЃРїРµС€РЅРѕ РїРѕР»СѓС‡РµРЅРѕ {len(posts)} РїРѕСЃС‚РѕРІ С‡РµСЂРµР· Telethon")
        except Exception as e:
            logger.error(f"РќРµРїСЂРµРґРІРёРґРµРЅРЅР°СЏ РѕС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РїРѕСЃС‚РѕРІ РєР°РЅР°Р»Р° @{username} С‡РµСЂРµР· Telethon: {e}")
            errors_list.append(f"РћС€РёР±РєР° Telethon: {str(e)}")
    
    # --- РќРђР§РђР›Рћ: РРЎРџРћР›Р¬Р—РЈР•Рњ РџР РРњР•Р Р« РљРђРљ РџРћРЎР›Р•Р”РќРР™ Р’РђР РРђРќРў ---
    # Р•СЃР»Рё РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ РїРѕСЃС‚С‹ РЅРё С‡РµСЂРµР· HTTP, РЅРё С‡РµСЂРµР· Telethon
    sample_data_used = False
    if not posts:
        logger.warning(f"РСЃРїРѕР»СЊР·СѓРµРј РїСЂРёРјРµСЂС‹ РїРѕСЃС‚РѕРІ РґР»СЏ РєР°РЅР°Р»Р° {username}")
        sample_posts = get_sample_posts(username)
        posts = [{"text": post} for post in sample_posts]
        error_message = "РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ СЂРµР°Р»СЊРЅС‹Рµ РїРѕСЃС‚С‹. РСЃРїРѕР»СЊР·СѓСЋС‚СЃСЏ РїСЂРёРјРµСЂС‹ РґР»СЏ РґРµРјРѕРЅСЃС‚СЂР°С†РёРё."
        errors_list.append(error_message)
        sample_data_used = True
        logger.info(f"РСЃРїРѕР»СЊР·СѓРµРј РїСЂРёРјРµСЂС‹ РїРѕСЃС‚РѕРІ РґР»СЏ РєР°РЅР°Р»Р° {username}")
    
    # РћРіСЂР°РЅРёС‡РёРІР°РµРј Р°РЅР°Р»РёР· РїРµСЂРІС‹РјРё 20 РїРѕСЃС‚Р°РјРё
    posts = posts[:20]
    logger.info(f"РђРЅР°Р»РёР·РёСЂСѓРµРј {len(posts)} РїРѕСЃС‚РѕРІ")
    
    # РђРЅР°Р»РёР· РєРѕРЅС‚РµРЅС‚Р°
    themes = []
    styles = []
    sample_posts = []
    
    try:
        # РџРѕРґРіРѕС‚РѕРІРєР° СЃРїРёСЃРєР° С‚РµРєСЃС‚РѕРІ РґР»СЏ Р°РЅР°Р»РёР·Р°
        texts = [post.get("text", "") for post in posts if post.get("text")]
        
        # РђРЅР°Р»РёР· С‡РµСЂРµР· deepseek
        analysis_result = await analyze_content_with_deepseek(texts, OPENROUTER_API_KEY)
        
        # РР·РІР»РµРєР°РµРј СЂРµР·СѓР»СЊС‚Р°С‚С‹ РёР· РІРѕР·РІСЂР°С‰Р°РµРјРѕРіРѕ СЃР»РѕРІР°СЂСЏ
        themes = analysis_result.get("themes", [])
        styles = analysis_result.get("styles", [])
        
        # РЎРѕС…СЂР°РЅРµРЅРёРµ СЂРµР·СѓР»СЊС‚Р°С‚Р° Р°РЅР°Р»РёР·Р° РІ Р±Р°Р·Рµ РґР°РЅРЅС‹С… (РµСЃР»Рё РµСЃС‚СЊ telegram_user_id)
        if telegram_user_id and supabase:
            try:
                # РџРµСЂРµРґ СЃРѕС…СЂР°РЅРµРЅРёРµРј СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ Р°РЅР°Р»РёР·Р° РІС‹Р·С‹РІР°РµРј С„СѓРЅРєС†РёСЋ РёСЃРїСЂР°РІР»РµРЅРёСЏ СЃС…РµРјС‹
                try:
                    logger.info("Р’С‹Р·РѕРІ С„СѓРЅРєС†РёРё fix_schema РїРµСЂРµРґ СЃРѕС…СЂР°РЅРµРЅРёРµРј СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ Р°РЅР°Р»РёР·Р°")
                    schema_fix_result = await fix_schema()
                    logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ РёСЃРїСЂР°РІР»РµРЅРёСЏ СЃС…РµРјС‹: {schema_fix_result}")
                except Exception as schema_error:
                    logger.warning(f"РћС€РёР±РєР° РїСЂРё РёСЃРїСЂР°РІР»РµРЅРёРё СЃС…РµРјС‹: {schema_error}")
                
                # РџСЂРѕРІРµСЂСЏРµРј, СЃСѓС‰РµСЃС‚РІСѓРµС‚ Р»Рё СѓР¶Рµ Р·Р°РїРёСЃСЊ РґР»СЏ СЌС‚РѕРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Рё РєР°РЅР°Р»Р°
                analysis_check = supabase.table("channel_analysis").select("id").eq("user_id", telegram_user_id).eq("channel_name", username).execute()
                
                # РџРѕР»СѓС‡РµРЅРёРµ С‚РµРєСѓС‰РµР№ РґР°С‚С‹-РІСЂРµРјРµРЅРё РІ ISO С„РѕСЂРјР°С‚Рµ РґР»СЏ updated_at
                current_datetime = datetime.now().isoformat()
                
                # РЎРѕР·РґР°РµРј СЃР»РѕРІР°СЂСЊ СЃ РґР°РЅРЅС‹РјРё Р°РЅР°Р»РёР·Р°
                analysis_data = {
                    "user_id": int(telegram_user_id),  # РЈР±РµРґРёРјСЃСЏ, С‡С‚Рѕ user_id - С†РµР»РѕРµ С‡РёСЃР»Рѕ
                    "channel_name": username,
                    "themes": themes,
                    "styles": styles,
                    "analyzed_posts_count": len(posts),
                    "sample_posts": sample_posts[:5] if len(sample_posts) > 5 else sample_posts,
                    "best_posting_time": "18:00 - 20:00 РњРЎРљ",  # Р’СЂРµРјРµРЅРЅР°СЏ Р·Р°РіР»СѓС€РєР°
                    "is_sample_data": sample_data_used,
                    "updated_at": current_datetime
                }
                
                # РџРѕРїСЂРѕР±СѓРµРј РїСЂСЏРјРѕР№ SQL Р·Р°РїСЂРѕСЃ РґР»СЏ РІСЃС‚Р°РІРєРё/РѕР±РЅРѕРІР»РµРЅРёСЏ РґР°РЅРЅС‹С…, РµСЃР»Рё РѕР±С‹С‡РЅС‹Р№ РјРµС‚РѕРґ РЅРµ СЃСЂР°Р±РѕС‚Р°РµС‚
                try:
                    # Р•СЃР»Рё Р·Р°РїРёСЃСЊ СЃСѓС‰РµСЃС‚РІСѓРµС‚, РѕР±РЅРѕРІР»СЏРµРј РµРµ, РёРЅР°С‡Рµ СЃРѕР·РґР°РµРј РЅРѕРІСѓСЋ
                    if hasattr(analysis_check, 'data') and len(analysis_check.data) > 0:
                        # РћР±РЅРѕРІР»СЏРµРј СЃСѓС‰РµСЃС‚РІСѓСЋС‰СѓСЋ Р·Р°РїРёСЃСЊ
                        result = supabase.table("channel_analysis").update(analysis_data).eq("user_id", telegram_user_id).eq("channel_name", username).execute()
                        logger.info(f"РћР±РЅРѕРІР»РµРЅ СЂРµР·СѓР»СЊС‚Р°С‚ Р°РЅР°Р»РёР·Р° РґР»СЏ РєР°РЅР°Р»Р° @{username} РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {telegram_user_id}")
                    else:
                        # РЎРѕР·РґР°РµРј РЅРѕРІСѓСЋ Р·Р°РїРёСЃСЊ
                        result = supabase.table("channel_analysis").insert(analysis_data).execute()
                        logger.info(f"РЎРѕС…СЂР°РЅРµРЅ РЅРѕРІС‹Р№ СЂРµР·СѓР»СЊС‚Р°С‚ Р°РЅР°Р»РёР·Р° РґР»СЏ РєР°РЅР°Р»Р° @{username} РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {telegram_user_id}")
                except Exception as api_error:
                    logger.warning(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё С‡РµСЂРµР· API: {api_error}. РџСЂРѕР±СѓРµРј РїСЂСЏРјРѕР№ SQL Р·Р°РїСЂРѕСЃ.")
                    
                    # РџРѕР»СѓС‡Р°РµРј URL Рё РєР»СЋС‡ Supabase
                    supabase_url = os.getenv('SUPABASE_URL')
                    supabase_key = os.getenv('SUPABASE_ANON_KEY')
                    
                    if supabase_url and supabase_key:
                        # РџСЂСЏРјРѕР№ Р·Р°РїСЂРѕСЃ С‡РµСЂРµР· SQL
                        url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json"
                        headers = {
                            "apikey": supabase_key,
                            "Authorization": f"Bearer {supabase_key}",
                            "Content-Type": "application/json"
                        }
                        
                        # РЎРµСЂРёР°Р»РёР·СѓРµРј JSON РґР°РЅРЅС‹Рµ РґР»СЏ SQL Р·Р°РїСЂРѕСЃР°
                        themes_json = json.dumps(themes)
                        styles_json = json.dumps(styles)
                        sample_posts_json = json.dumps(sample_posts[:5] if len(sample_posts) > 5 else sample_posts)
                        
                        # SQL Р·Р°РїСЂРѕСЃ РґР»СЏ РІСЃС‚Р°РІРєРё/РѕР±РЅРѕРІР»РµРЅРёСЏ
                        sql_query = f"""
                        INSERT INTO channel_analysis 
                        (user_id, channel_name, themes, styles, analyzed_posts_count, sample_posts, best_posting_time, is_sample_data, updated_at)
                        VALUES 
                        ({telegram_user_id}, '{username}', '{themes_json}'::jsonb, '{styles_json}'::jsonb, {len(posts)}, 
                         '{sample_posts_json}'::jsonb, '18:00 - 20:00 РњРЎРљ', {sample_data_used}, '{current_datetime}')
                        ON CONFLICT (user_id, channel_name) 
                        DO UPDATE SET 
                        themes = '{themes_json}'::jsonb,
                        styles = '{styles_json}'::jsonb,
                        analyzed_posts_count = {len(posts)},
                        sample_posts = '{sample_posts_json}'::jsonb,
                        best_posting_time = '18:00 - 20:00 РњРЎРљ',
                        is_sample_data = {sample_data_used},
                        updated_at = '{current_datetime}';
                        """
                        
                        response = requests.post(url, json={"query": sql_query}, headers=headers)
                        
                        if response.status_code in [200, 204]:
                            logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ Р°РЅР°Р»РёР·Р° РґР»СЏ РєР°РЅР°Р»Р° @{username} СЃРѕС…СЂР°РЅРµРЅ С‡РµСЂРµР· РїСЂСЏРјРѕР№ SQL Р·Р°РїСЂРѕСЃ")
                        else:
                            logger.error(f"РћС€РёР±РєР° РїСЂРё РІС‹РїРѕР»РЅРµРЅРёРё РїСЂСЏРјРѕРіРѕ SQL Р·Р°РїСЂРѕСЃР°: {response.status_code} - {response.text}")
                
            except Exception as db_error:
                logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ Р°РЅР°Р»РёР·Р° РІ Р‘Р”: {db_error}")
                errors_list.append(f"РћС€РёР±РєР° Р‘Р”: {str(db_error)}")
        
        # РџРѕРґРіРѕС‚РѕРІРєР° РѕР±СЂР°Р·С†РѕРІ РїРѕСЃС‚РѕРІ РґР»СЏ РѕС‚РІРµС‚Р°
        sample_texts = [post.get("text", "") for post in posts[:5] if post.get("text")]
        sample_posts = sample_texts
        
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё Р°РЅР°Р»РёР·Рµ РєРѕРЅС‚РµРЅС‚Р°: {e}")
        # Р•СЃР»Рё РїСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР° РїСЂРё Р°РЅР°Р»РёР·Рµ, РІРѕР·РІСЂР°С‰Р°РµРј РѕС€РёР±РєСѓ 500
        raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° РїСЂРё Р°РЅР°Р»РёР·Рµ РєРѕРЅС‚РµРЅС‚Р°: {str(e)}")
    
    # Р’СЂРµРјРµРЅРЅР°СЏ Р·Р°РіР»СѓС€РєР° РґР»СЏ Р»СѓС‡С€РµРіРѕ РІСЂРµРјРµРЅРё РїРѕСЃС‚РёРЅРіР°
    best_posting_time = "18:00 - 20:00 РњРЎРљ"
    
    return AnalyzeResponse(
        themes=themes,
        styles=styles,
        analyzed_posts_sample=sample_posts,
        best_posting_time=best_posting_time,
        analyzed_posts_count=len(posts),
        message=error_message
    )

# --- РњР°СЂС€СЂСѓС‚ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ СЃРѕС…СЂР°РЅРµРЅРЅРѕРіРѕ Р°РЅР°Р»РёР·Р° РєР°РЅР°Р»Р° ---
@app.get("/channel-analysis", response_model=Dict[str, Any])
async def get_channel_analysis(request: Request, channel_name: str):
    """РџРѕР»СѓС‡РµРЅРёРµ СЃРѕС…СЂР°РЅРµРЅРЅРѕРіРѕ Р°РЅР°Р»РёР·Р° РєР°РЅР°Р»Р°."""
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            return {"error": "Р”Р»СЏ РїРѕР»СѓС‡РµРЅРёСЏ Р°РЅР°Р»РёР·Р° РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram"}
        
        if not supabase:
            return {"error": "Р‘Р°Р·Р° РґР°РЅРЅС‹С… РЅРµРґРѕСЃС‚СѓРїРЅР°"}
        
        # Р—Р°РїСЂРѕСЃ РґР°РЅРЅС‹С… РёР· Р±Р°Р·С‹
        result = supabase.table("channel_analysis").select("*").eq("user_id", telegram_user_id).eq("channel_name", channel_name).execute()
        
        # РџСЂРѕРІРµСЂРєР° СЂРµР·СѓР»СЊС‚Р°С‚Р°
        if not hasattr(result, 'data') or len(result.data) == 0:
            return {"error": f"РђРЅР°Р»РёР· РґР»СЏ РєР°РЅР°Р»Р° @{channel_name} РЅРµ РЅР°Р№РґРµРЅ"}
        
        # Р’РѕР·РІСЂР°С‰Р°РµРј РґР°РЅРЅС‹Рµ
        return result.data[0]
        
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё Р°РЅР°Р»РёР·Р° РєР°РЅР°Р»Р°: {e}")
        return {"error": str(e)}

# --- РњР°СЂС€СЂСѓС‚ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ СЃРїРёСЃРєР° РІСЃРµС… РїСЂРѕР°РЅР°Р»РёР·РёСЂРѕРІР°РЅРЅС‹С… РєР°РЅР°Р»РѕРІ ---
@app.get("/analyzed-channels", response_model=List[Dict[str, Any]])
async def get_analyzed_channels(request: Request):
    """РџРѕР»СѓС‡РµРЅРёРµ СЃРїРёСЃРєР° РІСЃРµС… РїСЂРѕР°РЅР°Р»РёР·РёСЂРѕРІР°РЅРЅС‹С… РєР°РЅР°Р»РѕРІ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ."""
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            return []
        
        if not supabase:
            return []
        
        # Р—Р°РїСЂРѕСЃ РґР°РЅРЅС‹С… РёР· Р±Р°Р·С‹
        result = supabase.table("channel_analysis").select("channel_name,updated_at").eq("user_id", telegram_user_id).order("updated_at", desc=True).execute()
        
        # РџСЂРѕРІРµСЂРєР° СЂРµР·СѓР»СЊС‚Р°С‚Р°
        if not hasattr(result, 'data'):
            return []
        
        # Р’РѕР·РІСЂР°С‰Р°РµРј РґР°РЅРЅС‹Рµ
        return result.data
        
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё СЃРїРёСЃРєР° РїСЂРѕР°РЅР°Р»РёР·РёСЂРѕРІР°РЅРЅС‹С… РєР°РЅР°Р»РѕРІ: {e}")
        return []

# --- РњРѕРґРµР»СЊ РґР»СЏ РѕС‚РІРµС‚Р° РѕС‚ /ideas ---
class SuggestedIdeasResponse(BaseModel):
    ideas: List[Dict[str, Any]] = []
    message: Optional[str] = None

# --- РњР°СЂС€СЂСѓС‚ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ СЂР°РЅРµРµ СЃРѕС…СЂР°РЅРµРЅРЅС‹С… СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ Р°РЅР°Р»РёР·Р° ---
@app.get("/ideas", response_model=SuggestedIdeasResponse)
async def get_saved_ideas(request: Request, channel_name: Optional[str] = None):
    """РџРѕР»СѓС‡РµРЅРёРµ СЂР°РЅРµРµ СЃРѕС…СЂР°РЅРµРЅРЅС‹С… СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ Р°РЅР°Р»РёР·Р°."""
    try:
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ РёРґРµР№ Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            return SuggestedIdeasResponse(
                message="Р”Р»СЏ РґРѕСЃС‚СѓРїР° Рє РёРґРµСЏРј РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram",
                ideas=[]
            )
        
        # РџСЂРµРѕР±СЂР°Р·СѓРµРј ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РІ С‡РёСЃР»Рѕ
        try:
            telegram_user_id = int(telegram_user_id)
        except (ValueError, TypeError):
            logger.error(f"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РІ Р·Р°РіРѕР»РѕРІРєРµ: {telegram_user_id}")
            return SuggestedIdeasResponse(
                message="РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ",
                ideas=[]
            )
        
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            return SuggestedIdeasResponse(
                message="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…",
                ideas=[]
            )
        
        # РЎС‚СЂРѕРёРј Р·Р°РїСЂРѕСЃ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…
        query = supabase.table("suggested_ideas").select("*").eq("user_id", telegram_user_id)
        
        # Р•СЃР»Рё СѓРєР°Р·Р°РЅРѕ РёРјСЏ РєР°РЅР°Р»Р°, С„РёР»СЊС‚СЂСѓРµРј РїРѕ РЅРµРјСѓ
        if channel_name:
            query = query.eq("channel_name", channel_name)
            
        # Р’С‹РїРѕР»РЅСЏРµРј Р·Р°РїСЂРѕСЃ
        result = query.order("created_at", desc=True).execute()
        
        # РћР±СЂР°Р±Р°С‚С‹РІР°РµРј СЂРµР·СѓР»СЊС‚Р°С‚
        if not hasattr(result, 'data'):
            logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РёРґРµР№ РёР· Р‘Р”: {result}")
            return SuggestedIdeasResponse(
                message="РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ СЃРѕС…СЂР°РЅРµРЅРЅС‹Рµ РёРґРµРё",
                ideas=[]
            )
            
        # === РР—РњР•РќР•РќРР•: РљРѕСЂСЂРµРєС‚РЅРѕРµ С„РѕСЂРјРёСЂРѕРІР°РЅРёРµ РѕС‚РІРµС‚Р° ===
        ideas = []
        for item in result.data:
            # РџСЂРѕСЃС‚Рѕ Р±РµСЂРµРј РЅСѓР¶РЅС‹Рµ РїРѕР»СЏ РЅР°РїСЂСЏРјСѓСЋ РёР· РѕС‚РІРµС‚Р° Р‘Р”
            idea = {
                "id": item.get("id"),
                "channel_name": item.get("channel_name"),
                "topic_idea": item.get("topic_idea"),  # Р‘РµСЂРµРј РЅР°РїСЂСЏРјСѓСЋ
                "format_style": item.get("format_style"),  # Р‘РµСЂРµРј РЅР°РїСЂСЏРјСѓСЋ
                "relative_day": item.get("relative_day"),
                "is_detailed": item.get("is_detailed"),
                "created_at": item.get("created_at")
                # РЈР±СЂР°РЅР° РЅРµРЅСѓР¶РЅР°СЏ РѕР±СЂР°Р±РѕС‚РєР° themes_json/styles_json
            }
            # Р”РѕР±Р°РІР»СЏРµРј С‚РѕР»СЊРєРѕ РµСЃР»Рё РµСЃС‚СЊ С‚РµРјР°
            if idea["topic_idea"]:
                ideas.append(idea)
            else:
                logger.warning(f"РџСЂРѕРїСѓС‰РµРЅР° РёРґРµСЏ Р±РµР· topic_idea: ID={idea.get('id', 'N/A')}")  # Р”РѕР±Р°РІРёР» .get РґР»СЏ Р±РµР·РѕРїР°СЃРЅРѕСЃС‚Рё
        # === РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ===
                
        logger.info(f"РџРѕР»СѓС‡РµРЅРѕ {len(ideas)} РёРґРµР№ РґР»СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {telegram_user_id}")
        return SuggestedIdeasResponse(ideas=ideas)
        
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РёРґРµР№: {e}")
        return SuggestedIdeasResponse(
            message=f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РёРґРµР№: {str(e)}",
            ideas=[]
        )

# --- РњРѕРґРµР»СЊ РѕС‚РІРµС‚Р° РґР»СЏ РіРµРЅРµСЂР°С†РёРё РїР»Р°РЅР° ---
class PlanGenerationResponse(BaseModel):
    plan: List[PlanItem] = []
    message: Optional[str] = None

# Р¤СѓРЅРєС†РёСЏ РґР»СЏ РѕС‡РёСЃС‚РєРё С‚РµРєСЃС‚Р° РѕС‚ РјР°СЂРєРµСЂРѕРІ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ
def clean_text_formatting(text):
    """РћС‡РёС‰Р°РµС‚ С‚РµРєСЃС‚ РѕС‚ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ РјР°СЂРєРґР°СѓРЅР° Рё РїСЂРѕС‡РµРіРѕ."""
    if not text:
        return ""
    
    # РЈРґР°Р»СЏРµРј Р·Р°РіРѕР»РѕРІРєРё С‚РёРїР° "### **Р”РµРЅСЊ 1**", "### **1 РґРµРЅСЊ**", "### **Р”Р•РќР¬ 1**" Рё РґСЂСѓРіРёРµ РІР°СЂРёР°С†РёРё
    text = re.sub(r'#{1,6}\s*\*?\*?(?:[Р”Рґ]РµРЅСЊ|Р”Р•РќР¬)?\s*\d+\s*(?:[Р”Рґ]РµРЅСЊ|Р”Р•РќР¬)?\*?\*?', '', text)
    
    # РЈРґР°Р»СЏРµРј С‡РёСЃР»Р° Рё СЃР»РѕРІРѕ "РґРµРЅСЊ" РІ РЅР°С‡Р°Р»Рµ СЃС‚СЂРѕРєРё (Р±РµР· СЃРёРјРІРѕР»РѕРІ #)
    text = re.sub(r'^(?:\*?\*?(?:[Р”Рґ]РµРЅСЊ|Р”Р•РќР¬)?\s*\d+\s*(?:[Р”Рґ]РµРЅСЊ|Р”Р•РќР¬)?\*?\*?)', '', text)
    
    # РЈРґР°Р»СЏРµРј СЃРёРјРІРѕР»С‹ РјР°СЂРєРґР°СѓРЅР°
    text = re.sub(r'\*\*|\*|__|_|#{1,6}', '', text)
    
    # РћС‡РёС‰Р°РµРј РЅР°С‡Р°Р»СЊРЅС‹Рµ Рё РєРѕРЅРµС‡РЅС‹Рµ РїСЂРѕР±РµР»С‹
    text = text.strip()
    
    # Р”РµР»Р°РµРј РїРµСЂРІСѓСЋ Р±СѓРєРІСѓ Р·Р°РіР»Р°РІРЅРѕР№, РµСЃР»Рё СЃС‚СЂРѕРєР° РЅРµ РїСѓСЃС‚Р°СЏ
    if text and len(text) > 0:
        text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
    
    return text

# --- РњР°СЂС€СЂСѓС‚ РґР»СЏ РіРµРЅРµСЂР°С†РёРё РїР»Р°РЅР° РїСѓР±Р»РёРєР°С†РёР№ ---
@app.post("/generate-plan", response_model=PlanGenerationResponse)
async def generate_content_plan(request: Request, req: PlanGenerationRequest):
    """Р“РµРЅРµСЂР°С†РёСЏ Рё СЃРѕС…СЂР°РЅРµРЅРёРµ РїР»Р°РЅР° РєРѕРЅС‚РµРЅС‚Р° РЅР° РѕСЃРЅРѕРІРµ С‚РµРј Рё СЃС‚РёР»РµР№."""
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ РіРµРЅРµСЂР°С†РёРё РїР»Р°РЅР° Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            return PlanGenerationResponse(
                message="Р”Р»СЏ РіРµРЅРµСЂР°С†РёРё РїР»Р°РЅР° РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram",
                plan=[]
            )
            
        themes = req.themes
        styles = req.styles
        period_days = req.period_days
        channel_name = req.channel_name
        
        if not themes or not styles:
            logger.warning(f"Р—Р°РїСЂРѕСЃ СЃ РїСѓСЃС‚С‹РјРё С‚РµРјР°РјРё РёР»Рё СЃС‚РёР»СЏРјРё: themes={themes}, styles={styles}")
            return PlanGenerationResponse(
                message="РќРµРѕР±С…РѕРґРёРјРѕ СѓРєР°Р·Р°С‚СЊ С‚РµРјС‹ Рё СЃС‚РёР»Рё РґР»СЏ РіРµРЅРµСЂР°С†РёРё РїР»Р°РЅР°",
                plan=[]
            )
            
        # РџСЂРѕРІРµСЂСЏРµРј РЅР°Р»РёС‡РёРµ API РєР»СЋС‡Р°
        if not OPENROUTER_API_KEY:
            logger.warning("Р“РµРЅРµСЂР°С†РёСЏ РїР»Р°РЅР° РЅРµРІРѕР·РјРѕР¶РЅР°: РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ OPENROUTER_API_KEY")
            # Р“РµРЅРµСЂРёСЂСѓРµРј РїСЂРѕСЃС‚РѕР№ РїР»Р°РЅ Р±РµР· РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ API
            plan_items = []
            for day in range(1, period_days + 1):
                random_theme = random.choice(themes)
                random_style = random.choice(styles)
                plan_items.append(PlanItem(
                    day=day,
                    topic_idea=f"РџРѕСЃС‚ Рѕ {random_theme}",
                    format_style=random_style
                ))
            logger.info(f"РЎРѕР·РґР°РЅ Р±Р°Р·РѕРІС‹Р№ РїР»Р°РЅ РёР· {len(plan_items)} РёРґРµР№ (Р±РµР· РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ API)")
            return PlanGenerationResponse(
                plan=plan_items,
                message="РџР»Р°РЅ СЃРіРµРЅРµСЂРёСЂРѕРІР°РЅ СЃ Р±Р°Р·РѕРІС‹РјРё РёРґРµСЏРјРё (API РЅРµРґРѕСЃС‚СѓРїРµРЅ)"
            )
            
        # --- РР—РњР•РќР•РќРР• РќРђР§РђР›Рћ: РЈС‚РѕС‡РЅРµРЅРЅС‹Рµ РїСЂРѕРјРїС‚С‹ --> Р•Р©Р• Р‘РћР›Р•Р• РЎРўР РћР“РР™ РџР РћРњРџРў ---
        system_prompt = f"""РўС‹ - РѕРїС‹С‚РЅС‹Р№ РєРѕРЅС‚РµРЅС‚-РјР°СЂРєРµС‚РѕР»РѕРі. РўРІРѕСЏ Р·Р°РґР°С‡Р° - СЃРіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ РїР»Р°РЅ РїСѓР±Р»РёРєР°С†РёР№ РґР»СЏ Telegram-РєР°РЅР°Р»Р° РЅР° {period_days} РґРЅРµР№.
РСЃРїРѕР»СЊР·СѓР№ РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅРЅС‹Рµ С‚РµРјС‹ Рё СЃС‚РёР»Рё.

РўРµРјС‹: {', '.join(themes)}
РЎС‚РёР»Рё (РёСЃРїРѕР»СЊР·СѓР№ РўРћР›Р¬РљРћ РёС…): {', '.join(styles)}

Р”Р»СЏ РљРђР–Р”РћР“Рћ РґРЅСЏ РёР· {period_days} РґРЅРµР№ РїСЂРµРґР»РѕР¶Рё РўРћР›Р¬РљРћ РћР”РќРЈ РёРґРµСЋ РїРѕСЃС‚Р° (РєРѕРЅРєСЂРµС‚РЅС‹Р№ Р·Р°РіРѕР»РѕРІРѕРє/РєРѕРЅС†РµРїС†РёСЋ) Рё РІС‹Р±РµСЂРё РўРћР›Р¬РљРћ РћР”РРќ СЃС‚РёР»СЊ РёР· СЃРїРёСЃРєР° РІС‹С€Рµ.

РЎРўР РћР“Рћ РЎР›Р•Р”РЈР™ Р¤РћР РњРђРўРЈ Р’Р«Р’РћР”Рђ:
РљР°Р¶РґР°СЏ СЃС‚СЂРѕРєР° РґРѕР»Р¶РЅР° СЃРѕРґРµСЂР¶Р°С‚СЊ С‚РѕР»СЊРєРѕ РґРµРЅСЊ, РёРґРµСЋ Рё СЃС‚РёР»СЊ, СЂР°Р·РґРµР»РµРЅРЅС‹Рµ Р”Р’РЈРњРЇ РґРІРѕРµС‚РѕС‡РёСЏРјРё (::).
РќР• Р”РћР‘РђР’Р›РЇР™ РќРРљРђРљРРҐ Р—РђР“РћР›РћР’РљРћР’, РќРћРњР•Р РћР’ Р’Р•Р РЎРР™, РЎРџРРЎРљРћР’ Р¤РР§, РљРћРњРњР•РќРўРђР РР•Р’ РР›Р Р›Р®Р‘РћР“Рћ Р”Р РЈР“РћР“Рћ Р›РРЁРќР•Р“Рћ РўР•РљРЎРўРђ.
РўРѕР»СЊРєРѕ СЃС‚СЂРѕРєРё РїР»Р°РЅР°.

РџСЂРёРјРµСЂ РќРЈР–РќРћР“Рћ С„РѕСЂРјР°С‚Р°:
Р”РµРЅСЊ 1:: Р—Р°РїСѓСЃРє РЅРѕРІРѕРіРѕ РїСЂРѕРґСѓРєС‚Р° X:: РђРЅРѕРЅСЃ
Р”РµРЅСЊ 2:: РЎРѕРІРµС‚С‹ РїРѕ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЋ Y:: Р›Р°Р№С„С…Р°Рє
Р”РµРЅСЊ 3:: РРЅС‚РµСЂРІСЊСЋ СЃ СЌРєСЃРїРµСЂС‚РѕРј Z:: РРЅС‚РµСЂРІСЊСЋ

Р¤РѕСЂРјР°С‚ РљРђР–Р”РћР™ СЃС‚СЂРѕРєРё: Р”РµРЅСЊ <РЅРѕРјРµСЂ_РґРЅСЏ>:: <РРґРµСЏ РїРѕСЃС‚Р°>:: <РЎС‚РёР»СЊ РёР· СЃРїРёСЃРєР°>"""

        user_prompt = f"""РЎРіРµРЅРµСЂРёСЂСѓР№ РїР»Р°РЅ РєРѕРЅС‚РµРЅС‚Р° РґР»СЏ Telegram-РєР°РЅР°Р»Р° \"{channel_name}\" РЅР° {period_days} РґРЅРµР№.
РўРµРјС‹: {', '.join(themes)}
РЎС‚РёР»Рё (РёСЃРїРѕР»СЊР·СѓР№ РўРћР›Р¬РљРћ РёС…): {', '.join(styles)}

Р’С‹РґР°Р№ СЂРѕРІРЅРѕ {period_days} СЃС‚СЂРѕРє РЎРўР РћР“Рћ РІ С„РѕСЂРјР°С‚Рµ:
Р”РµРЅСЊ <РЅРѕРјРµСЂ_РґРЅСЏ>:: <РРґРµСЏ РїРѕСЃС‚Р°>:: <РЎС‚РёР»СЊ РёР· СЃРїРёСЃРєР°>

РќРµ РІРєР»СЋС‡Р°Р№ РЅРёС‡РµРіРѕ, РєСЂРѕРјРµ СЌС‚РёС… СЃС‚СЂРѕРє."""
        # --- РР—РњР•РќР•РќРР• РљРћРќР•Р¦ ---

        # РќР°СЃС‚СЂРѕР№РєР° РєР»РёРµРЅС‚Р° OpenAI РґР»СЏ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ OpenRouter
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        
        # Р—Р°РїСЂРѕСЃ Рє API
        logger.info(f"РћС‚РїСЂР°РІРєР° Р·Р°РїСЂРѕСЃР° РЅР° РіРµРЅРµСЂР°С†РёСЋ РїР»Р°РЅР° РєРѕРЅС‚РµРЅС‚Р° РґР»СЏ РєР°РЅР°Р»Р° @{channel_name} СЃ СѓС‚РѕС‡РЅРµРЅРЅС‹Рј РїСЂРѕРјРїС‚РѕРј")
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free", # <--- РР—РњР•РќР•РќРћ РќРђ РќРћР’РЈР® Р‘Р•РЎРџР›РђРўРќРЈР® РњРћР”Р•Р›Р¬
            messages=[
                # {"role": "system", "content": system_prompt}, # РЎРёСЃС‚РµРјРЅС‹Р№ РїСЂРѕРјРїС‚ РјРѕР¶РµС‚ РєРѕРЅС„Р»РёРєС‚РѕРІР°С‚СЊ СЃ РЅРµРєРѕС‚РѕСЂС‹РјРё РјРѕРґРµР»СЏРјРё, С‚РµСЃС‚РёСЂСѓРµРј Р±РµР· РЅРµРіРѕ РёР»Рё СЃ РЅРёРј
                {"role": "user", "content": user_prompt} # РџРѕРјРµС‰Р°РµРј РІСЃРµ РёРЅСЃС‚СЂСѓРєС†РёРё РІ user_prompt
            ],
            temperature=0.7, # РќРµРјРЅРѕРіРѕ СЃРЅРёР¶Р°РµРј С‚РµРјРїРµСЂР°С‚СѓСЂСѓ РґР»СЏ СЃС‚СЂРѕРіРѕСЃС‚Рё С„РѕСЂРјР°С‚Р°
            max_tokens=150 * period_days, # РџСЂРёРјРµСЂРЅРѕ 150 С‚РѕРєРµРЅРѕРІ РЅР° РёРґРµСЋ
            timeout=120,
            extra_headers={
                "HTTP-Referer": "https://content-manager.onrender.com",
                "X-Title": "Smart Content Assistant"
            }
        )
        
        # === РќРђР§РђР›Рћ РР—РњР•РќР•РќРРЇ: РџСЂРѕРІРµСЂРєР° РѕС‚РІРµС‚Р° API ===
        plan_text = ""
        if response and response.choices and len(response.choices) > 0 and response.choices[0].message and response.choices[0].message.content:
            plan_text = response.choices[0].message.content.strip()
            logger.info(f"РџРѕР»СѓС‡РµРЅ РѕС‚РІРµС‚ СЃ РїР»Р°РЅРѕРј РїСѓР±Р»РёРєР°С†РёР№ (РїРµСЂРІС‹Рµ 100 СЃРёРјРІРѕР»РѕРІ): {plan_text[:100]}...")
        else:
            # Р›РѕРіРёСЂСѓРµРј РїРѕР»РЅС‹Р№ РѕС‚РІРµС‚, РµСЃР»Рё СЃС‚СЂСѓРєС‚СѓСЂР° РЅРµРѕР¶РёРґР°РЅРЅР°СЏ
            logger.error(f"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РёР»Рё РїСѓСЃС‚РѕР№ РѕС‚РІРµС‚ РѕС‚ OpenRouter API РїСЂРё РіРµРЅРµСЂР°С†РёРё РїР»Р°РЅР°. Status: {response.response.status_code if hasattr(response, 'response') else 'N/A'}")
            try:
                # РџРѕРїСЂРѕР±СѓРµРј Р·Р°Р»РѕРіРёСЂРѕРІР°С‚СЊ С‚РµР»Рѕ РѕС‚РІРµС‚Р°, РµСЃР»Рё РѕРЅРѕ РµСЃС‚СЊ
                raw_response_content = await response.response.text() if hasattr(response, 'response') and hasattr(response.response, 'text') else str(response)
                logger.error(f"РџРѕР»РЅС‹Р№ РѕС‚РІРµС‚ API (РёР»Рё РµРіРѕ РїСЂРµРґСЃС‚Р°РІР»РµРЅРёРµ): {raw_response_content}")
            except Exception as log_err:
                logger.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°Р»РѕРіРёСЂРѕРІР°С‚СЊ С‚РµР»Рѕ РѕС‚РІРµС‚Р° API: {log_err}")
                
            # Р’РѕР·РІСЂР°С‰Р°РµРј РїСѓСЃС‚РѕР№ РїР»Р°РЅ СЃ СЃРѕРѕР±С‰РµРЅРёРµРј РѕР± РѕС€РёР±РєРµ
            return PlanGenerationResponse(
                plan=[],
                message="РћС€РёР±РєР°: API РЅРµ РІРµСЂРЅСѓР» РѕР¶РёРґР°РµРјС‹Р№ СЂРµР·СѓР»СЊС‚Р°С‚ РґР»СЏ РіРµРЅРµСЂР°С†РёРё РїР»Р°РЅР°."
            )
        # === РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ===
        
        plan_items = []
        lines = plan_text.split('\n')

        # --- РР—РњР•РќР•РќРР• РќРђР§РђР›Рћ: РЈР»СѓС‡С€РµРЅРЅС‹Р№ РїР°СЂСЃРёРЅРі СЃ РЅРѕРІС‹Рј СЂР°Р·РґРµР»РёС‚РµР»РµРј ---
        expected_style_set = set(s.lower() for s in styles) # Р”Р»СЏ Р±С‹СЃС‚СЂРѕР№ РїСЂРѕРІРµСЂРєРё
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            parts = line.split('::')
            if len(parts) == 3:
                # === РРЎРџР РђР’Р›Р•РќРћ: Р’С‹СЂРѕРІРЅРµРЅ РѕС‚СЃС‚СѓРї РґР»СЏ try ===
                try:
                    day_part = parts[0].lower().replace('РґРµРЅСЊ', '').strip()
                    day = int(day_part)
                    topic_idea = clean_text_formatting(parts[1].strip())
                    format_style = clean_text_formatting(parts[2].strip())

                    # РџСЂРѕРІРµСЂСЏРµРј, РІС…РѕРґРёС‚ Р»Рё СЃС‚РёР»СЊ РІ Р·Р°РїСЂРѕС€РµРЅРЅС‹Р№ СЃРїРёСЃРѕРє (Р±РµР· СѓС‡РµС‚Р° СЂРµРіРёСЃС‚СЂР°)
                    if format_style.lower() not in expected_style_set:
                        logger.warning(f"РЎС‚РёР»СЊ '{format_style}' РёР· РѕС‚РІРµС‚Р° LLM РЅРµ РЅР°Р№РґРµРЅ РІ Р·Р°РїСЂРѕС€РµРЅРЅС‹С… СЃС‚РёР»СЏС…. Р’С‹Р±РёСЂР°РµРј СЃР»СѓС‡Р°Р№РЅС‹Р№.")
                        format_style = random.choice(styles) if styles else "Р‘РµР· СѓРєР°Р·Р°РЅРёСЏ СЃС‚РёР»СЏ"

                    if topic_idea: # РџСЂРѕРїСѓСЃРєР°РµРј, РµСЃР»Рё С‚РµРјР° РїСѓСЃС‚Р°СЏ
                        plan_items.append(PlanItem(
                            day=day,
                            topic_idea=topic_idea,
                            format_style=format_style
                        ))
                    else:
                        logger.warning(f"РџСЂРѕРїСѓС‰РµРЅР° СЃС‚СЂРѕРєР° РїР»Р°РЅР° РёР·-Р·Р° РїСѓСЃС‚РѕР№ С‚РµРјС‹ РїРѕСЃР»Рµ РѕС‡РёСЃС‚РєРё: {line}")
                # === РРЎРџР РђР’Р›Р•РќРћ: Р’С‹СЂРѕРІРЅРµРЅ РѕС‚СЃС‚СѓРї РґР»СЏ except ===
                except ValueError:
                    logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ РёР·РІР»РµС‡СЊ РЅРѕРјРµСЂ РґРЅСЏ РёР· СЃС‚СЂРѕРєРё РїР»Р°РЅР°: {line}")
                except Exception as parse_err:
                    logger.warning(f"РћС€РёР±РєР° РїР°СЂСЃРёРЅРіР° СЃС‚СЂРѕРєРё РїР»Р°РЅР° '{line}': {parse_err}")
            # === РРЎРџР РђР’Р›Р•РќРћ: Р’С‹СЂРѕРІРЅРµРЅ РѕС‚СЃС‚СѓРї РґР»СЏ else ===
            else:
                logger.warning(f"РЎС‚СЂРѕРєР° РїР»Р°РЅР° РЅРµ СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚ С„РѕСЂРјР°С‚Сѓ 'Р”РµРЅСЊ X:: РўРµРјР°:: РЎС‚РёР»СЊ': {line}")
        # --- РР—РњР•РќР•РќРР• РљРћРќР•Р¦ ---

        # ... (РѕСЃС‚Р°Р»СЊРЅР°СЏ Р»РѕРіРёРєР° РѕР±СЂР°Р±РѕС‚РєРё plan_items: СЃРѕСЂС‚РёСЂРѕРІРєР°, РґРѕРїРѕР»РЅРµРЅРёРµ, РїСЂРѕРІРµСЂРєР° РїСѓСЃС‚РѕРіРѕ РїР»Р°РЅР°) ...
        # Р•СЃР»Рё Рё СЃРµР№С‡Р°СЃ РЅРµС‚ РёРґРµР№, РіРµРЅРµСЂРёСЂСѓРµРј РІСЂСѓС‡РЅСѓСЋ
        if not plan_items:
            logger.warning("РќРµ СѓРґР°Р»РѕСЃСЊ РёР·РІР»РµС‡СЊ РёРґРµРё РёР· РѕС‚РІРµС‚Р° LLM РёР»Рё РІСЃРµ СЃС‚СЂРѕРєРё Р±С‹Р»Рё РЅРµРєРѕСЂСЂРµРєС‚РЅС‹РјРё, РіРµРЅРµСЂРёСЂСѓРµРј Р±Р°Р·РѕРІС‹Р№ РїР»Р°РЅ.")
            for day in range(1, period_days + 1):
                random_theme = random.choice(themes) if themes else "РћР±С‰Р°СЏ С‚РµРјР°"
                random_style = random.choice(styles) if styles else "РћР±С‰РёР№ СЃС‚РёР»СЊ"
                # === РР—РњР•РќР•РќРР•: РЈР±РёСЂР°РµРј 'РџРѕСЃС‚ Рѕ' ===
                fallback_topic = f"{random_theme} ({random_style})"
                plan_items.append(PlanItem(
                    day=day,
                    topic_idea=fallback_topic, # <--- РСЃРїРѕР»СЊР·СѓРµРј РЅРѕРІСѓСЋ СЃС‚СЂРѕРєСѓ
                    format_style=random_style
                ))
        
        # РЎРѕСЂС‚РёСЂСѓРµРј РїРѕ РґРЅСЏРј
        plan_items.sort(key=lambda x: x.day)
        
        # РћР±СЂРµР·Р°РµРј РґРѕ Р·Р°РїСЂРѕС€РµРЅРЅРѕРіРѕ РєРѕР»РёС‡РµСЃС‚РІР° РґРЅРµР№ (РЅР° СЃР»СѓС‡Р°Р№, РµСЃР»Рё LLM РІС‹РґР°Р» Р±РѕР»СЊС€Рµ)
        plan_items = plan_items[:period_days]
        
        # Р•СЃР»Рё РїР»Р°РЅ РїРѕР»СѓС‡РёР»СЃСЏ РєРѕСЂРѕС‡Рµ Р·Р°РїСЂРѕС€РµРЅРЅРѕРіРѕ РїРµСЂРёРѕРґР°, РґРѕРїРѕР»РЅСЏРµРј (РІРѕР·РјРѕР¶РЅРѕ, РёР·-Р·Р° РѕС€РёР±РѕРє РїР°СЂСЃРёРЅРіР°)
        if len(plan_items) < period_days:
            existing_days = {item.day for item in plan_items}
            needed_days = period_days - len(plan_items)
            logger.warning(f"РџР»Р°РЅ РєРѕСЂРѕС‡Рµ Р·Р°РїСЂРѕС€РµРЅРЅРѕРіРѕ ({len(plan_items)}/{period_days}), РґРѕРїРѕР»РЅСЏРµРј {needed_days} РёРґРµСЏРјРё.")
            start_day = max(existing_days) + 1 if existing_days else 1
            for i in range(needed_days):
                current_day = start_day + i
                if current_day not in existing_days:
                    random_theme = random.choice(themes) if themes else "Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅР°СЏ С‚РµРјР°"
                    random_style = random.choice(styles) if styles else "Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Р№ СЃС‚РёР»СЊ"
                    # === РР—РњР•РќР•РќРР•: РЈР±РёСЂР°РµРј 'РџРѕСЃС‚ Рѕ' Рё '(Р”РѕРїРѕР»РЅРµРЅРѕ)' ===
                    fallback_topic = f"{random_theme} ({random_style})"
                    plan_items.append(PlanItem(
                        day=current_day,
                        topic_idea=fallback_topic, # <--- РСЃРїРѕР»СЊР·СѓРµРј РЅРѕРІСѓСЋ СЃС‚СЂРѕРєСѓ
                        format_style=random_style
                    ))
        
            # РЎРѕСЂС‚РёСЂСѓРµРј РїРѕ РґРЅСЏРј РµС‰Рµ СЂР°Р· РїРѕСЃР»Рµ РІРѕР·РјРѕР¶РЅРѕРіРѕ РґРѕРїРѕР»РЅРµРЅРёСЏ
            plan_items.sort(key=lambda x: x.day)
        
        logger.info(f"РЎРіРµРЅРµСЂРёСЂРѕРІР°РЅ Рё РѕР±СЂР°Р±РѕС‚Р°РЅ РїР»Р°РЅ РёР· {len(plan_items)} РёРґРµР№ РґР»СЏ РєР°РЅР°Р»Р° @{channel_name}")
        return PlanGenerationResponse(plan=plan_items)
                
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РіРµРЅРµСЂР°С†РёРё РїР»Р°РЅР°: {e}\\n{traceback.format_exc()}") # Р”РѕР±Р°РІР»СЏРµРј traceback
        return PlanGenerationResponse(
            message=f"РћС€РёР±РєР° РїСЂРё РіРµРЅРµСЂР°С†РёРё РїР»Р°РЅР°: {str(e)}",
            plan=[]
        )

# --- РќР°СЃС‚СЂРѕР№РєР° РѕР±СЂР°Р±РѕС‚РєРё РєРѕСЂРЅРµРІРѕРіРѕ РјР°СЂС€СЂСѓС‚Р° РґР»СЏ РѕР±СЃР»СѓР¶РёРІР°РЅРёСЏ СЃС‚Р°С‚РёС‡РµСЃРєРёС… С„Р°Р№Р»РѕРІ ---
@app.get("/")
async def root():
    """РћР±СЃР»СѓР¶РёРІР°РЅРёРµ РєРѕСЂРЅРµРІРѕРіРѕ РјР°СЂС€СЂСѓС‚Р° - РІРѕР·РІСЂР°С‰Р°РµС‚ index.html"""
    if SHOULD_MOUNT_STATIC:
        return FileResponse(os.path.join(static_folder, "index.html"))
    else:
        return {"message": "API СЂР°Р±РѕС‚Р°РµС‚, РЅРѕ СЃС‚Р°С‚РёС‡РµСЃРєРёРµ С„Р°Р№Р»С‹ РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹. РћР±СЂР°С‚РёС‚РµСЃСЊ Рє API РЅР°РїСЂСЏРјСѓСЋ."}

# --- Р”РћР‘РђР’Р›РЇР•Рњ API Р­РќР”РџРћРРќРўР« Р”Р›РЇ Р РђР‘РћРўР« РЎ РџРћРЎРўРђРњР ---
@app.get("/posts", response_model=List[SavedPostResponse])
async def get_posts(request: Request, channel_name: Optional[str] = None):
    """РџРѕР»СѓС‡РµРЅРёРµ СЃРѕС…СЂР°РЅРµРЅРЅС‹С… РїРѕСЃС‚РѕРІ."""
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ РїРѕСЃС‚РѕРІ Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ РґРѕСЃС‚СѓРїР° Рє РїРѕСЃС‚Р°Рј РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")
        
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")
        
        # РЎС‚СЂРѕРёРј Р·Р°РїСЂРѕСЃ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…
        query = supabase.table("saved_posts").select("*").eq("user_id", telegram_user_id)
        
        # Р•СЃР»Рё СѓРєР°Р·Р°РЅРѕ РёРјСЏ РєР°РЅР°Р»Р°, С„РёР»СЊС‚СЂСѓРµРј РїРѕ РЅРµРјСѓ
        if channel_name:
            query = query.eq("channel_name", channel_name)
            
        # Р’С‹РїРѕР»РЅСЏРµРј Р·Р°РїСЂРѕСЃ
        result = query.order("target_date", desc=True).execute()
        
        # РџСЂРѕРІРµСЂРєР° СЂРµР·СѓР»СЊС‚Р°С‚Р°
        if not hasattr(result, 'data'):
            logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РїРѕСЃС‚РѕРІ РёР· Р‘Р”: {result}")
            return []
            
        # === РР—РњР•РќР•РќРР•: Р—Р°РїСЂРѕСЃ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ СЃРІСЏР·Р°РЅРЅС‹С… РёР·РѕР±СЂР°Р¶РµРЅРёР№ ===
        # РЎС‚СЂРѕРёРј Р·Р°РїСЂРѕСЃ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…, Р·Р°РїСЂР°С€РёРІР°СЏ СЃРІСЏР·Р°РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ РёР· saved_images
        # РћР±СЂР°С‚РёС‚Рµ РІРЅРёРјР°РЅРёРµ: РёРјСЏ С‚Р°Р±Р»РёС†С‹ saved_images РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РєР°Рє РёРјСЏ СЃРІСЏР·Рё
        query = supabase.table("saved_posts").select(
            "*, saved_images(*)" # <--- Р—Р°РїСЂР°С€РёРІР°РµРј РІСЃРµ РїРѕР»СЏ РїРѕСЃС‚Р° Рё РІСЃРµ РїРѕР»СЏ СЃРІСЏР·Р°РЅРЅРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
        ).eq("user_id", int(telegram_user_id))
        # === РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ===
        
        # Р•СЃР»Рё СѓРєР°Р·Р°РЅРѕ РёРјСЏ РєР°РЅР°Р»Р°, С„РёР»СЊС‚СЂСѓРµРј РїРѕ РЅРµРјСѓ
        if channel_name:
            query = query.eq("channel_name", channel_name)
            
        # Р’С‹РїРѕР»РЅСЏРµРј Р·Р°РїСЂРѕСЃ
        result = query.order("target_date", desc=True).execute()
        
        # РџСЂРѕРІРµСЂРєР° СЂРµР·СѓР»СЊС‚Р°С‚Р°
        if not hasattr(result, 'data'):
            logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РїРѕСЃС‚РѕРІ РёР· Р‘Р”: {result}")
            return []
            
        # === РР—РњР•РќР•РќРР•: РћР±СЂР°Р±РѕС‚РєР° РѕС‚РІРµС‚Р° РґР»СЏ РІРєР»СЋС‡РµРЅРёСЏ РґР°РЅРЅС‹С… РёР·РѕР±СЂР°Р¶РµРЅРёСЏ ===
        posts_with_images = []
        for post_data in result.data:
            # РЎРѕР·РґР°РµРј РѕР±СЉРµРєС‚ SavedPostResponse РёР· РѕСЃРЅРѕРІРЅС‹С… РґР°РЅРЅС‹С… РїРѕСЃС‚Р°
            response_item = SavedPostResponse(**post_data)
            
            # РџСЂРѕРІРµСЂСЏРµРј, РµСЃС‚СЊ Р»Рё СЃРІСЏР·Р°РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ Рё РѕРЅРё РЅРµ РїСѓСЃС‚С‹Рµ
            image_relation_data = post_data.get("saved_images")
            
            # === РР—РњР•РќР•РќРћ: Р›РѕРіРёСЂРѕРІР°РЅРёРµ РЅР° СѓСЂРѕРІРЅРµ INFO ===
            logger.info(f"РћР±СЂР°Р±РѕС‚РєР° РїРѕСЃС‚Р° ID: {response_item.id}. РЎРІСЏР·Р°РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {image_relation_data}")
            # === РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ===
            
            if image_relation_data and isinstance(image_relation_data, dict):
                # РЎРѕР·РґР°РµРј РѕР±СЉРµРєС‚ PostImage РёР· РґР°РЅРЅС‹С… saved_images
                # РЈР±РµРґРёРјСЃСЏ, С‡С‚Рѕ РєР»СЋС‡Рё СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓСЋС‚ РјРѕРґРµР»Рё PostImage
                try:
                    # --- РР—РњР•РќР•РќРР•: РџСЂРёРѕСЂРёС‚РµС‚ alt_description, Р·Р°С‚РµРј alt ---
                    alt_text = image_relation_data.get("alt_description") or image_relation_data.get("alt")
                    # --- РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ---
                    response_item.selected_image_data = PostImage(
                        id=image_relation_data.get("id"),
                        url=image_relation_data.get("url"),
                        preview_url=image_relation_data.get("preview_url"),
                        alt=alt_text, # <--- РСЃРїРѕР»СЊР·СѓРµРј РїРѕРґРіРѕС‚РѕРІР»РµРЅРЅС‹Р№ alt_text
                        author=image_relation_data.get("author"), # Р’ saved_images СЌС‚Рѕ 'author'
                        author_url=image_relation_data.get("author_url"),
                        source=image_relation_data.get("source")
                    )
                    # === РР—РњР•РќР•РќРћ: Р›РѕРіРёСЂРѕРІР°РЅРёРµ РЅР° СѓСЂРѕРІРЅРµ INFO ===
                    logger.info(f"РЈСЃРїРµС€РЅРѕ СЃРѕР·РґР°РЅРѕ selected_image_data РґР»СЏ РїРѕСЃС‚Р° {response_item.id} СЃ РёР·РѕР±СЂР°Р¶РµРЅРёРµРј ID: {response_item.selected_image_data.id}")
                    # === РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ===
                except Exception as mapping_error:
                     logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё PostImage РґР»СЏ РїРѕСЃС‚Р° {response_item.id}: {mapping_error}")
                     logger.error(f"Р”Р°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {image_relation_data}")
                     response_item.selected_image_data = None # РћС‡РёС‰Р°РµРј РїСЂРё РѕС€РёР±РєРµ
            else:
                # Р•СЃР»Рё РєР»СЋС‡ 'saved_images' РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РёР»Рё РїСѓСЃС‚, selected_image_data РѕСЃС‚Р°РµС‚СЃСЏ None
                response_item.selected_image_data = None
                # Р›РѕРіРёСЂСѓРµРј, РµСЃР»Рё РѕР¶РёРґР°Р»Рё РёР·РѕР±СЂР°Р¶РµРЅРёРµ (С‚.Рµ. saved_image_id РЅРµ None), РЅРѕ РµРіРѕ РЅРµС‚
                if post_data.get("saved_image_id"):
                    logger.warning(f"Р”Р»СЏ РїРѕСЃС‚Р° {post_data['id']} РµСЃС‚СЊ saved_image_id, РЅРѕ СЃРІСЏР·Р°РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РЅРµ Р±С‹Р»Рё РїРѕР»СѓС‡РµРЅС‹ РёР»Рё РїСѓСЃС‚С‹. РЎРІСЏР·Р°РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ: {image_relation_data}")


            posts_with_images.append(response_item)
            
        return posts_with_images
        # === РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ===
        
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РїРѕСЃС‚РѕРІ: {e}")
        # === Р”РћР‘РђР’Р›Р•РќРћ: РџРµСЂРµРІС‹Р±СЂРѕСЃ HTTPException РґР»СЏ РєРѕСЂСЂРµРєС‚РЅРѕРіРѕ РѕС‚РІРµС‚Р° ===
        raise HTTPException(status_code=500, detail=str(e))
        # === РљРћРќР•Р¦ Р”РћР‘РђР’Р›Р•РќРРЇ ===

@app.post("/posts", response_model=SavedPostResponse)
async def create_post(request: Request, post_data: PostData):
    """РЎРѕР·РґР°РЅРёРµ РЅРѕРІРѕРіРѕ РїРѕСЃС‚Р°."""
    try:
        # === Р”РћР‘РђР’Р›Р•РќРћ: РџСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕРµ РѕР±РЅРѕРІР»РµРЅРёРµ СЃС…РµРјС‹ РїРµСЂРµРґ РѕРїРµСЂР°С†РёРµР№ ===
        try:
            logger.info("Р’С‹Р·РѕРІ fix_schema РїРµСЂРµРґ СЃРѕР·РґР°РЅРёРµРј РїРѕСЃС‚Р°...")
            fix_result = await fix_schema()
            if not fix_result.get("success"):
                logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ/РїСЂРѕРІРµСЂРёС‚СЊ СЃС…РµРјСѓ РїРµСЂРµРґ СЃРѕР·РґР°РЅРёРµРј РїРѕСЃС‚Р°: {fix_result}")
                # РњРѕР¶РЅРѕ СЂРµС€РёС‚СЊ, РїСЂРµСЂС‹РІР°С‚СЊ Р»Рё РѕРїРµСЂР°С†РёСЋ РёР»Рё РЅРµС‚. РџРѕРєР° РїСЂРѕРґРѕР»Р¶Р°РµРј.
            else:
                logger.info("РџСЂРѕРІРµСЂРєР°/РѕР±РЅРѕРІР»РµРЅРёРµ СЃС…РµРјС‹ РїРµСЂРµРґ СЃРѕР·РґР°РЅРёРµРј РїРѕСЃС‚Р° Р·Р°РІРµСЂС€РµРЅР° СѓСЃРїРµС€РЅРѕ.")
        except Exception as pre_save_fix_err:
            logger.error(f"РћС€РёР±РєР° РїСЂРё РІС‹Р·РѕРІРµ fix_schema РїРµСЂРµРґ СЃРѕР·РґР°РЅРёРµРј РїРѕСЃС‚Р°: {pre_save_fix_err}", exc_info=True)
            # РџСЂРѕРґРѕР»Р¶Р°РµРј, РЅРѕ Р»РѕРіРёСЂСѓРµРј РѕС€РёР±РєСѓ
        # === РљРћРќР•Р¦ Р”РћР‘РђР’Р›Р•РќРРЇ ===

        # === Р”РћР‘РђР’Р›Р•РќРћ: РџР°СѓР·Р° РїРѕСЃР»Рµ РѕР±РЅРѕРІР»РµРЅРёСЏ СЃС…РµРјС‹ ===
        logger.info("РќРµР±РѕР»СЊС€Р°СЏ РїР°СѓР·Р° РїРѕСЃР»Рµ fix_schema, С‡С‚РѕР±С‹ РґР°С‚СЊ PostgREST РІСЂРµРјСЏ...")
        await asyncio.sleep(0.7) # РџР°СѓР·Р° 0.7 СЃРµРєСѓРЅРґС‹
        # === РљРћРќР•Р¦ Р”РћР‘РђР’Р›Р•РќРРЇ ===

        # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ СЃРѕР·РґР°РЅРёСЏ РїРѕСЃС‚Р° Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ СЃРѕР·РґР°РЅРёСЏ РїРѕСЃС‚Р° РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")
        
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")
        
        # РР·РІР»РµРєР°РµРј РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РѕС‚РґРµР»СЊРЅРѕ
        selected_image = post_data.selected_image_data
        
        # РЎРѕР·РґР°РµРј СЃР»РѕРІР°СЂСЊ СЃ РѕСЃРЅРѕРІРЅС‹РјРё РґР°РЅРЅС‹РјРё РїРѕСЃС‚Р° РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ
        post_to_save = post_data.dict(exclude={"selected_image_data"}) # РСЃРєР»СЋС‡Р°РµРј РѕР±СЉРµРєС‚ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
        post_to_save["user_id"] = int(telegram_user_id)
        post_to_save["id"] = str(uuid.uuid4()) # Р“РµРЅРµСЂРёСЂСѓРµРј ID РґР»СЏ РЅРѕРІРѕРіРѕ РїРѕСЃС‚Р°
        
        # === Р”РћР‘РђР’Р›Р•РќРћ: РћР±СЂР°Р±РѕС‚РєР° target_date ===
        if not post_to_save.get("target_date"):
            logger.warning(f"РџРѕР»СѓС‡РµРЅР° РїСѓСЃС‚Р°СЏ target_date РґР»СЏ РЅРѕРІРѕРіРѕ РїРѕСЃС‚Р° {post_to_save['id']}, СѓСЃС‚Р°РЅР°РІР»РёРІР°РµРј РІ NULL.")
            post_to_save["target_date"] = None
        else:
            # Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅРѕ РјРѕР¶РЅРѕ РґРѕР±Р°РІРёС‚СЊ РІР°Р»РёРґР°С†РёСЋ С„РѕСЂРјР°С‚Р° YYYY-MM-DD, РµСЃР»Рё РЅСѓР¶РЅРѕ
            try:
                datetime.strptime(post_to_save["target_date"], '%Y-%m-%d')
            except ValueError:
                logger.error(f"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ С„РѕСЂРјР°С‚ target_date: {post_to_save['target_date']} РґР»СЏ РїРѕСЃС‚Р° {post_to_save['id']}. РЈСЃС‚Р°РЅР°РІР»РёРІР°РµРј РІ NULL.")
                post_to_save["target_date"] = None
        # === РљРћРќР•Р¦ Р”РћР‘РђР’Р›Р•РќРРЇ ===
        
        # --- РќРђР§РђР›Рћ: РћР±СЂР°Р±РѕС‚РєР° РІС‹Р±СЂР°РЅРЅРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ --- 
        saved_image_id = None
        if selected_image:
            try:
                # --- РЈР”РђР›Р•РќРћ: РџСЂРѕРІРµСЂРєР° РЅР°Р»РёС‡РёСЏ РєРѕР»РѕРЅРєРё external_id --- 

                # РџСЂРѕРІРµСЂСЏРµРј, СЃСѓС‰РµСЃС‚РІСѓРµС‚ Р»Рё РёР·РѕР±СЂР°Р¶РµРЅРёРµ СЃ С‚Р°РєРёРј URL (Р±РѕР»РµРµ РЅР°РґРµР¶РЅРѕ)
                image_check = None
                if selected_image.url:
                    image_check_result = supabase.table("saved_images").select("id").eq("url", selected_image.url).limit(1).execute()
                    if hasattr(image_check_result, 'data') and len(image_check_result.data) > 0:
                        image_check = image_check_result.data[0]
                # --- РљРћРќР•Р¦ РџР РћР’Р•Р РљР РџРћ URL ---

                if image_check:
                    # РР·РѕР±СЂР°Р¶РµРЅРёРµ СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚, РёСЃРїРѕР»СЊР·СѓРµРј РµРіРѕ ID (UUID)
                    saved_image_id = image_check["id"]
                    logger.info(f"РСЃРїРѕР»СЊР·СѓРµРј СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ {saved_image_id} (URL: {selected_image.url}) РґР»СЏ РїРѕСЃС‚Р°")
                else:
                    # РР·РѕР±СЂР°Р¶РµРЅРёРµ РЅРµ РЅР°Р№РґРµРЅРѕ, СЃРѕС…СЂР°РЅСЏРµРј РЅРѕРІРѕРµ
                    # Р“Р•РќР•Р РР РЈР•Рњ РќРћР’Р«Р™ UUID РґР»СЏ РЅР°С€РµР№ Р‘Р”
                    new_internal_id = str(uuid.uuid4()) 
                    # --- РЈР”РђР›Р•РќРћ: Р›РѕРіРёРєР° СЃ external_id --- 
                    
                    image_data_to_save = {
                        "id": new_internal_id, # РСЃРїРѕР»СЊР·СѓРµРј РЅР°С€ UUID
                        "url": selected_image.url,
                        "preview_url": selected_image.preview_url or selected_image.url,
                        "alt": selected_image.alt or "",
                        "author": selected_image.author or "", # РЎРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚ 'author' РІ PostImage
                        "author_url": selected_image.author_url or "",
                        "source": selected_image.source or "frontend_selection",
                        "user_id": int(telegram_user_id),
                        # --- РЈР”РђР›Р•РќРћ: external_id ---
                    }
                    
                    image_result = supabase.table("saved_images").insert(image_data_to_save).execute()
                    if hasattr(image_result, 'data') and len(image_result.data) > 0:
                        saved_image_id = new_internal_id # РСЃРїРѕР»СЊР·СѓРµРј РЅР°С€ ID РґР»СЏ СЃРІСЏР·Рё
                        logger.info(f"РЎРѕС…СЂР°РЅРµРЅРѕ РЅРѕРІРѕРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ {saved_image_id} РґР»СЏ РїРѕСЃС‚Р°")
                    else:
                        logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РЅРѕРІРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {image_result}")
                        raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РЅРѕРІРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {getattr(image_result, 'error', 'Unknown error')}")
            except Exception as img_err:
                logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ/СЃРѕС…СЂР°РЅРµРЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {img_err}")
                raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ/СЃРѕС…СЂР°РЅРµРЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {str(img_err)}")
        # --- РљРћРќР•Р¦: РћР±СЂР°Р±РѕС‚РєР° РІС‹Р±СЂР°РЅРЅРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ --- 

        # РЈРґР°Р»СЏРµРј СЃС‚Р°СЂС‹Рµ РїРѕР»СЏ РёР· РґР°РЅРЅС‹С… РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ РїРѕСЃС‚Р°
        post_to_save.pop('image_url', None)
        post_to_save.pop('images_ids', None)
        
        # === РР—РњР•РќР•РќРР• РќРђР§РђР›Рћ ===
        # Р”РѕР±Р°РІР»СЏРµРј ID СЃРѕС…СЂР°РЅРµРЅРЅРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РІ РґР°РЅРЅС‹Рµ РїРѕСЃС‚Р°
        post_to_save["saved_image_id"] = saved_image_id
        # === РР—РњР•РќР•РќРР• РљРћРќР•Р¦ ===
        
        # === РР—РњР•РќР•РќРР• РќРђР§РђР›Рћ: Р›РѕРіРёСЂРѕРІР°РЅРёРµ РґР°РЅРЅС‹С… РїРµСЂРµРґ СЃРѕС…СЂР°РЅРµРЅРёРµРј ===
        logger.info(f"РџРѕРґРіРѕС‚РѕРІР»РµРЅС‹ РґР°РЅРЅС‹Рµ РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ РІ saved_posts: {post_to_save}")
        # === РљРћРќР•Р¦ Р”РћР‘РђР’Р›Р•РќРРЇ ===

        # === РР—РњР•РќР•РќРћ: РЈР±СЂР°РЅ РјРµС…Р°РЅРёР·Рј СЂРµС‚СЂР°СЏ ===
        try:
            logger.info(f"Р’С‹РїРѕР»РЅСЏРµРј insert РІ saved_posts РґР»СЏ ID {post_to_save['id']}...")
            # === РРЎРџР РђР’Р›Р•РќРћ: Р’С‹СЂРѕРІРЅРµРЅ РѕС‚СЃС‚СѓРї ===
            result = supabase.table("saved_posts").insert(post_to_save).execute()
            logger.info(f"Insert РІС‹РїРѕР»РЅРµРЅ. Status: {result.status_code if hasattr(result, 'status_code') else 'N/A'}")
        except APIError as e:
            logger.error(f"РћС€РёР±РєР° APIError РїСЂРё insert РІ saved_posts: {e}")
            # РџРµСЂРµС…РІР°С‚С‹РІР°РµРј Рё Р»РѕРіРёСЂСѓРµРј, С‡С‚РѕР±С‹ СѓРІРёРґРµС‚СЊ РґРµС‚Р°Р»Рё РїРµСЂРµРґ 500 РѕС€РёР±РєРѕР№
            raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° Р‘Р” РїСЂРё СЃРѕР·РґР°РЅРёРё РїРѕСЃС‚Р°: {e.message}")
        except Exception as general_e:
            logger.error(f"РќРµРїСЂРµРґРІРёРґРµРЅРЅР°СЏ РѕС€РёР±РєР° РїСЂРё insert РІ saved_posts: {general_e}")
            raise HTTPException(status_code=500, detail=f"РќРµРїСЂРµРґРІРёРґРµРЅРЅР°СЏ РѕС€РёР±РєР° Р‘Р” РїСЂРё СЃРѕР·РґР°РЅРёРё РїРѕСЃС‚Р°: {str(general_e)}")
        
        # === РР—РњР•РќР•РќРћ: РЈР±СЂР°РЅ Р»РёС€РЅРёР№ РѕС‚СЃС‚СѓРї ===
        # РџСЂРѕРІРµСЂРєР° СЂРµР·СѓР»СЊС‚Р°С‚Р°
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РїРѕСЃС‚Р° {post_to_save['id']}: РћС‚РІРµС‚ Supabase РїСѓСЃС‚ РёР»Рё РЅРµ СЃРѕРґРµСЂР¶РёС‚ РґР°РЅРЅС‹С….")
            last_error_details = f"Status: {result.status_code if hasattr(result, 'status_code') else 'N/A'}"
            raise HTTPException(status_code=500, detail=f"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ РїРѕСЃС‚. {last_error_details}")
        # === РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ===

        created_post = result.data[0]
        post_id = created_post["id"]
        
        logger.info(f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {telegram_user_id} СЃРѕР·РґР°Р» РїРѕСЃС‚: {post_data.topic_idea}")
        
        # Р’РѕР·РІСЂР°С‰Р°РµРј РґР°РЅРЅС‹Рµ СЃРѕР·РґР°РЅРЅРѕРіРѕ РїРѕСЃС‚Р°, РѕР±РѕРіР°С‰РµРЅРЅС‹Рµ РґР°РЅРЅС‹РјРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
        response_data = SavedPostResponse(**created_post)
        if saved_image_id and selected_image: # Р•СЃР»Рё Р±С‹Р»Рѕ РІС‹Р±СЂР°РЅРѕ Рё СЃРѕС…СЂР°РЅРµРЅРѕ/РЅР°Р№РґРµРЅРѕ РёР·РѕР±СЂР°Р¶РµРЅРёРµ
             response_data.selected_image_data = selected_image # Р’РѕР·РІСЂР°С‰Р°РµРј РёСЃС…РѕРґРЅС‹Рµ РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
        elif saved_image_id: # Р•СЃР»Рё РёР·РѕР±СЂР°Р¶РµРЅРёРµ Р±С‹Р»Рѕ РЅР°Р№РґРµРЅРѕ, РЅРѕ РЅРµ РїРµСЂРµРґР°РЅРѕ (РјР°Р»РѕРІРµСЂРѕСЏС‚РЅРѕ, РЅРѕ РЅР° РІСЃСЏРєРёР№ СЃР»СѓС‡Р°Р№)
             # РџС‹С‚Р°РµРјСЃСЏ РїРѕР»СѓС‡РёС‚СЊ РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РёР· Р‘Р”
             img_data_res = supabase.table("saved_images").select("id, url, preview_url, alt, author, author_url, source").eq("id", saved_image_id).maybe_single().execute()
             if img_data_res.data:
                  response_data.selected_image_data = PostImage(**img_data_res.data)

        return response_data
        
    except HTTPException as http_err:
        # РџРµСЂРµС…РІР°С‚С‹РІР°РµРј HTTP РёСЃРєР»СЋС‡РµРЅРёСЏ, С‡С‚РѕР±С‹ РЅРµ РїРѕРїР°СЃС‚СЊ РІ РѕР±С‰РёР№ Exception
        raise http_err
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё РїРѕСЃС‚Р°: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Р’РЅСѓС‚СЂРµРЅРЅСЏСЏ РѕС€РёР±РєР° СЃРµСЂРІРµСЂР° РїСЂРё СЃРѕР·РґР°РЅРёРё РїРѕСЃС‚Р°: {str(e)}")

@app.put("/posts/{post_id}", response_model=SavedPostResponse)
async def update_post(post_id: str, request: Request, post_data: PostData):
    """РћР±РЅРѕРІР»РµРЅРёРµ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРіРѕ РїРѕСЃС‚Р°."""
    try:
        # === Р”РћР‘РђР’Р›Р•РќРћ: РџСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕРµ РѕР±РЅРѕРІР»РµРЅРёРµ СЃС…РµРјС‹ РїРµСЂРµРґ РѕРїРµСЂР°С†РёРµР№ ===
        try:
            logger.info(f"Р’С‹Р·РѕРІ fix_schema РїРµСЂРµРґ РѕР±РЅРѕРІР»РµРЅРёРµРј РїРѕСЃС‚Р° {post_id}...")
            fix_result = await fix_schema()
            if not fix_result.get("success"):
                logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ/РїСЂРѕРІРµСЂРёС‚СЊ СЃС…РµРјСѓ РїРµСЂРµРґ РѕР±РЅРѕРІР»РµРЅРёРµРј РїРѕСЃС‚Р° {post_id}: {fix_result}")
            else:
                logger.info(f"РџСЂРѕРІРµСЂРєР°/РѕР±РЅРѕРІР»РµРЅРёРµ СЃС…РµРјС‹ РїРµСЂРµРґ РѕР±РЅРѕРІР»РµРЅРёРµРј РїРѕСЃС‚Р° {post_id} Р·Р°РІРµСЂС€РµРЅР° СѓСЃРїРµС€РЅРѕ.")
        except Exception as pre_update_fix_err:
            logger.error(f"РћС€РёР±РєР° РїСЂРё РІС‹Р·РѕРІРµ fix_schema РїРµСЂРµРґ РѕР±РЅРѕРІР»РµРЅРёРµРј РїРѕСЃС‚Р° {post_id}: {pre_update_fix_err}", exc_info=True)
        # === РљРћРќР•Р¦ Р”РћР‘РђР’Р›Р•РќРРЇ ===

        # === Р”РћР‘РђР’Р›Р•РќРћ: РџР°СѓР·Р° РїРѕСЃР»Рµ РѕР±РЅРѕРІР»РµРЅРёСЏ СЃС…РµРјС‹ ===
        logger.info(f"РќРµР±РѕР»СЊС€Р°СЏ РїР°СѓР·Р° РїРѕСЃР»Рµ fix_schema РґР»СЏ РїРѕСЃС‚Р° {post_id}, С‡С‚РѕР±С‹ РґР°С‚СЊ PostgREST РІСЂРµРјСЏ...")
        await asyncio.sleep(0.7) # РџР°СѓР·Р° 0.7 СЃРµРєСѓРЅРґС‹
        # === РљРћРќР•Р¦ Р”РћР‘РђР’Р›Р•РќРРЇ ===

        # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ РѕР±РЅРѕРІР»РµРЅРёСЏ РїРѕСЃС‚Р° Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ РїРѕСЃС‚Р° РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")
        
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")
        
        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РїРѕСЃС‚ РїСЂРёРЅР°РґР»РµР¶РёС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ
        post_check = supabase.table("saved_posts").select("id").eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
        if not hasattr(post_check, 'data') or len(post_check.data) == 0:
            logger.warning(f"РџРѕРїС‹С‚РєР° РѕР±РЅРѕРІРёС‚СЊ С‡СѓР¶РѕР№ РёР»Рё РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РёР№ РїРѕСЃС‚: {post_id}")
            raise HTTPException(status_code=404, detail="РџРѕСЃС‚ РЅРµ РЅР°Р№РґРµРЅ РёР»Рё РЅРµС‚ РїСЂР°РІ РЅР° РµРіРѕ СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ")
        
        # === РР—РњР•РќР•РќРР• Р›РћР“РРљР РћР‘Р РђР‘РћРўРљР РР—РћР‘Р РђР–Р•РќРРЇ ===
        # РСЃРїРѕР»СЊР·СѓРµРј getattr РґР»СЏ Р±РµР·РѕРїР°СЃРЅРѕРіРѕ РґРѕСЃС‚СѓРїР°, РЅР° СЃР»СѓС‡Р°Р№ РµСЃР»Рё РїРѕР»Рµ РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РІ Р·Р°РїСЂРѕСЃРµ
        selected_image = getattr(post_data, 'selected_image_data', None)
        # Р¤Р»Р°Рі, СѓРєР°Р·С‹РІР°СЋС‰РёР№, Р±С‹Р»Рѕ Р»Рё РїРѕР»Рµ selected_image_data *СЏРІРЅРѕ* РїРµСЂРµРґР°РЅРѕ РІ Р·Р°РїСЂРѕСЃРµ
        image_field_provided_in_request = hasattr(post_data, 'selected_image_data')

        # РџРµСЂРµРјРµРЅРЅР°СЏ РґР»СЏ С…СЂР°РЅРµРЅРёСЏ ID РёР·РѕР±СЂР°Р¶РµРЅРёСЏ, РєРѕС‚РѕСЂРѕРµ РЅСѓР¶РЅРѕ СЃРѕС…СЂР°РЅРёС‚СЊ РІ РїРѕСЃС‚Рµ
        # РР·РЅР°С‡Р°Р»СЊРЅРѕ None, РёР·РјРµРЅРёС‚СЃСЏ С‚РѕР»СЊРєРѕ РµСЃР»Рё РёР·РѕР±СЂР°Р¶РµРЅРёРµ РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅРѕ
        image_id_to_set_in_post = None
        image_processed = False # Р¤Р»Р°Рі, С‡С‚Рѕ РјС‹ РѕР±СЂР°Р±РѕС‚Р°Р»Рё РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РёР· Р·Р°РїСЂРѕСЃР°

        if image_field_provided_in_request:
            image_processed = True # РћС‚РјРµС‡Р°РµРј, С‡С‚Рѕ РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ Р±С‹Р»Рё РІ Р·Р°РїСЂРѕСЃРµ
            if selected_image: # Р•СЃР»Рё РёР·РѕР±СЂР°Р¶РµРЅРёРµ РїРµСЂРµРґР°РЅРѕ Рё РѕРЅРѕ РЅРµ None/РїСѓСЃС‚РѕРµ
                try:
                    # РџСЂРѕРІРµСЂСЏРµРј, СЃСѓС‰РµСЃС‚РІСѓРµС‚ Р»Рё РёР·РѕР±СЂР°Р¶РµРЅРёРµ СЃ С‚Р°РєРёРј URL
                    image_check = None
                    if selected_image.url:
                        image_check_result = supabase.table("saved_images").select("id").eq("url", selected_image.url).limit(1).execute()
                        if hasattr(image_check_result, 'data') and len(image_check_result.data) > 0:
                            image_check = image_check_result.data[0]

                    if image_check:
                        image_id_to_set_in_post = image_check["id"]
                        logger.info(f"РСЃРїРѕР»СЊР·СѓРµРј СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ {image_id_to_set_in_post} РґР»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ РїРѕСЃС‚Р° {post_id}")
                    else:
                        # РЎРѕС…СЂР°РЅСЏРµРј РЅРѕРІРѕРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ
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
            else: # Р•СЃР»Рё selected_image_data РїРµСЂРµРґР°РЅ РєР°Рє null РёР»Рё РїСѓСЃС‚РѕР№ РѕР±СЉРµРєС‚
                image_id_to_set_in_post = None # РЇРІРЅРѕ СѓРєР°Р·С‹РІР°РµРј, С‡С‚Рѕ СЃРІСЏР·СЊ РЅСѓР¶РЅРѕ СѓРґР°Р»РёС‚СЊ
                logger.info(f"Р’ Р·Р°РїСЂРѕСЃРµ РЅР° РѕР±РЅРѕРІР»РµРЅРёРµ РїРѕСЃС‚Р° {post_id} РїРµСЂРµРґР°РЅРѕ РїСѓСЃС‚РѕРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ (None/null). РЎРІСЏР·СЊ Р±СѓРґРµС‚ РѕС‡РёС‰РµРЅР°.")
        # Р•СЃР»Рё image_field_provided_in_request == False, С‚Рѕ image_processed РѕСЃС‚Р°РµС‚СЃСЏ False,
        # Рё РјС‹ РќР• Р±СѓРґРµРј РѕР±РЅРѕРІР»СЏС‚СЊ РїРѕР»Рµ saved_image_id РІ post_to_update РґР°Р»РµРµ.

        # РЎРѕР·РґР°РµРј СЃР»РѕРІР°СЂСЊ СЃ РѕСЃРЅРѕРІРЅС‹РјРё РґР°РЅРЅС‹РјРё РїРѕСЃС‚Р° РґР»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ
        # РСЃРєР»СЋС‡Р°РµРј selected_image_data, С‚.Рє. РµРіРѕ РЅРµ РЅСѓР¶РЅРѕ РїРёСЃР°С‚СЊ РІ saved_posts
        post_to_update = post_data.dict(exclude={"selected_image_data", "image_url", "images_ids"})
        post_to_update["updated_at"] = datetime.now().isoformat()

        # РћР±СЂР°Р±РѕС‚РєР° target_date (РѕСЃС‚Р°РµС‚СЃСЏ РєР°Рє Р±С‹Р»Рѕ)
        if "target_date" in post_to_update and not post_to_update.get("target_date"):
            logger.warning(f"РџРѕР»СѓС‡РµРЅР° РїСѓСЃС‚Р°СЏ target_date РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р° {post_id}, СѓСЃС‚Р°РЅР°РІР»РёРІР°РµРј РІ NULL.")
            post_to_update["target_date"] = None
        elif post_to_update.get("target_date"):
            try:
                datetime.strptime(post_to_update["target_date"], '%Y-%m-%d')
            except ValueError:
                logger.error(f"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ С„РѕСЂРјР°С‚ target_date: {post_to_update['target_date']} РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р° {post_id}. РЈСЃС‚Р°РЅР°РІР»РёРІР°РµРј РІ NULL.")
                post_to_update["target_date"] = None

        # РћР±РЅРѕРІР»СЏРµРј saved_image_id РўРћР›Р¬РљРћ РµСЃР»Рё РїРѕР»Рµ selected_image_data Р±С‹Р»Рѕ СЏРІРЅРѕ РїРµСЂРµРґР°РЅРѕ РІ Р·Р°РїСЂРѕСЃРµ
        if image_processed:
            # РћР±РЅРѕРІР»СЏРµРј РїРѕР»Рµ saved_image_id Р·РЅР°С‡РµРЅРёРµРј, РїРѕР»СѓС‡РµРЅРЅС‹Рј РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
            # Р•СЃР»Рё Р±С‹Р»Рѕ РїРµСЂРµРґР°РЅРѕ РїСѓСЃС‚РѕРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ, image_id_to_set_in_post Р±СѓРґРµС‚ None, Рё СЃРІСЏР·СЊ РѕС‡РёСЃС‚РёС‚СЃСЏ
            post_to_update["saved_image_id"] = image_id_to_set_in_post
            logger.info(f"РџРѕР»Рµ saved_image_id РґР»СЏ РїРѕСЃС‚Р° {post_id} Р±СѓРґРµС‚ РѕР±РЅРѕРІР»РµРЅРѕ РЅР°: {image_id_to_set_in_post}")
        else:
            # Р•СЃР»Рё РїРѕР»Рµ selected_image_data РќР• Р‘Р«Р›Рћ РїРµСЂРµРґР°РЅРѕ РІ Р·Р°РїСЂРѕСЃРµ,
            # РќР• С‚СЂРѕРіР°РµРј РїРѕР»Рµ saved_image_id РІ post_to_update.
            # РЈР±РµРґРёРјСЃСЏ, С‡С‚Рѕ РµРіРѕ С‚РѕС‡РЅРѕ РЅРµС‚ РІ СЃР»РѕРІР°СЂРµ РґР»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ, С‡С‚РѕР±С‹ РЅРµ Р·Р°С‚РµСЂРµС‚СЊ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРµ Р·РЅР°С‡РµРЅРёРµ РІ Р‘Р”.
            post_to_update.pop("saved_image_id", None)
            logger.info(f"РџРѕР»Рµ selected_image_data РЅРµ РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅРѕ РІ Р·Р°РїСЂРѕСЃРµ РЅР° РѕР±РЅРѕРІР»РµРЅРёРµ РїРѕСЃС‚Р° {post_id}. РџРѕР»Рµ saved_image_id РЅРµ Р±СѓРґРµС‚ РёР·РјРµРЅРµРЅРѕ.")

        # Р›РѕРіРёСЂРѕРІР°РЅРёРµ РґР°РЅРЅС‹С… РїРµСЂРµРґ СЃРѕС…СЂР°РЅРµРЅРёРµРј
        logger.info(f"РџРѕРґРіРѕС‚РѕРІР»РµРЅС‹ РґР°РЅРЅС‹Рµ РґР»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ РІ saved_posts: {post_to_update}")

        # Р’С‹РїРѕР»РЅРµРЅРёРµ UPDATE Р·Р°РїСЂРѕСЃР°
        try:
            logger.info(f"Р’С‹РїРѕР»РЅСЏРµРј update РІ saved_posts РґР»СЏ ID {post_id}...")
            result = supabase.table("saved_posts").update(post_to_update).eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
            logger.info(f"Update РІС‹РїРѕР»РЅРµРЅ. Status: {result.status_code if hasattr(result, 'status_code') else 'N/A'}")
        except APIError as e:
            logger.error(f"РћС€РёР±РєР° APIError РїСЂРё update РІ saved_posts РґР»СЏ ID {post_id}: {e}")
            raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° Р‘Р” РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р°: {e.message}")
        except Exception as general_e:
            logger.error(f"РќРµРїСЂРµРґРІРёРґРµРЅРЅР°СЏ РѕС€РёР±РєР° РїСЂРё update РІ saved_posts РґР»СЏ ID {post_id}: {general_e}")
            raise HTTPException(status_code=500, detail=f"РќРµРїСЂРµРґРІРёРґРµРЅРЅР°СЏ РѕС€РёР±РєР° Р‘Р” РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р°: {str(general_e)}")
        
        # РџСЂРѕРІРµСЂРєР° СЂРµР·СѓР»СЊС‚Р°С‚Р°
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р° {post_id}: РћС‚РІРµС‚ Supabase РїСѓСЃС‚ РёР»Рё РЅРµ СЃРѕРґРµСЂР¶РёС‚ РґР°РЅРЅС‹С….")
            last_error_details = f"Status: {result.status_code if hasattr(result, 'status_code') else 'N/A'}"
            raise HTTPException(status_code=500, detail=f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ РїРѕСЃС‚. {last_error_details}")

        updated_post = result.data[0]
        logger.info(f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {telegram_user_id} РѕР±РЅРѕРІРёР» РїРѕСЃС‚: {post_id}")

        # Р’РѕР·РІСЂР°С‰Р°РµРј РґР°РЅРЅС‹Рµ РѕР±РЅРѕРІР»РµРЅРЅРѕРіРѕ РїРѕСЃС‚Р°, РѕР±РѕРіР°С‰РµРЅРЅС‹Рµ РђРљРўРЈРђР›Р¬РќР«РњР РґР°РЅРЅС‹РјРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
        response_data = SavedPostResponse(**updated_post)
        # РџРѕР»СѓС‡Р°РµРј ID РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РёР· РѕР±РЅРѕРІР»РµРЅРЅРѕРіРѕ РїРѕСЃС‚Р° (updated_post),
        # С‚Р°Рє РєР°Рє РѕРЅРѕ РјРѕРіР»Рѕ РёР·РјРµРЅРёС‚СЊСЃСЏ РёР»Рё РѕСЃС‚Р°С‚СЊСЃСЏ РїСЂРµР¶РЅРёРј
        final_image_id = updated_post.get("saved_image_id")

        if final_image_id:
            # Р•СЃР»Рё ID РµСЃС‚СЊ, РїС‹С‚Р°РµРјСЃСЏ РїРѕР»СѓС‡РёС‚СЊ РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РёР· Р‘Р”
            img_data_res = supabase.table("saved_images").select("id, url, preview_url, alt, author, author_url, source").eq("id", final_image_id).maybe_single().execute()
            if img_data_res.data:
                 try: # Р”РѕР±Р°РІР»СЏРµРј try-except РґР»СЏ РјР°РїРїРёРЅРіР°
                     alt_text = img_data_res.data.get("alt_description") or img_data_res.data.get("alt")
                     response_data.selected_image_data = PostImage(
                          id=img_data_res.data.get("id"),
                          url=img_data_res.data.get("url"),
                          preview_url=img_data_res.data.get("preview_url"),
                          alt=alt_text,
                          author=img_data_res.data.get("author"),
                          author_url=img_data_res.data.get("author_url"),
                          source=img_data_res.data.get("source")
                     )
                 except Exception as mapping_err:
                     logger.error(f"РћС€РёР±РєР° РїСЂРё РјР°РїРїРёРЅРіРµ РґР°РЅРЅС‹С… РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РёР· Р‘Р” РґР»СЏ РѕР±РЅРѕРІР»РµРЅРЅРѕРіРѕ РїРѕСЃС‚Р° {post_id}: {mapping_err}")
                     response_data.selected_image_data = None
            else:
                 logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ {final_image_id} РёР· Р‘Р” РґР»СЏ РѕС‚РІРµС‚Р° РЅР° РѕР±РЅРѕРІР»РµРЅРёРµ РїРѕСЃС‚Р° {post_id}")
                 response_data.selected_image_data = None
        else:
            # Р•СЃР»Рё final_image_id РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РІ РѕР±РЅРѕРІР»РµРЅРЅРѕРј РїРѕСЃС‚Рµ, selected_image_data РѕСЃС‚Р°РµС‚СЃСЏ None
            response_data.selected_image_data = None

        return response_data

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р° {post_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Р’РЅСѓС‚СЂРµРЅРЅСЏСЏ РѕС€РёР±РєР° СЃРµСЂРІРµСЂР° РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РїРѕСЃС‚Р°: {str(e)}")

@app.delete("/posts/{post_id}")
async def delete_post(post_id: str, request: Request):
    """РЈРґР°Р»РµРЅРёРµ РїРѕСЃС‚Р°."""
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ СѓРґР°Р»РµРЅРёСЏ РїРѕСЃС‚Р° Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ СѓРґР°Р»РµРЅРёСЏ РїРѕСЃС‚Р° РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")
        
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")
        
        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РїРѕСЃС‚ РїСЂРёРЅР°РґР»РµР¶РёС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ
        post_check = supabase.table("saved_posts").select("id").eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
        if not hasattr(post_check, 'data') or len(post_check.data) == 0:
            logger.warning(f"РџРѕРїС‹С‚РєР° СѓРґР°Р»РёС‚СЊ С‡СѓР¶РѕР№ РёР»Рё РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РёР№ РїРѕСЃС‚: {post_id}")
            raise HTTPException(status_code=404, detail="РџРѕСЃС‚ РЅРµ РЅР°Р№РґРµРЅ РёР»Рё РЅРµС‚ РїСЂР°РІ РЅР° РµРіРѕ СѓРґР°Р»РµРЅРёРµ")
        
        # --- Р”РћР‘РђР’Р›Р•РќРћ: РЈРґР°Р»РµРЅРёРµ СЃРІСЏР·РµР№ РїРµСЂРµРґ СѓРґР°Р»РµРЅРёРµРј РїРѕСЃС‚Р° --- 
        try:
            delete_links_res = supabase.table("post_images").delete().eq("post_id", post_id).execute()
            logger.info(f"РЈРґР°Р»РµРЅРѕ {len(delete_links_res.data) if hasattr(delete_links_res, 'data') else 0} СЃРІСЏР·РµР№ РґР»СЏ СѓРґР°Р»СЏРµРјРѕРіРѕ РїРѕСЃС‚Р° {post_id}")
        except Exception as del_link_err:
            logger.error(f"РћС€РёР±РєР° РїСЂРё СѓРґР°Р»РµРЅРёРё СЃРІСЏР·РµР№ post_images РґР»СЏ РїРѕСЃС‚Р° {post_id} РїРµСЂРµРґ СѓРґР°Р»РµРЅРёРµРј РїРѕСЃС‚Р°: {del_link_err}")
            # РџСЂРѕРґРѕР»Р¶Р°РµРј СѓРґР°Р»РµРЅРёРµ РїРѕСЃС‚Р°, РЅРѕ Р»РѕРіРёСЂСѓРµРј РѕС€РёР±РєСѓ
        # --- РљРћРќР•Р¦ Р”РћР‘РђР’Р›Р•РќРРЇ ---
        
        # РЈРґР°Р»РµРЅРёРµ РёР· Supabase
        result = supabase.table("saved_posts").delete().eq("id", post_id).execute()
        
        # РџСЂРѕРІРµСЂРєР° СЂРµР·СѓР»СЊС‚Р°С‚Р°
        if not hasattr(result, 'data'):
            logger.error(f"РћС€РёР±РєР° РїСЂРё СѓРґР°Р»РµРЅРёРё РїРѕСЃС‚Р°: {result}")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР° РїСЂРё СѓРґР°Р»РµРЅРёРё РїРѕСЃС‚Р°")
            
        logger.info(f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {telegram_user_id} СѓРґР°Р»РёР» РїРѕСЃС‚ {post_id}")
        return {"message": "РџРѕСЃС‚ СѓСЃРїРµС€РЅРѕ СѓРґР°Р»РµРЅ"}
        
    except HTTPException as http_err:
        # РџРµСЂРµС…РІР°С‚С‹РІР°РµРј HTTP РёСЃРєР»СЋС‡РµРЅРёСЏ
        raise http_err
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё СѓРґР°Р»РµРЅРёРё РїРѕСЃС‚Р°: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Р’РЅСѓС‚СЂРµРЅРЅСЏСЏ РѕС€РёР±РєР° СЃРµСЂРІРµСЂР° РїСЂРё СѓРґР°Р»РµРЅРёРё РїРѕСЃС‚Р°: {str(e)}")

# --- РќР°СЃС‚СЂР°РёРІР°РµРј РѕР±СЂР°Р±РѕС‚РєСѓ РІСЃРµС… РїСѓС‚РµР№ SPA РґР»СЏ РѕР±СЃР»СѓР¶РёРІР°РЅРёСЏ СЃС‚Р°С‚РёС‡РµСЃРєРёС… С„Р°Р№Р»РѕРІ (РІ РєРѕРЅС†Рµ С„Р°Р№Р»Р°) ---
@app.get("/{rest_of_path:path}")
async def serve_spa(rest_of_path: str):
    """РћР±СЃР»СѓР¶РёРІР°РµС‚ РІСЃРµ Р·Р°РїСЂРѕСЃС‹ Рє РїСѓС‚СЏРј SPA, РІРѕР·РІСЂР°С‰Р°СЏ index.html"""
    # РџСЂРѕРІРµСЂСЏРµРј, РµСЃС‚СЊ Р»Рё Р·Р°РїСЂРѕС€РµРЅРЅС‹Р№ С„Р°Р№Р»
    if SHOULD_MOUNT_STATIC:
        file_path = os.path.join(static_folder, rest_of_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # Р•СЃР»Рё С„Р°Р№Р» РЅРµ РЅР°Р№РґРµРЅ, РІРѕР·РІСЂР°С‰Р°РµРј index.html РґР»СЏ РїРѕРґРґРµСЂР¶РєРё SPA-СЂРѕСѓС‚РёРЅРіР°
        return FileResponse(os.path.join(static_folder, "index.html"))
    else:
        return {"message": "API СЂР°Р±РѕС‚Р°РµС‚, РЅРѕ СЃС‚Р°С‚РёС‡РµСЃРєРёРµ С„Р°Р№Р»С‹ РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹. РћР±СЂР°С‚РёС‚РµСЃСЊ Рє API РЅР°РїСЂСЏРјСѓСЋ."}

# --- Р¤СѓРЅРєС†РёСЏ РґР»СЏ РіРµРЅРµСЂР°С†РёРё РєР»СЋС‡РµРІС‹С… СЃР»РѕРІ РґР»СЏ РїРѕРёСЃРєР° РёР·РѕР±СЂР°Р¶РµРЅРёР№ ---
async def generate_image_keywords(text: str, topic: str, format_style: str) -> List[str]:
    """Р“РµРЅРµСЂР°С†РёСЏ РєР»СЋС‡РµРІС‹С… СЃР»РѕРІ РґР»СЏ РїРѕРёСЃРєР° РёР·РѕР±СЂР°Р¶РµРЅРёР№ СЃ РїРѕРјРѕС‰СЊСЋ РР."""
    try:
        # Р•СЃР»Рё РЅРµС‚ API-РєР»СЋС‡Р°, РІРµСЂРЅРµРј СЃРїРёСЃРѕРє СЃ С‚РµРјР°С‚РёРєРѕР№ РїРѕСЃС‚Р°
        if not OPENROUTER_API_KEY:
            words = re.findall(r'\b[Р°-СЏРђ-РЇa-zA-Z]{4,}\b', text.lower())
            stop_words = ["Рё", "РІ", "РЅР°", "СЃ", "РїРѕ", "РґР»СЏ", "Р°", "РЅРѕ", "С‡С‚Рѕ", "РєР°Рє", "С‚Р°Рє", "СЌС‚Рѕ"]
            filtered_words = [w for w in words if w not in stop_words]
            
            # Р•СЃР»Рё РµСЃС‚СЊ С‚РµРјР° Рё С„РѕСЂРјР°С‚, РґРѕР±Р°РІР»СЏРµРј РёС…
            result = []
            if topic:
                result.append(topic)
            if format_style:
                result.append(format_style)
                
            # Р”РѕР±Р°РІР»СЏРµРј РЅРµСЃРєРѕР»СЊРєРѕ РЅР°РёР±РѕР»РµРµ С‡Р°СЃС‚Рѕ РІСЃС‚СЂРµС‡Р°СЋС‰РёС…СЃСЏ СЃР»РѕРІ
            word_counts = Counter(filtered_words)
            common_words = [word for word, _ in word_counts.most_common(3)]
            result.extend(common_words)
            
            # Р”РѕР±Р°РІР»СЏРµРј РєРѕРЅС‚РµРєСЃС‚РЅС‹Рµ СЃР»РѕРІР° РґР»СЏ СЂР°Р·РЅРѕРѕР±СЂР°Р·РёСЏ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ
            context_words = ["business", "abstract", "professional", "technology", "creative", "modern"]
            result.extend(random.sample(context_words, 2))
            
            return result
        
        # РРЅРёС†РёР°Р»РёР·РёСЂСѓРµРј РєР»РёРµРЅС‚ OpenAI С‡РµСЂРµР· OpenRouter
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        
        # РЎРѕР·РґР°РµРј РїСЂРѕРјРїС‚ РґР»СЏ РіРµРЅРµСЂР°С†РёРё РєР»СЋС‡РµРІС‹С… СЃР»РѕРІ
        system_prompt = """РўРІРѕСЏ Р·Р°РґР°С‡Р° - СЃРіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ 2-3 СЌС„С„РµРєС‚РёРІРЅС‹С… РєР»СЋС‡РµРІС‹С… СЃР»РѕРІР° РґР»СЏ РїРѕРёСЃРєР° РёР·РѕР±СЂР°Р¶РµРЅРёР№.
        РљР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР° РґРѕР»Р¶РЅС‹ С‚РѕС‡РЅРѕ РѕС‚СЂР°Р¶Р°С‚СЊ С‚РµРјР°С‚РёРєСѓ С‚РµРєСЃС‚Р° Рё Р±С‹С‚СЊ СѓРЅРёРІРµСЂСЃР°Р»СЊРЅС‹РјРё РґР»СЏ РїРѕРёСЃРєР° СЃС‚РѕРєРѕРІС‹С… РёР·РѕР±СЂР°Р¶РµРЅРёР№.
        Р’С‹Р±РёСЂР°Р№ РєРѕСЂРѕС‚РєРёРµ РєРѕРЅРєСЂРµС‚РЅС‹Рµ СЃСѓС‰РµСЃС‚РІРёС‚РµР»СЊРЅС‹Рµ РЅР° Р°РЅРіР»РёР№СЃРєРѕРј СЏР·С‹РєРµ, РґР°Р¶Рµ РµСЃР»Рё С‚РµРєСЃС‚ РЅР° СЂСѓСЃСЃРєРѕРј.
        Р¤РѕСЂРјР°С‚ РѕС‚РІРµС‚Р°: СЃРїРёСЃРѕРє РєР»СЋС‡РµРІС‹С… СЃР»РѕРІ С‡РµСЂРµР· Р·Р°РїСЏС‚СѓСЋ."""
        
        user_prompt = f"""РўРµРєСЃС‚ РїРѕСЃС‚Р°: {text[:300]}...

РўРµРјР°С‚РёРєР° РїРѕСЃС‚Р°: {topic}
Р¤РѕСЂРјР°С‚ РїРѕСЃС‚Р°: {format_style}

Р’С‹РґР°Р№ 2-3 Р»СѓС‡С€РёС… РєР»СЋС‡РµРІС‹С… СЃР»РѕРІР° РЅР° Р°РЅРіР»РёР№СЃРєРѕРј СЏР·С‹РєРµ РґР»СЏ РїРѕРёСЃРєР° РїРѕРґС…РѕРґСЏС‰РёС… РёР·РѕР±СЂР°Р¶РµРЅРёР№. РўРѕР»СЊРєРѕ РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР°, Р±РµР· РѕР±СЉСЏСЃРЅРµРЅРёР№."""
        
        # Р—Р°РїСЂРѕСЃ Рє API
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free", # <--- РР—РњР•РќР•РќРћ РќРђ РќРћР’РЈР® Р‘Р•РЎРџР›РђРўРќРЈР® РњРћР”Р•Р›Р¬
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=100,
            timeout=15,
            extra_headers={
                "HTTP-Referer": "https://content-manager.onrender.com",
                "X-Title": "Smart Content Assistant"
            }
        )
        
        # РџРѕР»СѓС‡Р°РµРј Рё РѕР±СЂР°Р±Р°С‚С‹РІР°РµРј РѕС‚РІРµС‚
        keywords_text = response.choices[0].message.content.strip()
        keywords_list = re.split(r'[,;\n]', keywords_text)
        keywords = [k.strip() for k in keywords_list if k.strip()]
        
        # Р•СЃР»Рё РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР°, РёСЃРїРѕР»СЊР·СѓРµРј Р·Р°РїР°СЃРЅРѕР№ РІР°СЂРёР°РЅС‚
        if not keywords:
            logger.warning("РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР° РѕС‚ API, РёСЃРїРѕР»СЊР·СѓРµРј Р·Р°РїР°СЃРЅРѕР№ РІР°СЂРёР°РЅС‚")
            return [topic, format_style] + random.sample(["business", "abstract", "professional"], 2)
        
        logger.info(f"РЎРіРµРЅРµСЂРёСЂРѕРІР°РЅС‹ РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР° РґР»СЏ РїРѕРёСЃРєР° РёР·РѕР±СЂР°Р¶РµРЅРёР№: {keywords}")
        return keywords
        
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РіРµРЅРµСЂР°С†РёРё РєР»СЋС‡РµРІС‹С… СЃР»РѕРІ РґР»СЏ РїРѕРёСЃРєР° РёР·РѕР±СЂР°Р¶РµРЅРёР№: {e}")
        # Р’ СЃР»СѓС‡Р°Рµ РѕС€РёР±РєРё РІРѕР·РІСЂР°С‰Р°РµРј Р±Р°Р·РѕРІС‹Рµ РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР°
        return [topic, format_style, "concept", "idea"]

# --- Р¤СѓРЅРєС†РёСЏ РґР»СЏ РїРѕРёСЃРєР° РёР·РѕР±СЂР°Р¶РµРЅРёР№ РІ Unsplash ---
async def search_unsplash_images(query: str, count: int = 5, topic: str = "", format_style: str = "", post_text: str = "") -> List[FoundImage]:
    """РџРѕРёСЃРє РёР·РѕР±СЂР°Р¶РµРЅРёР№ РІ Unsplash API СЃ СѓР»СѓС‡С€РµРЅРЅС‹Рј РІС‹Р±РѕСЂРѕРј РєР»СЋС‡РµРІС‹С… СЃР»РѕРІ."""
    # РџСЂРѕРІРµСЂСЏРµРј РЅР°Р»РёС‡РёРµ РєР»СЋС‡Р°
    if not UNSPLASH_ACCESS_KEY:
        logger.warning(f"РџРѕРёСЃРє РёР·РѕР±СЂР°Р¶РµРЅРёР№ РІ Unsplash РЅРµРІРѕР·РјРѕР¶РµРЅ: РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ UNSPLASH_ACCESS_KEY")
        # Р’РѕР·РІСЂР°С‰Р°РµРј Р·Р°РіР»СѓС€РєРё СЃ РёР·РѕР±СЂР°Р¶РµРЅРёСЏРјРё-Р·Р°РїРѕР»РЅРёС‚РµР»СЏРјРё
        placeholder_images = []
        for i in range(min(count, 5)):  # РћРіСЂР°РЅРёС‡РёРІР°РµРј РґРѕ 5 Р·Р°РіР»СѓС€РµРє
            placeholder_images.append(FoundImage(
                id=f"placeholder_{i}",
                source="unsplash",
                preview_url=f"https://via.placeholder.com/150x100?text=Image+{i+1}",
                regular_url=f"https://via.placeholder.com/800x600?text=Unsplash+API+key+required",
                description=f"Placeholder image {i+1}",
                author_name="Demo",
                author_url="https://unsplash.com"
            ))
        return placeholder_images
    
    try:
        # РСЃРїРѕР»СЊР·СѓРµРј РР РґР»СЏ РіРµРЅРµСЂР°С†РёРё Р»СѓС‡С€РёС… РєР»СЋС‡РµРІС‹С… СЃР»РѕРІ
        keywords = []
        if post_text:
            keywords = await generate_image_keywords(post_text, topic, format_style)
        
        # Р•СЃР»Рё РЅРµ СѓРґР°Р»РѕСЃСЊ СЃРіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР° РёР»Рё РёС… РјР°Р»Рѕ, РґРѕР±Р°РІР»СЏРµРј РёСЃС…РѕРґРЅС‹Р№ Р·Р°РїСЂРѕСЃ
        if not keywords or len(keywords) < 2:
            if query:
                keywords.append(query)
            
            # Р”РѕР±Р°РІР»СЏРµРј С‚РµРјСѓ Рё С„РѕСЂРјР°С‚, РµСЃР»Рё РѕРЅРё РµСЃС‚СЊ
            if topic and topic not in keywords:
                keywords.append(topic)
            if format_style and format_style not in keywords:
                keywords.append(format_style)
                
            # Р•СЃР»Рё РІСЃРµ РµС‰Рµ РјР°Р»Рѕ РєР»СЋС‡РµРІС‹С… СЃР»РѕРІ, РґРѕР±Р°РІР»СЏРµРј РєРѕРЅС‚РµРєСЃС‚РЅС‹Рµ
            if len(keywords) < 3:
                context_words = ["business", "abstract", "professional", "technology"]
                keywords.extend(random.sample(context_words, min(2, len(context_words))))
        
        logger.info(f"РС‚РѕРіРѕРІС‹Рµ РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР° РґР»СЏ РїРѕРёСЃРєР°: {keywords}")
        
        unsplash_api_url = f"https://api.unsplash.com/search/photos"
        per_page = min(count * 3, 30) 
        headers = {
            "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}",
            "Accept-Version": "v1"
        }
        
        all_photos = []
        async with httpx.AsyncClient(timeout=15.0) as client: # РЈРІРµР»РёС‡РёРј С‚Р°Р№РјР°СѓС‚
            for keyword in keywords[:3]:
                try:
                    logger.info(f"РџРѕРёСЃРє РёР·РѕР±СЂР°Р¶РµРЅРёР№ РІ Unsplash РїРѕ Р·Р°РїСЂРѕСЃСѓ: {keyword}")
                    response = await client.get(
                        unsplash_api_url,
                        headers=headers,
                        params={"query": keyword, "per_page": per_page}
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"РћС€РёР±РєР° РїСЂРё Р·Р°РїСЂРѕСЃРµ Рє Unsplash API: {response.status_code} {response.text}")
                        continue
                    
                    results = response.json()
                    if 'results' in results and results['results']:
                        all_photos.extend(results['results'])
                    else:
                        logger.warning(f"РќРµС‚ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ РїРѕ Р·Р°РїСЂРѕСЃСѓ '{keyword}'")
                         
                except httpx.ReadTimeout:
                    logger.warning(f"РўР°Р№РјР°СѓС‚ РїСЂРё РїРѕРёСЃРєРµ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕ РєР»СЋС‡РµРІРѕРјСѓ СЃР»РѕРІСѓ '{keyword}'")
                    continue
                except Exception as e:
                    logger.error(f"РћС€РёР±РєР° РїСЂРё РІС‹РїРѕР»РЅРµРЅРёРё Р·Р°РїСЂРѕСЃР° Рє Unsplash РїРѕ РєР»СЋС‡РµРІРѕРјСѓ СЃР»РѕРІСѓ '{keyword}': {e}")
                    continue
        
        if not all_photos:
            logger.warning(f"РќРµ РЅР°Р№РґРµРЅРѕ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕ РІСЃРµРј РєР»СЋС‡РµРІС‹Рј СЃР»РѕРІР°Рј")
            return []
            
        random.shuffle(all_photos)
        selected_photos = all_photos[:count] # Р‘РµСЂРµРј РЅСѓР¶РЅРѕРµ РєРѕР»РёС‡РµСЃС‚РІРѕ *РїРѕСЃР»Рµ* РїРµСЂРµРјРµС€РёРІР°РЅРёСЏ
        
        images = []
        for photo in selected_photos:
            # РџСЂРѕСЃС‚Рѕ С„РѕСЂРјРёСЂСѓРµРј РѕР±СЉРµРєС‚С‹ FoundImage Р±РµР· СЃРѕС…СЂР°РЅРµРЅРёСЏ РІ Р‘Р”
            images.append(FoundImage(
                id=photo['id'],
                source="unsplash",
                preview_url=photo['urls']['small'],
                regular_url=photo['urls']['regular'],
                description=photo.get('description') or photo.get('alt_description') or query,
                author_name=photo['user']['name'],
                author_url=photo['user']['links']['html']
            ))
        
        logger.info(f"РќР°Р№РґРµРЅРѕ Рё РѕС‚РѕР±СЂР°РЅРѕ {len(images)} РёР·РѕР±СЂР°Р¶РµРЅРёР№ РёР· {len(all_photos)} РІ Unsplash РґР»СЏ РїСЂРµРґР»РѕР¶РµРЅРёСЏ")
        return images
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕРёСЃРєРµ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РІ Unsplash: {e}")
        return []

# --- Endpoint РґР»СЏ РіРµРЅРµСЂР°С†РёРё РґРµС‚Р°Р»РµР№ РїРѕСЃС‚Р° ---
@app.post("/generate-post-details", response_model=PostDetailsResponse)
async def generate_post_details(request: Request, req: GeneratePostDetailsRequest):
    """Р“РµРЅРµСЂР°С†РёСЏ РґРµС‚Р°Р»СЊРЅРѕРіРѕ РїРѕСЃС‚Р° РЅР° РѕСЃРЅРѕРІРµ РёРґРµРё, СЃ С‚РµРєСЃС‚РѕРј Рё СЂРµР»РµРІР°РЅС‚РЅС‹РјРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏРјРё."""
    # === РР—РњР•РќР•РќРћ: РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ found_images РІ РЅР°С‡Р°Р»Рµ ===
    found_images = [] 
    channel_name = req.channel_name if hasattr(req, 'channel_name') else ""
    api_error_message = None # Р”РѕР±Р°РІР»СЏРµРј РїРµСЂРµРјРµРЅРЅСѓСЋ РґР»СЏ С…СЂР°РЅРµРЅРёСЏ РѕС€РёР±РєРё API
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ РіРµРЅРµСЂР°С†РёРё РїРѕСЃС‚Р° Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            # РСЃРїРѕР»СЊР·СѓРµРј HTTPException РґР»СЏ РєРѕСЂСЂРµРєС‚РЅРѕРіРѕ РѕС‚РІРµС‚Р°
            raise HTTPException(
                status_code=401, 
                detail="Р”Р»СЏ РіРµРЅРµСЂР°С†РёРё РїРѕСЃС‚РѕРІ РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram"
            )
            
        topic_idea = req.topic_idea
        format_style = req.format_style
        # channel_name СѓР¶Рµ РѕРїСЂРµРґРµР»РµРЅ РІС‹С€Рµ
        
        # РџСЂРѕРІРµСЂРєР° РЅР°Р»РёС‡РёСЏ API РєР»СЋС‡Р°
        if not OPENROUTER_API_KEY:
            logger.warning("Р“РµРЅРµСЂР°С†РёСЏ РґРµС‚Р°Р»РµР№ РїРѕСЃС‚Р° РЅРµРІРѕР·РјРѕР¶РЅР°: РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ OPENROUTER_API_KEY")
            raise HTTPException(
                status_code=503, # Service Unavailable
                detail="API РґР»СЏ РіРµРЅРµСЂР°С†РёРё С‚РµРєСЃС‚Р° РЅРµРґРѕСЃС‚СѓРїРµРЅ"
            )
            
        # РџСЂРѕРІРµСЂРєР° РЅР°Р»РёС‡РёСЏ РёРјРµРЅРё РєР°РЅР°Р»Р° РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РїСЂРёРјРµСЂРѕРІ РїРѕСЃС‚РѕРІ
        post_samples = []
        if channel_name:
            try:
                # РџС‹С‚Р°РµРјСЃСЏ РїРѕР»СѓС‡РёС‚СЊ РїСЂРёРјРµСЂС‹ РїРѕСЃС‚РѕРІ РёР· РёРјРµСЋС‰РµРіРѕСЃСЏ Р°РЅР°Р»РёР·Р° РєР°РЅР°Р»Р°
                channel_data = await get_channel_analysis(request, channel_name)
                if channel_data and "analyzed_posts_sample" in channel_data:
                    post_samples = channel_data["analyzed_posts_sample"]
                    logger.info(f"РџРѕР»СѓС‡РµРЅРѕ {len(post_samples)} РїСЂРёРјРµСЂРѕРІ РїРѕСЃС‚РѕРІ РґР»СЏ РєР°РЅР°Р»Р° @{channel_name}")
            except Exception as e:
                logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ РїСЂРёРјРµСЂС‹ РїРѕСЃС‚РѕРІ РґР»СЏ РєР°РЅР°Р»Р° @{channel_name}: {e}")
                # РџСЂРѕРґРѕР»Р¶Р°РµРј Р±РµР· РїСЂРёРјРµСЂРѕРІ
                pass
                
        # Р¤РѕСЂРјРёСЂСѓРµРј СЃРёСЃС‚РµРјРЅС‹Р№ РїСЂРѕРјРїС‚
        system_prompt = """РўС‹ - РѕРїС‹С‚РЅС‹Р№ РєРѕРЅС‚РµРЅС‚-РјР°СЂРєРµС‚РѕР»РѕРі РґР»СЏ Telegram-РєР°РЅР°Р»РѕРІ.
РўРІРѕСЏ Р·Р°РґР°С‡Р° - СЃРіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ С‚РµРєСЃС‚ РїРѕСЃС‚Р° РЅР° РѕСЃРЅРѕРІРµ РёРґРµРё Рё С„РѕСЂРјР°С‚Р°, РєРѕС‚РѕСЂС‹Р№ Р±СѓРґРµС‚ РіРѕС‚РѕРІ Рє РїСѓР±Р»РёРєР°С†РёРё.

РџРѕСЃС‚ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ:
1. РҐРѕСЂРѕС€Рѕ СЃС‚СЂСѓРєС‚СѓСЂРёСЂРѕРІР°РЅРЅС‹Рј Рё Р»РµРіРєРѕ С‡РёС‚Р°РµРјС‹Рј
2. РЎРѕРѕС‚РІРµС‚СЃС‚РІРѕРІР°С‚СЊ СѓРєР°Р·Р°РЅРЅРѕР№ С‚РµРјРµ/РёРґРµРµ
3. РЎРѕРѕС‚РІРµС‚СЃС‚РІРѕРІР°С‚СЊ СѓРєР°Р·Р°РЅРЅРѕРјСѓ С„РѕСЂРјР°С‚Сѓ/СЃС‚РёР»СЋ
4. РРјРµС‚СЊ РїСЂР°РІРёР»СЊРЅРѕРµ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ РґР»СЏ Telegram (РµСЃР»Рё РЅСѓР¶РЅРѕ - СЃ СЌРјРѕРґР·Рё, Р°Р±Р·Р°С†Р°РјРё, СЃРїРёСЃРєР°РјРё)

РќРµ РёСЃРїРѕР»СЊР·СѓР№ С…СЌС€С‚РµРіРё, РµСЃР»Рё СЌС‚Рѕ РЅРµ СЏРІР»СЏРµС‚СЃСЏ С‡Р°СЃС‚СЊСЋ С„РѕСЂРјР°С‚Р°.
РЎРґРµР»Р°Р№ РїРѕСЃС‚ СѓРЅРёРєР°Р»СЊРЅС‹Рј Рё РёРЅС‚РµСЂРµСЃРЅС‹Рј, СѓС‡РёС‚С‹РІР°СЏ СЃРїРµС†РёС„РёРєСѓ Telegram-Р°СѓРґРёС‚РѕСЂРёРё.
РСЃРїРѕР»СЊР·СѓР№ РїСЂРёРјРµСЂС‹ РїРѕСЃС‚РѕРІ РєР°РЅР°Р»Р°, РµСЃР»Рё РѕРЅРё РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅС‹, С‡С‚РѕР±С‹ СЃРѕС…СЂР°РЅРёС‚СЊ СЃС‚РёР»СЊ."""

        # Р¤РѕСЂРјРёСЂСѓРµРј Р·Р°РїСЂРѕСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
        user_prompt = f"""РЎРѕР·РґР°Р№ РїРѕСЃС‚ РґР»СЏ Telegram-РєР°РЅР°Р»Р° "@{channel_name}" РЅР° С‚РµРјСѓ:
"{topic_idea}"

Р¤РѕСЂРјР°С‚ РїРѕСЃС‚Р°: {format_style}

РќР°РїРёС€Рё РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚ РїРѕСЃС‚Р°, РєРѕС‚РѕСЂС‹Р№ Р±СѓРґРµС‚ РіРѕС‚РѕРІ Рє РїСѓР±Р»РёРєР°С†РёРё.
"""

        # Р•СЃР»Рё РµСЃС‚СЊ РїСЂРёРјРµСЂС‹ РїРѕСЃС‚РѕРІ РєР°РЅР°Р»Р°, РґРѕР±Р°РІР»СЏРµРј РёС…
        if post_samples:
            sample_text = "\n\n".join(post_samples[:3])  # Р‘РµСЂРµРј РґРѕ 3 РїСЂРёРјРµСЂРѕРІ, С‡С‚РѕР±С‹ РЅРµ РїСЂРµРІС‹С€Р°С‚СЊ С‚РѕРєРµРЅС‹
            user_prompt += f"""
            
Р’РѕС‚ РЅРµСЃРєРѕР»СЊРєРѕ РїСЂРёРјРµСЂРѕРІ РїРѕСЃС‚РѕРІ РёР· СЌС‚РѕРіРѕ РєР°РЅР°Р»Р° РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ СЃС‚РёР»СЏ:

{sample_text}
"""

        # РќР°СЃС‚СЂРѕР№РєР° РєР»РёРµРЅС‚Р° OpenAI РґР»СЏ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ OpenRouter
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        
        # === РР—РњР•РќР•РќРћ: Р”РѕР±Р°РІР»РµРЅР° РѕР±СЂР°Р±РѕС‚РєР° РѕС€РёР±РѕРє API ===
        post_text = ""
        try:
            # Р—Р°РїСЂРѕСЃ Рє API
            logger.info(f"РћС‚РїСЂР°РІРєР° Р·Р°РїСЂРѕСЃР° РЅР° РіРµРЅРµСЂР°С†РёСЋ РїРѕСЃС‚Р° РїРѕ РёРґРµРµ: {topic_idea}")
            response = await client.chat.completions.create(
                model="deepseek/deepseek-chat-v3-0324:free", # <--- РР—РњР•РќР•РќРћ РќРђ РќРћР’РЈР® Р‘Р•РЎРџР›РђРўРќРЈР® РњРћР”Р•Р›Р¬
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=850, # === РР—РњР•РќР•РќРћ: РЈРјРµРЅСЊС€РµРЅ Р»РёРјРёС‚ С‚РѕРєРµРЅРѕРІ СЃ 1000 РґРѕ 850 ===
                timeout=60,
                extra_headers={
                    "HTTP-Referer": "https://content-manager.onrender.com",
                    "X-Title": "Smart Content Assistant"
                }
            )
            
            # РџСЂРѕРІРµСЂРєР° РѕС‚РІРµС‚Р° Рё РёР·РІР»РµС‡РµРЅРёРµ С‚РµРєСЃС‚Р°
            if response and response.choices and len(response.choices) > 0 and response.choices[0].message and response.choices[0].message.content:
                post_text = response.choices[0].message.content.strip()
                logger.info(f"РџРѕР»СѓС‡РµРЅ С‚РµРєСЃС‚ РїРѕСЃС‚Р° ({len(post_text)} СЃРёРјРІРѕР»РѕРІ)")
            # === Р”РћР‘РђР’Р›Р•РќРћ: РЇРІРЅР°СЏ РїСЂРѕРІРµСЂРєР° РЅР° РѕС€РёР±РєСѓ РІ РѕС‚РІРµС‚Рµ ===
            elif response and hasattr(response, 'error') and response.error:
                err_details = response.error
                # РџС‹С‚Р°РµРјСЃСЏ РїРѕР»СѓС‡РёС‚СЊ СЃРѕРѕР±С‰РµРЅРёРµ РѕР± РѕС€РёР±РєРµ
                api_error_message = getattr(err_details, 'message', str(err_details)) 
                logger.error(f"OpenRouter API РІРµСЂРЅСѓР» РѕС€РёР±РєСѓ: {api_error_message}")
                post_text = "[РўРµРєСЃС‚ РЅРµ СЃРіРµРЅРµСЂРёСЂРѕРІР°РЅ РёР·-Р·Р° РѕС€РёР±РєРё API]"
            # === РљРћРќР•Р¦ Р”РћР‘РђР’Р›Р•РќРРЇ ===
            else:
                # РћР±С‰РёР№ СЃР»СѓС‡Р°Р№ РЅРµРєРѕСЂСЂРµРєС‚РЅРѕРіРѕ РѕС‚РІРµС‚Р°
                api_error_message = "API РІРµСЂРЅСѓР» РЅРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РёР»Рё РїСѓСЃС‚РѕР№ РѕС‚РІРµС‚"
                logger.error(f"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РёР»Рё РїСѓСЃС‚РѕР№ РѕС‚РІРµС‚ РѕС‚ OpenRouter API. РћС‚РІРµС‚: {response}")
                post_text = "[РўРµРєСЃС‚ РЅРµ СЃРіРµРЅРµСЂРёСЂРѕРІР°РЅ РёР·-Р·Р° РѕС€РёР±РєРё API]"
                
        except Exception as api_error:
            # Р›РѕРІРёРј РѕС€РёР±РєРё HTTP Р·Р°РїСЂРѕСЃР° РёР»Рё РґСЂСѓРіРёРµ РёСЃРєР»СЋС‡РµРЅРёСЏ
            api_error_message = f"РћС€РёР±РєР° СЃРѕРµРґРёРЅРµРЅРёСЏ СЃ API: {str(api_error)}"
            logger.error(f"РћС€РёР±РєР° РїСЂРё Р·Р°РїСЂРѕСЃРµ Рє OpenRouter API: {api_error}", exc_info=True)
            post_text = "[РўРµРєСЃС‚ РЅРµ СЃРіРµРЅРµСЂРёСЂРѕРІР°РЅ РёР·-Р·Р° РѕС€РёР±РєРё API]"
        # === РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ===

        # Р“РµРЅРµСЂРёСЂСѓРµРј РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР° РґР»СЏ РїРѕРёСЃРєР° РёР·РѕР±СЂР°Р¶РµРЅРёР№ РЅР° РѕСЃРЅРѕРІРµ С‚РµРјС‹ Рё С‚РµРєСЃС‚Р°
        image_keywords = await generate_image_keywords(post_text, topic_idea, format_style)
        logger.info(f"РЎРіРµРЅРµСЂРёСЂРѕРІР°РЅС‹ РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР° РґР»СЏ РїРѕРёСЃРєР° РёР·РѕР±СЂР°Р¶РµРЅРёР№: {image_keywords}")
        
        # РџРѕРёСЃРє РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕ РєР»СЋС‡РµРІС‹Рј СЃР»РѕРІР°Рј
        # found_images РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ РІ РЅР°С‡Р°Р»Рµ
        for keyword in image_keywords[:3]:  # РћРіСЂР°РЅРёС‡РёРІР°РµРј РґРѕ 3 РєР»СЋС‡РµРІС‹С… СЃР»РѕРІ РґР»СЏ РїРѕРёСЃРєР°
            try:
                # РџРѕР»СѓС‡Р°РµРј РЅРµ Р±РѕР»РµРµ 5 РёР·РѕР±СЂР°Р¶РµРЅРёР№
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
                
                # Р”РѕР±Р°РІР»СЏРµРј С‚РѕР»СЊРєРѕ СѓРЅРёРєР°Р»СЊРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
                existing_ids = {img.id for img in found_images}
                unique_images = [img for img in images if img.id not in existing_ids]
                found_images.extend(unique_images)
                
                # РћРіСЂР°РЅРёС‡РёРІР°РµРј РґРѕ 5 РёР·РѕР±СЂР°Р¶РµРЅРёР№ РІСЃРµРіРѕ
                if len(found_images) >= 5:
                    found_images = found_images[:5]
                    break
                    
                logger.info(f"РќР°Р№РґРµРЅРѕ {len(unique_images)} СѓРЅРёРєР°Р»СЊРЅС‹С… РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕ РєР»СЋС‡РµРІРѕРјСѓ СЃР»РѕРІСѓ '{keyword}'")
            except Exception as e:
                logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕРёСЃРєРµ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РґР»СЏ РєР»СЋС‡РµРІРѕРіРѕ СЃР»РѕРІР° '{keyword}': {e}")
                continue
        
        # Р•СЃР»Рё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РЅРµ РЅР°Р№РґРµРЅС‹, РїРѕРІС‚РѕСЂСЏРµРј РїРѕРёСЃРє СЃ РѕР±С‰РµР№ РёРґРµРµР№
        if not found_images:
            try:
                found_images = await search_unsplash_images(
                    topic_idea, 
                    count=5,
                    topic=topic_idea,
                    format_style=format_style
                )
                logger.info(f"РќР°Р№РґРµРЅРѕ {len(found_images)} РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕ РѕСЃРЅРѕРІРЅРѕР№ С‚РµРјРµ")
            except Exception as e:
                logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕРёСЃРєРµ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕ РѕСЃРЅРѕРІРЅРѕР№ С‚РµРјРµ: {e}")
                found_images = []
        
        # РџСЂРѕСЃС‚Рѕ РІРѕР·РІСЂР°С‰Р°РµРј РЅР°Р№РґРµРЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ Р±РµР· СЃРѕС…СЂР°РЅРµРЅРёСЏ
        logger.info(f"РџРѕРґРіРѕС‚РѕРІР»РµРЅРѕ {len(found_images)} РїСЂРµРґР»РѕР¶РµРЅРЅС‹С… РёР·РѕР±СЂР°Р¶РµРЅРёР№")
        
        # === РР—РњР•РќР•РќРћ: РџРµСЂРµРґР°С‡Р° СЃРѕРѕР±С‰РµРЅРёСЏ РѕР± РѕС€РёР±РєРµ РІ РѕС‚РІРµС‚Рµ ===
        response_message = f"РЎРіРµРЅРµСЂРёСЂРѕРІР°РЅ РїРѕСЃС‚ СЃ {len(found_images[:IMAGE_RESULTS_COUNT])} РїСЂРµРґР»РѕР¶РµРЅРЅС‹РјРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏРјРё"
        if api_error_message:
            # Р•СЃР»Рё Р±С‹Р»Р° РѕС€РёР±РєР° API, РґРѕР±Р°РІР»СЏРµРј РµРµ РІ СЃРѕРѕР±С‰РµРЅРёРµ РѕС‚РІРµС‚Р°
            response_message = f"РћС€РёР±РєР° РіРµРЅРµСЂР°С†РёРё С‚РµРєСЃС‚Р°: {api_error_message}. РР·РѕР±СЂР°Р¶РµРЅРёР№ РЅР°Р№РґРµРЅРѕ: {len(found_images[:IMAGE_RESULTS_COUNT])}"
        
        return PostDetailsResponse(
            generated_text=post_text, # Р‘СѓРґРµС‚ РїСѓСЃС‚С‹Рј РёР»Рё '[...]' РїСЂРё РѕС€РёР±РєРµ
            found_images=found_images[:IMAGE_RESULTS_COUNT],
            message=response_message, # <--- РЎРѕРѕР±С‰РµРЅРёРµ РІРєР»СЋС‡Р°РµС‚ РѕС€РёР±РєСѓ API
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
        # === РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ===
                
    except HTTPException as http_err:
        # РџРµСЂРµС…РІР°С‚С‹РІР°РµРј HTTPException, С‡С‚РѕР±С‹ РѕРЅРё РЅРµ РїРѕРїР°РґР°Р»Рё РІ РѕР±С‰РёР№ Exception
        raise http_err
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РіРµРЅРµСЂР°С†РёРё РґРµС‚Р°Р»РµР№ РїРѕСЃС‚Р°: {e}")
        traceback.print_exc() # РџРµС‡Р°С‚Р°РµРј traceback РґР»СЏ РґРёР°РіРЅРѕСЃС‚РёРєРё
        # === РР—РњР•РќР•РќРћ: РСЃРїРѕР»СЊР·СѓРµРј HTTPException РґР»СЏ РѕС‚РІРµС‚Р° ===
        raise HTTPException(
            status_code=500,
            detail=f"Р’РЅСѓС‚СЂРµРЅРЅСЏСЏ РѕС€РёР±РєР° СЃРµСЂРІРµСЂР° РїСЂРё РіРµРЅРµСЂР°С†РёРё РґРµС‚Р°Р»РµР№ РїРѕСЃС‚Р°: {str(e)}"
        )
        # === РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ===

# --- Р¤СѓРЅРєС†РёСЏ РґР»СЏ РёСЃРїСЂР°РІР»РµРЅРёСЏ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ РІ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёС… РёРґРµСЏС… ---
async def fix_existing_ideas_formatting():
    """РСЃРїСЂР°РІР»СЏРµС‚ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ РІ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёС… РёРґРµСЏС…."""
    if not supabase:
        logger.error("РќРµРІРѕР·РјРѕР¶РЅРѕ РёСЃРїСЂР°РІРёС‚СЊ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ: РєР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
        return
    
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ РІСЃРµС… РёРґРµР№
        result = supabase.table("suggested_ideas").select("id,topic_idea,format_style").execute()
        
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.info("РќРµС‚ РёРґРµР№ РґР»СЏ РёСЃРїСЂР°РІР»РµРЅРёСЏ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ")
            return
        
        fixed_count = 0
        for idea in result.data:
            original_topic = idea.get("topic_idea", "")
            original_format = idea.get("format_style", "")
            
            # РћС‡РёС‰Р°РµРј С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ
            cleaned_topic = clean_text_formatting(original_topic)
            cleaned_format = clean_text_formatting(original_format)
            
            # Р•СЃР»Рё С‚РµРєСЃС‚ РёР·РјРµРЅРёР»СЃСЏ, РѕР±РЅРѕРІР»СЏРµРј Р·Р°РїРёСЃСЊ
            if cleaned_topic != original_topic or cleaned_format != original_format:
                supabase.table("suggested_ideas").update({
                    "topic_idea": cleaned_topic,
                    "format_style": cleaned_format
                }).eq("id", idea["id"]).execute()
                fixed_count += 1
        
        logger.info(f"РСЃРїСЂР°РІР»РµРЅРѕ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ РІ {fixed_count} РёРґРµСЏС…")
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РёСЃРїСЂР°РІР»РµРЅРёРё С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ: {e}")

# --- Р—Р°РїСѓСЃРє РёСЃРїСЂР°РІР»РµРЅРёСЏ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ РїСЂРё СЃС‚Р°СЂС‚Рµ СЃРµСЂРІРµСЂР° ---
@app.on_event("startup")
async def startup_event():
    """Р—Р°РїСѓСЃРє РѕР±СЃР»СѓР¶РёРІР°СЋС‰РёС… РїСЂРѕС†РµСЃСЃРѕРІ РїСЂРё СЃС‚Р°СЂС‚Рµ РїСЂРёР»РѕР¶РµРЅРёСЏ."""
    logger.info("Р—Р°РїСѓСЃРє РѕР±СЃР»СѓР¶РёРІР°СЋС‰РёС… РїСЂРѕС†РµСЃСЃРѕРІ...")
    
    # РџСЂРѕРІРµСЂСЏРµРј Рё Р»РѕРіРёСЂСѓРµРј РЅР°Р»РёС‡РёРµ РїРµСЂРµРјРµРЅРЅС‹С… РѕРєСЂСѓР¶РµРЅРёСЏ (Р·Р°РјР°СЃРєРёСЂРѕРІР°РЅРЅС‹Рµ РґР»СЏ Р±РµР·РѕРїР°СЃРЅРѕСЃС‚Рё)
    supabase_url = os.getenv("SUPABASE_URL")
    database_url = os.getenv("DATABASE_URL")
    render_database_url = os.getenv("RENDER_DATABASE_URL")
    
    # Р›РѕРіРёСЂСѓРµРј РґРѕСЃС‚СѓРїРЅС‹Рµ РїРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ (Р·Р°РјР°СЃРєРёСЂРѕРІР°РЅРЅС‹Рµ)
    if supabase_url:
        masked_url = supabase_url[:10] + "..." + supabase_url[-5:] if len(supabase_url) > 15 else "***"
        logger.info(f"РќР°Р№РґРµРЅР° РїРµСЂРµРјРµРЅРЅР°СЏ SUPABASE_URL: {masked_url}")
    if database_url:
        masked_url = database_url[:10] + "..." + database_url[-5:] if len(database_url) > 15 else "***" 
        logger.info(f"РќР°Р№РґРµРЅР° РїРµСЂРµРјРµРЅРЅР°СЏ DATABASE_URL: {masked_url}")
    if render_database_url:
        masked_url = render_database_url[:10] + "..." + render_database_url[-5:] if len(render_database_url) > 15 else "***"
        logger.info(f"РќР°Р№РґРµРЅР° РїРµСЂРµРјРµРЅРЅР°СЏ RENDER_DATABASE_URL: {masked_url}")
    
    # РџСЂРѕРІРµСЂСЏРµРј РЅР°Р»РёС‡РёРµ РїРµСЂРµРјРµРЅРЅС‹С… РѕРєСЂСѓР¶РµРЅРёСЏ
    db_url = supabase_url or database_url or render_database_url
    if not db_url:
        logger.error("РћС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ РїРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ SUPABASE_URL, DATABASE_URL Рё RENDER_DATABASE_URL!")
        # РџСЂРѕРґРѕР»Р¶Р°РµРј СЂР°Р±РѕС‚Сѓ РїСЂРёР»РѕР¶РµРЅРёСЏ СЃ РїСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµРј
    else:
        # РџСЂРѕРІРµСЂСЏРµРј С„РѕСЂРјР°С‚ URL Рё Р»РѕРіРёСЂСѓРµРј РµРіРѕ
        if db_url.startswith('https://'):
            logger.info(f"URL Р±Р°Р·С‹ РґР°РЅРЅС‹С… РёРјРµРµС‚ С„РѕСЂРјР°С‚ https:// - Р±СѓРґРµС‚ РїСЂРµРѕР±СЂР°Р·РѕРІР°РЅ РІ postgresql://")
        elif db_url.startswith('postgresql://') or db_url.startswith('postgres://'):
            logger.info(f"URL Р±Р°Р·С‹ РґР°РЅРЅС‹С… РёРјРµРµС‚ РїСЂР°РІРёР»СЊРЅС‹Р№ С„РѕСЂРјР°С‚ postgresql://")
        else:
            logger.warning(f"URL Р±Р°Р·С‹ РґР°РЅРЅС‹С… РёРјРµРµС‚ РЅРµРёР·РІРµСЃС‚РЅС‹Р№ С„РѕСЂРјР°С‚! РќР°С‡Р°Р»Рѕ: {db_url[:10]}...")
    
    # РџСЂРѕРІРµСЂРєР° Рё РґРѕР±Р°РІР»РµРЅРёРµ РЅРµРґРѕСЃС‚Р°СЋС‰РёС… СЃС‚РѕР»Р±С†РѕРІ (РѕСЃС‚Р°РІР»СЏРµРј СЃСѓС‰РµСЃС‚РІСѓСЋС‰СѓСЋ Р»РѕРіРёРєСѓ)
    if supabase:
        if not await check_db_tables():
            logger.error("РћС€РёР±РєР° РїСЂРё РїСЂРѕРІРµСЂРєРµ С‚Р°Р±Р»РёС† РІ Р±Р°Р·Рµ РґР°РЅРЅС‹С…!")
            # РџСЂРѕРґРѕР»Р¶Р°РµРј СЂР°Р±РѕС‚Сѓ РїСЂРёР»РѕР¶РµРЅРёСЏ РґР°Р¶Рµ РїСЂРё РѕС€РёР±РєРµ
        else:
            logger.info("РџСЂРѕРІРµСЂРєР° С‚Р°Р±Р»РёС† Р±Р°Р·С‹ РґР°РЅРЅС‹С… Р·Р°РІРµСЂС€РµРЅР° СѓСЃРїРµС€РЅРѕ.")
    else:
        logger.warning("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ, РїСЂРѕРІРµСЂРєР° С‚Р°Р±Р»РёС† РїСЂРѕРїСѓС‰РµРЅР°.")
    
    # РСЃРїСЂР°РІР»РµРЅРёРµ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ РІ JSON РїРѕР»СЏС…
    # await fix_formatting_in_json_fields() # РћС‚РєР»СЋС‡Р°РµРј РІСЂРµРјРµРЅРЅРѕ, РµСЃР»Рё РЅРµ РЅСѓР¶РЅРѕ
    
    logger.info("РћР±СЃР»СѓР¶РёРІР°СЋС‰РёРµ РїСЂРѕС†РµСЃСЃС‹ Р·Р°РїСѓС‰РµРЅС‹ СѓСЃРїРµС€РЅРѕ")

    # --- Р”РћР‘РђР’Р›Р•РќРћ: Р’С‹Р·РѕРІ fix_schema РїСЂРё СЃС‚Р°СЂС‚Рµ --- 
    try:
        fix_result = await fix_schema()
        logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ РїСЂРѕРІРµСЂРєРё/РёСЃРїСЂР°РІР»РµРЅРёСЏ СЃС…РµРјС‹ РїСЂРё СЃС‚Р°СЂС‚Рµ: {fix_result}")
        if not fix_result.get("success"):
            logger.error("РћС€РёР±РєР° РїСЂРё РїСЂРѕРІРµСЂРєРµ/РёСЃРїСЂР°РІР»РµРЅРёРё СЃС…РµРјС‹ Р‘Р” РїСЂРё Р·Р°РїСѓСЃРєРµ!")
            # Р РµС€РёС‚Рµ, СЃР»РµРґСѓРµС‚ Р»Рё РїСЂРµСЂС‹РІР°С‚СЊ Р·Р°РїСѓСЃРє РёР»Рё РЅРµС‚.
            # РџРѕРєР° РїСЂРѕРґРѕР»Р¶Р°РµРј СЂР°Р±РѕС‚Сѓ.
    except Exception as schema_fix_error:
        logger.error(f"РСЃРєР»СЋС‡РµРЅРёРµ РїСЂРё РІС‹Р·РѕРІРµ fix_schema РІРѕ РІСЂРµРјСЏ СЃС‚Р°СЂС‚Р°: {schema_fix_error}", exc_info=True)
    # --- РљРћРќР•Р¦ Р”РћР‘РђР’Р›Р•РќРРЇ ---

# --- Р¤СѓРЅРєС†РёСЏ РґР»СЏ РёСЃРїСЂР°РІР»РµРЅРёСЏ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ РІ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёС… РїРѕСЃС‚Р°С… ---
async def fix_existing_posts_formatting():
    """РСЃРїСЂР°РІР»СЏРµС‚ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ РІ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёС… РїРѕСЃС‚Р°С…."""
    if not supabase:
        logger.error("РќРµРІРѕР·РјРѕР¶РЅРѕ РёСЃРїСЂР°РІРёС‚СЊ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ РїРѕСЃС‚РѕРІ: РєР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
        return
    
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ РІСЃРµС… РїРѕСЃС‚РѕРІ
        result = supabase.table("saved_posts").select("id,topic_idea,format_style,final_text").execute()
        
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.info("РќРµС‚ РїРѕСЃС‚РѕРІ РґР»СЏ РёСЃРїСЂР°РІР»РµРЅРёСЏ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ")
            return
        
        fixed_count = 0
        for post in result.data:
            original_topic = post.get("topic_idea", "")
            original_format = post.get("format_style", "")
            original_text = post.get("final_text", "")
            
            # РћС‡РёС‰Р°РµРј С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ
            cleaned_topic = clean_text_formatting(original_topic)
            cleaned_format = clean_text_formatting(original_format)
            cleaned_text = clean_text_formatting(original_text)
            
            # Р•СЃР»Рё С‚РµРєСЃС‚ РёР·РјРµРЅРёР»СЃСЏ, РѕР±РЅРѕРІР»СЏРµРј Р·Р°РїРёСЃСЊ
            if (cleaned_topic != original_topic or 
                cleaned_format != original_format or 
                cleaned_text != original_text):
                supabase.table("saved_posts").update({
                    "topic_idea": cleaned_topic,
                    "format_style": cleaned_format,
                    "final_text": cleaned_text
                }).eq("id", post["id"]).execute()
                fixed_count += 1
        
        logger.info(f"РСЃРїСЂР°РІР»РµРЅРѕ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ РІ {fixed_count} РїРѕСЃС‚Р°С…")
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РёСЃРїСЂР°РІР»РµРЅРёРё С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ РїРѕСЃС‚РѕРІ: {e}")

# --- Р­РЅРґРїРѕРёРЅС‚ РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ ---
@app.post("/save-image", response_model=Dict[str, Any])
async def save_image(request: Request, image_data: Dict[str, Any]):
    """РЎРѕС…СЂР°РЅРµРЅРёРµ РёРЅС„РѕСЂРјР°С†РёРё РѕР± РёР·РѕР±СЂР°Р¶РµРЅРёРё РІ Р±Р°Р·Сѓ РґР°РЅРЅС‹С…."""
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ СЃРѕС…СЂР°РЅРµРЅРёСЏ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")
        
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")
        
        # Р”РѕР±Р°РІР»СЏРµРј РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Рє РґР°РЅРЅС‹Рј РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
        image_data["user_id"] = int(telegram_user_id)
        
        # РџСЂРѕРІРµСЂСЏРµРј РЅР°Р»РёС‡РёРµ РѕР±СЏР·Р°С‚РµР»СЊРЅС‹С… РїРѕР»РµР№
        if not image_data.get("url"):
            raise HTTPException(status_code=400, detail="URL РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РѕР±СЏР·Р°С‚РµР»РµРЅ")
        
        # Р•СЃР»Рё РЅРµ РїРµСЂРµРґР°РЅ id, РіРµРЅРµСЂРёСЂСѓРµРј РµРіРѕ
        if not image_data.get("id"):
            image_data["id"] = f"img_{str(uuid.uuid4())}"
        
        # Р•СЃР»Рё РЅРµ РїРµСЂРµРґР°РЅ preview_url, РёСЃРїРѕР»СЊР·СѓРµРј РѕСЃРЅРѕРІРЅРѕР№ URL
        if not image_data.get("preview_url"):
            image_data["preview_url"] = image_data["url"]
        
        # Р”РѕР±Р°РІР»СЏРµРј timestamp
        image_data["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # РџСЂРѕРІРµСЂСЏРµРј, СЃСѓС‰РµСЃС‚РІСѓРµС‚ Р»Рё СѓР¶Рµ С‚Р°РєРѕРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ
        image_check = supabase.table("saved_images").select("id").eq("url", image_data["url"]).execute()
        
        if hasattr(image_check, 'data') and len(image_check.data) > 0:
            # РР·РѕР±СЂР°Р¶РµРЅРёРµ СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚, РІРѕР·РІСЂР°С‰Р°РµРј РµРіРѕ id
            return {"id": image_check.data[0]["id"], "status": "exists"}
        
        # РЎРѕС…СЂР°РЅСЏРµРј РёРЅС„РѕСЂРјР°С†РёСЋ РѕР± РёР·РѕР±СЂР°Р¶РµРЅРёРё
        result = supabase.table("saved_images").insert(image_data).execute()
        
        # РџСЂРѕРІРµСЂРєР° СЂРµР·СѓР»СЊС‚Р°С‚Р°
        if not hasattr(result, 'data') or len(result.data) == 0:
            logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {result}")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ")
        
        logger.info(f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {telegram_user_id} СЃРѕС…СЂР°РЅРёР» РёР·РѕР±СЂР°Р¶РµРЅРёРµ {image_data.get('id')}")
        return result.data[0]
        
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Р­РЅРґРїРѕРёРЅС‚ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РІСЃРµС… РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ ---
@app.get("/images", response_model=List[Dict[str, Any]])
async def get_user_images(request: Request, limit: int = 20):
    """РџРѕР»СѓС‡РµРЅРёРµ РІСЃРµС… СЃРѕС…СЂР°РЅРµРЅРЅС‹С… РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ."""
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ РїРѕР»СѓС‡РµРЅРёСЏ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")
        
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")
        
        # РџРѕР»СѓС‡Р°РµРј РІСЃРµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
        result = supabase.table("saved_images").select("*").eq("user_id", int(telegram_user_id)).limit(limit).execute()
        
        # Р•СЃР»Рё РІ СЂРµР·СѓР»СЊС‚Р°С‚Рµ РµСЃС‚СЊ РґР°РЅРЅС‹Рµ, РІРѕР·РІСЂР°С‰Р°РµРј РёС…
        if hasattr(result, 'data'):
            logger.info(f"РџРѕР»СѓС‡РµРЅРѕ {len(result.data)} РёР·РѕР±СЂР°Р¶РµРЅРёР№ РґР»СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {telegram_user_id}")
            return result.data
        
        return []
        
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- РќРћР’Р«Р™ Р­РќР”РџРћРРќРў: РџРѕР»СѓС‡РµРЅРёРµ РѕРґРЅРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РїРѕ ID --- 
@app.get("/images/{image_id}", response_model=Dict[str, Any])
async def get_image_by_id(request: Request, image_id: str):
    """РџРѕР»СѓС‡РµРЅРёРµ РґР°РЅРЅС‹С… РѕРґРЅРѕРіРѕ СЃРѕС…СЂР°РЅРµРЅРЅРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РїРѕ РµРіРѕ ID."""
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ РїРѕР»СѓС‡РµРЅРёСЏ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РїРѕ ID Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ")
        
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")
        
        # РџРѕР»СѓС‡Р°РµРј РёР·РѕР±СЂР°Р¶РµРЅРёРµ РїРѕ ID, РїСЂРѕРІРµСЂСЏСЏ РїСЂРёРЅР°РґР»РµР¶РЅРѕСЃС‚СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ
        result = supabase.table("saved_images").select("*").eq("id", image_id).eq("user_id", int(telegram_user_id)).maybe_single().execute()
        
        # Р•СЃР»Рё РёР·РѕР±СЂР°Р¶РµРЅРёРµ РЅР°Р№РґРµРЅРѕ, РІРѕР·РІСЂР°С‰Р°РµРј РµРіРѕ
        if result.data:
            logger.info(f"РџРѕР»СѓС‡РµРЅРѕ РёР·РѕР±СЂР°Р¶РµРЅРёРµ {image_id} РґР»СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {telegram_user_id}")
            return result.data
        else:
            logger.warning(f"РР·РѕР±СЂР°Р¶РµРЅРёРµ {image_id} РЅРµ РЅР°Р№РґРµРЅРѕ РёР»Рё РЅРµ РїСЂРёРЅР°РґР»РµР¶РёС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ {telegram_user_id}")
            raise HTTPException(status_code=404, detail="РР·РѕР±СЂР°Р¶РµРЅРёРµ РЅРµ РЅР°Р№РґРµРЅРѕ РёР»Рё РґРѕСЃС‚СѓРї Р·Р°РїСЂРµС‰РµРЅ")
            
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РїРѕ ID {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Р­РЅРґРїРѕРёРЅС‚ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕСЃС‚Р° ---
@app.get("/post-images/{post_id}", response_model=List[Dict[str, Any]])
async def get_post_images(request: Request, post_id: str):
    """РџРѕР»СѓС‡РµРЅРёРµ РёР·РѕР±СЂР°Р¶РµРЅРёР№, СЃРІСЏР·Р°РЅРЅС‹С… СЃ РїРѕСЃС‚РѕРј."""
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ РїРѕР»СѓС‡РµРЅРёСЏ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕСЃС‚Р° Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕСЃС‚Р° РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")
        
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")
        
        # РџСЂРѕРІРµСЂСЏРµРј СЃСѓС‰РµСЃС‚РІРѕРІР°РЅРёРµ РїРѕСЃС‚Р° Рё РїСЂРёРЅР°РґР»РµР¶РЅРѕСЃС‚СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ
        post_check = supabase.table("saved_posts").select("id").eq("id", post_id).eq("user_id", int(telegram_user_id)).execute()
        
        if not hasattr(post_check, 'data') or len(post_check.data) == 0:
            logger.warning(f"РџРѕРїС‹С‚РєР° РїРѕР»СѓС‡РёС‚СЊ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ С‡СѓР¶РѕРіРѕ РёР»Рё РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРіРѕ РїРѕСЃС‚Р° {post_id}")
            raise HTTPException(status_code=404, detail="РџРѕСЃС‚ РЅРµ РЅР°Р№РґРµРЅ РёР»Рё РІС‹ РЅРµ РёРјРµРµС‚Рµ Рє РЅРµРјСѓ РґРѕСЃС‚СѓРїР°")
        
        # РџРѕР»СѓС‡Р°РµРј РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РїРѕСЃС‚Р° С‡РµСЂРµР· С‚Р°Р±Р»РёС†Сѓ СЃРІСЏР·РµР№
        result = supabase.table("post_images").select("saved_images(*)").eq("post_id", post_id).execute()
        
        # Р•СЃР»Рё РІ СЂРµР·СѓР»СЊС‚Р°С‚Рµ РµСЃС‚СЊ РґР°РЅРЅС‹Рµ Рё РѕРЅРё РёРјРµСЋС‚ РЅСѓР¶РЅСѓСЋ СЃС‚СЂСѓРєС‚СѓСЂСѓ, РёР·РІР»РµРєР°РµРј РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
        images = []
        if hasattr(result, 'data') and len(result.data) > 0:
            for item in result.data:
                if "saved_images" in item and item["saved_images"]:
                    images.append(item["saved_images"])
        
        # Р•СЃР»Рё РёР·РѕР±СЂР°Р¶РµРЅРёР№ РЅРµ РЅР°Р№РґРµРЅРѕ, РїСЂРѕРІРµСЂСЏРµРј, РµСЃС‚СЊ Р»Рё РїСЂСЏРјР°СЏ СЃСЃС‹Р»РєР° РІ РґР°РЅРЅС‹С… РїРѕСЃС‚Р°
        if not images:
            post_data = supabase.table("saved_posts").select("image_url").eq("id", post_id).execute()
            if hasattr(post_data, 'data') and len(post_data.data) > 0 and post_data.data[0].get("image_url"):
                images.append({
                    "id": f"direct_img_{post_id}",
                    "url": post_data.data[0]["image_url"],
                    "preview_url": post_data.data[0]["image_url"],
                    "alt": "РР·РѕР±СЂР°Р¶РµРЅРёРµ РїРѕСЃС‚Р°",
                    "source": "direct"
                })
        
        return images
        
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕСЃС‚Р°: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Р­РЅРґРїРѕРёРЅС‚ РґР»СЏ РїСЂРѕРєСЃРёСЂРѕРІР°РЅРёСЏ РёР·РѕР±СЂР°Р¶РµРЅРёР№ С‡РµСЂРµР· РЅР°С€ СЃРµСЂРІРµСЂ ---
@app.get("/image-proxy/{image_id}")
async def proxy_image(request: Request, image_id: str, size: Optional[str] = None):
    """
    РџСЂРѕРєСЃРёСЂСѓРµС‚ РёР·РѕР±СЂР°Р¶РµРЅРёРµ С‡РµСЂРµР· РЅР°С€ СЃРµСЂРІРµСЂ, СЃРєСЂС‹РІР°СЏ РёСЃС…РѕРґРЅС‹Р№ URL.
    
    Args:
        image_id: ID РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РІ Р±Р°Р·Рµ РґР°РЅРЅС‹С…
        size: СЂР°Р·РјРµСЂ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ (small, medium, large)
    """
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ telegram_user_id РёР· Р·Р°РіРѕР»РѕРІРєРѕРІ
        telegram_user_id = request.headers.get("X-Telegram-User-Id")
        if not telegram_user_id:
            logger.warning("Р—Р°РїСЂРѕСЃ РїСЂРѕРєСЃРёСЂРѕРІР°РЅРёСЏ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
            raise HTTPException(status_code=401, detail="Р”Р»СЏ РґРѕСЃС‚СѓРїР° Рє РёР·РѕР±СЂР°Р¶РµРЅРёСЋ РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")
        
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")
        
        # РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ РѕР± РёР·РѕР±СЂР°Р¶РµРЅРёРё РёР· Р±Р°Р·С‹
        image_data = supabase.table("saved_images").select("*").eq("id", image_id).execute()
        
        if not hasattr(image_data, 'data') or len(image_data.data) == 0:
            logger.warning(f"РР·РѕР±СЂР°Р¶РµРЅРёРµ СЃ ID {image_id} РЅРµ РЅР°Р№РґРµРЅРѕ")
            raise HTTPException(status_code=404, detail="РР·РѕР±СЂР°Р¶РµРЅРёРµ РЅРµ РЅР°Р№РґРµРЅРѕ")
        
        image = image_data.data[0]
        
        # РџРѕР»СѓС‡Р°РµРј URL РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
        image_url = image.get("url")
        if not image_url:
            logger.error(f"Р”Р»СЏ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ {image_id} РЅРµ СѓРєР°Р·Р°РЅ URL")
            raise HTTPException(status_code=500, detail="Р”Р°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РїРѕРІСЂРµР¶РґРµРЅС‹")
        
        # Р’С‹РїРѕР»РЅСЏРµРј Р·Р°РїСЂРѕСЃ Рє РІРЅРµС€РЅРµРјСѓ СЃРµСЂРІРёСЃСѓ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    logger.error(f"РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ {image_id} РїРѕ URL {image_url}: {response.status}")
                    raise HTTPException(status_code=response.status, detail="РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ РёР·РѕР±СЂР°Р¶РµРЅРёРµ")
                
                # РћРїСЂРµРґРµР»СЏРµРј С‚РёРї РєРѕРЅС‚РµРЅС‚Р°
                content_type = response.headers.get("Content-Type", "image/jpeg")
                
                # РџРѕР»СѓС‡Р°РµРј СЃРѕРґРµСЂР¶РёРјРѕРµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
                image_content = await response.read()
                
                # Р’РѕР·РІСЂР°С‰Р°РµРј РёР·РѕР±СЂР°Р¶РµРЅРёРµ РєР°Рє РѕС‚РІРµС‚
                return Response(content=image_content, media_type=content_type)
    
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РїСЂРѕРєСЃРёСЂРѕРІР°РЅРёРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Р­РЅРґРїРѕРёРЅС‚ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РІСЃРµС… РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ ---
@app.get("/user-images", response_model=List[Dict[str, Any]])
async def get_user_images_legacy(request: Request, limit: int = 20):
    """
    РџРѕР»СѓС‡РµРЅРёРµ РІСЃРµС… РёР·РѕР±СЂР°Р¶РµРЅРёР№ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ (СѓСЃС‚Р°СЂРµРІС€РёР№ СЌРЅРґРїРѕРёРЅС‚).
    РџРµСЂРµР°РґСЂРµСЃСѓРµС‚ РЅР° РЅРѕРІС‹Р№ СЌРЅРґРїРѕРёРЅС‚ /images.
    """
    return await get_user_images(request, limit)

@app.post("/save-suggested-idea", response_model=Dict[str, Any])
async def save_suggested_idea(idea_data: Dict[str, Any], request: Request):
    telegram_user_id = request.headers.get("x-telegram-user-id")
    if not telegram_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not supabase:
        logging.error("Supabase client not initialized")
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        # РћС‡РёС‰Р°РµРј С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ С‚РµРєСЃС‚Р° РїРµСЂРµРґ СЃРѕС…СЂР°РЅРµРЅРёРµРј
        if "topic_idea" in idea_data:
            idea_data["topic_idea"] = clean_text_formatting(idea_data["topic_idea"])
        
        # Р“РµРЅРµСЂРёСЂСѓРµРј СѓРЅРёРєР°Р»СЊРЅС‹Р№ ID РґР»СЏ РёРґРµРё
        idea_id = f"idea_{int(time.time())}_{random.randint(1000, 9999)}"
        idea_data["id"] = idea_id
        idea_data["user_id"] = int(telegram_user_id)
        idea_data["created_at"] = datetime.now().isoformat()
        
        # РЎРѕС…СЂР°РЅСЏРµРј РёРґРµСЋ РІ Р±Р°Р·Рµ РґР°РЅРЅС‹С…
        result = supabase.table("suggested_ideas").insert(idea_data).execute()
        
        if hasattr(result, 'data') and result.data:
            logging.info(f"Saved idea with ID {idea_id}")
            return {"id": idea_id, "message": "Idea saved successfully"}
        else:
            logging.error(f"Failed to save idea: {result}")
            raise HTTPException(status_code=500, detail="Failed to save idea")
    except Exception as e:
        logging.error(f"Error saving idea: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

async def check_db_tables():
    """РџСЂРѕРІРµСЂРєР° Рё СЃРѕР·РґР°РЅРёРµ РЅРµРѕР±С…РѕРґРёРјС‹С… С‚Р°Р±Р»РёС† РІ Р±Р°Р·Рµ РґР°РЅРЅС‹С…."""
    try:
        # РџРѕР»СѓС‡Р°РµРј URL Р±Р°Р·С‹ РґР°РЅРЅС‹С…
        db_url = os.getenv("SUPABASE_URL") or os.getenv("DATABASE_URL")
        if not db_url:
            logger.error("РћС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ SUPABASE_URL Рё DATABASE_URL РІ РїРµСЂРµРјРµРЅРЅС‹С… РѕРєСЂСѓР¶РµРЅРёСЏ РїСЂРё РїСЂРѕРІРµСЂРєРµ С‚Р°Р±Р»РёС† Р‘Р”")
            return False
        
        # РџСЂРѕРІРµСЂСЏРµРј РµСЃС‚СЊ Р»Рё РєР»РёРµРЅС‚ Supabase
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ РґР»СЏ РїСЂРѕРІРµСЂРєРё С‚Р°Р±Р»РёС†")
            return False
            
        # Р”Р»СЏ РїСЂРѕРІРµСЂРєРё РїСЂРѕСЃС‚Рѕ Р·Р°РїСЂР°С€РёРІР°РµРј РѕРґРЅСѓ СЃС‚СЂРѕРєСѓ РёР· С‚Р°Р±Р»РёС†С‹, С‡С‚РѕР±С‹ СѓР±РµРґРёС‚СЊСЃСЏ, С‡С‚Рѕ СЃРѕРµРґРёРЅРµРЅРёРµ СЂР°Р±РѕС‚Р°РµС‚
        try:
        result = supabase.table("suggested_ideas").select("id").limit(1).execute()
        logger.info("РўР°Р±Р»РёС†Р° suggested_ideas СЃСѓС‰РµСЃС‚РІСѓРµС‚ Рё РґРѕСЃС‚СѓРїРЅР°.")
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РїСЂРё РїСЂРѕРІРµСЂРєРµ СЃРѕРµРґРёРЅРµРЅРёСЏ СЃ Supabase: {e}")
            return False
        
        # РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРѕРµ РґРѕР±Р°РІР»РµРЅРёРµ РЅРµРґРѕСЃС‚Р°СЋС‰РёС… СЃС‚РѕР»Р±С†РѕРІ
        try:
            move_temp_files.add_missing_columns()
            logger.info("РџСЂРѕРІРµСЂРєР° Рё РґРѕР±Р°РІР»РµРЅРёРµ РЅРµРґРѕСЃС‚Р°СЋС‰РёС… СЃС‚РѕР»Р±С†РѕРІ РІС‹РїРѕР»РЅРµРЅС‹.")
            
            # РЇРІРЅРѕРµ РґРѕР±Р°РІР»РµРЅРёРµ СЃС‚РѕР»Р±С†Р° updated_at РІ С‚Р°Р±Р»РёС†Сѓ channel_analysis Рё РѕР±РЅРѕРІР»РµРЅРёРµ РєСЌС€Р° СЃС…РµРјС‹
            try:
                # РџРѕР»СѓС‡РµРЅРёРµ URL Рё РєР»СЋС‡Р° Supabase
                supabase_url = os.getenv('SUPABASE_URL') or os.getenv('DATABASE_URL')
                supabase_key = os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_ANON_KEY')
                
                if supabase_url and supabase_key:
                    # РџСЂСЏРјРѕР№ Р·Р°РїСЂРѕСЃ С‡РµСЂРµР· API
                    url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json"
                    headers = {
                        "apikey": supabase_key,
                        "Authorization": f"Bearer {supabase_key}",
                        "Content-Type": "application/json"
                    }
                    
                    # SQL-РєРѕРјР°РЅРґР° РґР»СЏ РґРѕР±Р°РІР»РµРЅРёСЏ СЃС‚РѕР»Р±С†Р° Рё РѕР±РЅРѕРІР»РµРЅРёСЏ РєСЌС€Р°
                    sql_query = """
                    ALTER TABLE channel_analysis 
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
                    
                    NOTIFY pgrst, 'reload schema';
                    """
                    
                    response = requests.post(url, json={"query": sql_query}, headers=headers)
                    
                    if response.status_code in [200, 204]:
                        logger.info("РЎС‚РѕР»Р±РµС† updated_at СѓСЃРїРµС€РЅРѕ РґРѕР±Р°РІР»РµРЅ Рё РєСЌС€ СЃС…РµРјС‹ РѕР±РЅРѕРІР»РµРЅ")
                    else:
                        logger.warning(f"РћС€РёР±РєР° РїСЂРё РґРѕР±Р°РІР»РµРЅРёРё СЃС‚РѕР»Р±С†Р° updated_at: {response.status_code} - {response.text}")
            except Exception as column_e:
                logger.warning(f"РћС€РёР±РєР° РїСЂРё СЏРІРЅРѕРј РґРѕР±Р°РІР»РµРЅРёРё СЃС‚РѕР»Р±С†Р° updated_at: {str(column_e)}")
            
        except Exception as e:
            logger.warning(f"РћС€РёР±РєР° РїСЂРё РґРѕР±Р°РІР»РµРЅРёРё РЅРµРґРѕСЃС‚Р°СЋС‰РёС… СЃС‚РѕР»Р±С†РѕРІ: {str(e)}")
            
        return True
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РїСЂРѕРІРµСЂРєРµ С‚Р°Р±Р»РёС† Р±Р°Р·С‹ РґР°РЅРЅС‹С…: {e}")
        return False

async def fix_formatting_in_json_fields():
    """РСЃРїСЂР°РІР»РµРЅРёРµ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ РІ JSON РїРѕР»СЏС…."""
    try:
        # РСЃРїСЂР°РІР»СЏРµРј С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ РІ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёС… РёРґРµСЏС…
        await fix_existing_ideas_formatting()
        
        # РСЃРїСЂР°РІР»СЏРµРј С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ РІ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёС… РїРѕСЃС‚Р°С…
        await fix_existing_posts_formatting()
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РёСЃРїСЂР°РІР»РµРЅРёРё С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ: {str(e)}")
        # РџСЂРѕРґРѕР»Р¶Р°РµРј СЂР°Р±РѕС‚Сѓ РїСЂРёР»РѕР¶РµРЅРёСЏ РґР°Р¶Рµ РїСЂРё РѕС€РёР±РєРµ

@app.get("/fix-schema")
async def fix_schema():
    """РСЃРїСЂР°РІР»РµРЅРёРµ СЃС…РµРјС‹ Р±Р°Р·С‹ РґР°РЅРЅС‹С…: РґРѕР±Р°РІР»РµРЅРёРµ РЅРµРґРѕСЃС‚Р°СЋС‰РёС… РєРѕР»РѕРЅРѕРє Рё РѕР±РЅРѕРІР»РµРЅРёРµ РєСЌС€Р° СЃС…РµРјС‹."""
    logger.info("Р—Р°РїСѓСЃРє РёСЃРїСЂР°РІР»РµРЅРёСЏ СЃС…РµРјС‹ Р‘Р”...")
    results = {
        "success": False,
        "message": "РќРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ",
        "response_code": 500,
        "operations": []
    }
    try:
        if not supabase:
            logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
            results["message"] = "РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…"
            return results

        # РЎРїРёСЃРѕРє РєРѕРјР°РЅРґ РґР»СЏ РІС‹РїРѕР»РЅРµРЅРёСЏ
        sql_commands = [
            # Р”РѕР±Р°РІР»РµРЅРёРµ preview_url РІ saved_images
            {
                "name": "add_preview_url_to_saved_images",
                "query": "ALTER TABLE saved_images ADD COLUMN IF NOT EXISTS preview_url TEXT;"
            },
            # Р”РѕР±Р°РІР»РµРЅРёРµ updated_at РІ channel_analysis
            {
                "name": "add_updated_at_to_channel_analysis",
                "query": "ALTER TABLE channel_analysis ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"
            },
            # Р”РѕР±Р°РІР»РµРЅРёРµ external_id РІ saved_images
            {
                "name": "add_external_id_to_saved_images",
                "query": "ALTER TABLE saved_images ADD COLUMN IF NOT EXISTS external_id TEXT;"
            },
            # Р”РѕР±Р°РІР»РµРЅРёРµ saved_image_id РІ saved_posts
            {
                "name": "add_saved_image_id_to_saved_posts",
                "query": "ALTER TABLE saved_posts ADD COLUMN IF NOT EXISTS saved_image_id UUID REFERENCES saved_images(id) ON DELETE SET NULL;"
            }
        ]

        all_commands_successful = True
        saved_image_id_column_verified = False # Р¤Р»Р°Рі РґР»СЏ РїСЂРѕРІРµСЂРєРё РєРѕР»РѕРЅРєРё

        for command in sql_commands:
            logger.info(f"Р’С‹РїРѕР»РЅРµРЅРёРµ РєРѕРјР°РЅРґС‹ SQL: {command['name']}")
            result = await _execute_sql_direct(command['query'])
            status_code = result.get("status_code")
            op_result = {
                "name": command['name'],
                "status_code": status_code,
                "error": result.get("error")
            }
            results["operations"] .append(op_result)

            if status_code not in [200, 204]:
                logger.warning(f"РћС€РёР±РєР° РїСЂРё РІС‹РїРѕР»РЅРµРЅРёРё {command['name']}: {status_code} - {result.get('error')}")
                all_commands_successful = False
            else:
                logger.info(f"РљРѕРјР°РЅРґР° {command['name']} РІС‹РїРѕР»РЅРµРЅР° СѓСЃРїРµС€РЅРѕ (РёР»Рё РєРѕР»РѕРЅРєР° СѓР¶Рµ СЃСѓС‰РµСЃС‚РІРѕРІР°Р»Р°).")

            # === Р”РћР‘РђР’Р›Р•РќРћ: РџСЂРѕРІРµСЂРєР° СЃСѓС‰РµСЃС‚РІРѕРІР°РЅРёСЏ РєРѕР»РѕРЅРєРё saved_image_id ===
            if command['name'] == 'add_saved_image_id_to_saved_posts' and status_code in [200, 204]:
                logger.info("РџСЂРѕРІРµСЂРєР° С„Р°РєС‚РёС‡РµСЃРєРѕРіРѕ РЅР°Р»РёС‡РёСЏ РєРѕР»РѕРЅРєРё 'saved_image_id' РІ 'saved_posts'...")
                verification_query = "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'saved_posts' AND column_name = 'saved_image_id'" # РЈР‘Р РђРќРђ РўРћР§РљРђ РЎ Р—РђРџРЇРўРћР™
                verify_result = await _execute_sql_direct(verification_query)
                verify_status = verify_result.get("status_code")
                op_result_verify = {
                    "name": "verify_saved_image_id_column",
                    "status_code": verify_status,
                    "data": verify_result.get("data"),
                    "error": verify_result.get("error")
                }
                results["operations"].append(op_result_verify)

                # === РќРђР§РђР›Рћ РР—РњР•РќР•РќРРЇ: Р‘РѕР»РµРµ РЅР°РґРµР¶РЅР°СЏ РїСЂРѕРІРµСЂРєР° ===
                column_found = False
                verification_data = verify_result.get("data")
                if verify_status == 200 and isinstance(verification_data, list) and len(verification_data) > 0:
                    first_item = verification_data[0]
                    if isinstance(first_item, dict) and first_item.get("column_name") == "saved_image_id":
                        column_found = True
                
                if column_found:
                    logger.info("РџР РћР’Р•Р РљРђ РЈРЎРџР•РЁРќРђ (РЅРѕРІР°СЏ Р»РѕРіРёРєР°): РљРѕР»РѕРЅРєР° 'saved_image_id' РЅР°Р№РґРµРЅР° РІ 'saved_posts'.")
                    saved_image_id_column_verified = True
                else:
                    # Р­С‚РѕС‚ Р±Р»РѕРє С‚РµРїРµСЂСЊ РґРѕР»Р¶РµРЅ РІС‹РїРѕР»РЅСЏС‚СЊСЃСЏ С‚РѕР»СЊРєРѕ РµСЃР»Рё РєРѕР»РѕРЅРєР° Р”Р•Р™РЎРўР’РРўР•Р›Р¬РќРћ РЅРµ РЅР°Р№РґРµРЅР° РёР»Рё РїСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР° Р·Р°РїСЂРѕСЃР°
                    logger.error("РџР РћР’Р•Р РљРђ РќР•РЈР”РђР§РќРђ (РЅРѕРІР°СЏ Р»РѕРіРёРєР°): РљРѕР»РѕРЅРєР° 'saved_image_id' РќР• РЅР°Р№РґРµРЅР° РІ 'saved_posts' РёР»Рё РѕС€РёР±РєР° РІ РґР°РЅРЅС‹С….")
                    logger.error(f"Р РµР·СѓР»СЊС‚Р°С‚ РїСЂРѕРІРµСЂРєРё (РґР»СЏ РѕС‚Р»Р°РґРєРё): status={verify_status}, data={verification_data}, error={verify_result.get('error')}")
                    # РњС‹ РІСЃРµ РµС‰Рµ РґРѕР»Р¶РЅС‹ СЃС‡РёС‚Р°С‚СЊ СЌС‚Рѕ РѕС€РёР±РєРѕР№, РµСЃР»Рё РєРѕР»РѕРЅРєР° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ
                    all_commands_successful = False 
                # === РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ===
        else: # Р­С‚РѕС‚ else РѕС‚РЅРѕСЃРёС‚СЃСЏ Рє if command['name'] == 'add_saved_image_id_to_saved_posts' ...
             # РћРЅ Р±СѓРґРµС‚ РІС‹РїРѕР»РЅРµРЅ, РµСЃР»Рё РєРѕРјР°РЅРґР° РґРѕР±Р°РІР»РµРЅРёСЏ РєРѕР»РѕРЅРєРё РќР• РЈР”РђР›РђРЎР¬ (status_code != 200/204)
             # РР»Рё РµСЃР»Рё СЌС‚Рѕ Р±С‹Р»Р° РЅРµ РєРѕРјР°РЅРґР° РґРѕР±Р°РІР»РµРЅРёСЏ saved_image_id
             pass # РќРёС‡РµРіРѕ РЅРµ РґРµР»Р°РµРј Р·РґРµСЃСЊ, РѕС€РёР±РєР° СѓР¶Рµ Р·Р°Р»РѕРіРёСЂРѕРІР°РЅР° РІС‹С€Рµ

            # === РљРћРќР•Р¦ Р”РћР‘РђР’Р›Р•РќРРЇ === # Р­С‚Рѕ РєРѕРјРјРµРЅС‚Р°СЂРёР№ РёР· РѕСЂРёРіРёРЅР°Р»СЊРЅРѕРіРѕ РєРѕРґР°, РЅРµ РёРјРµРµС‚ РѕС‚РЅРѕС€РµРЅРёСЏ Рє РјРѕРёРј РёР·РјРµРЅРµРЅРёСЏРј

        # --- End of loop ---

        # РџСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕ РѕР±РЅРѕРІР»СЏРµРј РєСЌС€ СЃС…РµРјС‹ РџРћРЎР›Р• РІСЃРµС… РёР·РјРµРЅРµРЅРёР№
        logger.info("РџСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕРµ РѕР±РЅРѕРІР»РµРЅРёРµ РєСЌС€Р° СЃС…РµРјС‹ PostgREST...")
        # === РР—РњР•РќР•РќРР•: РЈСЃРёР»РµРЅРЅРѕРµ РѕР±РЅРѕРІР»РµРЅРёРµ РєСЌС€Р° ===
        notify_successful = True
        for i in range(3): # РџРѕРїСЂРѕР±СѓРµРј РЅРµСЃРєРѕР»СЊРєРѕ СЂР°Р· СЃ Р·Р°РґРµСЂР¶РєРѕР№
            refresh_result = await _execute_sql_direct("NOTIFY pgrst, 'reload schema';")
            status_code = refresh_result.get("status_code")
            results["operations"] .append({
                 "name": f"notify_pgrst_attempt_{i+1}",
                 "status_code": status_code,
                 "error": refresh_result.get("error")
            })
            if status_code not in [200, 204]:
                 logger.warning(f"РџРѕРїС‹С‚РєР° {i+1} РѕР±РЅРѕРІР»РµРЅРёСЏ РєСЌС€Р° РЅРµ СѓРґР°Р»Р°СЃСЊ: {status_code} - {refresh_result.get('error')}")
                 notify_successful = False
            else:
                 logger.info(f"РџРѕРїС‹С‚РєР° {i+1} РѕР±РЅРѕРІР»РµРЅРёСЏ РєСЌС€Р° СѓСЃРїРµС€РЅР°.")
                 notify_successful = True # Р”РѕСЃС‚Р°С‚РѕС‡РЅРѕ РѕРґРЅРѕР№ СѓСЃРїРµС€РЅРѕР№ РїРѕРїС‹С‚РєРё
                 break # Р’С‹С…РѕРґРёРј РёР· С†РёРєР»Р°, РµСЃР»Рё СѓСЃРїРµС€РЅРѕ
            await asyncio.sleep(0.5) # РќРµР±РѕР»СЊС€Р°СЏ РїР°СѓР·Р° РјРµР¶РґСѓ РїРѕРїС‹С‚РєР°РјРё
        # === РљРћРќР•Р¦ РР—РњР•РќР•РќРРЇ ===

        if all_commands_successful and saved_image_id_column_verified and notify_successful:
            results["success"] = True
            results["message"] = "РЎС…РµРјР° РїСЂРѕРІРµСЂРµРЅР°/РёСЃРїСЂР°РІР»РµРЅР°, РєРѕР»РѕРЅРєР° 'saved_image_id' РїРѕРґС‚РІРµСЂР¶РґРµРЅР°, РєСЌС€ РѕР±РЅРѕРІР»РµРЅ."
            results["response_code"] = 200
            logger.info("РСЃРїСЂР°РІР»РµРЅРёРµ СЃС…РµРјС‹, РїСЂРѕРІРµСЂРєР° РєРѕР»РѕРЅРєРё Рё РѕР±РЅРѕРІР»РµРЅРёРµ РєСЌС€Р° Р·Р°РІРµСЂС€РµРЅРѕ СѓСЃРїРµС€РЅРѕ.")
        elif not saved_image_id_column_verified:
             results["success"] = False
             results["message"] = "РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РґРѕР±Р°РІРёС‚СЊ/РїРѕРґС‚РІРµСЂРґРёС‚СЊ РєРѕР»РѕРЅРєСѓ 'saved_image_id' РІ С‚Р°Р±Р»РёС†Рµ 'saved_posts'."
             results["response_code"] = 500
             logger.error(f"РћС€РёР±РєР° РїСЂРё РїСЂРѕРІРµСЂРєРµ/РґРѕР±Р°РІР»РµРЅРёРё РєРѕР»РѕРЅРєРё saved_image_id. Р”РµС‚Р°Р»Рё: {results['operations']}")
        else:
            results["success"] = False
            results["message"] = "Р’Рѕ РІСЂРµРјСЏ РёСЃРїСЂР°РІР»РµРЅРёСЏ СЃС…РµРјС‹ РёР»Рё РѕР±РЅРѕРІР»РµРЅРёСЏ РєСЌС€Р° РІРѕР·РЅРёРєР»Рё РѕС€РёР±РєРё."
            results["response_code"] = 500
            logger.error(f"РћС€РёР±РєРё РІРѕ РІСЂРµРјСЏ РёСЃРїСЂР°РІР»РµРЅРёСЏ СЃС…РµРјС‹ РёР»Рё РѕР±РЅРѕРІР»РµРЅРёСЏ РєСЌС€Р°. Р”РµС‚Р°Р»Рё: {results['operations']}")

        return results

    except Exception as e:
        logger.error(f"РљСЂРёС‚РёС‡РµСЃРєР°СЏ РѕС€РёР±РєР° РїСЂРё РёСЃРїСЂР°РІР»РµРЅРёРё СЃС…РµРјС‹ Р‘Р”: {e}", exc_info=True)
        results["success"] = False
        results["message"] = f"РћС€РёР±РєР° РїСЂРё РёСЃРїСЂР°РІР»РµРЅРёРё СЃС…РµРјС‹: {e}"
        results["response_code"] = 500
        return results

@app.get("/check-schema")
async def check_schema():
    """РџСЂРѕРІРµСЂРєР° СЃС‚СЂСѓРєС‚СѓСЂС‹ С‚Р°Р±Р»РёС†С‹ channel_analysis Рё СЃРѕРґРµСЂР¶РёРјРѕРіРѕ РєСЌС€Р° СЃС…РµРјС‹."""
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ URL Рё РєР»СЋС‡Р° Supabase
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            return {"success": False, "message": "РќРµ РЅР°Р№РґРµРЅС‹ РїРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ SUPABASE_URL РёР»Рё SUPABASE_ANON_KEY"}
        
        # РџСЂСЏРјРѕР№ Р·Р°РїСЂРѕСЃ С‡РµСЂРµР· API
        url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
        
        # SQL Р·Р°РїСЂРѕСЃ РґР»СЏ РїСЂРѕРІРµСЂРєРё СЃС‚СЂСѓРєС‚СѓСЂС‹ С‚Р°Р±Р»РёС†С‹
        table_structure_query = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'channel_analysis'
        AND table_schema = 'public'
        ORDER BY ordinal_position;
        """
        
        # SQL Р·Р°РїСЂРѕСЃ РґР»СЏ РїСЂРѕРІРµСЂРєРё РєСЌС€Р° СЃС…РµРјС‹
        cache_query = """
        SELECT pg_notify('pgrst', 'reload schema');
        SELECT 'Cache reloaded' as status;
        """
        
        # Р’С‹РїРѕР»РЅРµРЅРёРµ Р·Р°РїСЂРѕСЃР° РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ СЃС‚СЂСѓРєС‚СѓСЂС‹ С‚Р°Р±Р»РёС†С‹
        table_response = requests.post(url, json={"query": table_structure_query}, headers=headers)
        
        # Р’С‹РїРѕР»РЅРµРЅРёРµ Р·Р°РїСЂРѕСЃР° РґР»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ РєСЌС€Р° СЃС…РµРјС‹
        cache_response = requests.post(url, json={"query": cache_query}, headers=headers)
        
        # РџСЂРѕРІРµСЂРєР° РЅР°Р»РёС‡РёСЏ РєРѕР»РѕРЅРєРё updated_at
        updated_at_exists = False
        columns = []
        if table_response.status_code == 200:
            try:
                table_data = table_response.json()
                columns = table_data
                for column in table_data:
                    if column.get('column_name') == 'updated_at':
                        updated_at_exists = True
                        break
            except Exception as parse_error:
                logger.error(f"РћС€РёР±РєР° РїСЂРё СЂР°Р·Р±РѕСЂРµ РѕС‚РІРµС‚Р°: {parse_error}")
        
        # Р•СЃР»Рё РєРѕР»РѕРЅРєРё updated_at РЅРµС‚, РґРѕР±Р°РІР»СЏРµРј РµРµ
        if not updated_at_exists:
            add_column_query = """
            ALTER TABLE channel_analysis 
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
            
            NOTIFY pgrst, 'reload schema';
            """
            add_column_response = requests.post(url, json={"query": add_column_query}, headers=headers)
            
            # РџРѕРІС‚РѕСЂРЅР°СЏ РїСЂРѕРІРµСЂРєР° СЃС‚СЂСѓРєС‚СѓСЂС‹ РїРѕСЃР»Рµ РґРѕР±Р°РІР»РµРЅРёСЏ РєРѕР»РѕРЅРєРё
            table_response2 = requests.post(url, json={"query": table_structure_query}, headers=headers)
            if table_response2.status_code == 200:
                try:
                    columns = table_response2.json()
                    for column in columns:
                        if column.get('column_name') == 'updated_at':
                            updated_at_exists = True
                            break
                except Exception:
                    pass
        
        return {
            "success": True,
            "table_structure": columns,
            "updated_at_exists": updated_at_exists,
            "cache_response": {
                "status_code": cache_response.status_code,
                "response": cache_response.json() if cache_response.status_code == 200 else None
            }
        }
            
    except Exception as e:
        logger.error(f"РСЃРєР»СЋС‡РµРЅРёРµ РїСЂРё РїСЂРѕРІРµСЂРєРµ СЃС…РµРјС‹: {str(e)}")
        return {"success": False, "message": f"РћС€РёР±РєР°: {str(e)}"}

@app.get("/recreate-schema")
async def recreate_schema():
    """РџРµСЂРµСЃРѕР·РґР°РЅРёРµ С‚Р°Р±Р»РёС†С‹ channel_analysis СЃ РЅСѓР¶РЅРѕР№ СЃС‚СЂСѓРєС‚СѓСЂРѕР№."""
    try:
        # РџРѕР»СѓС‡РµРЅРёРµ URL Рё РєР»СЋС‡Р° Supabase
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            return {"success": False, "message": "РќРµ РЅР°Р№РґРµРЅС‹ РїРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ SUPABASE_URL РёР»Рё SUPABASE_ANON_KEY"}
        
        # РџСЂСЏРјРѕР№ Р·Р°РїСЂРѕСЃ С‡РµСЂРµР· API
        url = f"{supabase_url}/rest/v1/rpc/exec_sql_array_json"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
        
        # SQL Р·Р°РїСЂРѕСЃ РґР»СЏ СЃРѕР·РґР°РЅРёСЏ СЂРµР·РµСЂРІРЅРѕР№ РєРѕРїРёРё РґР°РЅРЅС‹С…
        backup_query = """
        CREATE TEMPORARY TABLE temp_channel_analysis AS
        SELECT * FROM channel_analysis;
        SELECT COUNT(*) AS backup_rows FROM temp_channel_analysis;
        """
        
        # SQL Р·Р°РїСЂРѕСЃ РґР»СЏ СѓРґР°Р»РµРЅРёСЏ Рё РїРµСЂРµСЃРѕР·РґР°РЅРёСЏ С‚Р°Р±Р»РёС†С‹ СЃ РЅСѓР¶РЅРѕР№ СЃС‚СЂСѓРєС‚СѓСЂРѕР№
        recreate_query = """
        DROP TABLE IF EXISTS channel_analysis;
        
        CREATE TABLE channel_analysis (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id BIGINT NOT NULL,
            channel_name TEXT NOT NULL,
            themes JSONB DEFAULT '[]'::jsonb,
            styles JSONB DEFAULT '[]'::jsonb,
            sample_posts JSONB DEFAULT '[]'::jsonb,
            best_posting_time TEXT,
            analyzed_posts_count INTEGER DEFAULT 0,
            is_sample_data BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(user_id, channel_name)
        );
        
        CREATE INDEX idx_channel_analysis_user_id ON channel_analysis(user_id);
        CREATE INDEX idx_channel_analysis_channel_name ON channel_analysis(channel_name);
        CREATE INDEX idx_channel_analysis_updated_at ON channel_analysis(updated_at);
        
        NOTIFY pgrst, 'reload schema';
        SELECT 'Table recreated' AS status;
        """
        
        # SQL Р·Р°РїСЂРѕСЃ РґР»СЏ РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёСЏ РґР°РЅРЅС‹С… РёР· СЂРµР·РµСЂРІРЅРѕР№ РєРѕРїРёРё
        restore_query = """
        INSERT INTO channel_analysis (
            id, user_id, channel_name, themes, styles, sample_posts, 
            best_posting_time, analyzed_posts_count, is_sample_data, created_at
        )
        SELECT 
            id, user_id, channel_name, themes, styles, sample_posts, 
            best_posting_time, analyzed_posts_count, is_sample_data, created_at
        FROM temp_channel_analysis
        ON CONFLICT (user_id, channel_name) DO NOTHING;
        
        SELECT COUNT(*) AS restored_rows FROM channel_analysis;
        DROP TABLE IF EXISTS temp_channel_analysis;
        """
        
        # Р’С‹РїРѕР»РЅРµРЅРёРµ Р·Р°РїСЂРѕСЃР° РґР»СЏ СЃРѕР·РґР°РЅРёСЏ СЂРµР·РµСЂРІРЅРѕР№ РєРѕРїРёРё РґР°РЅРЅС‹С…
        backup_response = requests.post(url, json={"query": backup_query}, headers=headers)
        backup_success = backup_response.status_code == 200
        backup_data = backup_response.json() if backup_success else None
        
        # Р’С‹РїРѕР»РЅРµРЅРёРµ Р·Р°РїСЂРѕСЃР° РґР»СЏ РїРµСЂРµСЃРѕР·РґР°РЅРёСЏ С‚Р°Р±Р»РёС†С‹
        recreate_response = requests.post(url, json={"query": recreate_query}, headers=headers)
        recreate_success = recreate_response.status_code == 200
        
        # Р•СЃР»Рё СЃРѕР·РґР°РЅРёРµ СЂРµР·РµСЂРІРЅРѕР№ РєРѕРїРёРё СѓСЃРїРµС€РЅРѕ, РїС‹С‚Р°РµРјСЃСЏ РІРѕСЃСЃС‚Р°РЅРѕРІРёС‚СЊ РґР°РЅРЅС‹Рµ
        restore_data = None
        restore_success = False
        if backup_success:
            restore_response = requests.post(url, json={"query": restore_query}, headers=headers)
            restore_success = restore_response.status_code == 200
            restore_data = restore_response.json() if restore_success else None
        
        # Р¤РёРЅР°Р»СЊРЅРѕРµ РѕР±РЅРѕРІР»РµРЅРёРµ РєСЌС€Р° СЃС…РµРјС‹
        cache_query = """
        NOTIFY pgrst, 'reload schema';
        SELECT pg_sleep(1);
        NOTIFY pgrst, 'reload schema';
        SELECT 'Cache reloaded twice' as status;
        """
        cache_response = requests.post(url, json={"query": cache_query}, headers=headers)
        
        return {
            "success": recreate_success,
            "backup": {
                "success": backup_success,
                "data": backup_data
            },
            "recreate": {
                "success": recreate_success,
                "data": recreate_response.json() if recreate_success else None
            },
            "restore": {
                "success": restore_success,
                "data": restore_data
            },
            "cache_reload": {
                "success": cache_response.status_code == 200,
                "data": cache_response.json() if cache_response.status_code == 200 else None
            }
        }
            
    except Exception as e:
        logger.error(f"РСЃРєР»СЋС‡РµРЅРёРµ РїСЂРё РїРµСЂРµСЃРѕР·РґР°РЅРёРё СЃС…РµРјС‹: {str(e)}")
        return {"success": False, "message": f"РћС€РёР±РєР°: {str(e)}"}

# --- РќРћР’Р«Р™ Р­РќР”РџРћРРќРў РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ РќР•РЎРљРћР›Р¬РљРРҐ РёРґРµР№ --- 
class SaveIdeasRequest(BaseModel):
    ideas: List[Dict[str, Any]]
    channel_name: Optional[str] = None # РњРѕР¶РЅРѕ РїРµСЂРµРґР°С‚СЊ РёРјСЏ РєР°РЅР°Р»Р° РѕРґРёРЅ СЂР°Р·

@app.post("/save-suggested-ideas", response_model=Dict[str, Any])
async def save_suggested_ideas_batch(payload: SaveIdeasRequest, request: Request):
    """РЎРѕС…СЂР°РЅСЏРµС‚ СЃРїРёСЃРѕРє РїСЂРµРґР»РѕР¶РµРЅРЅС‹С… РёРґРµР№ РІ Р±Р°Р·Сѓ РґР°РЅРЅС‹С…."""
    telegram_user_id = request.headers.get("x-telegram-user-id")
    if not telegram_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # РџСЂРµРѕР±СЂР°Р·СѓРµРј ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РІ С†РµР»РѕРµ С‡РёСЃР»Рѕ
    try:
        telegram_user_id = int(telegram_user_id)
    except (ValueError, TypeError):
        logger.error(f"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РІ Р·Р°РіРѕР»РѕРІРєРµ: {telegram_user_id}")
        raise HTTPException(status_code=400, detail="РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ С„РѕСЂРјР°С‚ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ")

    if not supabase:
        logger.error("Supabase client not initialized")
        raise HTTPException(status_code=500, detail="Database not initialized")

    saved_count = 0
    errors = []
    saved_ids = []

    ideas_to_save = payload.ideas
    channel_name = payload.channel_name
    logger.info(f"РџРѕР»СѓС‡РµРЅ Р·Р°РїСЂРѕСЃ РЅР° СЃРѕС…СЂР°РЅРµРЅРёРµ {len(ideas_to_save)} РёРґРµР№ РґР»СЏ РєР°РЅР°Р»Р° {channel_name}")

    # --- РќРђР§РђР›Рћ: РЈРґР°Р»РµРЅРёРµ СЃС‚Р°СЂС‹С… РёРґРµР№ РґР»СЏ СЌС‚РѕРіРѕ РєР°РЅР°Р»Р° РїРµСЂРµРґ СЃРѕС…СЂР°РЅРµРЅРёРµРј РЅРѕРІС‹С… --- 
    if channel_name:
        try:
            delete_result = supabase.table("suggested_ideas")\
                .delete()\
                .eq("user_id", int(telegram_user_id))\
                .eq("channel_name", channel_name)\
                .execute()
            logger.info(f"РЈРґР°Р»РµРЅРѕ {len(delete_result.data)} СЃС‚Р°СЂС‹С… РёРґРµР№ РґР»СЏ РєР°РЅР°Р»Р° {channel_name}")
        except Exception as del_err:
            logger.error(f"РћС€РёР±РєР° РїСЂРё СѓРґР°Р»РµРЅРёРё СЃС‚Р°СЂС‹С… РёРґРµР№ РґР»СЏ РєР°РЅР°Р»Р° {channel_name}: {del_err}")
            # РќРµ РїСЂРµСЂС‹РІР°РµРј РІС‹РїРѕР»РЅРµРЅРёРµ, РЅРѕ Р»РѕРіРёСЂСѓРµРј РѕС€РёР±РєСѓ
            errors.append(f"РћС€РёР±РєР° СѓРґР°Р»РµРЅРёСЏ СЃС‚Р°СЂС‹С… РёРґРµР№: {str(del_err)}")
    # --- РљРћРќР•Р¦: РЈРґР°Р»РµРЅРёРµ СЃС‚Р°СЂС‹С… РёРґРµР№ --- 

    # --- Р”РћР‘РђР’Р›Р•РќРћ: Р’С‹Р·РѕРІ fix_schema РїРµСЂРµРґ РІСЃС‚Р°РІРєРѕР№ --- 
    try:
        logger.info("Р’С‹Р·РѕРІ fix_schema РЅРµРїРѕСЃСЂРµРґСЃС‚РІРµРЅРЅРѕ РїРµСЂРµРґ СЃРѕС…СЂР°РЅРµРЅРёРµРј РёРґРµР№...")
        fix_result = await fix_schema()
        if not fix_result.get("success"):
            logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ/РїСЂРѕРІРµСЂРёС‚СЊ СЃС…РµРјСѓ РїРµСЂРµРґ СЃРѕС…СЂР°РЅРµРЅРёРµРј РёРґРµР№: {fix_result}")
            # РќРµ РїСЂРµСЂС‹РІР°РµРј, РЅРѕ Р»РѕРіРёСЂСѓРµРј. РћС€РёР±РєР°, СЃРєРѕСЂРµРµ РІСЃРµРіРѕ, РїРѕРІС‚РѕСЂРёС‚СЃСЏ РїСЂРё РІСЃС‚Р°РІРєРµ.
            errors.append("РџСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ: РЅРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕРІРµСЂРёС‚СЊ/РѕР±РЅРѕРІРёС‚СЊ СЃС…РµРјСѓ РїРµСЂРµРґ СЃРѕС…СЂР°РЅРµРЅРёРµРј.")
        else:
            logger.info("РџСЂРѕРІРµСЂРєР°/РѕР±РЅРѕРІР»РµРЅРёРµ СЃС…РµРјС‹ РїРµСЂРµРґ СЃРѕС…СЂР°РЅРµРЅРёРµРј РёРґРµР№ Р·Р°РІРµСЂС€РµРЅР° СѓСЃРїРµС€РЅРѕ.")
    except Exception as pre_save_fix_err:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РІС‹Р·РѕРІРµ fix_schema РїРµСЂРµРґ СЃРѕС…СЂР°РЅРµРЅРёРµРј РёРґРµР№: {pre_save_fix_err}", exc_info=True)
        errors.append(f"РћС€РёР±РєР° РїСЂРѕРІРµСЂРєРё СЃС…РµРјС‹ РїРµСЂРµРґ СЃРѕС…СЂР°РЅРµРЅРёРµРј: {str(pre_save_fix_err)}")
    # --- РљРћРќР•Р¦ Р”РћР‘РђР’Р›Р•РќРРЇ ---

    records_to_insert = []
    for idea_data in ideas_to_save:
        try:
            # РћС‡РёС‰Р°РµРј С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ С‚РµРєСЃС‚Р° РїРµСЂРµРґ СЃРѕС…СЂР°РЅРµРЅРёРµРј
            topic_idea = clean_text_formatting(idea_data.get("topic_idea", ""))
            format_style = clean_text_formatting(idea_data.get("format_style", ""))

            if not topic_idea: # РџСЂРѕРїСѓСЃРєР°РµРј РёРґРµРё Р±РµР· С‚РµРјС‹
                continue

            # Р“РµРЅРµСЂРёСЂСѓРµРј СѓРЅРёРєР°Р»СЊРЅС‹Р№ ID РґР»СЏ РёРґРµРё (РёСЃРїРѕР»СЊР·СѓРµРј UUID)
            idea_id = str(uuid.uuid4())
            record = {
                "id": idea_id,
                "user_id": int(telegram_user_id),
                "channel_name": idea_data.get("channel_name") or channel_name, # РСЃРїРѕР»СЊР·СѓРµРј РёР· РёРґРµРё РёР»Рё РѕР±С‰РёР№
                "topic_idea": topic_idea,
                "format_style": format_style,
                "relative_day": idea_data.get("day"),
                "created_at": datetime.now().isoformat(),
                "is_detailed": idea_data.get("is_detailed", False),
            }
            records_to_insert.append(record)
            saved_ids.append(idea_id)

        except Exception as e:
            errors.append(f"РћС€РёР±РєР° РїРѕРґРіРѕС‚РѕРІРєРё РёРґРµРё {idea_data.get('topic_idea')}: {str(e)}")
            logger.error(f"РћС€РёР±РєР° РїРѕРґРіРѕС‚РѕРІРєРё РёРґРµРё {idea_data.get('topic_idea')}: {str(e)}")

    if not records_to_insert:
        logger.warning("РќРµС‚ РёРґРµР№ РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ РїРѕСЃР»Рµ РѕР±СЂР°Р±РѕС‚РєРё.")
        return {"message": "РќРµС‚ РєРѕСЂСЂРµРєС‚РЅС‹С… РёРґРµР№ РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ.", "saved_count": 0, "errors": errors}

    try:
        # РЎРѕС…СЂР°РЅСЏРµРј РІСЃРµ РїРѕРґРіРѕС‚РѕРІР»РµРЅРЅС‹Рµ Р·Р°РїРёСЃРё РѕРґРЅРёРј Р·Р°РїСЂРѕСЃРѕРј
        result = supabase.table("suggested_ideas").insert(records_to_insert).execute()

        if hasattr(result, 'data') and result.data:
            saved_count = len(result.data)
            logger.info(f"РЈСЃРїРµС€РЅРѕ СЃРѕС…СЂР°РЅРµРЅРѕ {saved_count} РёРґРµР№ Р±Р°С‚С‡РµРј.")
            return {"message": f"РЈСЃРїРµС€РЅРѕ СЃРѕС…СЂР°РЅРµРЅРѕ {saved_count} РёРґРµР№.", "saved_count": saved_count, "saved_ids": saved_ids, "errors": errors}
        else:
            error_detail = getattr(result, 'error', 'Unknown error')
            logger.error(f"РћС€РёР±РєР° РїСЂРё Р±Р°С‚С‡-СЃРѕС…СЂР°РЅРµРЅРёРё РёРґРµР№: {error_detail}")
            errors.append(f"РћС€РёР±РєР° РїСЂРё Р±Р°С‚С‡-СЃРѕС…СЂР°РЅРµРЅРёРё: {error_detail}")
            # РџС‹С‚Р°РµРјСЃСЏ СЃРѕС…СЂР°РЅРёС‚СЊ РїРѕ РѕРґРЅРѕР№, РµСЃР»Рё Р±Р°С‚С‡ РЅРµ СѓРґР°Р»СЃСЏ
            logger.warning("РџРѕРїС‹С‚РєР° СЃРѕС…СЂР°РЅРёС‚СЊ РёРґРµРё РїРѕ РѕРґРЅРѕР№...")
            saved_count_single = 0
            saved_ids_single = []
            for record in records_to_insert:
                 try:
                     single_result = supabase.table("suggested_ideas").insert(record).execute()
                     if hasattr(single_result, 'data') and single_result.data:
                         saved_count_single += 1
                         saved_ids_single.append(record['id'])
                     else:
                         single_error = getattr(single_result, 'error', 'Unknown error')
                         errors.append(f"РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ РёРґРµРё {record.get('topic_idea')}: {single_error}")
                         logger.error(f"РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ РёРґРµРё {record.get('topic_idea')}: {single_error}")
                 except Exception as single_e:
                     errors.append(f"РСЃРєР»СЋС‡РµРЅРёРµ РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РёРґРµРё {record.get('topic_idea')}: {str(single_e)}")
                     logger.error(f"РСЃРєР»СЋС‡РµРЅРёРµ РїСЂРё СЃРѕС…СЂР°РЅРµРЅРёРё РёРґРµРё {record.get('topic_idea')}: {str(single_e)}")
                     
            logger.info(f"РЎРѕС…СЂР°РЅРµРЅРѕ {saved_count_single} РёРґРµР№ РїРѕ РѕРґРЅРѕР№.")
            return {
                 "message": f"РЎРѕС…СЂР°РЅРµРЅРѕ {saved_count_single} РёРґРµР№ (РѕСЃС‚Р°Р»СЊРЅС‹Рµ СЃ РѕС€РёР±РєРѕР№).", 
                 "saved_count": saved_count_single, 
                 "saved_ids": saved_ids_single, 
                 "errors": errors
            }

    except Exception as e:
        logger.error(f"РСЃРєР»СЋС‡РµРЅРёРµ РїСЂРё Р±Р°С‚С‡-СЃРѕС…СЂР°РЅРµРЅРёРё РёРґРµР№: {str(e)}")
        raise HTTPException(status_code=500, detail=f"РСЃРєР»СЋС‡РµРЅРёРµ РїСЂРё Р±Р°С‚С‡-СЃРѕС…СЂР°РЅРµРЅРёРё: {str(e)}")

# --- РЎРѕР·РґР°РµРј РїР°РїРєСѓ РґР»СЏ Р·Р°РіСЂСѓР·РѕРє, РµСЃР»Рё РµРµ РЅРµС‚ ---
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads") # РСЃРїРѕР»СЊР·СѓРµРј РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅС‹Р№ РїСѓС‚СЊ РІРЅСѓС‚СЂРё backend
os.makedirs(UPLOADS_DIR, exist_ok=True)
logger.info(f"РџР°РїРєР° РґР»СЏ Р·Р°РіСЂСѓР¶РµРЅРЅС‹С… РёР·РѕР±СЂР°Р¶РµРЅРёР№: {os.path.abspath(UPLOADS_DIR)}")

# --- РќРћР’Р«Р™ Р­РќР”РџРћРРќРў Р”Р›РЇ Р—РђР“Р РЈР—РљР РР—РћР‘Р РђР–Р•РќРР™ ---
@app.post("/upload-image")
async def upload_image(request: Request, file: UploadFile = File(...)):
    """Р—Р°РіСЂСѓР¶Р°РµС‚ С„Р°Р№Р» РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РІ Supabase Storage."""
    telegram_user_id = request.headers.get("X-Telegram-User-Id")
    if not telegram_user_id:
        logger.warning("Р—Р°РїСЂРѕСЃ Р·Р°РіСЂСѓР·РєРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Telegram")
        raise HTTPException(status_code=401, detail="Р”Р»СЏ Р·Р°РіСЂСѓР·РєРё РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РЅРµРѕР±С…РѕРґРёРјРѕ Р°РІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ С‡РµСЂРµР· Telegram")

    # РџСЂРµРѕР±СЂР°Р·СѓРµРј ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РІ С†РµР»РѕРµ С‡РёСЃР»Рѕ
    try:
        telegram_user_id = int(telegram_user_id)
    except (ValueError, TypeError):
        logger.error(f"РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РІ Р·Р°РіРѕР»РѕРІРєРµ: {telegram_user_id}")
        raise HTTPException(status_code=400, detail="РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ С„РѕСЂРјР°С‚ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ")

    if not supabase:
        logger.error("РљР»РёРµРЅС‚ Supabase РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
        raise HTTPException(status_code=500, detail="РћС€РёР±РєР°: РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…")

    try:
        # РџСЂРѕРІРµСЂРєР° С‚РёРїР° С„Р°Р№Р»Р°
        content_type = file.content_type
        if not content_type or not content_type.startswith("image/"):
             logger.warning(f"РџРѕРїС‹С‚РєР° Р·Р°РіСЂСѓР·РёС‚СЊ РЅРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ: {file.filename}, С‚РёРї: {content_type}")
             raise HTTPException(status_code=400, detail="Р”РѕРїСѓСЃРєР°СЋС‚СЃСЏ С‚РѕР»СЊРєРѕ С„Р°Р№Р»С‹ РёР·РѕР±СЂР°Р¶РµРЅРёР№ (JPEG, PNG, GIF, WEBP)")

        # Р“РµРЅРµСЂРёСЂСѓРµРј СѓРЅРёРєР°Р»СЊРЅРѕРµ РёРјСЏ С„Р°Р№Р»Р°/РїСѓС‚СЊ РІ Р±Р°РєРµС‚Рµ, СЃРѕС…СЂР°РЅСЏСЏ СЂР°СЃС€РёСЂРµРЅРёРµ
        _, ext = os.path.splitext(file.filename)
        allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        if ext.lower() not in allowed_extensions:
             logger.warning(f"РџРѕРїС‹С‚РєР° Р·Р°РіСЂСѓР·РёС‚СЊ С„Р°Р№Р» СЃ РЅРµРґРѕРїСѓСЃС‚РёРјС‹Рј СЂР°СЃС€РёСЂРµРЅРёРµРј: {file.filename}")
             raise HTTPException(status_code=400, detail=f"РќРµРґРѕРїСѓСЃС‚РёРјРѕРµ СЂР°СЃС€РёСЂРµРЅРёРµ С„Р°Р№Р»Р°. Р Р°Р·СЂРµС€РµРЅС‹: {', '.join(allowed_extensions)}")

        # Р¤РѕСЂРјРёСЂСѓРµРј РїСѓС‚СЊ РІРЅСѓС‚СЂРё Р±Р°РєРµС‚Р° (РЅР°РїСЂРёРјРµСЂ, public/<uuid>.<ext>)
        # 'public/' - РЅРµРѕР±СЏР·Р°С‚РµР»СЊРЅР°СЏ РїР°РїРєР° РІРЅСѓС‚СЂРё Р±Р°РєРµС‚Р° РґР»СЏ СѓРґРѕР±СЃС‚РІР° РѕСЂРіР°РЅРёР·Р°С†РёРё
        storage_path = f"public/{uuid.uuid4()}{ext.lower()}"
        bucket_name = "post-images" # РРјСЏ Р±Р°РєРµС‚Р° РІ Supabase Storage

        # Р§РёС‚Р°РµРј СЃРѕРґРµСЂР¶РёРјРѕРµ С„Р°Р№Р»Р°
        file_content = await file.read()
        # РЎР±СЂР°СЃС‹РІР°РµРј СѓРєР°Р·Р°С‚РµР»СЊ С„Р°Р№Р»Р°, РµСЃР»Рё РѕРЅ РїРѕРЅР°РґРѕР±РёС‚СЃСЏ СЃРЅРѕРІР° (С…РѕС‚СЏ Р·РґРµСЃСЊ РЅРµ РЅСѓР¶РµРЅ)
        await file.seek(0)

        logger.info(f"РџРѕРїС‹С‚РєР° Р·Р°РіСЂСѓР·РєРё С„Р°Р№Р»Р° РІ Supabase Storage: Р±Р°РєРµС‚='{bucket_name}', РїСѓС‚СЊ='{storage_path}', С‚РёРї='{content_type}'")

        # Р—Р°РіСЂСѓР¶Р°РµРј С„Р°Р№Р» РІ Supabase Storage
        # РСЃРїРѕР»СЊР·СѓРµРј file_options РґР»СЏ СѓСЃС‚Р°РЅРѕРІРєРё content-type
        upload_response = supabase.storage.from_(bucket_name).upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": content_type, "cache-control": "3600"} # РЈСЃС‚Р°РЅР°РІР»РёРІР°РµРј С‚РёРї Рё РєСЌС€РёСЂРѕРІР°РЅРёРµ
        )

        # Supabase Python client v1 РЅРµ РІРѕР·РІСЂР°С‰Р°РµС‚ РїРѕР»РµР·РЅС‹С… РґР°РЅРЅС‹С… РїСЂРё СѓСЃРїРµС…Рµ, РїСЂРѕРІРµСЂСЏРµРј РЅР° РёСЃРєР»СЋС‡РµРЅРёСЏ
        # Р’ v2 (РµСЃР»Рё РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ) РѕС‚РІРµС‚ Р±СѓРґРµС‚ РґСЂСѓРіРёРј. РџРѕРєР° РѕСЂРёРµРЅС‚РёСЂСѓРµРјСЃСЏ РЅР° РѕС‚СЃСѓС‚СЃС‚РІРёРµ РѕС€РёР±РѕРє.
        logger.info(f"Р¤Р°Р№Р» СѓСЃРїРµС€РЅРѕ Р·Р°РіСЂСѓР¶РµРЅ РІ Supabase Storage (РѕС‚РІРµС‚ API: {upload_response}). РџСѓС‚СЊ: {storage_path}")

        # РџРѕР»СѓС‡Р°РµРј РїСѓР±Р»РёС‡РЅС‹Р№ URL РґР»СЏ Р·Р°РіСЂСѓР¶РµРЅРЅРѕРіРѕ С„Р°Р№Р»Р°
        public_url_response = supabase.storage.from_(bucket_name).get_public_url(storage_path)

        if not public_url_response:
             logger.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ РїСѓР±Р»РёС‡РЅС‹Р№ URL РґР»СЏ С„Р°Р№Р»Р°: {storage_path}")
             raise HTTPException(status_code=500, detail="РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ URL РґР»СЏ Р·Р°РіСЂСѓР¶РµРЅРЅРѕРіРѕ С„Р°Р№Р»Р°.")

        public_url = public_url_response # Р’ v1 get_public_url РІРѕР·РІСЂР°С‰Р°РµС‚ СЃС‚СЂРѕРєСѓ URL

        logger.info(f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {telegram_user_id} СѓСЃРїРµС€РЅРѕ Р·Р°РіСЂСѓР·РёР» РёР·РѕР±СЂР°Р¶РµРЅРёРµ: {storage_path}, URL: {public_url}")

        # Р’РѕР·РІСЂР°С‰Р°РµРј РўРћР›Р¬РљРћ РїСѓР±Р»РёС‡РЅС‹Р№ URL
        return {"url": public_url}

    except HTTPException as http_err:
        raise http_err
    except APIError as storage_api_err:
        logger.error(f"РћС€РёР±РєР° API Supabase Storage РїСЂРё Р·Р°РіСЂСѓР·РєРµ С„Р°Р№Р»Р°: {storage_api_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° С…СЂР°РЅРёР»РёС‰Р° РїСЂРё Р·Р°РіСЂСѓР·РєРµ: {storage_api_err.message}")
    except Exception as e:
        logger.error(f"РќРµРїСЂРµРґРІРёРґРµРЅРЅР°СЏ РѕС€РёР±РєР° РїСЂРё Р·Р°РіСЂСѓР·РєРµ С„Р°Р№Р»Р° РІ Supabase Storage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±СЂР°Р±РѕС‚Р°С‚СЊ Р·Р°РіСЂСѓР·РєСѓ С„Р°Р№Р»Р°: {str(e)}")
    finally:
        # Р’Р°Р¶РЅРѕ Р·Р°РєСЂС‹С‚СЊ С„Р°Р№Р» РІ Р»СЋР±РѕРј СЃР»СѓС‡Р°Рµ
        if file and hasattr(file, 'close') and callable(file.close):
            await file.close()

# --- РќР°СЃС‚СЂРѕР№РєР° РѕР±СЃР»СѓР¶РёРІР°РЅРёСЏ СЃС‚Р°С‚РёС‡РµСЃРєРёС… С„Р°Р№Р»РѕРІ (SPA) ---
# РЈР±РµРґРёРјСЃСЏ, С‡С‚Рѕ СЌС‚РѕС‚ РєРѕРґ РёРґРµС‚ РџРћРЎР›Р• РјРѕРЅС‚РёСЂРѕРІР°РЅРёСЏ /uploads
# РџСѓС‚СЊ Рє РїР°РїРєРµ СЃР±РѕСЂРєРё С„СЂРѕРЅС‚РµРЅРґР° (РїСЂРµРґРїРѕР»Р°РіР°РµРј, С‡С‚Рѕ РѕРЅР° РЅР° РґРІР° СѓСЂРѕРІРЅСЏ РІС‹С€Рµ Рё РІ РїР°РїРєРµ frontend/dist)
static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

# Р¤Р›РђР“ РґР»СЏ РјРѕРЅС‚РёСЂРѕРІР°РЅРёСЏ СЃС‚Р°С‚РёРєРё РІ РєРѕРЅС†Рµ С„Р°Р№Р»Р°
SHOULD_MOUNT_STATIC = os.path.exists(static_folder) and os.path.isdir(static_folder)

if SHOULD_MOUNT_STATIC:
    logger.info(f"РЎС‚Р°С‚РёС‡РµСЃРєРёРµ С„Р°Р№Р»С‹ SPA Р±СѓРґСѓС‚ РѕР±СЃР»СѓР¶РёРІР°С‚СЊСЃСЏ РёР· РїР°РїРєРё: {static_folder}")
    try: # РРЎРџР РђР’Р›Р•РќРћ: Р”РѕР±Р°РІР»РµРЅ Р±Р»РѕРє try...except
        app.mount("/", StaticFiles(directory=static_folder, html=True), name="static-spa") # РРЎРџР РђР’Р›Р•РќРћ: РЈР±СЂР°РЅС‹ Р»РёС€РЅРёРµ `\`
        logger.info(f"РЎС‚Р°С‚РёС‡РµСЃРєРёРµ С„Р°Р№Р»С‹ SPA СѓСЃРїРµС€РЅРѕ СЃРјРѕРЅС‚РёСЂРѕРІР°РЅС‹ РІ РєРѕСЂРЅРµРІРѕРј РїСѓС‚Рё '/'")

        # РЇРІРЅРѕ РґРѕР±Р°РІРёРј РѕР±СЂР°Р±РѕС‚С‡РёРє РґР»СЏ РєРѕСЂРЅРµРІРѕРіРѕ РїСѓС‚Рё, РµСЃР»Рё StaticFiles РЅРµ СЃРїСЂР°РІР»СЏРµС‚СЃСЏ
        @app.get("/") # РРЎРџР РђР’Р›Р•РќРћ: РЈР±СЂР°РЅС‹ Р»РёС€РЅРёРµ `\`
        async def serve_index():
            index_path = os.path.join(static_folder, "index.html")
            if os.path.exists(index_path):
                 return FileResponse(index_path)
            else:
                 logger.error(f"Р¤Р°Р№Р» index.html РЅРµ РЅР°Р№РґРµРЅ РІ {static_folder}")
                 raise HTTPException(status_code=404, detail="Index file not found")

        # РћР±СЂР°Р±РѕС‚С‡РёРє РґР»СЏ РІСЃРµС… РѕСЃС‚Р°Р»СЊРЅС‹С… РїСѓС‚РµР№ SPA (РµСЃР»Рё StaticFiles(html=True) РЅРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ)
        # Р­С‚РѕС‚ РѕР±СЂР°Р±РѕС‚С‡РёРє РџР•Р Р•РҐР’РђРўРРў РІСЃРµ, С‡С‚Рѕ РЅРµ Р±С‹Р»Рѕ РїРµСЂРµС…РІР°С‡РµРЅРѕ СЂР°РЅРµРµ (/api, /uploads, etc.)
        @app.get("/{rest_of_path:path}") # РРЎРџР РђР’Р›Р•РќРћ: РЈР±СЂР°РЅС‹ Р»РёС€РЅРёРµ `\`
        async def serve_spa_catch_all(request: Request, rest_of_path: str):
            # РСЃРєР»СЋС‡Р°РµРј API РїСѓС‚Рё, С‡С‚РѕР±С‹ РёР·Р±РµР¶Р°С‚СЊ РєРѕРЅС„Р»РёРєС‚РѕРІ (РЅР° РІСЃСЏРєРёР№ СЃР»СѓС‡Р°Р№)
            # РџСЂРѕРІРµСЂСЏРµРј, РЅРµ РЅР°С‡РёРЅР°РµС‚СЃСЏ Р»Рё РїСѓС‚СЊ СЃ /api/, /docs, /openapi.json РёР»Рё /uploads/
            if rest_of_path.startswith("api/") or \
               rest_of_path.startswith("docs") or \
               rest_of_path.startswith("openapi.json") or \
               rest_of_path.startswith("uploads/"):
                 # Р­С‚РѕС‚ РєРѕРґ РЅРµ РґРѕР»Р¶РµРЅ РІС‹РїРѕР»РЅСЏС‚СЊСЃСЏ, С‚.Рє. СЂРѕСѓС‚С‹ API/docs/uploads РѕРїСЂРµРґРµР»РµРЅС‹ РІС‹С€Рµ, РЅРѕ РґР»СЏ РЅР°РґРµР¶РЅРѕСЃС‚Рё
                 # Р›РѕРіРёСЂСѓРµРј РїРѕРїС‹С‚РєСѓ РґРѕСЃС‚СѓРїР° Рє API С‡РµСЂРµР· SPA catch-all
                 logger.debug(f"Р—Р°РїСЂРѕСЃ Рє '{rest_of_path}' РїРµСЂРµС…РІР°С‡РµРЅ SPA catch-all, РЅРѕ РїСЂРѕРёРіРЅРѕСЂРёСЂРѕРІР°РЅ (API/Docs/Uploads).")
                 # Р’Р°Р¶РЅРѕ РІРµСЂРЅСѓС‚СЊ 404, С‡С‚РѕР±С‹ FastAPI РјРѕРі РЅР°Р№С‚Рё РїСЂР°РІРёР»СЊРЅС‹Р№ РѕР±СЂР°Р±РѕС‚С‡РёРє, РµСЃР»Рё РѕРЅ РµСЃС‚СЊ
                 raise HTTPException(status_code=404, detail="Not Found (SPA Catch-all exclusion)")


            index_path = os.path.join(static_folder, "index.html")
            if os.path.exists(index_path):
                # Р›РѕРіРёСЂСѓРµРј РІРѕР·РІСЂР°С‚ index.html РґР»СЏ SPA РїСѓС‚Рё
                logger.debug(f"Р’РѕР·РІСЂР°С‰Р°РµРј index.html РґР»СЏ SPA РїСѓС‚Рё: '{rest_of_path}'")
                return FileResponse(index_path)
            else:
                logger.error(f"Р¤Р°Р№Р» index.html РЅРµ РЅР°Р№РґРµРЅ РІ {static_folder} РґР»СЏ РїСѓС‚Рё {rest_of_path}")
                raise HTTPException(status_code=404, detail="Index file not found")

        logger.info("РћР±СЂР°Р±РѕС‚С‡РёРєРё РґР»СЏ SPA РЅР°СЃС‚СЂРѕРµРЅС‹.")

    except RuntimeError as mount_error: # РРЎРџР РђР’Р›Р•РќРћ: Р”РѕР±Р°РІР»РµРЅ Р±Р»РѕРє except
        logger.error(f"РћС€РёР±РєР° РїСЂРё РјРѕРЅС‚РёСЂРѕРІР°РЅРёРё СЃС‚Р°С‚РёС‡РµСЃРєРёС… С„Р°Р№Р»РѕРІ SPA: {mount_error}. Р’РѕР·РјРѕР¶РЅРѕ, РёРјСЏ 'static-spa' СѓР¶Рµ РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РёР»Рё РїСѓС‚СЊ '/' Р·Р°РЅСЏС‚.")
    except Exception as e: # РРЎРџР РђР’Р›Р•РќРћ: Р”РѕР±Р°РІР»РµРЅ Р±Р»РѕРє except
        logger.error(f"РќРµРїСЂРµРґРІРёРґРµРЅРЅР°СЏ РѕС€РёР±РєР° РїСЂРё РјРѕРЅС‚РёСЂРѕРІР°РЅРёРё СЃС‚Р°С‚РёС‡РµСЃРєРёС… С„Р°Р№Р»РѕРІ SPA: {e}")
else:
    logger.warning(f"РџР°РїРєР° СЃС‚Р°С‚РёС‡РµСЃРєРёС… С„Р°Р№Р»РѕРІ SPA РЅРµ РЅР°Р№РґРµРЅР°: {static_folder}")
    logger.warning("РћР±СЃР»СѓР¶РёРІР°РЅРёРµ SPA С„СЂРѕРЅС‚РµРЅРґР° РЅРµ РЅР°СЃС‚СЂРѕРµРЅРѕ. РўРѕР»СЊРєРѕ API endpoints РґРѕСЃС‚СѓРїРЅС‹.")

# --- Р—Р°РїСѓСЃРє СЃРµСЂРІРµСЂР° (РѕР±С‹С‡РЅРѕ РІ РєРѕРЅС†Рµ С„Р°Р№Р»Р°) ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Р—Р°РїСѓСЃРє СЃРµСЂРІРµСЂР° РЅР° РїРѕСЂС‚Сѓ {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True) # reload=True РґР»СЏ СЂР°Р·СЂР°Р±РѕС‚РєРё

# Р”РѕР±Р°РІР»СЏРµРј РїСЂСЏРјРѕР№ СЌРЅРґРїРѕРёРЅС‚ РґР»СЏ РїСЂРѕРІРµСЂРєРё Рё РѕР±РЅРѕРІР»РµРЅРёСЏ СЃС‚Р°С‚СѓСЃР° РїРѕРґРїРёСЃРєРё РёР· РєР»РёРµРЅС‚Р°
@app.get("/direct_premium_check", status_code=200)
async def direct_premium_check(request: Request, user_id: Optional[str] = None):
    """
    РџСЂСЏРјР°СЏ РїСЂРѕРІРµСЂРєР° РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР° РґР»СЏ РєР»РёРµРЅС‚Р°.
    РџСЂРёРЅРёРјР°РµС‚ user_id РІ РїР°СЂР°РјРµС‚СЂРµ Р·Р°РїСЂРѕСЃР° РёР»Рё Р±РµСЂРµС‚ РµРіРѕ РёР· Р·Р°РіРѕР»РѕРІРєР° x-telegram-user-id.
    """
    # Р”РѕР±Р°РІР»СЏРµРј Р·Р°РіРѕР»РѕРІРєРё CORS С‡С‚РѕР±С‹ API СЂР°Р±РѕС‚Р°Р»Рѕ РєРѕСЂСЂРµРєС‚РЅРѕ
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Content-Type": "application/json"
    }
    
    try:
        effective_user_id = user_id
        
        # Р•СЃР»Рё user_id РЅРµ РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅ РІ РїР°СЂР°РјРµС‚СЂР°С…, РїСЂРѕРІРµСЂСЏРµРј Р·Р°РіРѕР»РѕРІРєРё
        if not effective_user_id:
            effective_user_id = request.headers.get("x-telegram-user-id")
            
        # Р•СЃР»Рё РІСЃРµ СЂР°РІРЅРѕ РЅРµС‚ ID, РїСЂРѕР±СѓРµРј РїРѕР»СѓС‡РёС‚СЊ РёР· РґР°РЅРЅС‹С… Р·Р°РїСЂРѕСЃР°
        if not effective_user_id and hasattr(request, "state"):
            effective_user_id = request.state.get("user_id")
        
        # Р›РѕРіРёСЂСѓРµРј РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ Р·Р°РїСЂРѕСЃРµ
        logger.info(f"РџСЂСЏРјР°СЏ РїСЂРѕРІРµСЂРєР° РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР° РґР»СЏ user_id: {effective_user_id}")
            
        if not effective_user_id:
            return JSONResponse(
                content={
                    "has_premium": False,
                    "user_id": None,
                    "error": "ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РЅРµ РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅ",
                    "message": "РќРµ СѓРґР°Р»РѕСЃСЊ РѕРїСЂРµРґРµР»РёС‚СЊ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ"
                },
                headers=headers
            )
            
        # РџСЂРѕРІРµСЂСЏРµРј РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃ С‡РµСЂРµР· REST API
        try:
            # РџСЂРѕРІРµСЂСЏРµРј, РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ Р»Рё Supabase РєР»РёРµРЅС‚
            if not supabase:
                logger.error("Supabase РєР»РёРµРЅС‚ РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
                return JSONResponse(
                    content={
                        "has_premium": False,
                        "user_id": effective_user_id,
                        "error": "Supabase client not initialized"
                    },
                    headers=headers
                )
            
            # Р—Р°РїСЂР°С€РёРІР°РµРј Р°РєС‚РёРІРЅС‹Рµ РїРѕРґРїРёСЃРєРё РґР»СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ С‡РµСЂРµР· REST API
            subscription_query = supabase.table("user_subscription").select("*").eq("user_id", effective_user_id).eq("is_active", True).execute()
            
            logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ Р·Р°РїСЂРѕСЃР° РїРѕРґРїРёСЃРєРё С‡РµСЂРµР· REST API: data={subscription_query.data if hasattr(subscription_query, 'data') else None} count={len(subscription_query.data) if hasattr(subscription_query, 'data') else 0}")
            
            has_premium = False
            subscription_end_date = None
            
            # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚С‹ Р·Р°РїСЂРѕСЃР°
            if hasattr(subscription_query, 'data') and subscription_query.data:
                from datetime import datetime, timezone
                
                # РџСЂРѕРІРµСЂСЏРµРј РїРѕРґРїРёСЃРєРё РЅР° Р°РєС‚РёРІРЅРѕСЃС‚СЊ Рё СЃСЂРѕРє
                # РЎРѕР·РґР°РµРј datetime СЃ UTC timezone
                current_date = datetime.now(timezone.utc)
                logger.info(f"РўРµРєСѓС‰Р°СЏ РґР°С‚Р° СЃ timezone: {current_date.isoformat()}")
                active_subscriptions = []
                
                for subscription in subscription_query.data:
                    end_date = subscription.get("end_date")
                    if end_date:
                        try:
                            # РџСЂРµРѕР±СЂР°Р·СѓРµРј РґР°С‚Сѓ РёР· СЃС‚СЂРѕРєРё РІ РѕР±СЉРµРєС‚ datetime c timezone
                            if isinstance(end_date, str):
                                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                            
                            # Р•СЃР»Рё РґР°С‚Р° РѕРєРѕРЅС‡Р°РЅРёСЏ РІ Р±СѓРґСѓС‰РµРј, РґРѕР±Р°РІР»СЏРµРј РІ Р°РєС‚РёРІРЅС‹Рµ
                            logger.info(f"РЎСЂР°РІРЅРµРЅРёРµ РґР°С‚: end_date={end_date.isoformat()}, current_date={current_date.isoformat()}")
                            if end_date > current_date:
                                active_subscriptions.append(subscription)
                                logger.info(f"РџРѕРґРїРёСЃРєР° Р°РєС‚РёРІРЅР°: end_date РїРѕР·Р¶Рµ С‚РµРєСѓС‰РµР№ РґР°С‚С‹")
                            else:
                                logger.info(f"РџРѕРґРїРёСЃРєР° РЅРµР°РєС‚РёРІРЅР°: end_date СЂР°РЅСЊС€Рµ С‚РµРєСѓС‰РµР№ РґР°С‚С‹")
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
                    subscription_end_date = end_date.strftime('%Y-%m-%d %H:%M:%S')
            
            logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ РїСЂРѕРІРµСЂРєРё РїРѕРґРїРёСЃРєРё РґР»СЏ {effective_user_id}: has_premium={has_premium}, end_date={subscription_end_date}")
            
            # РџРѕР»СѓС‡Р°РµРј Р»РёРјРёС‚С‹ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ РІ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё РѕС‚ СЃС‚Р°С‚СѓСЃР°
            analysis_count = 9999 if has_premium else 3  # Р”Р»СЏ РїСЂРµРјРёСѓРј - РЅРµРѕРіСЂР°РЅРёС‡РµРЅРЅРѕ, РґР»СЏ Р±РµСЃРїР»Р°С‚РЅРѕРіРѕ - 3
            post_generation_count = 9999 if has_premium else 1  # Р”Р»СЏ РїСЂРµРјРёСѓРј - РЅРµРѕРіСЂР°РЅРёС‡РµРЅРЅРѕ, РґР»СЏ Р±РµСЃРїР»Р°С‚РЅРѕРіРѕ - 1
            
            # Р¤РѕСЂРјРёСЂСѓРµРј РѕС‚РІРµС‚
            response_data = {
                "has_premium": has_premium,
                "user_id": effective_user_id,
                "error": None,
                "analysis_count": analysis_count,
                "post_generation_count": post_generation_count
            }
            
            # Р”РѕР±Р°РІР»СЏРµРј РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ РїРѕРґРїРёСЃРєРё, РµСЃР»Рё РµСЃС‚СЊ
            if subscription_end_date:
                response_data["subscription_end_date"] = subscription_end_date
            
            return JSONResponse(content=response_data, headers=headers)
            
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РїСЂРё РїСЂСЏРјРѕР№ РїСЂРѕРІРµСЂРєРµ РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР° С‡РµСЂРµР· REST API: {e}")
            
            # РђР»СЊС‚РµСЂРЅР°С‚РёРІРЅС‹Р№ СЃРїРѕСЃРѕР± СЃ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёРµРј httpx
            try:
                supabase_url = os.getenv("SUPABASE_URL")
                supabase_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
                
                if not supabase_url or not supabase_key:
                    raise ValueError("РћС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ SUPABASE_URL РёР»Рё SUPABASE_KEY")
                
                # Р¤РѕСЂРјРёСЂСѓРµРј Р·Р°РїСЂРѕСЃ Рє REST API Supabase
                httpx_headers = {
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json"
                }
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{supabase_url}/rest/v1/user_subscription",
                        headers=httpx_headers,
                        params={
                            "select": "*",
                            "user_id": f"eq.{effective_user_id}",
                            "is_active": "eq.true"
                        }
                    )
                    
                    if response.status_code == 200:
                        subscriptions = response.json()
                        logger.info(f"РџРѕР»СѓС‡РµРЅС‹ РїРѕРґРїРёСЃРєРё С‡РµСЂРµР· httpx: {subscriptions}")
                        
                        # РџСЂРѕРІРµСЂСЏРµРј РїРѕРґРїРёСЃРєРё РЅР° Р°РєС‚РёРІРЅРѕСЃС‚СЊ Рё СЃСЂРѕРє
                        from datetime import datetime, timezone
                        # РЎРѕР·РґР°РµРј datetime СЃ UTC timezone
                        current_date = datetime.now(timezone.utc)
                        logger.info(f"РўРµРєСѓС‰Р°СЏ РґР°С‚Р° СЃ timezone (httpx): {current_date.isoformat()}")
                        active_subscriptions = []
                        
                        for subscription in subscriptions:
                            end_date = subscription.get("end_date")
                            if end_date:
                                try:
                                    # РџСЂРµРѕР±СЂР°Р·СѓРµРј РґР°С‚Сѓ РёР· СЃС‚СЂРѕРєРё РІ РѕР±СЉРµРєС‚ datetime c timezone
                                    if isinstance(end_date, str):
                                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                    
                                    # Р•СЃР»Рё РґР°С‚Р° РѕРєРѕРЅС‡Р°РЅРёСЏ РІ Р±СѓРґСѓС‰РµРј, РґРѕР±Р°РІР»СЏРµРј РІ Р°РєС‚РёРІРЅС‹Рµ
                                    logger.info(f"РЎСЂР°РІРЅРµРЅРёРµ РґР°С‚ (httpx): end_date={end_date.isoformat()}, current_date={current_date.isoformat()}")
                                    if end_date > current_date:
                                        active_subscriptions.append(subscription)
                                        logger.info(f"РџРѕРґРїРёСЃРєР° Р°РєС‚РёРІРЅР° (httpx): end_date РїРѕР·Р¶Рµ С‚РµРєСѓС‰РµР№ РґР°С‚С‹")
                                    else:
                                        logger.info(f"РџРѕРґРїРёСЃРєР° РЅРµР°РєС‚РёРІРЅР° (httpx): end_date СЂР°РЅСЊС€Рµ С‚РµРєСѓС‰РµР№ РґР°С‚С‹")
                                except Exception as e:
                                    logger.error(f"РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ РґР°С‚С‹ РїРѕРґРїРёСЃРєРё {end_date}: {e}")
                        
                        # Р•СЃР»Рё РµСЃС‚СЊ Р°РєС‚РёРІРЅС‹Рµ РїРѕРґРїРёСЃРєРё, СѓСЃС‚Р°РЅР°РІР»РёРІР°РµРј has_premium = True
                        has_premium = bool(active_subscriptions)
                        subscription_end_date = None
                        
                        if active_subscriptions:
                            # Р‘РµСЂРµРј СЃР°РјСѓСЋ РїРѕР·РґРЅСЋСЋ РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ
                            latest_subscription = max(active_subscriptions, key=lambda x: x.get("end_date"))
                            end_date = latest_subscription.get("end_date")
                            if isinstance(end_date, str):
                                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                            subscription_end_date = end_date.strftime('%Y-%m-%d %H:%M:%S')
                        
                        logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ РїСЂРѕРІРµСЂРєРё РїРѕРґРїРёСЃРєРё С‡РµСЂРµР· httpx РґР»СЏ {effective_user_id}: has_premium={has_premium}, end_date={subscription_end_date}")
                        
                        # РџРѕР»СѓС‡Р°РµРј Р»РёРјРёС‚С‹ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ
                        analysis_count = 9999 if has_premium else 3
                        post_generation_count = 9999 if has_premium else 1
                        
                        # Р¤РѕСЂРјРёСЂСѓРµРј РѕС‚РІРµС‚
                        response_data = {
                            "has_premium": has_premium,
                            "user_id": effective_user_id,
                            "error": None,
                            "analysis_count": analysis_count,
                            "post_generation_count": post_generation_count
                        }
                        
                        # Р”РѕР±Р°РІР»СЏРµРј РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ РїРѕРґРїРёСЃРєРё, РµСЃР»Рё РµСЃС‚СЊ
                        if subscription_end_date:
                            response_data["subscription_end_date"] = subscription_end_date
                        
                        return JSONResponse(content=response_data, headers=headers)
                    else:
                        logger.error(f"РћС€РёР±РєР° РїСЂРё Р·Р°РїСЂРѕСЃРµ Рє Supabase REST API: {response.status_code} - {response.text}")
                        return JSONResponse(
                            content={
                                "has_premium": False,
                                "user_id": effective_user_id,
                                "error": f"HTTP Error: {response.status_code}"
                            },
                            headers=headers
                        )
            
            except Exception as httpx_error:
                logger.error(f"РћС€РёР±РєР° РїСЂРё РїСЂРѕРІРµСЂРєРµ РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР° С‡РµСЂРµР· httpx: {httpx_error}")
                return JSONResponse(
                    content={
                        "has_premium": False,
                        "user_id": effective_user_id,
                        "error": str(httpx_error)
                    },
                    headers=headers
                )
    
    except Exception as e:
        logger.error(f"РћС€РёР±РєР° РїСЂРё РїСЂСЏРјРѕР№ РїСЂРѕРІРµСЂРєРµ РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР°: {e}")
        return JSONResponse(
            content={
                "has_premium": False,
                "user_id": effective_user_id if 'effective_user_id' in locals() else None,
                "error": str(e)
            },
            headers=headers
        )

# Р”РѕР±Р°РІР»СЏРµРј СЌРЅРґРїРѕРёРЅС‚ РґР»СЏ API v2 РґР»СЏ РїСЂРѕРІРµСЂРєРё РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР°
@app.get("/api-v2/premium/check", status_code=200)
async def premium_check_v2(request: Request, user_id: Optional[str] = None):
    """РђР»СЊС‚РµСЂРЅР°С‚РёРІРЅС‹Р№ СЌРЅРґРїРѕРёРЅС‚ РґР»СЏ РїСЂРѕРІРµСЂРєРё РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР° (API v2)"""
    return await direct_premium_check(request, user_id)

# Р”РѕР±Р°РІР»СЏРµРј raw API СЌРЅРґРїРѕРёРЅС‚ РґР»СЏ РѕР±С…РѕРґР° SPA СЂРѕСѓС‚РµСЂР°
@app.get("/raw-api-data/xyz123/premium-data/{user_id}", status_code=200)
async def raw_premium_data(user_id: str, request: Request):
    """
    РЎРїРµС†РёР°Р»СЊРЅС‹Р№ РЅРµСЃС‚Р°РЅРґР°СЂС‚РЅС‹Р№ URL РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР° РІ РѕР±С…РѕРґ SPA СЂРѕСѓС‚РµСЂР°.
    """
    return await direct_premium_check(request, user_id)

# Р”РѕР±Р°РІР»СЏРµРј СЌРЅРґРїРѕРёРЅС‚ РґР»СЏ РїСЂРѕРІРµСЂРєРё СЃС‚Р°С‚СѓСЃР° РїРѕРґРїРёСЃРєРё (РґР»СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё СЃ РєР»РёРµРЅС‚СЃРєРёРј РєРѕРґРѕРј)
@app.get("/subscription/status", status_code=200)
async def subscription_status(request: Request, user_id: Optional[str] = None):
    """
    РџСЂРѕРІРµСЂРєР° СЃС‚Р°С‚СѓСЃР° РїРѕРґРїРёСЃРєРё.
    РџРѕРґРґРµСЂР¶РёРІР°РµС‚СЃСЏ РґР»СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё СЃ РєР»РёРµРЅС‚СЃРєРёРј РєРѕРґРѕРј.
    Р”СѓР±Р»РёСЂСѓРµС‚ С„СѓРЅРєС†РёРѕРЅР°Р»СЊРЅРѕСЃС‚СЊ direct_premium_check.
    """
    logger.info(f"Р—Р°РїСЂРѕСЃ /subscription/status РґР»СЏ user_id: {user_id}")
    result = await direct_premium_check(request, user_id)
    
    # РџСЂРµРѕР±СЂР°Р·СѓРµРј С„РѕСЂРјР°С‚ РѕС‚РІРµС‚Р° РґР»СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё СЃ РёРЅС‚РµСЂС„РµР№СЃРѕРј РєР»РёРµРЅС‚Р°
    if isinstance(result, JSONResponse):
        data = result.body
        if isinstance(data, bytes):
            import json
            try:
                data = json.loads(data.decode('utf-8'))
            except:
                data = {}
    else:
        data = result
    
    return JSONResponse(
        content={
            "has_subscription": data.get("has_premium", False),
            "analysis_count": data.get("analysis_count", 3),
            "post_generation_count": data.get("post_generation_count", 1),
            "subscription_end_date": data.get("subscription_end_date")
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Content-Type": "application/json"
        }
    )

# Р”РѕР±Р°РІР»СЏРµРј РЅРѕРІС‹Р№ СЌРЅРґРїРѕРёРЅС‚ РґР»СЏ РїСЂСЏРјРѕРіРѕ РґРѕСЃС‚СѓРїР° Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С… РґР»СЏ РїСЂРѕРІРµСЂРєРё РїСЂРµРјРёСѓРј, РєР°Рє СЌС‚Рѕ РґРµР»Р°РµС‚ Р±РѕС‚
@app.get("/bot-style-premium-check/{user_id}", status_code=200)
async def bot_style_premium_check(user_id: str, request: Request):
    """
    РџСЂСЏРјР°СЏ РїСЂРѕРІРµСЂРєР° РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР° С‡РµСЂРµР· Р±Р°Р·Сѓ РґР°РЅРЅС‹С…, РёСЃРїРѕР»СЊР·СѓСЏ С‚РѕС‚ Р¶Рµ РјРµС‚РѕРґ, РєРѕС‚РѕСЂС‹Р№ РёСЃРїРѕР»СЊР·СѓРµС‚ Р±РѕС‚.
    Р­С‚РѕС‚ СЌРЅРґРїРѕРёРЅС‚ РёРіРЅРѕСЂРёСЂСѓРµС‚ РєСЌС€РёСЂРѕРІР°РЅРёРµ Рё РїСЂРѕРјРµР¶СѓС‚РѕС‡РЅС‹Рµ СЃР»РѕРё, СЂР°Р±РѕС‚Р°СЏ РЅР°РїСЂСЏРјСѓСЋ СЃ Р±Р°Р·РѕР№ РґР°РЅРЅС‹С….
    """
    try:
        logger.info(f"[BOT-STYLE] Р—Р°РїСЂРѕСЃ РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР° РґР»СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ: {user_id}")
        
        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ user_id РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅ Рё РїСЂРµРѕР±СЂР°Р·СѓРµРј РµРіРѕ РІ int
        if not user_id:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РЅРµ СѓРєР°Р·Р°РЅ"}
            )
        
        try:
            user_id_int = int(user_id)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ С‡РёСЃР»РѕРј"}
            )
        
        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ Сѓ РЅР°СЃ РµСЃС‚СЊ РґРѕСЃС‚СѓРї Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…
        db_url = os.getenv("SUPABASE_URL") or os.getenv("DATABASE_URL") or os.getenv("RENDER_DATABASE_URL")
        if not db_url:
            logger.error("[BOT-STYLE] РћС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ SUPABASE_URL, DATABASE_URL Рё RENDER_DATABASE_URL")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "РћС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ РЅР°СЃС‚СЂРѕР№РєРё РїРѕРґРєР»СЋС‡РµРЅРёСЏ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С…"}
            )
            
        # РќРѕСЂРјР°Р»РёР·СѓРµРј URL Р±Р°Р·С‹ РґР°РЅРЅС‹С…
        db_url = normalize_db_url(db_url)
        
        # РџРѕРґРєР»СЋС‡Р°РµРјСЃСЏ РЅР°РїСЂСЏРјСѓСЋ Рє Р±Р°Р·Рµ РґР°РЅРЅС‹С… (С‚Р°Рє Р¶Рµ, РєР°Рє СЌС‚Рѕ РґРµР»Р°РµС‚ Р±РѕС‚)
        conn = await asyncpg.connect(db_url)
        try:
            # РџСЂРѕРІРµСЂСЏРµРј РЅР°Р»РёС‡РёРµ Р°РєС‚РёРІРЅРѕР№ РїРѕРґРїРёСЃРєРё
            query = """
            SELECT
                id,
                user_id,
                start_date,
                end_date,
                is_active,
                payment_id,
                created_at,
                updated_at
            FROM user_subscription 
            WHERE user_id = $1 
              AND is_active = TRUE 
              AND end_date > NOW()
            ORDER BY end_date DESC
            LIMIT 1
            """
            
            subscription = await conn.fetchrow(query, user_id_int)
            
            # РџСЂРѕРІРµСЂСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
            if subscription:
                # РџРѕРґРїРёСЃРєР° СЃСѓС‰РµСЃС‚РІСѓРµС‚ Рё Р°РєС‚РёРІРЅР°
                has_premium = True
                subscription_end_date = subscription["end_date"].strftime('%Y-%m-%d %H:%M:%S') if subscription["end_date"] else None
                
                # Р¤РѕСЂРјР°С‚РёСЂСѓРµРј subscription РІ СЃР»РѕРІР°СЂСЊ
                subscription_data = {
                    "id": subscription["id"],
                    "user_id": subscription["user_id"],
                    "start_date": subscription["start_date"].strftime('%Y-%m-%d %H:%M:%S') if subscription["start_date"] else None,
                    "end_date": subscription_end_date,
                    "is_active": subscription["is_active"],
                    "payment_id": subscription["payment_id"],
                    "created_at": subscription["created_at"].strftime('%Y-%m-%d %H:%M:%S') if subscription["created_at"] else None,
                    "updated_at": subscription["updated_at"].strftime('%Y-%m-%d %H:%M:%S') if subscription["updated_at"] else None
                }
            else:
                # РџРѕРґРїРёСЃРєР° РЅРµ СЃСѓС‰РµСЃС‚РІСѓРµС‚ РёР»Рё РЅРµ Р°РєС‚РёРІРЅР°
                has_premium = False
                subscription_data = None
                subscription_end_date = None
            
            # РџРѕР»СѓС‡Р°РµРј Р»РёРјРёС‚С‹ РІ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё РѕС‚ СЃС‚Р°С‚СѓСЃР° РїРѕРґРїРёСЃРєРё
            analysis_count = 9999 if has_premium else 3
            post_generation_count = 9999 if has_premium else 1
            
            # Р¤РѕСЂРјРёСЂСѓРµРј РѕС‚РІРµС‚
            response = {
                "success": True,
                "user_id": user_id_int,
                "has_premium": has_premium,
                "analysis_count": analysis_count,
                "post_generation_count": post_generation_count,
                "subscription": subscription_data
            }
            
            # Р”РѕР±Р°РІР»СЏРµРј РґР°С‚Сѓ РѕРєРѕРЅС‡Р°РЅРёСЏ РїРѕРґРїРёСЃРєРё РµСЃР»Рё РµСЃС‚СЊ
            if subscription_end_date:
                response["subscription_end_date"] = subscription_end_date
            
            # Р’РѕР·РІСЂР°С‰Р°РµРј РѕС‚РІРµС‚ СЃ Р·Р°РіРѕР»РѕРІРєР°РјРё CORS
            return JSONResponse(
                content=response,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                    "Content-Type": "application/json"
                }
            )
            
        finally:
            # Р—Р°РєСЂС‹РІР°РµРј СЃРѕРµРґРёРЅРµРЅРёРµ СЃ Р±Р°Р·РѕР№ РґР°РЅРЅС‹С…
            await conn.close()
        
    except Exception as e:
        logger.error(f"[BOT-STYLE] РћС€РёР±РєР° РїСЂРё РїСЂРѕРІРµСЂРєРµ РїСЂРµРјРёСѓРј-СЃС‚Р°С‚СѓСЃР°: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


