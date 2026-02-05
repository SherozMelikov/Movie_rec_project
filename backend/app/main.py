from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import users, rating, recommendations
from app.core.model_loader import ModelLoader
from app.services.recommendation_service import RecommendationService

from app.services.rating_service import RatingService


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting FastAPI app...")
    
    create_tables()  # 👈 THIS creates movies/users/ratings tables in Render DB


    model_loader = ModelLoader()
    recommendation_service = RecommendationService(model_loader)
    rating_service = RatingService(recommendation_service)

    app.state.model_loader = model_loader
    app.state.recommendation_service = recommendation_service
    app.state.rating_service = rating_service

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





from app.db.database import create_tables
from contextlib import asynccontextmanager
from fastapi import FastAPI



