from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.database import get_db
from app.db.models import Event, User
from app.schemas.schemas import EventCreate, EventOut
from app.services.event_service import event_service

router = APIRouter()


@router.post("", response_model=EventOut, status_code=201)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return event_service.create_event(
        db=db,
        user_id=user.user_id,
        movie_id=payload.movie_id,
        event_type=payload.event_type,
        rating_value=payload.rating_value,
    )

@router.get("/me", response_model=list[EventOut])
def my_events(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(Event)
        .filter(Event.user_id == user.user_id)
        .order_by(Event.ts.desc())
        .limit(limit)
        .all()
    )
