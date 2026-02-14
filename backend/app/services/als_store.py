import os
import json
import numpy as np

ART_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "artifacts", "als")


class ALSStore:
    def __init__(self):
        self.user_factors = None
        self.item_factors = None
        self.user_id_to_idx = None
        self.movie_id_to_idx = None

    def load(self):
        self.user_factors = np.load(os.path.join(ART_DIR, "user_factors.npy"))
        self.item_factors = np.load(os.path.join(ART_DIR, "item_factors.npy"))

        with open(os.path.join(ART_DIR, "user_id_to_idx.json"), "r", encoding="utf-8") as f:
            self.user_id_to_idx = {int(k): int(v) for k, v in json.load(f).items()}

        with open(os.path.join(ART_DIR, "movie_id_to_idx.json"), "r", encoding="utf-8") as f:
            self.movie_id_to_idx = {int(k): int(v) for k, v in json.load(f).items()}

        return self

    def can_score_user(self, user_id: int) -> bool:
        return self.user_id_to_idx is not None and int(user_id) in self.user_id_to_idx

    def score_candidates(self, user_id: int, movie_ids: list[int]) -> list[tuple[int, float]]:
        """
        Returns list[(movie_id, score)] for candidates that exist in ALS mapping.
        """
        if self.user_factors is None:
            self.load()

        uid = int(user_id)
        if uid not in self.user_id_to_idx:
            return []

        uidx = self.user_id_to_idx[uid]
        uvec = self.user_factors[uidx]  # (factors,)

        mids = [int(mid) for mid in movie_ids if int(mid) in self.movie_id_to_idx]
        if not mids:
            return []

        iidx = np.array([self.movie_id_to_idx[mid] for mid in mids], dtype=np.int32)
        ivec = self.item_factors[iidx]  # (n, factors)

        scores = ivec @ uvec  # (n,)
        return list(zip(mids, scores.astype(float).tolist()))


als_store = ALSStore()
