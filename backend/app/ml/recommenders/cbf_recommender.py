import numpy as np

from app.services.vector_index import vector_index


class CBFRecommender:
    """
    Runtime content-based recommender logic.
    Uses vector_index as the artifact loader / ANN search layer.
    """

    def _ensure_loaded(self) -> None:
        if not vector_index.is_loaded():
            vector_index.load()

    def build_user_vector(self, seed_movie_ids: list[int]):
        """
        Build a user profile vector as the mean of seed movie vectors.
        """
        self._ensure_loaded()

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

    def top_n_from_seeds(
        self,
        seed_movie_ids: list[int],
        exclude_ids: set[int],
        n: int = 300,
        search_k: int = 5000,
    ) -> tuple[list[int], dict[int, float]]:
        """
        Build user vector from seeds, retrieve nearest neighbors, filter exclusions.
        Returns:
            (ranked_ids, {movie_id: cbf_score})
        """
        self._ensure_loaded()

        user_vec = self.build_user_vector(seed_movie_ids)
        if user_vec is None:
            return [], {}

        hits = vector_index.search(user_vec, k=search_k)

        ids: list[int] = []
        score_map: dict[int, float] = {}

        for mid, score in hits:
            mid = int(mid)
            if mid in exclude_ids:
                continue
            ids.append(mid)
            score_map[mid] = float(score)
            if len(ids) >= n:
                break

        return ids, score_map

    def more_like_movie_ids(
        self,
        seed_movie_id: int,
        exclude_ids: set[int],
        limit: int,
    ) -> list[int]:
        """
        Item-to-item retrieval from one seed movie.
        Returns ranked movie IDs only.
        """
        self._ensure_loaded()

        v = vector_index.get_vector(seed_movie_id)
        if v is None:
            return []

        hits = vector_index.search(v, k=limit * 5)

        ids: list[int] = []
        for mid, _ in hits:
            mid = int(mid)
            if mid == int(seed_movie_id) or mid in exclude_ids:
                continue
            ids.append(mid)
            if len(ids) >= limit:
                break

        return ids


cbf_recommender = CBFRecommender()