from pydantic import BaseModel
from typing import List

class RecommendationRequest(BaseModel):
    user_id: int
    movie_id: int
    top_n: int = 10


class RecommendationItem(BaseModel):
    movie_id: int
    score: float


class RecommendationResponse(BaseModel):
    recommendations: List[RecommendationItem]
