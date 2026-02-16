from __future__ import annotations

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models import Movie, Rating


class RatingService:
    def upsert(self, db: Session, user_id: int, movie_id: int, score: int) -> int:
        if score < 1 or score > 5:
            raise HTTPException(status_code=400, detail="score must be between 1 and 5")

        exists = db.query(Movie.movie_id).filter(Movie.movie_id == movie_id).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Movie not found")

        r = (
            db.query(Rating)
            .filter(Rating.user_id == user_id, Rating.movie_id == movie_id)
            .first()
        )

        if r:
            r.score = score
        else:
            r = Rating(user_id=user_id, movie_id=movie_id, score=score)
            db.add(r)

        db.commit()
        db.refresh(r)
        return r.score

    def get_my_score(self, db: Session, user_id: int, movie_id: int) -> int | None:
        r = (
            db.query(Rating)
            .filter(Rating.user_id == user_id, Rating.movie_id == movie_id)
            .first()
        )
        return r.score if r else None


rating_service = RatingService()
