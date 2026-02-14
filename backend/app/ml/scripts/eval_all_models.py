# backend/app/ml/scripts/eval_all_models.py
# Run:
#   python -m app.ml.scripts.eval_all_models

from math import log2
from sqlalchemy import text
from app.db.database import SessionLocal
from app.services.recommend_service import recommend_service
from app.services.als_store import als_store
from app.services.vector_index import vector_index
import numpy as np

K = 20

# IMPORTANT: quoted column names to match your DB schema
SQL_TEST = text("""
SELECT DISTINCT ON ("user_id")
  "user_id", "movie_id", "ts"
FROM events
WHERE "event_type" = 'like'
   OR ("event_type" = 'rate' AND "rating_value" >= 4)
ORDER BY "user_id", "ts" DESC;
""")


def hit_ndcg(test_mid: int, ranked_ids: list[int]):
    if test_mid not in ranked_ids:
        return 0, 0.0
    rank = ranked_ids.index(test_mid) + 1
    return 1, 1.0 / log2(rank + 1)


def build_user_vec_from_seeds(seeds: list[int]):
    vecs = []
    for mid in seeds:
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


def evaluate():
    db = SessionLocal()

    # Load artifacts once
    als_store.load()
    if vector_index.index is None:
        vector_index.load()

    # Build idx->movie_id map (ALS)
    idx_to_movie_id = {int(v): int(k) for k, v in als_store.movie_id_to_idx.items()}

    rows = db.execute(SQL_TEST).fetchall()

    results = {
        "ALS": {"hit": 0, "ndcg": 0.0, "n": 0},
        "CBF": {"hit": 0, "ndcg": 0.0, "n": 0},
        "Hybrid": {"hit": 0, "ndcg": 0.0, "n": 0},
    }

    for user_id, test_mid, test_ts in rows:
        user_id = int(user_id)
        test_mid = int(test_mid)

        # ----------------------
        # HYBRID (your service)
        # ----------------------
        recs = recommend_service.get_for_user(db=db, user_id=user_id, limit=K, as_of_ts=test_ts)
        hybrid_ids = [r.movie_id for r in recs]
        h, n = hit_ndcg(test_mid, hybrid_ids)
        results["Hybrid"]["hit"] += h
        results["Hybrid"]["ndcg"] += n
        results["Hybrid"]["n"] += 1

        # Seeds (as-of filtered)
        seeds = recommend_service._get_seed_movies_blended(db, user_id, as_of_ts=test_ts)
        if not seeds:
            continue

        user_vec = build_user_vec_from_seeds(seeds)
        if user_vec is None:
            continue

        # Exclusions (as-of filtered history + seeds)
        exclude = set(recommend_service._get_excluded_movie_ids(db, user_id, as_of_ts=test_ts))
        exclude.update(seeds)

        # ----------------------
        # CBF ONLY (HNSW)
        # ----------------------
        hits = vector_index.search(user_vec, k=K + len(exclude) + 200)
        cbf_ids = []
        for mid, _ in hits:
            mid = int(mid)
            if mid in exclude:
                continue
            cbf_ids.append(mid)
            if len(cbf_ids) >= K:
                break

        h, n = hit_ndcg(test_mid, cbf_ids)
        results["CBF"]["hit"] += h
        results["CBF"]["ndcg"] += n
        results["CBF"]["n"] += 1

        # ----------------------
        # ALS ONLY (TRUE ALS: score ALL items)
        # ----------------------
        if als_store.can_score_user(user_id):
            uidx = als_store.user_id_to_idx[user_id]
            uvec = als_store.user_factors[uidx]  # (factors,)

            # Score all items
            scores = als_store.item_factors @ uvec  # (n_items,)

            # Exclude items user already interacted with (as-of) and seed items
            exclude_iidx = [
                als_store.movie_id_to_idx[mid]
                for mid in exclude
                if mid in als_store.movie_id_to_idx
            ]
            if exclude_iidx:
                scores[np.array(exclude_iidx, dtype=np.int32)] = -1e9

            # Top-K selection
            top_iidx = np.argpartition(-scores, K)[:K]
            top_iidx = top_iidx[np.argsort(-scores[top_iidx])]
            als_ids = [idx_to_movie_id[int(i)] for i in top_iidx]

            h, n = hit_ndcg(test_mid, als_ids)
            results["ALS"]["hit"] += h
            results["ALS"]["ndcg"] += n
            results["ALS"]["n"] += 1

    db.close()

    print(f"\nEvaluation results (K={K})\n")
    print("{:<10} {:<12} {:<12} {:<10}".format("Model", f"HitRate@{K}", f"NDCG@{K}", "Users"))
    print("-" * 50)

    for model, r in results.items():
        n = r["n"]
        if n == 0:
            continue
        hitrate = r["hit"] / n
        ndcg = r["ndcg"] / n
        print("{:<10} {:<12.4f} {:<12.4f} {:<10}".format(model, hitrate, ndcg, n))


if __name__ == "__main__":
    evaluate()
