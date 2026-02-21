from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.schemas import EventCreate, EventOut
from app.services.event_service import event_service

router = APIRouter(tags=["Events"])

@router.post("", response_model=EventOut, status_code=201)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return event_service.create_view(
        db=db,
        user_id=user.user_id,
        movie_id=payload.movie_id,
    )
