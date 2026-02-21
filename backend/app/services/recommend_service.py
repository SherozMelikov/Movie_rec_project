from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.models import Movie, MovieMetadata
from app.schemas.schemas import RecommendationItem, RecommendationSection
from app.services.vector_index import vector_index
from app.services.als_store import als_store
from app.services.metadata_service import build_poster_url


@dataclass
class RecommendConfig:
    min_candidate_k: int = 300
    max_candidate_k: int = 1000
    candidate_multiplier: int = 15
    als_candidate_k: int = 300
    exclude_max_rows: int = 20000

    trending_days: int = 7
    blend_w_als: float = 0.7
    blend_w_cbf: float = 0.3


class RecommendService:
    def __init__(self, config: RecommendConfig | None = None):
        self.config = config or RecommendConfig()
        self._idx_to_movie_id: dict[int, int] | None = None

    # -----------------------
    # Public API
    # -----------------------

    def get_for_user(
        self,
        db: Session,
        user_id: int,
        limit: int,
        as_of_ts=None,
    ) -> list[RecommendationItem]:

        if vector_index.index is None:
            vector_index.load()

        # 1) Seeds (likes + high ratings + onboarding)
        seed_movie_ids = self._get_seed_movies_blended(db, user_id, as_of_ts=as_of_ts)

        # Cold-start: no seeds at all
        if not seed_movie_ids:
            return self._items_from_movies(
                db=db,
                movies=self._get_trending_movies(db, limit, days=self.config.trending_days),
                reason="Trending now",
                score_map=None,
            )

        # 2) Build user vector (mean of seed vectors)
        user_vec = self._build_user_vector(seed_movie_ids)

        # 🔥 NEW: smarter fallback if vectors missing
        if user_vec is None:
            seed = seed_movie_ids[0]
            items = self._more_like_movie(
                db=db,
                seed_movie_id=seed,
                limit=limit,
                exclude_ids=set(seed_movie_ids),
            )
            if items:
                return items

            return self._items_from_movies(
                db=db,
                movies=self._get_trending_movies(db, limit, days=self.config.trending_days),
                reason="Trending now",
                score_map=None,
            )

        # 3) Exclusions
        exclude_ids = set(
            self._get_excluded_movie_ids(
                db,
                user_id,
                as_of_ts=as_of_ts,
                max_rows=self.config.exclude_max_rows,
            )
        )
        exclude_ids.update(seed_movie_ids)

        # 4) Candidates from HNSW
        hnsw_k = min(
            max(self.config.min_candidate_k, limit * self.config.candidate_multiplier),
            self.config.max_candidate_k,
        )

        hits = vector_index.search(user_vec, k=hnsw_k)

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

        # 5) Candidates from ALS
        als_candidates = self._als_top_n(
            user_id=user_id,
            exclude_ids=exclude_ids,
            n=self.config.als_candidate_k,
        )

        candidate_ids = list(dict.fromkeys(als_candidates + hnsw_candidates))

        if not candidate_ids:
            return self._items_from_movies(
                db=db,
                movies=self._get_trending_movies(db, limit, days=self.config.trending_days),
                reason="Trending now",
                score_map=None,
            )

        # 🔥 NEW: dynamic blending weights
        interaction_count = self._interaction_count(db, user_id, as_of_ts=as_of_ts)

        if interaction_count < 10:
            w_als, w_cbf = 0.2, 0.8
        elif interaction_count < 30:
            w_als, w_cbf = 0.5, 0.5
        else:
            w_als, w_cbf = self.config.blend_w_als, self.config.blend_w_cbf

        # 6) Rerank blended
        reranked_ids, score_map, reason = self._rerank_blended(
            user_id=user_id,
            candidate_ids=candidate_ids,
            cbf_score_map=cbf_score_map,
            limit=limit,
            w_als=w_als,
            w_cbf=w_cbf,
        )

        return self._items_from_ids(
            db=db,
            movie_ids=reranked_ids,
            reason=reason,
            score_map=score_map,
        )
    def get_sections_for_user(
        self,
        db: Session,
        user_id: int,
        limit_per_section: int = 12,
        as_of_ts=None,
    ) -> list[RecommendationSection]:
        """
        Builds real homepage rows (not slices of one list).
        Dedupes across rows so users don't see repeats.
        Filters out already-interacted movies from NON-personalized rows too (Trending, Hidden Gems).
        """
        used: set[int] = set()

        # Seeds + exclusions (reused across sections)
        seed_movie_ids = self._get_seed_movies_blended(db, user_id, as_of_ts=as_of_ts)

        exclude_ids = set(
            self._get_excluded_movie_ids(
                db,
                user_id,
                as_of_ts=as_of_ts,
                max_rows=self.config.exclude_max_rows,
            )
        )
        exclude_ids.update(seed_movie_ids)

        sections: list[RecommendationSection] = []

        # 1) Top picks (personalized)
        top_picks = self.get_for_user(db, user_id, limit=limit_per_section * 2, as_of_ts=as_of_ts)
        top_picks = self._dedup_items(top_picks, used, limit_per_section)
        if top_picks:
            sections.append(
                RecommendationSection(
                    title="Top Picks for You",
                    subtitle="Based on your activity",
                    items=top_picks,
                )
            )

        # 2) Trending now (global, time-bounded) + filter out seen movies + fallback windows

        def pick_trending(days: int, pool_mult: int = 8) -> list[RecommendationItem]:
            movies = self._get_trending_movies(
                db,
                limit=limit_per_section * pool_mult,
                days=days,
            )
            items = self._items_from_movies(db, movies, reason="Trending now", score_map=None)
            items = [it for it in items if it.movie_id not in exclude_ids and it.movie_id not in used]
            return items

        trending_candidates = pick_trending(self.config.trending_days)              # 7 days
        if len(trending_candidates) < limit_per_section:
            trending_candidates += pick_trending(30)                                # 30 days

        # If still short, fall back to all-time popularity (reuse existing function by setting a huge days window)
        if len(trending_candidates) < limit_per_section:
            trending_candidates += pick_trending(3650)                              # ~10 years = "all-time"

        # Finally dedup and cut to size
        trending_items = self._dedup_items(trending_candidates, used, limit_per_section)

        if trending_items:
            sections.append(
                RecommendationSection(
                    title="Trending Now",
                    subtitle="Popular right now",
                    items=trending_items,
                )
            )

        # 3) Because you liked...
        because_items: list[RecommendationItem] = []
        if seed_movie_ids:
            seed = seed_movie_ids[0]  # most recent signal
            because_items = self._more_like_movie(
                db=db,
                seed_movie_id=seed,
                limit=limit_per_section * 3,
                exclude_ids=exclude_ids | used,
            )
            because_items = self._dedup_items(because_items, used, limit_per_section)

        if because_items:
            sections.append(
                RecommendationSection(
                    title="Because You Liked",
                    subtitle="Similar to what you enjoyed",
                    items=because_items,
                )
            )

        # 4) Hidden gems + filter out seen movies
        hidden_movies = self._get_hidden_gems(db, limit=limit_per_section * 5, days=30)
        hidden_items = self._items_from_movies(db, hidden_movies, reason="Hidden gem", score_map=None)

        # ✅ remove already-interacted movies for this user
        hidden_items = [it for it in hidden_items if it.movie_id not in exclude_ids]

        hidden_items = self._dedup_items(hidden_items, used, limit_per_section)
        if hidden_items:
            sections.append(
                RecommendationSection(
                    title="Hidden Gems",
                    subtitle="Great movies, less obvious",
                    items=hidden_items,
                )
            )

        return sections

    # -----------------------
    # Rerank (ALS + CBF blend)
    # -----------------------

    def _rerank_blended(
        self,
        user_id: int,
        candidate_ids: list[int],
        cbf_score_map: dict[int, float],
        limit: int,
        w_als: float,
        w_cbf: float,
    ) -> tuple[list[int], dict[int, float], str]:

        als_scores = als_store.score_candidates(user_id, candidate_ids)
        als_score_map = {int(mid): float(s) for mid, s in als_scores} if als_scores else {}

        def minmax(d: dict[int, float]) -> dict[int, float]:
            if not d:
                return {}
            vals = np.array(list(d.values()), dtype=np.float32)
            lo, hi = float(vals.min()), float(vals.max())
            if hi - lo < 1e-9:
                return {k: 0.0 for k in d}
            return {k: (v - lo) / (hi - lo) for k, v in d.items()}

        als_n = minmax(als_score_map)
        cbf_universe = {mid: float(cbf_score_map.get(mid, 0.0)) for mid in candidate_ids}
        cbf_n = minmax(cbf_universe)

        final: dict[int, float] = {}

        for mid in candidate_ids:
            a = als_n.get(mid)
            c = cbf_n.get(mid)

            if a is None and c is None:
                continue
            if a is None:
                final[mid] = c
            elif c is None:
                final[mid] = a
            else:
                final[mid] = w_als * a + w_cbf * c

        if not final:
            reranked = candidate_ids[:limit]
            return reranked, {mid: float(cbf_score_map.get(mid, 0.0)) for mid in reranked}, "Based on your activity (CBF)"

        ranked = sorted(final.items(), key=lambda x: x[1], reverse=True)[:limit]
        reranked_ids = [mid for mid, _ in ranked]
        score_map = {mid: float(s) for mid, s in ranked}

        if als_score_map and w_als > 0.3:
            reason = "Hybrid: blended collaborative + content"
        else:
            reason = "Based on your activity"

        return reranked_ids, score_map, reason
    # -----------------------
    # Item-to-item section
    # -----------------------

    def _more_like_movie(
        self,
        db: Session,
        seed_movie_id: int,
        limit: int,
        exclude_ids: set[int],
    ) -> list[RecommendationItem]:
        if vector_index.index is None:
            vector_index.load()

        v = vector_index.get_vector(seed_movie_id)
        if v is None:
            return []

        hits = vector_index.search(v, k=limit * 5)

        ids: list[int] = []
        for mid, _ in hits:
            mid = int(mid)
            if mid == seed_movie_id or mid in exclude_ids:
                continue
            ids.append(mid)
            if len(ids) >= limit:
                break

        if not ids:
            return []

        return self._items_from_ids(
            db=db,
            movie_ids=ids,
            reason="Because you liked a similar movie",
            score_map=None,
        )

    # -----------------------
    # Helpers
    # -----------------------

    def _als_top_n(self, user_id: int, exclude_ids: set[int], n: int = 300) -> list[int]:
        if not als_store.can_score_user(user_id):
            return []

        if als_store.user_factors is None:
            als_store.load()

        if self._idx_to_movie_id is None:
            self._idx_to_movie_id = {int(v): int(k) for k, v in als_store.movie_id_to_idx.items()}

        uid = int(user_id)
        uidx = als_store.user_id_to_idx[uid]
        uvec = als_store.user_factors[uidx]

        scores = als_store.item_factors @ uvec

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

    def _get_seed_movies_blended(self, db: Session, user_id: int, as_of_ts=None) -> list[int]:
        sql_events = text("""
            SELECT movie_id
            FROM (
              SELECT e.movie_id, MAX(e.ts) AS last_ts
              FROM interactions_all e
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
        event_rows = db.execute(sql_events, {"user_id": user_id, "as_of_ts": as_of_ts}).fetchall()
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
        seen = set()
        for mid in event_seeds + onb_seeds:
            if mid not in seen:
                seen.add(mid)
                out.append(mid)
            if len(out) >= 10:
                break
        return out

    def _build_user_vector(self, seed_movie_ids: list[int]) -> Optional[np.ndarray]:
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

    def _get_excluded_movie_ids(self, db: Session, user_id: int, as_of_ts=None, max_rows: int = 20000) -> list[int]:
        sql = text("""
            SELECT DISTINCT movie_id
            FROM interactions_all
            WHERE user_id = :user_id
              AND (:as_of_ts IS NULL OR ts < :as_of_ts)
            LIMIT :max_rows;
        """)
        rows = db.execute(sql, {"user_id": user_id, "as_of_ts": as_of_ts, "max_rows": max_rows}).fetchall()
        return [int(r[0]) for r in rows]

    def _get_trending_movies(self, db: Session, limit: int, days: int = 7) -> list[Movie]:
        # ✅ "Trending now" should be RECENT, not all-time.
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
                FROM interactions_all
                WHERE ts >= NOW() - (:days || ' days')::interval
                GROUP BY movie_id
                ORDER BY score DESC
                LIMIT :limit
            ) t;
        """)
        rows = db.execute(sql, {"limit": limit, "days": days}).fetchall()
        movie_ids = [int(r[0]) for r in rows]

        if not movie_ids:
            return db.query(Movie).limit(limit).all()

        movies = db.query(Movie).filter(Movie.movie_id.in_(movie_ids)).all()
        movie_map = {m.movie_id: m for m in movies}
        return [movie_map[mid] for mid in movie_ids if mid in movie_map]

    def _get_hidden_gems(self, db: Session, limit: int, days: int = 30) -> list[Movie]:
        """
        Simple 'hidden gems':
        - good average rating (>= 4.0)
        - low-ish interactions in the last N days
        """
        sql = text("""
            WITH stats AS (
              SELECT
                movie_id,
                AVG(CASE WHEN event_type='rate' THEN rating_value::float END) AS avg_rating,
                COUNT(*) FILTER (WHERE ts >= NOW() - (:days || ' days')::interval) AS recent_events
              FROM interactions_all
              GROUP BY movie_id
            )
            SELECT movie_id
            FROM stats
            WHERE avg_rating IS NOT NULL
              AND avg_rating >= 4.0
              AND recent_events <= 20
            ORDER BY avg_rating DESC, recent_events ASC
            LIMIT :limit;
        """)
        rows = db.execute(sql, {"limit": limit, "days": days}).fetchall()
        movie_ids = [int(r[0]) for r in rows]

        if not movie_ids:
            return []

        movies = db.query(Movie).filter(Movie.movie_id.in_(movie_ids)).all()
        movie_map = {m.movie_id: m for m in movies}
        return [movie_map[mid] for mid in movie_ids if mid in movie_map]

    def _items_from_ids(
        self,
        db: Session,
        movie_ids: list[int],
        reason: str,
        score_map: dict[int, float] | None,
    ) -> list[RecommendationItem]:

        if not movie_ids:
            return []

        movies = db.query(Movie).filter(Movie.movie_id.in_(movie_ids)).all()
        movie_map = {m.movie_id: m for m in movies}

        metas = db.query(MovieMetadata).filter(MovieMetadata.movie_id.in_(movie_ids)).all()
        meta_by_id = {mm.movie_id: mm for mm in metas}

        out: list[RecommendationItem] = []
        for mid in movie_ids:
            m = movie_map.get(mid)
            if not m:
                continue
            meta = meta_by_id.get(mid)
            out.append(
                RecommendationItem(
                    movie_id=m.movie_id,
                    title=m.title,
                    genres=m.genres,
                    poster_url=build_poster_url(meta.poster_path) if meta else None,
                    release_date=meta.release_date if meta else None,
                    reason=reason,
                    score=(score_map.get(mid) if score_map else None),
                )
            )
        return out

    def _items_from_movies(
        self,
        db: Session,
        movies: list[Movie],
        reason: str,
        score_map: dict[int, float] | None,
    ) -> list[RecommendationItem]:
        ids = [m.movie_id for m in movies]
        return self._items_from_ids(db, ids, reason=reason, score_map=score_map)

    def _dedup_items(
        self,
        items: list[RecommendationItem],
        used_ids: set[int],
        limit: int,
    ) -> list[RecommendationItem]:
        out: list[RecommendationItem] = []
        for it in items:
            if it.movie_id in used_ids:
                continue
            used_ids.add(it.movie_id)
            out.append(it)
            if len(out) >= limit:
                break
        return out

    def _interaction_count(self, db: Session, user_id: int, as_of_ts=None) -> int:
        sql = text("""
            SELECT COUNT(*)
            FROM interactions_all
            WHERE user_id = :user_id
            AND (:as_of_ts IS NULL OR ts < :as_of_ts)
        """)
        row = db.execute(sql, {"user_id": user_id, "as_of_ts": as_of_ts}).fetchone()
        return int(row[0] or 0)


recommend_service = RecommendService()
