from fastapi import APIRouter, Request
from backend.app.schemas.schemas import RatingCreate

router = APIRouter()

@router.post("/")
def add_rating(rating: RatingCreate, request: Request):
    """
    Add a new rating for a user.
    Trigger background recomputation of recommendations.
    """
    rating_service = request.app.state.rating_service
    return rating_service.add_rating(rating)
