import json
import numpy as np
import pytest

from app.services.als_store import ALSStore
from app.services.vector_index import VectorIndex
from app.services import startup as startup_module
from app.ml.scripts import build_hnsw_artifacts as build_vec_module
from app.ml.scripts import train_als as als_train_module


def test_als_store_load_sets_runtime_state_from_valid_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(als_train_module, "ART_DIR", str(tmp_path))

    fake_events = [
        (1, 101, "like", None),
        (1, 102, "rate", 5),
        (2, 101, "view", None),
        (2, 103, "like", None),
    ]
    fake_onboarding = [(2, 102)]

    monkeypatch.setattr(
        als_train_module,
        "load_events_and_onboarding",
        lambda: (fake_events, fake_onboarding),
    )

    als_train_module.train_als()

    store = ALSStore().load(als_dir=str(tmp_path))

    assert store.is_loaded() is True
    assert store.user_factors is not None
    assert store.item_factors is not None
    assert store.user_id_to_idx is not None
    assert store.movie_id_to_idx is not None
    assert store.user_factors.ndim == 2
    assert store.item_factors.ndim == 2


def test_als_store_can_score_user_and_score_candidates_after_load(tmp_path, monkeypatch):
    monkeypatch.setattr(als_train_module, "ART_DIR", str(tmp_path))

    fake_events = [
        (1, 101, "like", None),
        (1, 102, "rate", 4),
        (2, 101, "view", None),
        (2, 103, "like", None),
    ]
    fake_onboarding = []

    monkeypatch.setattr(
        als_train_module,
        "load_events_and_onboarding",
        lambda: (fake_events, fake_onboarding),
    )

    als_train_module.train_als()

    store = ALSStore().load(als_dir=str(tmp_path))

    assert store.can_score_user(1) is True
    assert store.can_score_user(999999) is False

    scores = store.score_candidates(1, [101, 102, 999999])
    assert isinstance(scores, list)
    assert len(scores) >= 1
    assert all(isinstance(mid, int) for mid, _ in scores)
    assert all(isinstance(score, float) for _, score in scores)


def test_vector_index_load_sets_runtime_state_from_valid_artifacts(tmp_path, monkeypatch):
    vec_dir = tmp_path / "vectors"
    hnsw_dir = tmp_path / "hnsw"

    monkeypatch.setattr(build_vec_module, "VEC_DIR", str(vec_dir))
    monkeypatch.setattr(build_vec_module, "HNSW_DIR", str(hnsw_dir))

    fake_movie_ids = np.array([1, 2, 3], dtype=np.int32)
    fake_texts = [
        "toy story animation family friendship adventure",
        "toy world animation family friendship journey",
        "space mission sci fi adventure family",
    ]

    monkeypatch.setattr(build_vec_module, "load_movies", lambda: (fake_movie_ids, fake_texts))
    build_vec_module.build_hnsw_artifacts()

    vi = VectorIndex().load(vec_dir=str(vec_dir), hnsw_dir=str(hnsw_dir))

    assert vi.is_loaded() is True
    assert vi.movie_ids is not None
    assert vi.vectors is not None
    assert vi.index is not None
    assert vi.dim > 0
    assert vi.vectors.ndim == 2


def test_vector_index_get_vector_and_search_work_after_load(tmp_path, monkeypatch):
    vec_dir = tmp_path / "vectors"
    hnsw_dir = tmp_path / "hnsw"

    monkeypatch.setattr(build_vec_module, "VEC_DIR", str(vec_dir))
    monkeypatch.setattr(build_vec_module, "HNSW_DIR", str(hnsw_dir))

    fake_movie_ids = np.array([11, 12, 13], dtype=np.int32)
    fake_texts = [
        "batman hero action city vigilante dark hero action city",
        "superman hero action city flying strong hero action city",
        "romance drama love city heartbreak drama love city",
    ]

    monkeypatch.setattr(build_vec_module, "load_movies", lambda: (fake_movie_ids, fake_texts))
    build_vec_module.build_hnsw_artifacts()

    vi = VectorIndex().load(vec_dir=str(vec_dir), hnsw_dir=str(hnsw_dir))

    query_vec = vi.get_vector(11)
    assert query_vec is not None
    assert query_vec.ndim == 1

    results = vi.search(query_vec, k=2)
    assert len(results) == 2
    assert results[0][0] == 11
    assert all(isinstance(mid, int) for mid, _ in results)
    assert all(isinstance(score, float) for _, score in results)
def test_run_startup_loads_local_artifacts_when_r2_disabled(monkeypatch):
    calls = []

    class FakeSettings:
        use_r2_artifacts = False

    monkeypatch.setattr(startup_module, "settings", FakeSettings())
    monkeypatch.setattr(startup_module.als_store, "load", lambda: calls.append("als_load"))
    monkeypatch.setattr(startup_module.vector_index, "load", lambda: calls.append("vector_load"))
    monkeypatch.setattr(startup_module, "_start_background_refresh_thread", lambda: calls.append("start_bg"))

    startup_module.run_startup()

    assert calls == ["als_load", "vector_load", "start_bg"]


def test_run_startup_restores_then_loads_when_r2_enabled_and_noop(monkeypatch):
    calls = []

    class FakeSettings:
        use_r2_artifacts = True

    monkeypatch.setattr(startup_module, "settings", FakeSettings())
    monkeypatch.setattr(
        startup_module,
        "ensure_production_run_restored",
        lambda force=False: {"status": "noop", "run_id": "run-prod-1"},
    )
    monkeypatch.setattr(startup_module.als_store, "load", lambda: calls.append("als_load"))
    monkeypatch.setattr(startup_module.vector_index, "load", lambda: calls.append("vector_load"))
    monkeypatch.setattr(startup_module, "_start_background_refresh_thread", lambda: calls.append("start_bg"))

    startup_module.run_startup()

    assert calls == ["als_load", "vector_load", "start_bg"]