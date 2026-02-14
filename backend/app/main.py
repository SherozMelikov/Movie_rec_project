from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.movies import router as movies_router
from app.api.users import router as users_router
from app.api import interactions
from app.api import events
from app.api import onboarding
from app.api import recommendations
from app.api.ops import router as ops_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(movies_router, prefix="/movies", tags=["Movies"])
app.include_router(users_router, prefix="/users", tags=["Users"])
# app.include_router(interactions.router, prefix="/interactions", tags=["Interactions"])
app.include_router(events.router, prefix="/events", tags=["Events"])
app.include_router(onboarding.router, prefix="/onboarding", tags=["Onboarding"])
app.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
app.include_router(ops_router)
