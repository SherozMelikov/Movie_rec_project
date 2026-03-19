from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.database import get_db
from app.db.models import Like, Movie, User
from fastapi import HTTPException
router = APIRouter(tags=["Likes"])

@router.get("/{movie_id}")
def is_liked(movie_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    liked = (
        db.query(Like)
        .filter(Like.user_id == user.user_id, Like.movie_id == movie_id)
        .first()
        is not None
    )
    return {"liked": liked}

@router.post("/{movie_id}")
def like_movie(movie_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # validate movie
    if not db.query(Movie.movie_id).filter(Movie.movie_id == movie_id).first():
        
        raise HTTPException(status_code=404, detail="Movie not found")

    existing = (
        db.query(Like)
        .filter(Like.user_id == user.user_id, Like.movie_id == movie_id)
        .first()
    )
    if existing:
        return {"liked": True}  # idempotent

    db.add(Like(user_id=user.user_id, movie_id=movie_id))
    db.commit()
    return {"liked": True}

@router.delete("/{movie_id}", status_code=204)
def unlike_movie(movie_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    existing = (
        db.query(Like)
        .filter(Like.user_id == user.user_id, Like.movie_id == movie_id)
        .first()
    )
    if not existing:
        return  # idempotent

    db.delete(existing)
    db.commit()
    return
