# tests/unit/test_eval_all_models.py
import json
from pathlib import Path
from types import SimpleNamespace

import app.ml.scripts.eval_all_models as eval_module


def test_hit_ndcg_returns_hit_and_score_when_item_present():
    hit, ndcg = eval_module.hit_ndcg(42, [10, 42, 77])

    assert hit == 1
    assert ndcg > 0


def test_hit_ndcg_returns_zero_when_item_missing():
    hit, ndcg = eval_module.hit_ndcg(42, [10, 11, 12])

    assert hit == 0
    assert ndcg == 0.0


def test_finalize_model_stats_returns_none_metrics_when_no_users():
    result = eval_module.finalize_model_stats(
        {
            "hit": 0,
            "ndcg": 0.0,
            "n": 0,
            "eligible": 3,
            "nonempty": 1,
        }
    )

    assert result == {
        "hitrate_at_k": None,
        "ndcg_at_k": None,
        "users": 0,
        "eligible_users": 3,
        "nonempty_recommendations": 1,
        "coverage_rate": 0.0,
    }


def test_finalize_model_stats_returns_expected_values():
    result = eval_module.finalize_model_stats(
        {
            "hit": 2,
            "ndcg": 1.5,
            "n": 4,
            "eligible": 4,
            "nonempty": 3,
        }
    )

    assert result["hitrate_at_k"] == 0.5
    assert result["ndcg_at_k"] == 1.5 / 4
    assert result["users"] == 4
    assert result["eligible_users"] == 4
    assert result["nonempty_recommendations"] == 3
    assert result["coverage_rate"] == 3 / 4


def test_detect_group_returns_warm_when_seeds_exist():
    assert eval_module.detect_group([1, 2], 0) == "warm"


def test_detect_group_returns_cold_when_no_seeds_and_no_interactions():
    assert eval_module.detect_group([], 0) == "cold"


def test_detect_group_returns_sparse_when_no_seeds_but_some_interactions():
    assert eval_module.detect_group([], 3) == "sparse"


def test_score_model_updates_bucket_correctly():
    bucket = eval_module.empty_stats()

    eval_module.score_model(bucket, test_mid=5, ranked_ids=[1, 5, 9])

    assert bucket["eligible"] == 1
    assert bucket["nonempty"] == 1
    assert bucket["n"] == 1
    assert bucket["hit"] == 1
    assert bucket["ndcg"] > 0


def test_evaluate_produces_summary_and_metrics(monkeypatch):
    class FakeExecuteResult:
        def fetchall(self):
            return [
                (1, 101, "2026-04-01T10:00:00Z"),
                (2, 202, "2026-04-01T11:00:00Z"),
            ]

    class FakeDB:
        def execute(self, sql, params=None):
            return FakeExecuteResult()

        def close(self):
            pass

    monkeypatch.setattr(eval_module, "SessionLocal", lambda: FakeDB())

    # recommend_service internals
    monkeypatch.setattr(
        eval_module.recommend_service,
        "_get_seed_movies_blended",
        lambda db, user_id, as_of_ts=None: [301, 302] if user_id == 1 else [],
    )
    monkeypatch.setattr(
        eval_module.recommend_service,
        "_get_excluded_movie_ids",
        lambda db, user_id, as_of_ts=None, max_rows=20000: [],
    )
    monkeypatch.setattr(
        eval_module.recommend_service,
        "_interaction_count",
        lambda db, user_id, as_of_ts=None: 5 if user_id == 1 else 0,
    )
    monkeypatch.setattr(
        eval_module.recommend_service,
        "get_for_user_for_eval",
        lambda db, user_id, limit, as_of_ts=None, force_seed_ids=None, force_exclude_ids=None:
            [101, 999] if user_id == 1 else [202, 888],
    )

    # ALS / CBF / Hybrid
    monkeypatch.setattr(
        eval_module.als_recommender,
        "can_score_user",
        lambda user_id: user_id == 1,
    )
    monkeypatch.setattr(
        eval_module.als_recommender,
        "top_n",
        lambda user_id, exclude_ids, n: [101, 777] if user_id == 1 else [],
    )
    monkeypatch.setattr(
        eval_module.cbf_recommender,
        "build_user_vector",
        lambda seeds: [0.1, 0.2] if seeds else None,
    )
    monkeypatch.setattr(
        eval_module.cbf_recommender,
        "top_n_from_seeds",
        lambda seed_movie_ids, exclude_ids, n, search_k=5000: ([101, 666], None),
    )

    hybrid_debug = SimpleNamespace(strategy="hybrid_light", reason="test", warnings=[])
    monkeypatch.setattr(
        eval_module.hybrid_recommender,
        "recommend_ids",
        lambda user_id, seed_movie_ids, exclude_ids, limit, interaction_count,
               als_candidate_k, cbf_candidate_k, search_k, debug=False:
               ([101, 555] if user_id == 1 else [202, 444], None, None, hybrid_debug),
    )

    result = eval_module.evaluate(k=20)

    assert result["k"] == 20
    assert result["num_test_rows"] == 2

    assert result["group_counts"]["warm"] == 1
    assert result["group_counts"]["cold"] == 1
    assert result["group_counts"]["sparse"] == 0

    assert result["coverage_debug"]["users_with_seeds"] == 1
    assert result["coverage_debug"]["users_without_seeds"] == 1
    assert result["coverage_debug"]["users_with_als"] == 1
    assert result["coverage_debug"]["users_with_cbf"] == 1
    assert result["coverage_debug"]["users_with_both"] == 1

    overall = result["overall_models"]
    assert "Hybrid_Service" in overall
    assert "ALS_FullCatalog" in overall
    assert "CBF_Seeded" in overall
    assert "Hybrid_Model" in overall

    assert overall["Hybrid_Service"]["hitrate_at_k"] is not None
    assert overall["Hybrid_Service"]["ndcg_at_k"] is not None


