# app/schemas/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional, List

# -------------------
# User Schemas
# -------------------

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str  # raw password from frontend

class UserRead(BaseModel):
    user_id: int
    username: str
    email: EmailStr

    class Config:
        orm_mode = True  # Allows reading data from SQLAlchemy models

# -------------------
# Rating Schemas
# -------------------

class RatingCreate(BaseModel):
    user_id: int
    movie_id: int
    rating: float

class RatingRead(BaseModel):
    user_id: int
    movie_id: int
    rating: float
    rated_at: Optional[str]  # ISO timestamp

    class Config:
        orm_mode = True

# -------------------
# Like Schemas
# -------------------

class LikeCreate(BaseModel):
    user_id: int
    movie_id: int

class LikeRead(BaseModel):
    user_id: int
    movie_id: int
    liked_at: Optional[str]  # ISO timestamp

    class Config:
        orm_mode = True

# -------------------
# User Preferences Schemas
# -------------------

class UserPreferenceCreate(BaseModel):
    user_id: int
    favorite_genres: str  # Comma-separated genres, e.g., "Action,Drama"

class UserPreferenceRead(BaseModel):
    user_id: int
    favorite_genres: str
    created_at: Optional[str]

    class Config:
        orm_mode = True

# -------------------
# Movie Schemas
# -------------------

class MovieRead(BaseModel):
    movie_id: int
    title: str
    genres: str  # Comma-separated genres

    class Config:
        orm_mode = True

class MovieMetadataRead(BaseModel):
    movie_id: int
    year: Optional[int]
    poster_url: Optional[str]
    backdrop_url: Optional[str]
    plot: Optional[str]

    class Config:
        orm_mode = True

# -------------------
# Recommendation Schema
# -------------------

class RecommendationItem(BaseModel):
    movie_id: int
    title: str
    genres: str
    year: Optional[int]
    poster_url: Optional[str]
    plot: Optional[str]
    score: float  # Predicted by hybrid model

# Optional: List of recommendations response
class RecommendationList(BaseModel):
    user_id: int
    recommendations: List[RecommendationItem]
