from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db

router = APIRouter(tags=["Ops"])

@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}

@router.get("/version")
def version():
    return {
        "app": "movie-recommender",
        "version": "1.0.0"
    }