def test_evaluate_continues_when_one_model_branch_raises(monkeypatch):
    class FakeExecuteResult:
        def fetchall(self):
            return [
                (1, 101, "2026-04-01T10:00:00Z"),
            ]

    class FakeDB:
        def execute(self, sql, params=None):
            return FakeExecuteResult()

        def close(self):
            pass

    monkeypatch.setattr(eval_module, "SessionLocal", lambda: FakeDB())

    monkeypatch.setattr(
        eval_module.recommend_service,
        "_get_seed_movies_blended",
        lambda db, user_id, as_of_ts=None: [301, 302],
    )
    monkeypatch.setattr(
        eval_module.recommend_service,
        "_get_excluded_movie_ids",
        lambda db, user_id, as_of_ts=None, max_rows=20000: [],
    )
    monkeypatch.setattr(
        eval_module.recommend_service,
        "_interaction_count",
        lambda db, user_id, as_of_ts=None: 5,
    )
    monkeypatch.setattr(
        eval_module.recommend_service,
        "get_for_user_for_eval",
        lambda db, user_id, limit, as_of_ts=None, force_seed_ids=None, force_exclude_ids=None: [101],
    )

    monkeypatch.setattr(eval_module.als_recommender, "can_score_user", lambda user_id: True)

    # ALS branch fails, others still work
    def boom_top_n(user_id, exclude_ids, n):
        raise RuntimeError("ALS failure")

    monkeypatch.setattr(eval_module.als_recommender, "top_n", boom_top_n)
    monkeypatch.setattr(eval_module.cbf_recommender, "build_user_vector", lambda seeds: [0.1])
    monkeypatch.setattr(
        eval_module.cbf_recommender,
        "top_n_from_seeds",
        lambda seed_movie_ids, exclude_ids, n, search_k=5000: ([101], None),
    )

    hybrid_debug = SimpleNamespace(strategy="hybrid_light", reason="test", warnings=[])
    monkeypatch.setattr(
        eval_module.hybrid_recommender,
        "recommend_ids",
        lambda user_id, seed_movie_ids, exclude_ids, limit, interaction_count,
               als_candidate_k, cbf_candidate_k, search_k, debug=False:
               ([101], None, None, hybrid_debug),
    )

    result = eval_module.evaluate(k=20)

    # Evaluation should still complete
    assert result["num_test_rows"] == 1
    assert result["overall_models"]["Hybrid_Service"]["users"] == 1
    assert result["overall_models"]["CBF_Seeded"]["users"] == 1
    # ALS branch had no successful scored rows
    assert result["overall_models"]["ALS_FullCatalog"]["users"] == 0


def test_save_metrics_writes_timestamped_and_latest_files(tmp_path, monkeypatch):
    monkeypatch.setattr(eval_module, "METRICS_DIR", str(tmp_path))

    class FakeNow:
        def isoformat(self):
            return "2026-04-19T12:00:00+00:00"

        def strftime(self, fmt):
            return "2026-04-19T12-00-00Z"

    class FakeDatetime:
        @staticmethod
        def now(tz=None):
            return FakeNow()

    monkeypatch.setattr(eval_module, "datetime", FakeDatetime)

    metrics = {
        "evaluated_at_utc": "2026-04-19T12:00:00+00:00",
        "k": 20,
        "num_test_rows": 2,
        "overall_models": {},
        "grouped_models": {},
        "group_counts": {},
        "coverage_debug": {},
        "note": "test",
    }

    saved_path = eval_module.save_metrics(metrics)

    saved_file = Path(saved_path)
    latest_file = tmp_path / "latest.json"

    assert saved_file.exists()
    assert latest_file.exists()

    with saved_file.open("r", encoding="utf-8") as f:
        saved_data = json.load(f)
    with latest_file.open("r", encoding="utf-8") as f:
        latest_data = json.load(f)

    assert saved_data == metrics
    assert latest_data == metrics