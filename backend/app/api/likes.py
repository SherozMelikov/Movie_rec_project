from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.db.models import Like
from backend.app.schemas.schemas import LikeCreate, LikeRead

router = APIRouter()

# Add a like
@router.post("/", response_model=LikeRead)
def add_like(like: LikeCreate, db: Session = Depends(get_db)):
    db_like = db.query(Like).filter(
        Like.user_id == like.user_id, Like.movie_id == like.movie_id
    ).first()
    if db_like:
        return db_like
    db_like = Like(**like.dict())
    db.add(db_like)
    db.commit()
    db.refresh(db_like)
    return db_like

# Get all likes by user
@router.get("/{user_id}", response_model=list[LikeRead])
def get_user_likes(user_id: int, db: Session = Depends(get_db)):
    likes = db.query(Like).filter(Like.user_id == user_id).all()
    return likes
