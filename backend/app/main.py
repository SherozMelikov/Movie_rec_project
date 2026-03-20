from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.movies import router as movies_router
from app.api.users import router as users_router
from app.api import interactions
from app.api import events
from app.api import onboarding
from app.api import recommendations
from app.api.ops import router as ops_router
from app.api.likes import router as likes_router
from app.api.ratings import router as ratings_router
from app.api.events import router as events_router


##########
from contextlib import asynccontextmanager
from app.services.startup import run_startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🔥 All startup logic is handled here
    run_startup()
    yield



app = FastAPI(lifespan=lifespan)
##############


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(movies_router, prefix="/movies", tags=["Movies"])
app.include_router(users_router, prefix="/users", tags=["Users"])
# app.include_router(interactions.router, prefix="/interactions", tags=["Interactions"])
app.include_router(events_router, prefix="/events")
app.include_router(onboarding.router, prefix="/onboarding", tags=["Onboarding"])
app.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
app.include_router(ops_router)
app.include_router(likes_router, prefix="/likes")
app.include_router(ratings_router, prefix="/ratings")
