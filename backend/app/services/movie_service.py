from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

from app.db.models import Movie
from app.services.vector_index import vector_index


class MovieService:
    def search_movies(self, db: Session, q: str, limit: int) -> list[Movie]:
        return (
            db.query(Movie)
            .filter(Movie.title.ilike(f"%{q}%"))
            .order_by(Movie.title.asc())
            .limit(limit)
            .all()
        )

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

    def browse_movies(
        self,
        db: Session,
        title: str | None,
        genre: str | None,
        limit: int,
    ) -> list[Movie]:
        query = db.query(Movie)
        if title:
            query = query.filter(Movie.title.ilike(f"%{title}%"))
        if genre:
            query = query.filter(Movie.genres.ilike(f"%{genre}%"))
        return query.limit(limit).all()

    def get_movie_or_404(self, db: Session, movie_id: int) -> Movie:
        movie = db.query(Movie).filter(Movie.movie_id == movie_id).first()
        if not movie:
            raise HTTPException(status_code=404, detail="Movie not found")
        return movie

    def similar_movies(self, movie_id: int, k: int) -> dict:
        # Lazy-load index on first request
        if vector_index.index is None:
            vector_index.load()

        q = vector_index.get_vector(movie_id)
        if q is None:
            raise HTTPException(status_code=404, detail="Movie not found in vector index")

        hits = vector_index.search(q, k=k + 1)  # +1 to remove self
        hits = [(mid, score) for (mid, score) in hits if int(mid) != int(movie_id)][:k]

        return {
            "movie_id": movie_id,
            "similar": [{"movie_id": int(mid), "score": float(score)} for mid, score in hits],
        }


movie_service = MovieService()
