from __future__ import annotations

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models import Movie, Like


class LikeService:
    def like(self, db: Session, user_id: int, movie_id: int) -> bool:
        exists = db.query(Movie.movie_id).filter(Movie.movie_id == movie_id).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Movie not found")

        found = (
            db.query(Like)
            .filter(Like.user_id == user_id, Like.movie_id == movie_id)
            .first()
        )
        if found:
            return True  # idempotent

        db.add(Like(user_id=user_id, movie_id=movie_id))
        db.commit()
        return True

    def unlike(self, db: Session, user_id: int, movie_id: int) -> bool:
        found = (
            db.query(Like)
            .filter(Like.user_id == user_id, Like.movie_id == movie_id)
            .first()
        )
        if not found:
            return False  # idempotent

        db.delete(found)
        db.commit()
        return True

    def is_liked(self, db: Session, user_id: int, movie_id: int) -> bool:
        return (
            db.query(Like)
            .filter(Like.user_id == user_id, Like.movie_id == movie_id)
            .first()
            is not None
        )


like_service = LikeService()
