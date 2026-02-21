# app/schemas/schemas.py
from datetime import date, datetime
from pydantic import BaseModel, Field, EmailStr
from typing import Literal, Optional


class MovieSchema(BaseModel):
    movie_id: int
    title: str
    genres: str

    class Config:
        orm_mode = True
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    user_id: int
    username: str
    email: str

    class Config:
        orm_mode = True

# Request schema for creating a rating
class RatingCreate(BaseModel):
    movie_id: int
    score: int = Field(..., ge=1, le=5)  # 1 to 5

# Response schema
class RatingOut(BaseModel):
    rating_id: int
    user_id: int
    movie_id: int
    score: int
    created_at: datetime

    class Config:
        orm_mode = True


class LikeCreate(BaseModel):
    movie_id: int

class LikeOut(BaseModel):
    like_id: int
    user_id: int
    movie_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class TagCreate(BaseModel):
    
    movie_id: int
    tag: str

class TagOut(BaseModel):
    tag_id: int
    user_id: int
    movie_id: int
    tag: str
    created_at: datetime

    class Config:
        orm_mode = True

class EventCreate(BaseModel):
    movie_id: int

class EventOut(BaseModel):
    id: int
    user_id: int
    movie_id: int
    event_type: str
    ts: datetime

    class Config:
        orm_mode = True

class OnboardingCreate(BaseModel):
    #favorite_genres: list[str] = Field(..., min_length=3, max_length=5)
    picked_movie_ids: list[int] = Field(..., min_length=5, max_length=10)

class OnboardingOut(BaseModel):
    user_id: int
    #favorite_genres: list[str]
    picked_movie_ids: list[int]

    class Config:
        orm_mode = True

class RecommendationItem(BaseModel):
    movie_id: int
    title: str
    genres: Optional[str] = None

    poster_url: Optional[str] = None
    release_date: Optional[date] = None

    reason: Optional[str] = None
    score: Optional[float] = None

    class Config:
        orm_mode = True
        
class RecommendationSection(BaseModel):
    title: str
    subtitle: Optional[str] = None
    items: list[RecommendationItem]

class MovieOut(BaseModel):
    movie_id: int
    title: str
    genres: Optional[str] = None

    poster_url: Optional[str] = None
    overview: Optional[str] = None
    release_date: Optional[date] = None

    class Config:
        orm_mode = True
        

