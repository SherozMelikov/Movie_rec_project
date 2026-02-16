from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.db.database import get_db
from app.db.models import Movie, Rating, User

router = APIRouter(tags=["Ratings"])

class RatingUpsert(BaseModel):
    score: int = Field(..., ge=1, le=5)

@router.get("/{movie_id}")
def get_my_rating(movie_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = (
        db.query(Rating)
        .filter(Rating.user_id == user.user_id, Rating.movie_id == movie_id)
        .first()
    )
    return {"score": r.score if r else None}

@router.put("/{movie_id}")
def set_rating(movie_id: int, payload: RatingUpsert, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # validate movie
    if not db.query(Movie.movie_id).filter(Movie.movie_id == movie_id).first():
        raise HTTPException(status_code=404, detail="Movie not found")

    r = (
        db.query(Rating)
        .filter(Rating.user_id == user.user_id, Rating.movie_id == movie_id)
        .first()
    )
    if r:
        r.score = payload.score
    else:
        r = Rating(user_id=user.user_id, movie_id=movie_id, score=payload.score)
        db.add(r)

    db.commit()
    db.refresh(r)
    return {"score": r.score}
