import os
import json
from typing import Tuple

import numpy as np
import joblib
import hnswlib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

from app.db.database import SessionLocal
from app.db.models import Movie, MovieMetadata

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts")
VEC_DIR = os.path.join(ARTIFACT_DIR, "vectors")
HNSW_DIR = os.path.join(ARTIFACT_DIR, "hnsw")


def ensure_dirs() -> None:
    os.makedirs(VEC_DIR, exist_ok=True)
    os.makedirs(HNSW_DIR, exist_ok=True)


def movie_text(title: str, genres: str | None, overview: str | None) -> str:
    title_text = (title or "").strip()
    genres_text = (genres or "").replace("|", " ").strip()
    overview_text = (overview or "").strip()

    return " ".join(
        part for part in [title_text, genres_text, overview_text] if part
    )


def load_movies() -> Tuple[np.ndarray, list[str]]:
    db = SessionLocal()
    try:
        rows = (
            db.query(
                Movie.movie_id,
                Movie.title,
                Movie.genres,
                MovieMetadata.overview,
            )
            .outerjoin(MovieMetadata, Movie.movie_id == MovieMetadata.movie_id)
            .yield_per(5000)
        )

        movie_ids = []
        texts = []

        for mid, title, genres, overview in rows:
            movie_ids.append(int(mid))
            texts.append(movie_text(title, genres, overview))

        return np.array(movie_ids, dtype=np.int32), texts
    finally:
        db.close()


def build_hnsw_artifacts() -> dict:
    ensure_dirs()

    print("✅ Vector artifact dir:", os.path.abspath(VEC_DIR))
    print("✅ HNSW artifact dir:", os.path.abspath(HNSW_DIR))

    movie_ids, texts = load_movies()
    print(f"Loaded {len(movie_ids)} movies")

    if len(movie_ids) == 0:
        raise RuntimeError("No movies found. Cannot build vector/HNSW artifacts.")

    vectorizer = TfidfVectorizer(
        min_df=2,
        max_features=300_000,
        ngram_range=(1, 2),
        stop_words="english",
    )
    X = vectorizer.fit_transform(texts)
    print(f"TF-IDF shape: {X.shape}")

    dim = 256
    max_valid_dim = min(X.shape[0] - 1, X.shape[1] - 1)

    if max_valid_dim < 2:
        raise RuntimeError(f"Not enough data to build SVD vectors safely. TF-IDF shape={X.shape}")

    if dim > max_valid_dim:
        print(f"⚠️ Requested dim={dim} too high for TF-IDF shape={X.shape}. Using dim={max_valid_dim}.")
        dim = max_valid_dim

    svd = TruncatedSVD(n_components=dim, random_state=42)
    X_dense = svd.fit_transform(X).astype(np.float32)

    # Normalize for cosine similarity
    X_dense = normalize(X_dense, norm="l2").astype(np.float32)

    movie_ids_path = os.path.join(VEC_DIR, "movie_ids.npy")
    vectors_path = os.path.join(VEC_DIR, "vectors.npy")
    tfidf_path = os.path.join(VEC_DIR, "tfidf.joblib")
    svd_path = os.path.join(VEC_DIR, "svd.joblib")

    np.save(movie_ids_path, movie_ids)
    np.save(vectors_path, X_dense)
    joblib.dump(vectorizer, tfidf_path)
    joblib.dump(svd, svd_path)

    index = hnswlib.Index(space="cosine", dim=dim)
    index.init_index(max_elements=X_dense.shape[0], ef_construction=200, M=32)
    index.add_items(X_dense, movie_ids)  # label = movie_id
    index.set_ef(64)

    index_path = os.path.join(HNSW_DIR, "movies_hnsw.bin")
    index.save_index(index_path)

    meta = {
        "dim": dim,
        "count": int(len(movie_ids)),
        "space": "cosine",
        "index_type": "hnswlib",
        "M": 32,
        "ef_construction": 200,
        "ef_search": 64,
        "tfidf_shape": [int(X.shape[0]), int(X.shape[1])],
        "vector_shape": [int(X_dense.shape[0]), int(X_dense.shape[1])],
        "text_fields": ["title", "genres", "overview"],
    }

    meta_path = os.path.join(HNSW_DIR, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print("✅ Artifacts saved:")
    print(f"- {movie_ids_path}")
    print(f"- {vectors_path}")
    print(f"- {tfidf_path}")
    print(f"- {svd_path}")
    print(f"- {index_path}")
    print(f"- {meta_path}")

    return {
        "vector_dir": os.path.abspath(VEC_DIR),
        "hnsw_dir": os.path.abspath(HNSW_DIR),
        "count": int(len(movie_ids)),
        "dim": dim,
        "meta": meta,
    }


if __name__ == "__main__":
    build_hnsw_artifacts()