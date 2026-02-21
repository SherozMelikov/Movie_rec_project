import os
import numpy as np
import hnswlib

ART_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "artifacts")


VEC_DIR = os.path.join(ART_DIR, "vectors")
HNSW_DIR = os.path.join(ART_DIR, "hnsw")


class VectorIndex:
    def __init__(self):
        self.index = None
        self.vectors = None
        self.movie_ids = None
        self.id_to_pos = {}
        self.dim = 256

    def load(self):
        movie_ids_path = os.path.join(VEC_DIR, "movie_ids.npy")
        vectors_path = os.path.join(VEC_DIR, "vectors.npy")
        index_path = os.path.join(HNSW_DIR, "movies_hnsw.bin")

        if not (os.path.exists(movie_ids_path) and os.path.exists(vectors_path) and os.path.exists(index_path)):
            raise FileNotFoundError("HNSW artifacts not found. Run build_hnsw_artifacts first.")

        self.movie_ids = np.load(movie_ids_path).astype(np.int32)
        self.vectors = np.load(vectors_path).astype(np.float32)
        self.dim = self.vectors.shape[1]

        self.id_to_pos = {int(mid): i for i, mid in enumerate(self.movie_ids)}

        idx = hnswlib.Index(space="cosine", dim=self.dim)
        idx.load_index(index_path)
        idx.set_ef(64)

        self.index = idx
        return self

    def get_vector(self, movie_id: int):
        pos = self.id_to_pos.get(int(movie_id))
        if pos is None:
            return None
        return self.vectors[pos]

    def search(self, query_vec: np.ndarray, k: int = 50):
        # query_vec shape (dim,) float32
        labels, distances = self.index.knn_query(query_vec, k=k)
        labels = labels[0].tolist()
        distances = distances[0].tolist()

        # For cosine space, distance is (1 - cosine_similarity)
        results = []
        for mid, dist in zip(labels, distances):
            score = 1.0 - float(dist)
            results.append((int(mid), score))
        return results


vector_index = VectorIndex()
