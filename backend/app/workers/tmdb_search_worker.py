# app/workers/tmdb_search_worker.py

import logging
from datetime import datetime, timezone

from app.db.database import SessionLocal
from app.db.models import Movie, MovieMetadata
from app.services.tmdb_client import tmdb_client
from app.services.metadata_service import parse_title_year

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tmdb_search_worker")


def run_once(limit: int = 100):
    db = SessionLocal()
    try:
        rows = (
            db.query(MovieMetadata, Movie)
            .join(Movie, Movie.movie_id == MovieMetadata.movie_id)
            .filter(MovieMetadata.tmdb_id.is_(None))
            .limit(limit)
            .all()
        )

        if not rows:
            logger.info("No rows without tmdb_id")
            return 0

        for meta, movie in rows:
            clean_title, year = parse_title_year(movie.title)

            code, results = tmdb_client.search_movie(clean_title, year)

            if not results:
                meta.status = "not_found"
                meta.last_checked_at = datetime.now(timezone.utc)
                continue

            best = results[0]
            meta.tmdb_id = int(best["id"])
            meta.status = "pending"
            meta.last_checked_at = datetime.now(timezone.utc)

            logger.info(f"Matched {movie.title} → TMDB {meta.tmdb_id}")

        db.commit()
        return len(rows)

    finally:
        db.close()


if __name__ == "__main__":
    while True:
        processed = run_once(200)
        if processed == 0:
            break