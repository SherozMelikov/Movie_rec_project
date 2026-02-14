# # app/api/interactions.py
# from fastapi import APIRouter, Depends
# from sqlalchemy.orm import Session
# from app.db.database import get_db
# from app.schemas.schemas import RatingCreate, RatingOut, LikeCreate, LikeOut, TagCreate, TagOut
# from app.services.interaction_service import create_like, create_rating, create_tag
# from app.core.auth import get_current_user
# from app.db.models import Rating , Like , Tag

# router = APIRouter()

# @router.post("/rating", response_model=RatingOut)
# def add_rating(
#     rating: RatingCreate,
#     db: Session = Depends(get_db),
#     current_user = Depends(get_current_user)
# ):
#     return create_rating(db, current_user.user_id, rating.movie_id, rating.score)

# @router.post("/likes", response_model=LikeOut)
# def add_like(
#     like: LikeCreate,
#     db: Session = Depends(get_db),
#     current_user = Depends(get_current_user)
# ):
#     return create_like(db, current_user.user_id, like.movie_id)


# @router.get("/ratings")
# def get_user_ratings(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
#     return db.query(Rating).filter(Rating.user_id == current_user.user_id).all()

# @router.get("/likes", response_model=list[LikeOut])
# def get_user_likes(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
#     return db.query(Like).filter(Like.user_id == current_user.user_id).all()

