from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User
from app.schemas.schemas import UserCreate, UserLogin, UserOut
from app.core.auth import get_current_user
from app.services.auth_service import signup_user, login_user, get_me_summary

router = APIRouter()


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    return signup_user(
        db,
        username=user.username,
        email=user.email,
        password=user.password,
    )


@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    return login_user(
        db,
        username=user.username,
        password=user.password,
    )


@router.get("/me")
def me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    summary = get_me_summary(db, user)
    return {
        "user": UserOut.model_validate(summary["user"]),
        "has_onboarding": summary["has_onboarding"],
        "event_count": summary["event_count"],
        "is_new": summary["is_new"],
    }