# app/api/movies.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.schemas import MovieOut
from app.services.movie_service import movie_service
from app.services.metadata_service import build_poster_url
from app.services.metadata_service import metadata_service


router = APIRouter(tags=["Movies"])


@router.get("/search", response_model=list[MovieOut])
def search_movies(
    q: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return movie_service.search_movies(db, q=q, limit=limit)


@router.get("/genres", response_model=list[str])
def list_genres(db: Session = Depends(get_db)):
    return movie_service.list_genres(db)


@router.get("/browse", response_model=list[MovieOut])
def browse_movies(
    title: str | None = None,
    genre: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return movie_service.browse_movies(db, title=title, genre=genre, limit=limit)


@router.get("/{movie_id}", response_model=MovieOut)
def get_movie(movie_id: int, db: Session = Depends(get_db)):
    movie = movie_service.get_movie_or_404(db, movie_id)
    meta = metadata_service.get_or_fetch(db, movie_id)

    poster_url = None
    overview = None
    release_date = None
    if meta and meta.status == "found":
        poster_url = build_poster_url(meta.poster_path)
        overview = meta.overview
        release_date = meta.release_date

    return MovieOut(
        movie_id=movie.movie_id,
        title=movie.title,
        genres=movie.genres,
        poster_url=poster_url,
        overview=overview,
        release_date=release_date,
    )


@router.get("/{movie_id}/similar", response_model=list[MovieOut])
def similar_movies(
    movie_id: int,
    k: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),   # ✅ FIX
):
    return movie_service.similar_movies(db, movie_id, k)
