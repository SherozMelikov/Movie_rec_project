from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.models import Movie
from app.schemas.schemas import RecommendationItem
from app.services.vector_index import vector_index
from app.services.als_store import als_store


@dataclass
class RecommendConfig:
    # how many candidates to pull from HNSW before reranking
    min_candidate_k: int = 300
    max_candidate_k: int = 1000
    candidate_multiplier: int = 15  # candidate_k = max(min_candidate_k, limit * multiplier)

    # ALS candidate pool size (global)
    als_candidate_k: int = 300

    # exclude cap
    exclude_max_rows: int = 20000


class RecommendService:
    def __init__(self, config: RecommendConfig | None = None):
        self.config = config or RecommendConfig()
        self._idx_to_movie_id: dict[int, int] | None = None  # cache for ALS

    def get_for_user(
        self,
        db: Session,
        user_id: int,
        limit: int,
        as_of_ts=None,
    ) -> list[RecommendationItem]:
        # Load HNSW index on demand
        if vector_index.index is None:
            vector_index.load()

        # 1) Seeds (blended)
        seed_movie_ids = self._get_seed_movies_blended(db, user_id, as_of_ts=as_of_ts)

        # Fallback #1: no onboarding and no strong events => trending
        if not seed_movie_ids:
            movies = self._get_trending_movies(db, limit)
            return [
                RecommendationItem(
                    movie_id=m.movie_id,
                    title=m.title,
                    genres=m.genres,
                    reason="Trending now",
                    score=None,
                )
                for m in movies
            ]

        # 2) Build user profile vector
        user_vec = self._build_user_vector(seed_movie_ids)

        # Fallback #2: seeds exist but none mapped in vectors => trending
        if user_vec is None:
            movies = self._get_trending_movies(db, limit)
            return [
                RecommendationItem(
                    movie_id=m.movie_id,
                    title=m.title,
                    genres=m.genres,
                    reason="Trending now",
                    score=None,
                )
                for m in movies
            ]

        # 3) Exclusions (as-of filtered)
        exclude_ids = set(
            self._get_excluded_movie_ids(
                db,
                user_id,
                as_of_ts=as_of_ts,
                max_rows=self.config.exclude_max_rows,
            )
        )
        exclude_ids.update(seed_movie_ids)

        # 4) Candidate generation
        # 4a) HNSW candidates (content)
        hnsw_k = min(
            max(self.config.min_candidate_k, limit * self.config.candidate_multiplier),
            self.config.max_candidate_k,
        )
        hits = vector_index.search(user_vec, k=hnsw_k)  # [(movie_id, score)]

        hnsw_candidates: list[int] = []
        cbf_score_map: dict[int, float] = {}

        for mid, score in hits:
            mid = int(mid)
            if mid in exclude_ids:
                continue
            hnsw_candidates.append(mid)
            cbf_score_map[mid] = float(score)
            if len(hnsw_candidates) >= hnsw_k:
                break

        # 4b) ALS candidates (collab) - NEW (global top-N)
        als_candidates = self._als_top_n(user_id=user_id, exclude_ids=exclude_ids, n=self.config.als_candidate_k)

        # 4c) Union candidates (keep order, unique)
        # Priority: ALS first (strong signal), then HNSW to add content-based exploration
        candidate_ids = list(dict.fromkeys(als_candidates + hnsw_candidates))

        # If we still have nothing (e.g., user not in ALS and HNSW empty), fallback
        if not candidate_ids:
            movies = self._get_trending_movies(db, limit)
            return [
                RecommendationItem(
                    movie_id=m.movie_id,
                    title=m.title,
                    genres=m.genres,
                    reason="Trending now",
                    score=None,
                )
                for m in movies
            ]

        # 5) Rerank
        als_scores = als_store.score_candidates(user_id, candidate_ids)

        if als_scores:
            # Primary rank by ALS
            als_scores.sort(key=lambda x: x[1], reverse=True)
            top = als_scores[:limit]
            reranked_ids = [mid for mid, _ in top]
            score_map = {mid: float(s) for mid, s in top}
            reason = "Hybrid: ALS top-N + HNSW candidates (union), reranked by ALS"
        else:
            # ALS not available for user -> fall back to CBF ranking
            reranked_ids = candidate_ids[:limit]
            score_map = {mid: float(cbf_score_map.get(mid, 0.0)) for mid in reranked_ids}
            reason = "Based on your onboarding + activity (CBF)"

        # 6) Fetch movies in one query, preserve order
        movies = db.query(Movie).filter(Movie.movie_id.in_(reranked_ids)).all()
        movie_map = {m.movie_id: m for m in movies}

        out: list[RecommendationItem] = []
        for mid in reranked_ids:
            m = movie_map.get(mid)
            if not m:
                continue
            out.append(
                RecommendationItem(
                    movie_id=m.movie_id,
                    title=m.title,
                    genres=m.genres,
                    reason=reason,
                    score=score_map.get(mid),
                )
            )

        return out

    # -----------------------
    # Helpers
    # -----------------------

    def _als_top_n(self, user_id: int, exclude_ids: set[int], n: int = 300) -> list[int]:
        """
        Return top-N movie_ids by ALS score (global scoring), excluding exclude_ids.
        If user not available in ALS, returns [].
        """
        if not als_store.can_score_user(user_id):
            return []

        # Ensure ALS loaded
        if als_store.user_factors is None:
            als_store.load()

        # Cache idx->movie_id mapping once
        if self._idx_to_movie_id is None:
            self._idx_to_movie_id = {int(v): int(k) for k, v in als_store.movie_id_to_idx.items()}

        uid = int(user_id)
        uidx = als_store.user_id_to_idx[uid]
        uvec = als_store.user_factors[uidx]  # (factors,)

        scores = als_store.item_factors @ uvec  # (n_items,)

        # Exclude already seen/seed items
        exclude_iidx = [
            als_store.movie_id_to_idx[mid]
            for mid in exclude_ids
            if mid in als_store.movie_id_to_idx
        ]
        if exclude_iidx:
            scores[np.array(exclude_iidx, dtype=np.int32)] = -1e9

        n = int(min(n, scores.shape[0]))
        if n <= 0:
            return []

        top_iidx = np.argpartition(-scores, n)[:n]
        top_iidx = top_iidx[np.argsort(-scores[top_iidx])]

        return [self._idx_to_movie_id[int(i)] for i in top_iidx]

    def _get_seed_movies_blended(
        self,
        db: Session,
        user_id: int,
        as_of_ts=None,
    ) -> list[int]:
        """
        Seed strategy:
        - up to 5 from strong events (like OR rate>=4), most recent first
        - fill remaining (to 10 total) from onboarding picked movies
        """
        sql_events = text("""
            SELECT movie_id
            FROM (
              SELECT e.movie_id, MAX(e.ts) AS last_ts
              FROM events e
              WHERE e.user_id = :user_id
                AND (:as_of_ts IS NULL OR e.ts < :as_of_ts)
                AND (
                  e.event_type = 'like'
                  OR (e.event_type = 'rate' AND e.rating_value >= 4)
                )
              GROUP BY e.movie_id
              ORDER BY last_ts DESC
              LIMIT 5
            ) t;
        """)
        event_rows = db.execute(
            sql_events,
            {"user_id": user_id, "as_of_ts": as_of_ts},
        ).fetchall()
        event_seeds = [int(r[0]) for r in event_rows] if event_rows else []

        sql_onb = text("""
            SELECT movie_id
            FROM user_onboarding_movies
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 10;
        """)
        onb_rows = db.execute(sql_onb, {"user_id": user_id}).fetchall()
        onb_seeds = [int(r[0]) for r in onb_rows] if onb_rows else []

        out: list[int] = []
        seen: set[int] = set()
        for mid in event_seeds + onb_seeds:
            if mid not in seen:
                seen.add(mid)
                out.append(mid)
            if len(out) >= 10:
                break

        return out

    def _build_user_vector(self, seed_movie_ids: list[int]) -> Optional[np.ndarray]:
        """
        Normalized mean of seed vectors. Returns (dim,) float32 or None.
        """
        vecs = []
        for mid in seed_movie_ids:
            v = vector_index.get_vector(mid)
            if v is not None:
                vecs.append(v)

        if not vecs:
            return None

        user_vec = np.mean(np.vstack(vecs), axis=0).astype(np.float32)
        norm = float(np.linalg.norm(user_vec))
        if norm > 0:
            user_vec /= norm

        return user_vec

    def _get_excluded_movie_ids(
        self,
        db: Session,
        user_id: int,
        as_of_ts=None,
        max_rows: int = 20000,
    ) -> list[int]:
        sql = text("""
            SELECT DISTINCT movie_id
            FROM events
            WHERE user_id = :user_id
              AND (:as_of_ts IS NULL OR ts < :as_of_ts)
            LIMIT :max_rows;
        """)
        rows = db.execute(
            sql,
            {"user_id": user_id, "as_of_ts": as_of_ts, "max_rows": max_rows},
        ).fetchall()
        return [int(r[0]) for r in rows]

    def _get_trending_movies(self, db: Session, limit: int) -> list[Movie]:
        """
        Weighted events:
        view = 1
        like = 3
        rate = rating_value (1–5)
        """
        sql = text("""
            SELECT movie_id
            FROM (
                SELECT
                    movie_id,
                    SUM(
                        CASE
                            WHEN event_type = 'view' THEN 1
                            WHEN event_type = 'like' THEN 3
                            WHEN event_type = 'rate' THEN COALESCE(rating_value, 0)
                            ELSE 0
                        END
                    ) AS score
                FROM events
                GROUP BY movie_id
                ORDER BY score DESC
                LIMIT :limit
            ) t;
        """)
        rows = db.execute(sql, {"limit": limit}).fetchall()
        movie_ids = [int(r[0]) for r in rows]

        if not movie_ids:
            return db.query(Movie).limit(limit).all()

        movies = db.query(Movie).filter(Movie.movie_id.in_(movie_ids)).all()
        movie_map = {m.movie_id: m for m in movies}
        return [movie_map[mid] for mid in movie_ids if mid in movie_map]


recommend_service = RecommendService()
