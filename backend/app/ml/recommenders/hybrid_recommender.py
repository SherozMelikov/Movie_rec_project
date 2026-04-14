import logging
from dataclasses import dataclass

import numpy as np

from app.ml.recommenders.als_recommender import als_recommender
from app.ml.recommenders.cbf_recommender import cbf_recommender

logger = logging.getLogger(__name__)


@dataclass
class HybridDebugInfo:
    user_id: int
    strategy: str
    reason: str
    has_als: bool
    has_cbf: bool
    interaction_count: int
    seed_count: int
    als_candidate_count: int
    cbf_candidate_count: int
    union_candidate_count: int
    cbf_best_score: float
    cbf_avg_top10: float
    warnings: list[str]


class HybridRecommender:
    def _safe_minmax(self, d: dict[int, float]) -> dict[int, float]:
        if not d:
            return {}

        vals = np.array(list(d.values()), dtype=np.float32)
        lo, hi = float(vals.min()), float(vals.max())

        # Important: flat scores should be neutral, not max confidence
        if hi - lo < 1e-9:
            return {k: 0.0 for k in d}

        return {k: float((v - lo) / (hi - lo)) for k, v in d.items()}

    def _cbf_stats(self, cbf_score_map: dict[int, float]) -> tuple[float, float]:
        if not cbf_score_map:
            return 0.0, 0.0

        vals = sorted(cbf_score_map.values(), reverse=True)
        best = float(vals[0])
        top10 = vals[:10]
        avg_top10 = float(sum(top10) / len(top10)) if top10 else 0.0
        return best, avg_top10

    def _is_cbf_strong(
        self,
        seed_count: int,
        cbf_candidate_count: int,
        cbf_best_score: float,
        cbf_avg_top10: float,
    ) -> bool:
        if seed_count < 2:
            return False
        if cbf_candidate_count < 20:
            return False
        if cbf_best_score < 0.45:
            return False
        if cbf_avg_top10 < 0.30:
            return False
        return True

    def _choose_strategy(
        self,
        has_als: bool,
        interaction_count: int,
        seed_count: int,
        cbf_candidate_count: int,
        cbf_best_score: float,
        cbf_avg_top10: float,
    ) -> tuple[str, str]:
        has_cbf = seed_count > 0 and cbf_candidate_count > 0
        cbf_strong = self._is_cbf_strong(
            seed_count=seed_count,
            cbf_candidate_count=cbf_candidate_count,
            cbf_best_score=cbf_best_score,
            cbf_avg_top10=cbf_avg_top10,
        )

        # Warm users: strongly protect ALS
        if has_als and interaction_count >= 20:
            if cbf_strong:
                return "als_plus_cbf_bonus", "warm user with strong CBF signal"
            return "als_only", "warm user; protecting strong ALS ranking"

        # Any ALS-capable user with some history
        if has_als and interaction_count > 0:
            if has_cbf:
                return "hybrid_light", "sparse user with ALS + CBF signal"
            return "als_only", "sparse user; no usable CBF"

        # Cold user but ALS still available
        if has_als:
            return "als_only", "cold user with ALS support"

        # No ALS but seeds exist
        if has_cbf:
            return "cbf_only", "no ALS support; using seed-based CBF"

        # No signal
        return "fallback_only", "no ALS and no usable CBF"
    def recommend_ids(
        self,
        user_id: int,
        seed_movie_ids: list[int],
        exclude_ids: set[int],
        limit: int,
        interaction_count: int = 0,
        als_candidate_k: int = 500,
        cbf_candidate_k: int = 500,
        search_k: int = 1000,
        debug: bool = False,
    ) -> tuple[list[int], dict[int, float], str, HybridDebugInfo]:

        warnings: list[str] = []

        has_als = als_recommender.can_score_user(user_id)

        als_candidates: list[int] = []
        if has_als:
            als_candidates = als_recommender.top_n(
                user_id=user_id,
                exclude_ids=exclude_ids,
                n=als_candidate_k,
            )

        cbf_candidates: list[int] = []
        cbf_score_map: dict[int, float] = {}
        if seed_movie_ids:
            cbf_candidates, cbf_score_map = cbf_recommender.top_n_from_seeds(
                seed_movie_ids=seed_movie_ids,
                exclude_ids=exclude_ids,
                n=cbf_candidate_k,
                search_k=search_k,
            )

        candidate_ids = list(dict.fromkeys(als_candidates + cbf_candidates))
        cbf_best_score, cbf_avg_top10 = self._cbf_stats(cbf_score_map)

        strategy, reason = self._choose_strategy(
            has_als=has_als,
            interaction_count=interaction_count,
            seed_count=len(seed_movie_ids),
            cbf_candidate_count=len(cbf_candidates),
            cbf_best_score=cbf_best_score,
            cbf_avg_top10=cbf_avg_top10,
        )

        if not candidate_ids and strategy != "fallback_only":
            warnings.append("no_candidates_after_retrieval")
            strategy = "fallback_only"
            reason = "retrieval returned no candidates"

        if strategy == "als_only":
            ranked_ids = als_candidates[:limit]
            score_map = als_recommender.score_candidates(user_id, ranked_ids) if ranked_ids else {}
            label = "Based on collaborative patterns"

        elif strategy == "als_plus_cbf_bonus":
            als_score_map = als_recommender.score_candidates(user_id, candidate_ids)
            als_n = self._safe_minmax(als_score_map)

            cbf_union_scores = {
                mid: cbf_score_map[mid]
                for mid in cbf_score_map
                if mid in candidate_ids
            }
            cbf_n = self._safe_minmax(cbf_union_scores)

            final: dict[int, float] = {}
            for mid in candidate_ids:
                a = als_n.get(mid, 0.0)
                c = cbf_n.get(mid, 0.0)
                final[mid] = (0.95 * a) + (0.05 * c)

            ranked = sorted(final.items(), key=lambda x: x[1], reverse=True)[:limit]
            ranked_ids = [mid for mid, _ in ranked]
            score_map = {mid: float(score) for mid, score in ranked}
            label = "Based on collaborative patterns and similar content"

        elif strategy == "hybrid_light":
            als_score_map = als_recommender.score_candidates(user_id, candidate_ids)
            als_n = self._safe_minmax(als_score_map)

            cbf_union_scores = {
                mid: cbf_score_map[mid]
                for mid in cbf_score_map
                if mid in candidate_ids
            }
            cbf_n = self._safe_minmax(cbf_union_scores)

            # Dynamic blending:
            # - sparse users should lean more toward CBF
            # - medium users are balanced
            # - stronger users lean toward ALS
            if interaction_count < 10:
                w_als, w_cbf = 0.20, 0.80
            elif interaction_count < 30:
                w_als, w_cbf = 0.50, 0.50
            else:
                w_als, w_cbf = 0.70, 0.30

            final: dict[int, float] = {}
            for mid in candidate_ids:
                a = als_n.get(mid, 0.0)
                c = cbf_n.get(mid, 0.0)
                final[mid] = (w_als * a) + (w_cbf * c)

            ranked = sorted(final.items(), key=lambda x: x[1], reverse=True)[:limit]
            ranked_ids = [mid for mid, _ in ranked]
            score_map = {mid: float(score) for mid, score in ranked}
            label = "Based on your activity and similar movies"

        elif strategy == "cbf_only":
            ranked_ids = cbf_candidates[:limit]
            score_map = {
                mid: float(cbf_score_map[mid])
                for mid in ranked_ids
                if mid in cbf_score_map
            }
            label = "Based on movies similar to your activity"

        else:
            ranked_ids = []
            score_map = {}
            label = "Fallback recommendations"

        if not ranked_ids:
            warnings.append("empty_final_ranking")

        debug_info = HybridDebugInfo(
            user_id=int(user_id),
            strategy=strategy,
            reason=reason,
            has_als=bool(has_als),
            has_cbf=bool(len(seed_movie_ids) > 0 and len(cbf_candidates) > 0),
            interaction_count=int(interaction_count),
            seed_count=len(seed_movie_ids),
            als_candidate_count=len(als_candidates),
            cbf_candidate_count=len(cbf_candidates),
            union_candidate_count=len(candidate_ids),
            cbf_best_score=float(cbf_best_score),
            cbf_avg_top10=float(cbf_avg_top10),
            warnings=warnings,
        )

        logger.info(
            "hybrid_recommendation_decision",
            extra={
                "user_id": debug_info.user_id,
                "strategy": debug_info.strategy,
                "reason": debug_info.reason,
                "has_als": debug_info.has_als,
                "has_cbf": debug_info.has_cbf,
                "interaction_count": debug_info.interaction_count,
                "seed_count": debug_info.seed_count,
                "als_candidate_count": debug_info.als_candidate_count,
                "cbf_candidate_count": debug_info.cbf_candidate_count,
                "union_candidate_count": debug_info.union_candidate_count,
                "cbf_best_score": debug_info.cbf_best_score,
                "cbf_avg_top10": debug_info.cbf_avg_top10,
                "warnings": debug_info.warnings,
                "top_ids": ranked_ids[:10],
            },
        )

        if debug:
            print("\n--- HYBRID DEBUG ---")
            print("user_id:", debug_info.user_id)
            print("strategy:", debug_info.strategy)
            print("reason:", debug_info.reason)
            print("has_als:", debug_info.has_als)
            print("has_cbf:", debug_info.has_cbf)
            print("interaction_count:", debug_info.interaction_count)
            print("seed_count:", debug_info.seed_count)
            print("als_candidate_count:", debug_info.als_candidate_count)
            print("cbf_candidate_count:", debug_info.cbf_candidate_count)
            print("union_candidate_count:", debug_info.union_candidate_count)
            print("cbf_best_score:", debug_info.cbf_best_score)
            print("cbf_avg_top10:", debug_info.cbf_avg_top10)
            print("warnings:", debug_info.warnings)
            print("top_ids[:10]:", ranked_ids[:10])

        return ranked_ids, score_map, label, debug_info


hybrid_recommender = HybridRecommender()