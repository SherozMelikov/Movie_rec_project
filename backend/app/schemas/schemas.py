# app/schemas/schemas.py
from datetime import date, datetime
from pydantic import BaseModel, Field
from pydantic import BaseModel, EmailStr
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
    event_type: Literal["view", "like", "rate"]
    rating_value: Optional[int] = Field(default=None, ge=1, le=5)

class EventOut(BaseModel):
    id: int
    user_id: int
    movie_id: int
    event_type: str
    rating_value: Optional[int]
    ts: datetime

    class Config:
        orm_mode = True

class OnboardingCreate(BaseModel):
    favorite_genres: list[str] = Field(..., min_length=3, max_length=5)
    picked_movie_ids: list[int] = Field(..., min_length=5, max_length=10)

class OnboardingOut(BaseModel):
    user_id: int
    favorite_genres: list[str]
    picked_movie_ids: list[int]

    class Config:
        orm_mode = True

class RecommendationItem(MovieSchema):
    reason: str | None = None
    score: float | None = None

class MovieOut(BaseModel):
    movie_id: int
    title: str
    genres: Optional[str] = None

    poster_url: Optional[str] = None
    overview: Optional[str] = None
    release_date: Optional[date] = None

    class Config:
        orm_mode = True


# # -------------------
# # User Schemas
# # -------------------

# class UserCreate(BaseModel):
#     username: str
#     email: EmailStr
#     password: str  # raw password from frontend

# class UserRead(BaseModel):
#     user_id: int
#     username: str
#     email: EmailStr

#     class Config:
#         orm_mode = True

# class UserLogin(BaseModel):
#     email: EmailStr
#     password: str
# # -------------------
# # Rating Schemas
# # -------------------

# class RatingCreate(BaseModel):
#     user_id: int
#     movie_id: int
#     rating: float
# class RatingRead(BaseModel):
#     user_id: int
#     movie_id: int
#     rating: float
#     rated_at: Optional[datetime]  # Pydantic will auto-convert to ISO8601 string

#     class Config:
#         orm_mode = True
# # -------------------
# # Like Schemas
# # -------------------

# class LikeCreate(BaseModel):
#     user_id: int
#     movie_id: int

# class LikeRead(BaseModel):
#     user_id: int
#     movie_id: int
#     liked_at: Optional[datetime]  

#     class Config:
#         orm_mode = True

# # -------------------
# # User Preferences Schemas
# # -------------------

# class UserPreferenceCreate(BaseModel):
#     user_id: int
#     favorite_genres: str  # Comma-separated genres, e.g., "Action,Drama"

# class UserPreferenceRead(BaseModel):
#     user_id: int
#     favorite_genres: str
#     created_at: Optional[datetime]

#     class Config:
#         orm_mode = True

# # -------------------
# # Movie Schemas
# # -------------------

# class MovieRead(BaseModel):
#     movie_id: int
#     title: str
#     genres: str  # Comma-separated genres

#     class Config:
#         orm_mode = True

# class MovieMetadataRead(BaseModel):
#     movie_id: int
#     year: Optional[int]
#     poster_url: Optional[str]
#     backdrop_url: Optional[str]
#     plot: Optional[str]
#     popularity: Optional[float]
#     vote_average: Optional[float]

#     class Config:
#         orm_mode = True
# # -------------------
# # Recommendation Schema
# # -------------------

# class RecommendationItem(BaseModel):
#     movie_id: int
#     title: str
#     genres: str
#     year: Optional[int]
#     poster_url: Optional[str]
#     plot: Optional[str]
#     score: float  # Predicted by hybrid model

# # Optional: List of recommendations response
# class RecommendationList(BaseModel):
#     user_id: int
#     recommendations: List[RecommendationItem]

#     class Config:
#         orm_mode = True




# class UserRecommendationCacheRead(BaseModel):
#     user_id: int
#     recommendations: str  # JSON string
#     is_stale: int
#     updated_at: Optional[datetime]

#     class Config:
#         orm_mode = True

# class UserRecommendationCacheUpdate(BaseModel):
#     recommendations: str
#     is_stale: int
