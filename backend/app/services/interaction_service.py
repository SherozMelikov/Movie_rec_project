# app/services/interaction_service.py
from sqlalchemy.orm import Session
from app.db.models import Rating, Like, Tag

# Rating
def create_rating(db: Session, user_id: int, movie_id: int, score: int):
    rating = Rating(user_id=user_id, movie_id=movie_id, score=score)
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating

# Like
def create_like(db: Session, user_id: int, movie_id: int):
    like = Like(user_id=user_id, movie_id=movie_id)
    db.add(like)
    db.commit()
    db.refresh(like)
    return like

# Tag
def create_tag(db: Session, user_id: int, movie_id: int, tag_text: str):
    tag = Tag(user_id=user_id, movie_id=movie_id, tag=tag_text)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag
