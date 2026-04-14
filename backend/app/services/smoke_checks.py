from __future__ import annotations

import os

from app.services.als_store import als_store
from app.services.vector_index import vector_index


def run_smoke_checks(run_id: str, cached_run_dir: str) -> dict:
    """
    These smoke checks run inside the worker process, not the live API process.
    So loading the candidate artifacts here is safe.

    First version checks:
    - ALS artifacts can be loaded and score a sample user against sample items
    - Vector/HNSW artifacts can be loaded and searched
    """
    checks: list[dict] = []

    als_dir = os.path.join(cached_run_dir, "als")
    vectors_dir = os.path.join(cached_run_dir, "vectors")
    hnsw_dir = os.path.join(cached_run_dir, "hnsw")

    try:
        als_store.load(als_dir)
        has_users = bool(als_store.user_id_to_idx)
        has_movies = bool(als_store.movie_id_to_idx)
        checks.append(
            {
                "name": "als_loaded",
                "ok": has_users and has_movies,
                "user_count": len(als_store.user_id_to_idx or {}),
                "movie_count": len(als_store.movie_id_to_idx or {}),
            }
        )

        if has_users and has_movies:
            sample_user_id = next(iter(als_store.user_id_to_idx.keys()))
            sample_movie_ids = list(als_store.movie_id_to_idx.keys())[:10]
            scores = als_store.score_candidates(sample_user_id, sample_movie_ids)
            checks.append(
                {
                    "name": "als_score_candidates",
                    "ok": len(scores) > 0,
                    "sample_user_id": int(sample_user_id),
                    "candidate_count": len(sample_movie_ids),
                    "scored_count": len(scores),
                }
            )
        else:
            checks.append(
                {
                    "name": "als_score_candidates",
                    "ok": False,
                    "reason": "ALS mappings empty",
                }
            )

    except Exception as e:
        checks.append(
            {
                "name": "als_checks",
                "ok": False,
                "error_type": type(e).__name__,
                "error_message": str(e),
            }
        )

    try:
        vector_index.load(vectors_dir, hnsw_dir)

        movie_count = int(len(vector_index.movie_ids)) if vector_index.movie_ids is not None else 0
        has_vectors = (
            vector_index.movie_ids is not None
            and vector_index.vectors is not None
            and movie_count > 0
        )

        checks.append(
            {
                "name": "vector_index_loaded",
                "ok": has_vectors,
                "movie_count": movie_count,
                "vector_dim": int(vector_index.dim),
            }
        )

        if has_vectors:
            query_vec = vector_index.vectors[0]
            results = vector_index.search(query_vec, k=min(5, movie_count))
            checks.append(
                {
                    "name": "vector_search",
                    "ok": len(results) > 0,
                    "result_count": len(results),
                }
            )
        else:
            checks.append(
                {
                    "name": "vector_search",
                    "ok": False,
                    "reason": "No vectors loaded",
                }
            )

    except Exception as e:
        checks.append(
            {
                "name": "vector_checks",
                "ok": False,
                "error_type": type(e).__name__,
                "error_message": str(e),
            }
        )

    return {
        "ok": all(c.get("ok") for c in checks),
        "run_id": run_id,
        "cached_run_dir": cached_run_dir,
        "checks": checks,
    }