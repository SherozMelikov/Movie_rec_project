from pydantic import BaseModel
from typing import List

class RecommendationItem(BaseModel):
    movie_id: int
    title: str
    genres: str
    year: str
    image_url: str
    description: str
    score: float

class RecommendationResponse(BaseModel):
    recommendations: List[RecommendationItem]

class RecommendRequest(BaseModel):
    user_id: int
    top_k: int = 10
