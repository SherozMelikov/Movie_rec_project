from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.schemas import OnboardingCreate, OnboardingOut
from app.services.onboarding_service import onboarding_service

router = APIRouter()


@router.post("", response_model=OnboardingOut)
def save_onboarding(
    payload: OnboardingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return onboarding_service.save_onboarding(
        db=db,
        user_id=user.user_id,
        favorite_genres=payload.favorite_genres,
        picked_movie_ids=payload.picked_movie_ids,
    )


@router.get("/me", response_model=OnboardingOut | None)
def get_my_onboarding(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return onboarding_service.get_my_onboarding(db=db, user_id=user.user_id)
