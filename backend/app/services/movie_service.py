from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text, case
from fastapi import HTTPException

from app.db.models import Movie, MovieMetadata
from app.schemas.schemas import MovieOut
from app.services.vector_index import vector_index
from app.services.metadata_service import build_poster_url


class MovieService:
    # -------------------------
    # Helpers
    # -------------------------
    def _hydrate_movies_out(self, db: Session, movies: list[Movie]) -> list[MovieOut]:
        """Attach cached TMDB metadata for a list of Movie rows (1 extra query)."""
        if not movies:
            return []

        ids = [m.movie_id for m in movies]

        metas = (
            db.query(MovieMetadata)
            .filter(MovieMetadata.movie_id.in_(ids))
            .all()
        )
        meta_by_id = {m.movie_id: m for m in metas}

        out: list[MovieOut] = []
        for m in movies:
            meta = meta_by_id.get(m.movie_id)
            out.append(
                MovieOut(
                    movie_id=m.movie_id,
                    title=m.title,
                    genres=m.genres,
                    poster_url=build_poster_url(meta.poster_path) if meta else None,
                    overview=meta.overview if meta else None,
                    release_date=meta.release_date if meta else None,
                )
            )
        return out

    # -------------------------
    # Search / Browse
    # -------------------------
    # ✅ CHANGED: now returns list[MovieOut] (with posters)
    def search_movies(self, db: Session, q: str, limit: int) -> list[MovieOut]:
        movies = (
            db.query(Movie)
            .filter(Movie.title.ilike(f"%{q}%"))
            .order_by(Movie.title.asc())
            .limit(limit)
            .all()
        )
        return self._hydrate_movies_out(db, movies)

    def list_genres(self, db: Session) -> list[str]:
        sql = text(r"""
            SELECT DISTINCT genre
            FROM (
              SELECT unnest(regexp_split_to_array(genres, '\|')) AS genre
              FROM movies
              WHERE genres IS NOT NULL AND genres <> ''
            ) g
            WHERE genre IS NOT NULL AND genre <> ''
            ORDER BY genre;
        """)
        rows = db.execute(sql).fetchall()
        return [r[0] for r in rows]

    # ✅ CHANGED: now returns list[MovieOut] (with posters)
    def browse_movies(
        self,
        db: Session,
        title: str | None,
        genre: str | None,
        limit: int,
    ) -> list[MovieOut]:
        query = db.query(Movie)
        if title:
            query = query.filter(Movie.title.ilike(f"%{title}%"))
        if genre:
            query = query.filter(Movie.genres.ilike(f"%{genre}%"))

        movies = query.limit(limit).all()
        return self._hydrate_movies_out(db, movies)

    def get_movie_or_404(self, db: Session, movie_id: int) -> Movie:
        movie = db.query(Movie).filter(Movie.movie_id == movie_id).first()
        if not movie:
            raise HTTPException(status_code=404, detail="Movie not found")
        return movie

    # -------------------------
    # Similar (keeps order)
    # -------------------------
    def similar_movies(self, db: Session, movie_id: int, k: int) -> list[MovieOut]:
        # Lazy-load index
        if vector_index.index is None:
            vector_index.load()

        qvec = vector_index.get_vector(movie_id)
        if qvec is None:
            raise HTTPException(status_code=404, detail="Movie not found in vector index")

        hits = vector_index.search(qvec, k=k + 1)  # includes self
        hits = [(mid, score) for (mid, score) in hits if int(mid) != int(movie_id)][:k]
        ids = [int(mid) for mid, _ in hits]

        if not ids:
            return []

        ordering = case({mid: idx for idx, mid in enumerate(ids)}, value=Movie.movie_id)
        movies = (
            db.query(Movie)
            .filter(Movie.movie_id.in_(ids))
            .order_by(ordering)
            .all()
        )

        # ✅ Optimize: fetch all metadata in one query (instead of per movie)
        metas = (
            db.query(MovieMetadata)
            .filter(MovieMetadata.movie_id.in_(ids))
            .all()
        )
        meta_by_id = {m.movie_id: m for m in metas}

        out: list[MovieOut] = []
        for m in movies:
            meta = meta_by_id.get(m.movie_id)
            out.append(
                MovieOut(
                    movie_id=m.movie_id,
                    title=m.title,
                    genres=m.genres,
                    poster_url=build_poster_url(meta.poster_path) if meta else None,
                    overview=meta.overview if meta else None,
                    release_date=meta.release_date if meta else None,
                )
            )
        return out


movie_service = MovieService()
