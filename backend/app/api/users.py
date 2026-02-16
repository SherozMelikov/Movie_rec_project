# app/api/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Event, User
from app.schemas.schemas import UserCreate, UserLogin, UserOut
from app.core.security import hash_password, verify_password, create_access_token
from app.core.auth import get_current_user

router = APIRouter()

@router.post("/signup", response_model=UserOut)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    db_user = User(
        username=user.username,
        email=user.email,
        password_hash=hash_password(user.password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"user_id": db_user.user_id})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me")
def me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Has onboarding?
    has_onboarding = db.execute(
        "SELECT 1 FROM user_onboarding_movies WHERE user_id = :uid LIMIT 1",
        {"uid": user.user_id},
    ).first() is not None

    # Has enough events to be considered "not new"?
    event_count = db.query(Event).filter(Event.user_id == user.user_id).count()

    return {
        "user": UserOut.model_validate(user),  # if pydantic v2
        "has_onboarding": has_onboarding,
        "event_count": event_count,
        "is_new": (event_count < 5) and (not has_onboarding),
    }









# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from app.db.database import get_db
# from app.db.models import User
# from app.schemas.schemas import UserCreate, UserRead, UserLogin
# from passlib.hash import argon2

# router = APIRouter()

# # -------------------
# # Registration
# # -------------------
# @router.post("/", response_model=UserRead)
# def create_user(user: UserCreate, db: Session = Depends(get_db)):
#     # check if user already exists
#     existing_user = db.query(User).filter(
#         (User.email == user.email) | (User.username == user.username)
#     ).first()
#     if existing_user:
#         raise HTTPException(status_code=400, detail="User already exists")

#     # hash password
#     hashed_pw = argon2.hash(user.password)
#     db_user = User(email=user.email, username=user.username, password_hash=hashed_pw)
#     db.add(db_user)
#     db.commit()
#     db.refresh(db_user)
#     return db_user

# # -------------------
# # Login
# # -------------------
# @router.post("/login")
# def login_user(user: UserLogin, db: Session = Depends(get_db)):
#     db_user = db.query(User).filter(User.email == user.email).first()
#     if not db_user or not argon2.verify(user.password, db_user.password_hash):
#         raise HTTPException(status_code=401, detail="Invalid email or password")
    
#     return {
#         "message": "Login successful",
#         "user_id": db_user.user_id,
#         "username": db_user.username
#     }
