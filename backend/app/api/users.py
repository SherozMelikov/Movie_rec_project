# app/api/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.database import get_db
from app.db.models import Event, User
from app.schemas.schemas import UserCreate, UserLogin, UserOut
from app.core.security import hash_password, verify_password, create_access_token
from app.core.auth import get_current_user

router = APIRouter()


def http_error(status_code: int, detail: str, code: str | None = None, field_errors: dict | None = None):
    payload = {"detail": detail}
    if code:
        payload["code"] = code
    if field_errors:
        payload["field_errors"] = field_errors
    raise HTTPException(status_code=status_code, detail=payload)


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    # Check username/email conflicts
    existing = (
        db.query(User)
        .filter(or_(User.username == user.username, User.email == user.email))
        .first()
    )
    if existing:
        field_errors = {}
        if existing.username == user.username:
            field_errors["username"] = "Username is already taken"
        if existing.email == user.email:
            field_errors["email"] = "Email is already registered"

        http_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists",
            code="ACCOUNT_CONFLICT",
            field_errors=field_errors,
        )

    db_user = User(
        username=user.username,
        email=user.email,
        password_hash=hash_password(user.password),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()

    # Do NOT reveal which part is wrong
    if not db_user or not verify_password(user.password, db_user.password_hash):
        http_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            code="INVALID_CREDENTIALS",
        )

    token = create_access_token({"user_id": db_user.user_id})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    has_onboarding = (
        db.execute(
            "SELECT 1 FROM user_onboarding_movies WHERE user_id = :uid LIMIT 1",
            {"uid": user.user_id},
        ).first()
        is not None
    )

    event_count = db.query(Event).filter(Event.user_id == user.user_id).count()

    return {
        "user": UserOut.model_validate(user),
        "has_onboarding": has_onboarding,
        "event_count": event_count,
        "is_new": (event_count < 5) and (not has_onboarding),
    }


