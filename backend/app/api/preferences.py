from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.db.models import UserPreference
from backend.app.schemas.schemas import UserPreferenceCreate, UserPreferenceRead

router = APIRouter()

# Add or update user preferences
@router.post("/", response_model=UserPreferenceRead)
def add_preferences(pref: UserPreferenceCreate, db: Session = Depends(get_db)):
    db_pref = db.query(UserPreference).filter(UserPreference.user_id == pref.user_id).first()
    if db_pref:
        db_pref.favorite_genres = pref.favorite_genres
    else:
        db_pref = UserPreference(**pref.dict())
        db.add(db_pref)
    db.commit()
    db.refresh(db_pref)
    return db_pref

# Get preferences by user
@router.get("/{user_id}", response_model=UserPreferenceRead)
def get_preferences(user_id: int, db: Session = Depends(get_db)):
    db_pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    return db_pref
