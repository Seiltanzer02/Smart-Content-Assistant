from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from uuid import UUID
from backend.main import get_posts, create_post, update_post, delete_post, generate_post_details, save_image, get_user_images, get_image_by_id, get_post_images, proxy_image

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

class PostDetailsResponse(BaseModel):
    details: str

class GeneratePostDetailsRequest(BaseModel):
    post_id: str

router = APIRouter()

@router.get("/posts", response_model=List[SavedPostResponse])
async def get_posts_router(request: Request, channel_name: Optional[str] = None):
    return await get_posts(request, channel_name)

@router.post("/posts", response_model=SavedPostResponse)
async def create_post_router(request: Request, post_data: PostData):
    return await create_post(request, post_data)

@router.put("/posts/{post_id}", response_model=SavedPostResponse)
async def update_post_router(post_id: str, request: Request, post_data: PostData):
    return await update_post(post_id, request, post_data)

@router.delete("/posts/{post_id}")
async def delete_post_router(post_id: str, request: Request):
    return await delete_post(post_id, request)

@router.post("/generate-post-details", response_model=PostDetailsResponse)
async def generate_post_details_router(request: Request, req: GeneratePostDetailsRequest):
    return await generate_post_details(request, req)

@router.post("/save-image", response_model=Dict[str, Any])
async def save_image_router(request: Request, image_data: Dict[str, Any]):
    return await save_image(request, image_data)

@router.get("/images", response_model=List[Dict[str, Any]])
async def get_user_images_router(request: Request, limit: int = 20):
    return await get_user_images(request, limit)

@router.get("/images/{image_id}", response_model=Dict[str, Any])
async def get_image_by_id_router(request: Request, image_id: str):
    return await get_image_by_id(request, image_id)

@router.get("/post-images/{post_id}", response_model=List[Dict[str, Any]])
async def get_post_images_router(request: Request, post_id: str):
    return await get_post_images(request, post_id)

@router.get("/image-proxy/{image_id}")
async def proxy_image_router(request: Request, image_id: str, size: Optional[str] = None):
    return await proxy_image(request, image_id, size) 