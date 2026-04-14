from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Movie, MovieMetadata
from app.schemas.schemas import RecommendationItem, RecommendationSection
from app.services.metadata_service import build_poster_url

from app.ml.recommenders.als_recommender import als_recommender
from app.ml.recommenders.cbf_recommender import cbf_recommender
from app.ml.recommenders.hybrid_recommender import hybrid_recommender

logger = logging.getLogger(__name__)


@dataclass
class RecommendConfig:
    # runtime-safe defaults
    min_candidate_k: int = 300
    max_candidate_k: int = 1500
    candidate_multiplier: int = 20
    als_candidate_k: int = 500
    exclude_max_rows: int = 20000

    trending_days: int = 7

    debug_pipeline: bool = False
    debug_rerank: bool = False


class RecommendService:
    def __init__(self, config: RecommendConfig | None = None):
        self.config = config or RecommendConfig()

    def _prepare_context(
        self,
        db: Session,
        user_id: int,
        as_of_ts=None,
        force_seed_ids: list[int] | None = None,
        force_exclude_ids: set[int] | None = None,
    ) -> tuple[list[int], set[int], bool, int]:
        seed_movie_ids = (
            list(force_seed_ids)
            if force_seed_ids is not None
            else self._get_seed_movies_blended(db, user_id, as_of_ts=as_of_ts)
        )

        exclude_ids = (
            set(force_exclude_ids)
            if force_exclude_ids is not None
            else set(
                self._get_excluded_movie_ids(
                    db=db,
                    user_id=user_id,
                    as_of_ts=as_of_ts,
                    max_rows=self.config.exclude_max_rows,
                )
            )
        )

        exclude_ids.update(seed_movie_ids)
        has_als = als_recommender.can_score_user(user_id)
        interaction_count = self._interaction_count(db, user_id, as_of_ts=as_of_ts)

        return seed_movie_ids, exclude_ids, has_als, interaction_count

    def _choose_strategy(
        self,
        has_als: bool,
        seed_movie_ids: list[int],
    ) -> tuple[str, str]:
        seed_count = len(seed_movie_ids)

        # If both ALS support and seed signal exist, let the hybrid recommender
        # make the nuanced decision internally.
        if has_als and seed_count > 0:
            return "hybrid_light", "ALS available and seed signal present"

        # ALS-capable user but no usable CBF seed signal.
        if has_als:
            return "als_only", "ALS available but no seed signal"

        # No ALS, but we still have seed items for content-based recommendations.
        if seed_count > 0:
            return "cbf_only", "no ALS support; using CBF from seeds"

        # No personalized signal at all.
        return "trending_fallback", "no ALS and no seed signal"
    
    def get_for_user(
        self,
        db: Session,
        user_id: int,
        limit: int,
        as_of_ts=None,
    ) -> list[RecommendationItem]:
        seed_movie_ids, exclude_ids, has_als, interaction_count = self._prepare_context(
            db=db,
            user_id=user_id,
            as_of_ts=as_of_ts,
        )

        strategy, strategy_reason = self._choose_strategy(
            has_als=has_als,
            seed_movie_ids=seed_movie_ids,
        )

        logger.info(
            "recommendation_strategy_selected",
            extra={
                "user_id": user_id,
                "strategy": strategy,
                "strategy_reason": strategy_reason,
                "limit": limit,
                "interaction_count": interaction_count,
                "seed_count": len(seed_movie_ids),
                "exclude_count": len(exclude_ids),
                "has_als": has_als,
                "as_of_ts": str(as_of_ts) if as_of_ts is not None else None,
            },
        )

        if self.config.debug_pipeline:
            print("\n--- GET_FOR_USER DEBUG ---")
            print("user_id:", user_id)
            print("limit:", limit)
            print("as_of_ts:", as_of_ts)
            print("interaction_count:", interaction_count)
            print("seed_count:", len(seed_movie_ids))
            print("seed_movie_ids[:10]:", seed_movie_ids[:10])
            print("exclude_count:", len(exclude_ids))
            print("has_als:", has_als)
            print("strategy:", strategy)
            print("strategy_reason:", strategy_reason)

        if strategy == "als_only":
            als_ids = als_recommender.top_n(
                user_id=user_id,
                exclude_ids=exclude_ids,
                n=max(limit, self.config.als_candidate_k),
            )[:limit]

            if als_ids:
                als_scores = als_recommender.score_candidates(user_id, als_ids)
                return self._items_from_ids(
                    db=db,
                    movie_ids=als_ids,
                    reason="Based on collaborative patterns",
                    score_map=als_scores,
                )

            logger.warning(
                "als_only_returned_empty",
                extra={"user_id": user_id, "interaction_count": interaction_count},
            )

        elif strategy == "hybrid_light":
            hybrid_ids, hybrid_scores, hybrid_reason, debug_info = hybrid_recommender.recommend_ids(
                user_id=user_id,
                seed_movie_ids=seed_movie_ids,
                exclude_ids=exclude_ids,
                limit=limit,
                interaction_count=interaction_count,
                als_candidate_k=self.config.als_candidate_k,
                cbf_candidate_k=min(
                    max(self.config.min_candidate_k, limit * self.config.candidate_multiplier),
                    self.config.max_candidate_k,
                ),
                search_k=min(
                    max(self.config.min_candidate_k, limit * self.config.candidate_multiplier),
                    self.config.max_candidate_k,
                ),
                debug=self.config.debug_rerank,
            )

            logger.info(
                "hybrid_result",
                extra={
                    "user_id": user_id,
                    "interaction_count": interaction_count,
                    "seed_count": len(seed_movie_ids),
                    "hybrid_strategy": debug_info.strategy,
                    "hybrid_reason": debug_info.reason,
                    "warnings": debug_info.warnings,
                    "result_count": len(hybrid_ids),
                    "top_ids": hybrid_ids[:10],
                },
            )

            if hybrid_ids:
                return self._items_from_ids(
                    db=db,
                    movie_ids=hybrid_ids,
                    reason=hybrid_reason,
                    score_map=hybrid_scores,
                )

            logger.warning(
                "hybrid_returned_empty",
                extra={
                    "user_id": user_id,
                    "interaction_count": interaction_count,
                    "seed_count": len(seed_movie_ids),
                    "warnings": debug_info.warnings,
                },
            )

            # fallback inside strategy chain: ALS first if possible
            if has_als:
                als_ids = als_recommender.top_n(
                    user_id=user_id,
                    exclude_ids=exclude_ids,
                    n=max(limit, self.config.als_candidate_k),
                )[:limit]
                if als_ids:
                    als_scores = als_recommender.score_candidates(user_id, als_ids)
                    return self._items_from_ids(
                        db=db,
                        movie_ids=als_ids,
                        reason="Based on collaborative patterns",
                        score_map=als_scores,
                    )

            if seed_movie_ids:
                cbf_ids, cbf_scores = cbf_recommender.top_n_from_seeds(
                    seed_movie_ids=seed_movie_ids,
                    exclude_ids=exclude_ids,
                    n=limit,
                    search_k=max(limit * 5, 100),
                )
                if cbf_ids:
                    return self._items_from_ids(
                        db=db,
                        movie_ids=cbf_ids[:limit],
                        reason="Based on movies similar to your activity",
                        score_map=cbf_scores,
                    )

        elif strategy == "cbf_only":
            cbf_ids, cbf_scores = cbf_recommender.top_n_from_seeds(
                seed_movie_ids=seed_movie_ids,
                exclude_ids=exclude_ids,
                n=limit,
                search_k=max(limit * 5, 100),
            )

            if cbf_ids:
                return self._items_from_ids(
                    db=db,
                    movie_ids=cbf_ids[:limit],
                    reason="Based on movies similar to your activity",
                    score_map=cbf_scores,
                )

            logger.warning(
                "cbf_only_returned_empty",
                extra={"user_id": user_id, "seed_count": len(seed_movie_ids)},
            )

        # final fallback
        return self._items_from_movies(
            db=db,
            movies=self._get_trending_movies(db, limit, days=self.config.trending_days),
            reason="Trending now",
            score_map=None,
        )

    def get_for_user_for_eval(
        self,
        db: Session,
        user_id: int,
        limit: int,
        as_of_ts=None,
        force_seed_ids: list[int] | None = None,
        force_exclude_ids: set[int] | None = None,
    ) -> list[int]:
        seed_movie_ids, exclude_ids, has_als, interaction_count = self._prepare_context(
            db=db,
            user_id=user_id,
            as_of_ts=as_of_ts,
            force_seed_ids=force_seed_ids,
            force_exclude_ids=force_exclude_ids,
        )

        strategy, _ = self._choose_strategy(
            has_als=has_als,
            seed_movie_ids=seed_movie_ids,
        )

        if strategy == "als_only":
            return als_recommender.top_n(
                user_id=user_id,
                exclude_ids=exclude_ids,
                n=max(limit, self.config.als_candidate_k),
            )[:limit]

        if strategy == "hybrid_light":
            ids, _, _, _ = hybrid_recommender.recommend_ids(
                user_id=user_id,
                seed_movie_ids=seed_movie_ids,
                exclude_ids=exclude_ids,
                limit=limit,
                interaction_count=interaction_count,
                als_candidate_k=self.config.als_candidate_k,
                cbf_candidate_k=min(
                    max(self.config.min_candidate_k, limit * self.config.candidate_multiplier),
                    self.config.max_candidate_k,
                ),
                search_k=min(
                    max(self.config.min_candidate_k, limit * self.config.candidate_multiplier),
                    self.config.max_candidate_k,
                ),
                debug=False,
            )
            if ids:
                return ids

            if has_als:
                return als_recommender.top_n(
                    user_id=user_id,
                    exclude_ids=exclude_ids,
                    n=max(limit, self.config.als_candidate_k),
                )[:limit]

            if seed_movie_ids:
                cbf_ids, _ = cbf_recommender.top_n_from_seeds(
                    seed_movie_ids=seed_movie_ids,
                    exclude_ids=exclude_ids,
                    n=limit,
                    search_k=max(limit * 5, 100),
                )
                return cbf_ids[:limit]

            return []

        if strategy == "cbf_only":
            cbf_ids, _ = cbf_recommender.top_n_from_seeds(
                seed_movie_ids=seed_movie_ids,
                exclude_ids=exclude_ids,
                n=limit,
                search_k=max(limit * 5, 100),
            )
            return cbf_ids[:limit]

        return []

    def get_hybrid_ids_for_eval(
        self,
        db: Session,
        user_id: int,
        limit: int,
        as_of_ts=None,
        force_seed_ids: list[int] | None = None,
        force_exclude_ids: set[int] | None = None,
    ) -> list[int]:
        seed_movie_ids, exclude_ids, _, interaction_count = self._prepare_context(
            db=db,
            user_id=user_id,
            as_of_ts=as_of_ts,
            force_seed_ids=force_seed_ids,
            force_exclude_ids=force_exclude_ids,
        )

        ids, _, _, _ = hybrid_recommender.recommend_ids(
            user_id=user_id,
            seed_movie_ids=seed_movie_ids,
            exclude_ids=exclude_ids,
            limit=limit,
            interaction_count=interaction_count,
            als_candidate_k=self.config.max_candidate_k,
            cbf_candidate_k=self.config.max_candidate_k,
            search_k=self.config.max_candidate_k,
            debug=False,
        )
        return ids

    def get_sections_for_user(
        self,
        db: Session,
        user_id: int,
        limit_per_section: int = 12,
        as_of_ts=None,
    ) -> list[RecommendationSection]:
        used: set[int] = set()

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

        def pick_trending(days: int, pool_mult: int = 8) -> list[RecommendationItem]:
            movies = self._get_trending_movies(
                db,
                limit=limit_per_section * pool_mult,
                days=days,
            )
            items = self._items_from_movies(db, movies, reason="Trending now", score_map=None)
            items = [it for it in items if it.movie_id not in exclude_ids and it.movie_id not in used]
            return items

        trending_candidates = pick_trending(self.config.trending_days)
        if len(trending_candidates) < limit_per_section:
            trending_candidates += pick_trending(30)
        if len(trending_candidates) < limit_per_section:
            trending_candidates += pick_trending(3650)

        trending_items = self._dedup_items(trending_candidates, used, limit_per_section)
        if trending_items:
            sections.append(
                RecommendationSection(
                    title="Trending Now",
                    subtitle="Popular right now",
                    items=trending_items,
                )
            )

        because_items: list[RecommendationItem] = []
        if seed_movie_ids:
            seed = seed_movie_ids[0]
            ids = cbf_recommender.more_like_movie_ids(
                seed_movie_id=seed,
                exclude_ids=exclude_ids | used,
                limit=limit_per_section * 3,
            )
            because_items = self._items_from_ids(
                db=db,
                movie_ids=ids,
                reason="Because you liked a similar movie",
                score_map=None,
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

        hidden_movies = self._get_hidden_gems(db, limit=limit_per_section * 5, days=30)
        hidden_items = self._items_from_movies(db, hidden_movies, reason="Hidden gem", score_map=None)
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

    def _get_seed_movies_blended(self, db: Session, user_id: int, as_of_ts=None) -> list[int]:
        # Tightened seed quality: rate >= 4 instead of >= 3
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
              LIMIT 10
            ) t;
        """)
        event_rows = db.execute(sql_events, {"user_id": user_id, "as_of_ts": as_of_ts}).fetchall()
        event_seeds = [int(r[0]) for r in event_rows] if event_rows else []

        sql_onb = text("""
            SELECT movie_id
            FROM user_onboarding_movies
            WHERE user_id = :user_id
              AND (:as_of_ts IS NULL OR created_at < :as_of_ts)
            ORDER BY created_at DESC
            LIMIT 10;
        """)
        onb_rows = db.execute(sql_onb, {"user_id": user_id, "as_of_ts": as_of_ts}).fetchall()
        onb_seeds = [int(r[0]) for r in onb_rows] if onb_rows else []

        out: list[int] = []
        seen = set()

        for mid in event_seeds + onb_seeds:
            if mid not in seen:
                seen.add(mid)
                out.append(mid)
            if len(out) >= 12:
                break

        return out

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