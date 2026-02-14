# app/services/metadata_service.py
import os
import re
from datetime import datetime, timezone, date
from sqlalchemy.orm import Session

from app.db.models import Movie, MovieMetadata
from app.services.tmdb_client import tmdb_client

TMDB_IMG_BASE = os.getenv("TMDB_IMG_BASE", "https://image.tmdb.org/t/p")
TMDB_IMG_SIZE = os.getenv("TMDB_IMG_SIZE", "w342")

YEAR_RE = re.compile(r"\((\d{4})\)\s*$")


def parse_title_year(title: str):
    m = YEAR_RE.search(title or "")
    if m:
        year = int(m.group(1))
        clean = YEAR_RE.sub("", title).strip()
        return clean, year
    return title, None


def build_poster_url(poster_path: str | None):
    if not poster_path:
        return None
    return f"{TMDB_IMG_BASE}/{TMDB_IMG_SIZE}{poster_path}"


class MetadataService:
    def get_or_fetch(self, db: Session, movie_id: int) -> MovieMetadata | None:
        meta = db.query(MovieMetadata).filter(MovieMetadata.movie_id == movie_id).one_or_none()
        if meta and meta.status == "found":
            return meta

        movie = db.query(Movie).filter(Movie.movie_id == movie_id).one_or_none()
        if not movie:
            return None

        clean_title, year = parse_title_year(movie.title)

        if meta is None:
            meta = MovieMetadata(movie_id=movie_id, status="pending")
            db.add(meta)
            db.commit()
            db.refresh(meta)

        meta.last_checked_at = datetime.now(timezone.utc)
        db.commit()

        try:
            results = tmdb_client.search_movie(clean_title, year=year)
            if not results:
                meta.status = "not_found"
                db.commit()
                return meta

            best = results[0]
            tmdb_id = int(best["id"])
            details = tmdb_client.movie_details(tmdb_id)

            meta.tmdb_id = tmdb_id
            meta.overview = details.get("overview")
            meta.poster_path = details.get("poster_path")
            meta.backdrop_path = details.get("backdrop_path")

            # ✅ FIX: parse string -> date
            rd = details.get("release_date")
            meta.release_date = date.fromisoformat(rd) if rd else None

            meta.status = "found"
            meta.fetched_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(meta)
            return meta

        except Exception:
            meta.status = "error"
            db.commit()
            return meta


metadata_service = MetadataService()
