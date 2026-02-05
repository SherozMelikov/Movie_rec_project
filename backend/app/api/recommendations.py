from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/top-picks")
def top_picks(user_id: int, request: Request):
    """
    Return cached recommendations immediately.
    If not available, trigger recomputation in the background.
    """
    service = request.app.state.recommendation_service
    return service.get_top_picks(user_id)
