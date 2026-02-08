from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import users, rating, recommendations , likes
from app.core.model_loader import ModelLoader
from app.services.recommendation_service import RecommendationService

from app.services.rating_service import RatingService
from app.services.like_service import LikeService

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting FastAPI app...")

    model_loader = ModelLoader()
    recommendation_service = RecommendationService(model_loader)
    rating_service = RatingService(recommendation_service)
    like_service = LikeService(recommendation_service)

    app.state.model_loader = model_loader
    app.state.recommendation_service = recommendation_service
    app.state.rating_service = rating_service
    app.state.like_service = like_service
    print("✅ Models & Services loaded")
    yield
    print("🛑 Shutting down...")

app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Routers
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(rating.router, prefix="/ratings", tags=["Ratings"])
app.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
app.include_router(likes.router, prefix="/likes", tags=["Likes"])