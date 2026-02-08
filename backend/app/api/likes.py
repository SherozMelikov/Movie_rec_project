from fastapi import APIRouter, Request
from app.schemas.schemas import LikeCreate

router = APIRouter()

@router.post("/")
def add_like(like: LikeCreate, request: Request):
    like_service = request.app.state.like_service
    return like_service.add_like(like)
