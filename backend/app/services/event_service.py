from __future__ import annotations

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models import Movie, Event, EventType


class EventService:
    def create_event(
        self,
        db: Session,
        user_id: int,
        movie_id: int,
        event_type: str,
        rating_value: int | None,
    ) -> Event:
        # validate movie exists (avoid FK error + clearer message)
        exists = db.query(Movie.movie_id).filter(Movie.movie_id == movie_id).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Movie not found")

        # enforce rating presence rules at service level too (DB also checks)
        if event_type == "rate" and rating_value is None:
            raise HTTPException(status_code=400, detail="rating_value is required for rate event")
        if event_type != "rate" and rating_value is not None:
            raise HTTPException(status_code=400, detail="rating_value is only allowed for rate event")

        e = Event(
            user_id=user_id,
            movie_id=movie_id,
            event_type=EventType(event_type),
            rating_value=rating_value,
        )

        db.add(e)
        try:
            db.commit()
        except Exception as ex:
            db.rollback()
            # If you enabled unique like index, duplicate like will land here
            raise HTTPException(status_code=409, detail="Duplicate or invalid event") from ex

        db.refresh(e)
        return e


event_service = EventService()
