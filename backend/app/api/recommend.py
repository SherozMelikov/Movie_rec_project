from fastapi import APIRouter
from backend.app.schemas.recommendation import RecommendRequest, RecommendationResponse
from backend.app.services.recomend_service import get_recommendations

router = APIRouter()

@router.post("/", response_model=RecommendationResponse)
def recommend_movies(request: RecommendRequest):
    return {"recommendations": get_recommendations(request.user_id, request.top_k)}
