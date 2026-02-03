from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api import users, rating, likes, preferences, recommendations

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(rating.router, prefix="/ratings", tags=["Ratings"])
app.include_router(likes.router, prefix="/likes", tags=["Likes"])
app.include_router(preferences.router, prefix="/preferences", tags=["Preferences"])
app.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
