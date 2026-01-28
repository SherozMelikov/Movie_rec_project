import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from backend.app.routes import recommend  # your existing router

# Load the project root .env
load_dotenv()  # automatically loads .env from project root

app = FastAPI()

# Use the FRONTEND_URL from .env
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include your routes
app.include_router(recommend.router, prefix="/recommend", tags=["Recommend"])
