from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from uuid import UUID

class PostImage(BaseModel):
    url: str
    id: Optional[str] = None
    preview_url: Optional[str] = None
    alt: Optional[str] = None
    author: Optional[str] = None
    author_url: Optional[str] = None
    source: Optional[str] = None

class PostData(BaseModel):
    target_date: str
    topic_idea: str
    format_style: str
    final_text: str
    image_url: Optional[str] = None
    images_ids: Optional[List[str]] = None
    channel_name: Optional[str] = None
    selected_image_data: Optional[PostImage] = None

class SavedPostResponse(PostData):
    id: str
    created_at: str
    updated_at: str

router = APIRouter()

@router.get("/posts", response_model=List[SavedPostResponse])
async def get_posts(request: Request, channel_name: Optional[str] = None):
    # Заглушка для получения постов
    return []

@router.post("/posts", response_model=SavedPostResponse)
async def create_post(request: Request, post_data: PostData):
    # Заглушка для создания поста
    return SavedPostResponse(**post_data.dict(), id="1", created_at="", updated_at="")

@router.put("/posts/{post_id}", response_model=SavedPostResponse)
async def update_post(post_id: str, request: Request, post_data: PostData):
    # Заглушка для обновления поста
    return SavedPostResponse(**post_data.dict(), id=post_id, created_at="", updated_at="")

@router.delete("/posts/{post_id}")
async def delete_post(post_id: str, request: Request):
    # Заглушка для удаления поста
    return {"success": True, "message": f"Пост {post_id} удалён (заглушка)"} 