from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models import Movie, Event, EventType

VIEW_COOLDOWN_SECONDS = 60

class EventService:
    def create_view(self, db: Session, user_id: int, movie_id: int) -> Event:
        exists = db.query(Movie.movie_id).filter(Movie.movie_id == movie_id).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Movie not found")

        latest = (
            db.query(Event)
            .filter(
                Event.user_id == user_id,
                Event.movie_id == movie_id,
                Event.event_type == EventType.view,
            )
            .order_by(Event.ts.desc())
            .first()
        )

        if latest and latest.ts:
            now = datetime.now(tz=latest.ts.tzinfo)
            if latest.ts + timedelta(seconds=VIEW_COOLDOWN_SECONDS) > now:
                return latest

        e = Event(
            user_id=user_id,
            movie_id=movie_id,
            event_type=EventType.view,
        )

        db.add(e)
        db.commit()
        db.refresh(e)
        return e

event_service = EventService()