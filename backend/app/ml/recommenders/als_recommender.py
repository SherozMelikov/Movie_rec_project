import numpy as np

from app.services.als_store import als_store


class ALSRecommender:
    """
    Runtime ALS recommender logic.
    Uses als_store as the artifact loader / scorer.
    """

    def __init__(self):
        self._idx_to_movie_id: dict[int, int] | None = None

    def _ensure_loaded(self) -> None:
        if not als_store.is_loaded():
            als_store.load()

        if self._idx_to_movie_id is None:
            self._idx_to_movie_id = {
                int(v): int(k) for k, v in als_store.movie_id_to_idx.items()
            }

    def can_score_user(self, user_id: int) -> bool:
        return als_store.can_score_user(user_id)

    def top_n(self, user_id: int, exclude_ids: set[int], n: int = 300) -> list[int]:
        """
        Full-catalog ALS ranking, excluding provided movie IDs.
        Returns ranked movie IDs.
        """
        self._ensure_loaded()

        uid = int(user_id)
        if uid not in als_store.user_id_to_idx:
            return []

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

        top_iidx = np.argpartition(-scores, n - 1)[:n]
        top_iidx = top_iidx[np.argsort(-scores[top_iidx])]

        return [self._idx_to_movie_id[int(i)] for i in top_iidx]

    def score_candidates(self, user_id: int, candidate_ids: list[int]) -> dict[int, float]:
        """
        Score only the given candidate IDs using ALS.
        Returns {movie_id: score}.
        """
        pairs = als_store.score_candidates(user_id, candidate_ids)
        return {int(mid): float(score) for mid, score in pairs}


als_recommender = ALSRecommender()