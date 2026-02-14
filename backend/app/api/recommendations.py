from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.schemas import RecommendationItem
from app.services.recommend_service import recommend_service

router = APIRouter()


@router.get("", response_model=list[RecommendationItem])
def get_recommendations(
    limit: int = Query(50, ge=10, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return recommend_service.get_for_user(db=db, user_id=user.user_id, limit=limit)
