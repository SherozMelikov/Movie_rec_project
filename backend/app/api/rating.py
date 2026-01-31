from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.db.models import Rating
from backend.app.schemas.schemas import RatingCreate, RatingRead

router = APIRouter()

# Add or update rating
@router.post("/", response_model=RatingRead)
def add_rating(rating: RatingCreate, db: Session = Depends(get_db)):
    db_rating = db.query(Rating).filter(
        Rating.user_id == rating.user_id, Rating.movie_id == rating.movie_id
    ).first()
    if db_rating:
        db_rating.rating = rating.rating
    else:
        db_rating = Rating(**rating.dict())
        db.add(db_rating)
    db.commit()
    db.refresh(db_rating)
    return db_rating

# Get all ratings by user
@router.get("/{user_id}", response_model=list[RatingRead])
def get_user_ratings(user_id: int, db: Session = Depends(get_db)):
    ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
    return ratings
