import os
import json
import threading
import numpy as np
import hnswlib

ART_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "artifacts")
DEFAULT_VEC_DIR = os.path.join(ART_DIR, "vectors")
DEFAULT_HNSW_DIR = os.path.join(ART_DIR, "hnsw")


class VectorIndex:
    def __init__(self):
        self.index = None
        self.vectors = None
        self.movie_ids = None
        self.id_to_pos = {}
        self.dim = 256
        self.meta = None
        self._lock = threading.RLock()

    def _load_from_dirs(self, vec_dir: str, hnsw_dir: str) -> dict:
        movie_ids_path = os.path.join(vec_dir, "movie_ids.npy")
        vectors_path = os.path.join(vec_dir, "vectors.npy")
        index_path = os.path.join(hnsw_dir, "movies_hnsw.bin")
        meta_path = os.path.join(hnsw_dir, "meta.json")

        required = [movie_ids_path, vectors_path, index_path]
        missing = [p for p in required if not os.path.exists(p)]
        if missing:
            raise FileNotFoundError(f"HNSW/vector artifacts missing: {missing}")

        new_movie_ids = np.load(movie_ids_path).astype(np.int32)
        new_vectors = np.load(vectors_path).astype(np.float32)

        if new_movie_ids.ndim != 1:
            raise ValueError(
                f"movie_ids.npy must be 1D, got shape {new_movie_ids.shape}"
            )
        if new_vectors.ndim != 2:
            raise ValueError(
                f"vectors.npy must be 2D, got shape {new_vectors.shape}"
            )
        if len(new_movie_ids) != new_vectors.shape[0]:
            raise ValueError(
                "movie_ids and vectors row count mismatch: "
                f"len(movie_ids)={len(new_movie_ids)}, "
                f"vectors.shape={new_vectors.shape}"
            )

        unique_count = len(set(map(int, new_movie_ids.tolist())))
        if unique_count != len(new_movie_ids):
            raise ValueError("movie_ids.npy contains duplicate movie IDs")

        new_dim = int(new_vectors.shape[1])
        if new_dim <= 0:
            raise ValueError(f"Invalid vector dim: {new_dim}")

        new_id_to_pos = {int(mid): i for i, mid in enumerate(new_movie_ids)}

        new_meta = None
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                new_meta = json.load(f)

        new_index = hnswlib.Index(space="cosine", dim=new_dim)
        new_index.load_index(index_path)
        new_index.set_ef(64)

        current_count = new_index.get_current_count()
        if current_count != len(new_movie_ids):
            raise ValueError(
                "HNSW index count mismatch: "
                f"index_count={current_count}, movie_ids_count={len(new_movie_ids)}"
            )

        return {
            "movie_ids": new_movie_ids,
            "vectors": new_vectors,
            "dim": new_dim,
            "id_to_pos": new_id_to_pos,
            "meta": new_meta,
            "index": new_index,
            "summary": {
                "vec_dir": vec_dir,
                "hnsw_dir": hnsw_dir,
                "movie_count": int(len(new_movie_ids)),
                "vector_dim": int(new_dim),
                "index_count": int(current_count),
            },
        }

    def validate_dirs(self, vec_dir: str | None = None, hnsw_dir: str | None = None) -> dict:
        target_vec_dir = vec_dir or DEFAULT_VEC_DIR
        target_hnsw_dir = hnsw_dir or DEFAULT_HNSW_DIR
        loaded = self._load_from_dirs(target_vec_dir, target_hnsw_dir)
        return {
            "ok": True,
            **loaded["summary"],
        }

    def load(self, vec_dir: str | None = None, hnsw_dir: str | None = None):
        target_vec_dir = vec_dir or DEFAULT_VEC_DIR
        target_hnsw_dir = hnsw_dir or DEFAULT_HNSW_DIR
        loaded = self._load_from_dirs(target_vec_dir, target_hnsw_dir)

        with self._lock:
            self.movie_ids = loaded["movie_ids"]
            self.vectors = loaded["vectors"]
            self.dim = loaded["dim"]
            self.id_to_pos = loaded["id_to_pos"]
            self.meta = loaded["meta"]
            self.index = loaded["index"]

        return self

    def is_loaded(self) -> bool:
        with self._lock:
            return (
                self.index is not None
                and self.vectors is not None
                and self.movie_ids is not None
            )

    def get_vector(self, movie_id: int):
        if not self.is_loaded():
            self.load()

        with self._lock:
            vectors = self.vectors
            id_to_pos = self.id_to_pos

        pos = id_to_pos.get(int(movie_id))
        if pos is None:
            return None
        return vectors[pos]

    def search(self, query_vec: np.ndarray, k: int = 50):
        if not self.is_loaded():
            self.load()

        if query_vec is None:
            return []

        query_vec = np.asarray(query_vec, dtype=np.float32)
        if query_vec.ndim != 1:
            raise ValueError(f"query_vec must be 1D, got shape {query_vec.shape}")

        with self._lock:
            index = self.index
            movie_ids = self.movie_ids

        max_k = len(movie_ids) if movie_ids is not None else k
        k = min(k, max_k)

        if k <= 0:
            return []

        labels, distances = index.knn_query(query_vec, k=k)
        labels = labels[0].tolist()
        distances = distances[0].tolist()

        results = []
        for mid, dist in zip(labels, distances):
            score = 1.0 - float(dist)
            results.append((int(mid), score))
        return results


vector_index = VectorIndex()