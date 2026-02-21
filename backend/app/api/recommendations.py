# app/api/recommendations.py (or wherever this router lives)
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.schemas import RecommendationItem, RecommendationSection
from app.services.recommend_service import recommend_service

router = APIRouter()


@router.get("", response_model=list[RecommendationItem])
def get_recommendations(
    limit: int = Query(50, ge=10, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return recommend_service.get_for_user(db=db, user_id=user.user_id, limit=limit)


@router.get("/sections", response_model=list[RecommendationSection])
def get_recommendations_sections(
    limit_per_section: int = Query(12, ge=6, le=30),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return recommend_service.get_sections_for_user(db=db, user_id=user.user_id, limit_per_section=limit_per_section)
