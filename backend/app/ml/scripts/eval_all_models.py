# backend/app/ml/scripts/eval_all_models.py
# Run:
#   python -m app.ml.scripts.eval_all_models

import os
import json
from math import log2
from datetime import datetime, timezone

from sqlalchemy import text

from app.db.database import SessionLocal
from app.services.recommend_service import recommend_service
from app.ml.recommenders.als_recommender import als_recommender
from app.ml.recommenders.cbf_recommender import cbf_recommender
from app.ml.recommenders.hybrid_recommender import hybrid_recommender

DEFAULT_K = 20

METRICS_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "artifacts",
        "metrics",
    )
)

SQL_TEST = text("""
SELECT DISTINCT ON (user_id)
  user_id, movie_id, ts
FROM interactions_all
WHERE event_type = 'like'
   OR (event_type = 'rate' AND rating_value >= 4)
ORDER BY user_id, ts DESC;
""")


def ensure_metrics_dir() -> None:
    os.makedirs(METRICS_DIR, exist_ok=True)


def hit_ndcg(test_mid: int, ranked_ids: list[int]) -> tuple[int, float]:
    if test_mid not in ranked_ids:
        return 0, 0.0
    rank = ranked_ids.index(test_mid) + 1
    return 1, 1.0 / log2(rank + 1)


def empty_stats() -> dict:
    return {
        "hit": 0,
        "ndcg": 0.0,
        "n": 0,
        "eligible": 0,
        "nonempty": 0,
    }


def score_model(bucket: dict, test_mid: int, ranked_ids: list[int]) -> None:
    bucket["eligible"] += 1

    if ranked_ids:
        bucket["nonempty"] += 1

    bucket["n"] += 1
    h, n = hit_ndcg(test_mid, ranked_ids)
    bucket["hit"] += h
    bucket["ndcg"] += n


def empty_group_results() -> dict:
    return {
        "ALS_FullCatalog": empty_stats(),
        "CBF_Seeded": empty_stats(),
        "Hybrid_Model": empty_stats(),
        "Hybrid_Service": empty_stats(),
    }


def finalize_model_stats(r: dict) -> dict:
    n = r["n"]
    if n == 0:
        return {
            "hitrate_at_k": None,
            "ndcg_at_k": None,
            "users": 0,
            "eligible_users": r["eligible"],
            "nonempty_recommendations": r["nonempty"],
            "coverage_rate": 0.0,
        }

    hitrate = r["hit"] / n
    ndcg = r["ndcg"] / n
    coverage_rate = (r["nonempty"] / r["eligible"]) if r["eligible"] > 0 else 0.0

    return {
        "hitrate_at_k": hitrate,
        "ndcg_at_k": ndcg,
        "users": n,
        "eligible_users": r["eligible"],
        "nonempty_recommendations": r["nonempty"],
        "coverage_rate": coverage_rate,
    }


def detect_group(seeds: list[int], interaction_count: int) -> str:
    if len(seeds) > 0:
        return "warm"
    if interaction_count == 0:
        return "cold"
    return "sparse"


