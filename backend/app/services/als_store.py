import os
import json
import threading
import numpy as np

DEFAULT_ALS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "ml", "artifacts", "als"
)


class ALSStore:
    def __init__(self):
        self.user_factors = None
        self.item_factors = None
        self.user_id_to_idx = None
        self.movie_id_to_idx = None
        self._lock = threading.RLock()

    def _load_from_dir(self, als_dir: str) -> dict:
        user_factors_path = os.path.join(als_dir, "user_factors.npy")
        item_factors_path = os.path.join(als_dir, "item_factors.npy")
        user_map_path = os.path.join(als_dir, "user_id_to_idx.json")
        movie_map_path = os.path.join(als_dir, "movie_id_to_idx.json")

        required = [
            user_factors_path,
            item_factors_path,
            user_map_path,
            movie_map_path,
        ]
        missing = [p for p in required if not os.path.exists(p)]
        if missing:
            raise FileNotFoundError(f"ALS artifacts missing in {als_dir}: {missing}")

        new_user_factors = np.load(user_factors_path)
        new_item_factors = np.load(item_factors_path)

        with open(user_map_path, "r", encoding="utf-8") as f:
            new_user_id_to_idx = {int(k): int(v) for k, v in json.load(f).items()}

        with open(movie_map_path, "r", encoding="utf-8") as f:
            new_movie_id_to_idx = {int(k): int(v) for k, v in json.load(f).items()}

        if new_user_factors.ndim != 2:
            raise ValueError(
                f"user_factors must be 2D, got shape {new_user_factors.shape}"
            )
        if new_item_factors.ndim != 2:
            raise ValueError(
                f"item_factors must be 2D, got shape {new_item_factors.shape}"
            )
        if new_user_factors.shape[1] != new_item_factors.shape[1]:
            raise ValueError(
                "ALS factor dims mismatch: "
                f"user_factors.shape={new_user_factors.shape}, "
                f"item_factors.shape={new_item_factors.shape}"
            )

        if new_user_id_to_idx:
            max_user_idx = max(new_user_id_to_idx.values())
            if max_user_idx >= new_user_factors.shape[0]:
                raise ValueError(
                    f"user_id_to_idx references row {max_user_idx}, "
                    f"but user_factors has {new_user_factors.shape[0]} rows"
                )

        if new_movie_id_to_idx:
            max_movie_idx = max(new_movie_id_to_idx.values())
            if max_movie_idx >= new_item_factors.shape[0]:
                raise ValueError(
                    f"movie_id_to_idx references row {max_movie_idx}, "
                    f"but item_factors has {new_item_factors.shape[0]} rows"
                )

        return {
            "user_factors": new_user_factors,
            "item_factors": new_item_factors,
            "user_id_to_idx": new_user_id_to_idx,
            "movie_id_to_idx": new_movie_id_to_idx,
            "summary": {
                "als_dir": als_dir,
                "user_count": int(new_user_factors.shape[0]),
                "item_count": int(new_item_factors.shape[0]),
                "factor_dim": int(new_user_factors.shape[1]),
            },
        }

    def validate_dir(self, als_dir: str | None = None) -> dict:
        target_dir = als_dir or DEFAULT_ALS_DIR
        loaded = self._load_from_dir(target_dir)
        return {
            "ok": True,
            **loaded["summary"],
        }

    def load(self, als_dir: str | None = None):
        target_dir = als_dir or DEFAULT_ALS_DIR
        loaded = self._load_from_dir(target_dir)

        with self._lock:
            self.user_factors = loaded["user_factors"]
            self.item_factors = loaded["item_factors"]
            self.user_id_to_idx = loaded["user_id_to_idx"]
            self.movie_id_to_idx = loaded["movie_id_to_idx"]

        return self

    def is_loaded(self) -> bool:
        with self._lock:
            return (
                self.user_factors is not None
                and self.item_factors is not None
                and self.user_id_to_idx is not None
                and self.movie_id_to_idx is not None
            )

    def can_score_user(self, user_id: int) -> bool:
        if not self.is_loaded():
            self.load()

        with self._lock:
            user_id_to_idx = self.user_id_to_idx

        return int(user_id) in user_id_to_idx

    def score_candidates(self, user_id: int, movie_ids: list[int]) -> list[tuple[int, float]]:
        """
        Returns list[(movie_id, score)] for candidates that exist in ALS mapping.
        """
        if not self.is_loaded():
            self.load()

        with self._lock:
            user_factors = self.user_factors
            item_factors = self.item_factors
            user_id_to_idx = self.user_id_to_idx
            movie_id_to_idx = self.movie_id_to_idx

        uid = int(user_id)
        if uid not in user_id_to_idx:
            return []

        uidx = user_id_to_idx[uid]
        uvec = user_factors[uidx]

        mids = [int(mid) for mid in movie_ids if int(mid) in movie_id_to_idx]
        if not mids:
            return []

        iidx = np.array([movie_id_to_idx[mid] for mid in mids], dtype=np.int32)
        ivec = item_factors[iidx]

        scores = ivec @ uvec
        return list(zip(mids, scores.astype(float).tolist()))


als_store = ALSStore()