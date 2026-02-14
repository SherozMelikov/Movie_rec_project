import os
import json
import numpy as np
import joblib

import hnswlib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

from app.db.database import SessionLocal
from app.db.models import Movie

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts")
VEC_DIR = os.path.join(ARTIFACT_DIR, "vectors")
HNSW_DIR = os.path.join(ARTIFACT_DIR, "hnsw")


def ensure_dirs():
    os.makedirs(VEC_DIR, exist_ok=True)
    os.makedirs(HNSW_DIR, exist_ok=True)


def movie_text(title: str, genres: str | None) -> str:
    g = (genres or "").replace("|", " ")
    return f"{title} {g}".strip()


def load_movies():
    db = SessionLocal()
    try:
        rows = db.query(Movie.movie_id, Movie.title, Movie.genres).yield_per(5000)
        movie_ids = []
        texts = []
        for mid, title, genres in rows:
            movie_ids.append(int(mid))
            texts.append(movie_text(title, genres))
        return np.array(movie_ids, dtype=np.int32), texts
    finally:
        db.close()


def build():
    ensure_dirs()
    movie_ids, texts = load_movies()
    print(f"Loaded {len(movie_ids)} movies")

    # TF-IDF
    vectorizer = TfidfVectorizer(
        min_df=2,
        max_features=300_000,
        ngram_range=(1, 2),
        stop_words="english",
    )
    X = vectorizer.fit_transform(texts)
    print(f"TF-IDF shape: {X.shape}")

    # SVD -> dense
    dim = 256
    svd = TruncatedSVD(n_components=dim, random_state=42)
    X_dense = svd.fit_transform(X).astype(np.float32)

    # Normalize for cosine similarity
    X_dense = normalize(X_dense, norm="l2").astype(np.float32)

    # Save vector artifacts
    np.save(os.path.join(VEC_DIR, "movie_ids.npy"), movie_ids)
    np.save(os.path.join(VEC_DIR, "vectors.npy"), X_dense)
    joblib.dump(vectorizer, os.path.join(VEC_DIR, "tfidf.joblib"))
    joblib.dump(svd, os.path.join(VEC_DIR, "svd.joblib"))

    # Build HNSW index (cosine space)
    # hnswlib cosine expects unnormalized vectors? It works best with normalized vectors anyway.
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
    }
    with open(os.path.join(HNSW_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print("Artifacts saved:")
    print(f"- {VEC_DIR}/movie_ids.npy")
    print(f"- {VEC_DIR}/vectors.npy")
    print(f"- {VEC_DIR}/tfidf.joblib")
    print(f"- {VEC_DIR}/svd.joblib")
    print(f"- {HNSW_DIR}/movies_hnsw.bin")
    print(f"- {HNSW_DIR}/meta.json")


if __name__ == "__main__":
    build()
