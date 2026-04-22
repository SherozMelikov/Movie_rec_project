from __future__ import annotations

from typing import Any
import re

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import User
from app.core.security import hash_password, verify_password, create_access_token


def http_error(
    status_code: int,
    detail: str,
    code: str | None = None,
    field_errors: dict[str, str] | None = None,
) -> None:
    payload: dict[str, Any] = {"detail": detail}
    if code:
        payload["code"] = code
    if field_errors:
        payload["field_errors"] = field_errors
    raise HTTPException(status_code=status_code, detail=payload)


def validate_password_strength(password: str) -> None:
    """
    Basic password policy:
    - minimum 8 chars
    - at least 1 uppercase
    - at least 1 lowercase
    - at least 1 digit
    - at least 1 special character
    """
    field_errors: dict[str, str] = {}

    if len(password) < 8:
        field_errors["password"] = "Password must be at least 8 characters long"
    elif len(password) > 128:
        field_errors["password"] = "Password must be at most 128 characters long"
    elif not re.search(r"[A-Z]", password):
        field_errors["password"] = "Password must include at least one uppercase letter"
    elif not re.search(r"[a-z]", password):
        field_errors["password"] = "Password must include at least one lowercase letter"
    elif not re.search(r"\d", password):
        field_errors["password"] = "Password must include at least one digit"
    elif not re.search(r"[^\w\s]", password):
        field_errors["password"] = "Password must include at least one special character"

    if field_errors:
        http_error(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Password does not meet security requirements",
            code="WEAK_PASSWORD",
            field_errors=field_errors,
        )

def signup_user(
    db: Session,
    *,
    username: str,
    email: str,
    password: str,
) -> User:
    validate_password_strength(password)

    existing = (
        db.query(User)
        .filter(or_(User.username == username, User.email == email))
        .first()
    )

    if existing:
        field_errors: dict[str, str] = {}
        if existing.username == username:
            field_errors["username"] = "Username is already taken"
        if existing.email == email:
            field_errors["email"] = "Email is already registered"

        http_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists",
            code="ACCOUNT_CONFLICT",
            field_errors=field_errors,
        )

    try:
        db_user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    except SQLAlchemyError:
        db.rollback()
        http_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create account",
            code="SIGNUP_FAILED",
        )


def login_user(
    db: Session,
    *,
    username: str,
    password: str,
) -> dict[str, str]:
    try:
        db_user = db.query(User).filter(User.username == username).first()
    except SQLAlchemyError:
        db.rollback()
        http_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query user",
            code="LOGIN_QUERY_FAILED",
        )

    # Do not reveal whether username or password was wrong
    if not db_user or not verify_password(password, db_user.password_hash):
        http_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            code="INVALID_CREDENTIALS",
        )

    token = create_access_token({"user_id": db_user.user_id})
    return {"access_token": token, "token_type": "bearer"}


def get_me_summary(db: Session, user: User) -> dict[str, Any]:
    try:
        has_onboarding = (
            db.execute(
                "SELECT 1 FROM user_onboarding_movies WHERE user_id = :uid LIMIT 1",
                {"uid": user.user_id},
            ).first()
            is not None
        )

        # If your Event model is available/imported, keep this here or move to another service
        from app.db.models import Event

        event_count = db.query(Event).filter(Event.user_id == user.user_id).count()

        return {
            "user": user,
            "has_onboarding": has_onboarding,
            "event_count": event_count,
            "is_new": (event_count < 5) and (not has_onboarding),
        }

    except SQLAlchemyError:
        db.rollback()
        http_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load user profile",
            code="PROFILE_LOAD_FAILED",
        )