def evaluate(k: int = DEFAULT_K) -> dict:
    db = SessionLocal()

    try:
        rows = db.execute(SQL_TEST).fetchall()

        overall_results = empty_group_results()
        grouped_results = {
            "warm": empty_group_results(),
            "sparse": empty_group_results(),
            "cold": empty_group_results(),
        }

        group_counts = {
            "warm": 0,
            "sparse": 0,
            "cold": 0,
        }

        coverage_debug = {
            "total_test_rows": len(rows),
            "users_with_seeds": 0,
            "users_without_seeds": 0,
            "users_with_als": 0,
            "users_with_cbf": 0,
            "users_with_both": 0,
            "users_with_neither": 0,
        }

        for row_idx, (user_id, test_mid, test_ts) in enumerate(rows):
            user_id = int(user_id)
            test_mid = int(test_mid)
            debug_mode = row_idx < 5

            seeds = recommend_service._get_seed_movies_blended(
                db=db,
                user_id=user_id,
                as_of_ts=test_ts,
            )
            seeds = [mid for mid in seeds if mid != test_mid]

            exclude = set(
                recommend_service._get_excluded_movie_ids(
                    db=db,
                    user_id=user_id,
                    as_of_ts=test_ts,
                    max_rows=recommend_service.config.exclude_max_rows,
                )
            )
            exclude.update(seeds)

            # make sure the held-out target is not excluded
            exclude.discard(test_mid)

            interaction_count = recommend_service._interaction_count(
                db=db,
                user_id=user_id,
                as_of_ts=test_ts,
            )

            has_als = als_recommender.can_score_user(user_id)
            user_vec = cbf_recommender.build_user_vector(seeds) if seeds else None
            has_cbf = user_vec is not None

            group = detect_group(seeds=seeds, interaction_count=interaction_count)
            group_counts[group] += 1

            if seeds:
                coverage_debug["users_with_seeds"] += 1
            else:
                coverage_debug["users_without_seeds"] += 1

            if has_als:
                coverage_debug["users_with_als"] += 1
            if has_cbf:
                coverage_debug["users_with_cbf"] += 1
            if has_als and has_cbf:
                coverage_debug["users_with_both"] += 1
            if not has_als and not has_cbf:
                coverage_debug["users_with_neither"] += 1

            if debug_mode:
                print("\n==============================")
                print("ROW:", row_idx)
                print("group:", group)
                print("user_id:", user_id)
                print("test_mid:", test_mid)
                print("test_ts:", test_ts)
                print("interaction_count:", interaction_count)
                print("seed_count:", len(seeds))
                print("seeds[:10]:", seeds[:10])
                print("exclude_count:", len(exclude))
                print("test_mid in exclude:", test_mid in exclude)
                print("has_als:", has_als)
                print("has_cbf:", has_cbf)

            # -----------------------------
            # Hybrid Service (production path)
            # -----------------------------
            hybrid_service_ids = []
            try:
                hybrid_service_ids = recommend_service.get_for_user_for_eval(
                    db=db,
                    user_id=user_id,
                    limit=k,
                    as_of_ts=test_ts,
                    force_seed_ids=seeds,
                    force_exclude_ids=exclude,
                )
            except Exception as e:
                if debug_mode:
                    print("\n--- HYBRID SERVICE ERROR ---")
                    print("error:", repr(e))

            score_model(overall_results["Hybrid_Service"], test_mid, hybrid_service_ids)
            score_model(grouped_results[group]["Hybrid_Service"], test_mid, hybrid_service_ids)

            if debug_mode:
                print("\n--- HYBRID SERVICE DEBUG ---")
                print("hybrid_service_ids[:20]:", hybrid_service_ids[:20])
                print("test_mid in hybrid_service_ids:", test_mid in hybrid_service_ids)

            # -----------------------------
            # ALS full-catalog
            # -----------------------------
            als_ids = []
            if has_als:
                try:
                    als_ids = als_recommender.top_n(
                        user_id=user_id,
                        exclude_ids=exclude,
                        n=k,
                    )
                except Exception as e:
                    if debug_mode:
                        print("\n--- ALS ERROR ---")
                        print("error:", repr(e))

                score_model(overall_results["ALS_FullCatalog"], test_mid, als_ids)
                score_model(grouped_results[group]["ALS_FullCatalog"], test_mid, als_ids)

            if debug_mode:
                print("\n--- ALS DEBUG ---")
                print("als_ids[:20]:", als_ids[:20])
                print("test_mid in als_ids:", test_mid in als_ids)

            # -----------------------------
            # CBF seeded
            # -----------------------------
            cbf_ids = []
            if has_cbf:
                try:
                    cbf_ids, _ = cbf_recommender.top_n_from_seeds(
                        seed_movie_ids=seeds,
                        exclude_ids=exclude,
                        n=k,
                        search_k=5000,
                    )
                except Exception as e:
                    if debug_mode:
                        print("\n--- CBF ERROR ---")
                        print("error:", repr(e))

                score_model(overall_results["CBF_Seeded"], test_mid, cbf_ids)
                score_model(grouped_results[group]["CBF_Seeded"], test_mid, cbf_ids)

            if debug_mode:
                print("\n--- CBF DEBUG ---")
                print("cbf_ids[:20]:", cbf_ids[:20])
                print("test_mid in cbf_ids:", test_mid in cbf_ids)

            # -----------------------------
            # Hybrid Model (direct model path)
            # -----------------------------
            hybrid_model_ids = []
            hybrid_debug = None

            if has_als or has_cbf:
                try:
                    hybrid_model_ids, _, _, hybrid_debug = hybrid_recommender.recommend_ids(
                        user_id=user_id,
                        seed_movie_ids=seeds,
                        exclude_ids=exclude,
                        limit=k,
                        interaction_count=interaction_count,
                        als_candidate_k=recommend_service.config.max_candidate_k,
                        cbf_candidate_k=recommend_service.config.max_candidate_k,
                        search_k=recommend_service.config.max_candidate_k,
                        debug=False,
                    )
                except Exception as e:
                    if debug_mode:
                        print("\n--- HYBRID MODEL ERROR ---")
                        print("error:", repr(e))

                score_model(overall_results["Hybrid_Model"], test_mid, hybrid_model_ids)
                score_model(grouped_results[group]["Hybrid_Model"], test_mid, hybrid_model_ids)

            if debug_mode:
                print("\n--- HYBRID MODEL DEBUG ---")
                print("hybrid_model_ids[:20]:", hybrid_model_ids[:20])
                print("test_mid in hybrid_model_ids:", test_mid in hybrid_model_ids)
                if hybrid_debug is not None:
                    print("hybrid_model_strategy:", hybrid_debug.strategy)
                    print("hybrid_model_reason:", hybrid_debug.reason)
                    print("hybrid_model_warnings:", hybrid_debug.warnings)

                if als_ids and (test_mid in als_ids) and (test_mid not in hybrid_model_ids):
                    print("[WARNING] Hybrid_Model lost a good ALS hit")

            # Optional useful warning for service too
            if debug_mode and als_ids and (test_mid in als_ids) and (test_mid not in hybrid_service_ids):
                print("[WARNING] Hybrid_Service lost a good ALS hit")

        summary = {
            "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
            "k": k,
            "num_test_rows": len(rows),
            "note": (
                "This evaluation is useful for debugging and comparison, but ALS artifacts "
                "may still contain temporal leakage if they were trained on the full interaction set."
            ),
            "group_counts": group_counts,
            "coverage_debug": coverage_debug,
            "overall_models": {},
            "grouped_models": {},
        }

        print(f"\nOverall evaluation results (K={k})\n")
        print("{:<18} {:<12} {:<12} {:<10} {:<10} {:<10}".format(
            "Model", f"HitRate@{k}", f"NDCG@{k}", "Users", "Eligible", "NonEmpty"
        ))
        print("-" * 80)

        for model, r in overall_results.items():
            stats = finalize_model_stats(r)
            summary["overall_models"][model] = stats

            if stats["users"] > 0:
                print("{:<18} {:<12.4f} {:<12.4f} {:<10} {:<10} {:<10}".format(
                    model,
                    stats["hitrate_at_k"],
                    stats["ndcg_at_k"],
                    stats["users"],
                    stats["eligible_users"],
                    stats["nonempty_recommendations"],
                ))
            else:
                print("{:<18} {:<12} {:<12} {:<10} {:<10} {:<10}".format(
                    model, "None", "None", 0, stats["eligible_users"], stats["nonempty_recommendations"]
                ))

        summary["grouped_models"] = {}

        for group_name in ["warm", "sparse", "cold"]:
            print(f"\nGroup: {group_name.upper()} (users={group_counts[group_name]})")
            print("{:<18} {:<12} {:<12} {:<10} {:<10} {:<10}".format(
                "Model", f"HitRate@{k}", f"NDCG@{k}", "Users", "Eligible", "NonEmpty"
            ))
            print("-" * 80)

            summary["grouped_models"][group_name] = {}

            for model, r in grouped_results[group_name].items():
                stats = finalize_model_stats(r)
                summary["grouped_models"][group_name][model] = stats

                if stats["users"] > 0:
                    print("{:<18} {:<12.4f} {:<12.4f} {:<10} {:<10} {:<10}".format(
                        model,
                        stats["hitrate_at_k"],
                        stats["ndcg_at_k"],
                        stats["users"],
                        stats["eligible_users"],
                        stats["nonempty_recommendations"],
                    ))
                else:
                    print("{:<18} {:<12} {:<12} {:<10} {:<10} {:<10}".format(
                        model, "None", "None", 0, stats["eligible_users"], stats["nonempty_recommendations"]
                    ))

        print("\nGroup counts:")
        for key, value in group_counts.items():
            print(f"- {key}: {value}")

        print("\nCoverage debug:")
        for key, value in coverage_debug.items():
            print(f"- {key}: {value}")

        return summary

    finally:
        db.close()


def save_metrics(metrics: dict) -> str:
    ensure_metrics_dir()

    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_path = os.path.join(METRICS_DIR, f"eval_{run_id}.json")
    latest_path = os.path.join(METRICS_DIR, "latest.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    return out_path


if __name__ == "__main__":
    metrics = evaluate(k=DEFAULT_K)
    saved_to = save_metrics(metrics)

    print("\nJSON summary:")
    print(json.dumps(metrics, indent=2))
    print(f"\n✅ Metrics saved to: {saved_to}")