## pytest tests/unit/test_build_hnsw_artifacts.py -v   

import json
import numpy as np
import pytest

from app.services.vector_index import VectorIndex

# Adjust this import to your real builder script filename
from app.ml.scripts import build_hnsw_artifacts as build_module


def test_movie_text_combines_fields_correctly():
    text = build_module.movie_text(
        title="Toy Story",
        genres="Animation|Comedy|Family",
        overview="A story about toys that come alive.",
    )

    assert "Toy Story" in text
    assert "Animation Comedy Family" in text
    assert "A story about toys that come alive." in text
    assert "|" not in text


def test_movie_text_omits_empty_parts():
    text = build_module.movie_text(
        title="Inception",
        genres=None,
        overview="",
    )

    assert text == "Inception"


def test_ensure_dirs_creates_vector_and_hnsw_dirs(tmp_path, monkeypatch):
    vec_dir = tmp_path / "vectors"
    hnsw_dir = tmp_path / "hnsw"

    monkeypatch.setattr(build_module, "VEC_DIR", str(vec_dir))
    monkeypatch.setattr(build_module, "HNSW_DIR", str(hnsw_dir))

    build_module.ensure_dirs()

    assert vec_dir.exists()
    assert hnsw_dir.exists()
    assert vec_dir.is_dir()
    assert hnsw_dir.is_dir()


def test_build_hnsw_artifacts_creates_expected_files_and_metadata(tmp_path, monkeypatch):
    vec_dir = tmp_path / "vectors"
    hnsw_dir = tmp_path / "hnsw"

    monkeypatch.setattr(build_module, "VEC_DIR", str(vec_dir))
    monkeypatch.setattr(build_module, "HNSW_DIR", str(hnsw_dir))

    # Need enough docs and enough distinct terms for min_df=2 and SVD
    fake_movie_ids = np.array([1, 2, 3], dtype=np.int32)
    fake_texts = [
        "toy story animation family friendship adventure",
        "toy world animation family friendship journey",
        "space mission sci fi adventure family",
    ]

    monkeypatch.setattr(build_module, "load_movies", lambda: (fake_movie_ids, fake_texts))

    result = build_module.build_hnsw_artifacts()

    assert result["count"] == 3
    assert result["dim"] > 0

    assert (vec_dir / "movie_ids.npy").exists()
    assert (vec_dir / "vectors.npy").exists()
    assert (vec_dir / "tfidf.joblib").exists()
    assert (vec_dir / "svd.joblib").exists()
    assert (hnsw_dir / "movies_hnsw.bin").exists()
    assert (hnsw_dir / "meta.json").exists()

    movie_ids = np.load(vec_dir / "movie_ids.npy")
    vectors = np.load(vec_dir / "vectors.npy")

    assert movie_ids.shape == (3,)
    assert vectors.shape[0] == 3
    assert vectors.shape[1] > 0

    norms = np.linalg.norm(vectors, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)

    meta = json.loads((hnsw_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["count"] == 3
    assert meta["dim"] == vectors.shape[1]
    assert meta["vector_shape"] == [3, vectors.shape[1]]
    assert meta["tfidf_shape"][0] == 3
    assert meta["space"] == "cosine"
    assert meta["index_type"] == "hnswlib"
    assert meta["text_fields"] == ["title", "genres", "overview"]


def test_build_hnsw_artifacts_raises_when_no_movies(tmp_path, monkeypatch):
    vec_dir = tmp_path / "vectors"
    hnsw_dir = tmp_path / "hnsw"

    monkeypatch.setattr(build_module, "VEC_DIR", str(vec_dir))
    monkeypatch.setattr(build_module, "HNSW_DIR", str(hnsw_dir))
    monkeypatch.setattr(build_module, "load_movies", lambda: (np.array([], dtype=np.int32), []))

    with pytest.raises(RuntimeError, match="No movies found"):
        build_module.build_hnsw_artifacts()


def test_vector_index_validate_dirs_accepts_valid_artifacts(tmp_path, monkeypatch):
    vec_dir = tmp_path / "vectors"
    hnsw_dir = tmp_path / "hnsw"

    monkeypatch.setattr(build_module, "VEC_DIR", str(vec_dir))
    monkeypatch.setattr(build_module, "HNSW_DIR", str(hnsw_dir))

    fake_movie_ids = np.array([10, 20, 30], dtype=np.int32)
    fake_texts = [
        "action hero mission city rescue",
        "action detective mystery city case",
        "romance drama love relationship city",
    ]
    monkeypatch.setattr(build_module, "load_movies", lambda: (fake_movie_ids, fake_texts))

    build_module.build_hnsw_artifacts()

    vi = VectorIndex()
    summary = vi.validate_dirs(vec_dir=str(vec_dir), hnsw_dir=str(hnsw_dir))

    assert summary["ok"] is True
    assert summary["movie_count"] == 3
    assert summary["vector_dim"] > 0
    assert summary["index_count"] == 3


def test_vector_index_load_and_get_vector_work_with_generated_artifacts(tmp_path, monkeypatch):
    vec_dir = tmp_path / "vectors"
    hnsw_dir = tmp_path / "hnsw"

    monkeypatch.setattr(build_module, "VEC_DIR", str(vec_dir))
    monkeypatch.setattr(build_module, "HNSW_DIR", str(hnsw_dir))

    fake_movie_ids = np.array([101, 102, 103], dtype=np.int32)
    fake_texts = [
        "space sci fi aliens future galaxy",
        "space sci fi mission stars galaxy",
        "romantic comedy love wedding relationship",
    ]
    monkeypatch.setattr(build_module, "load_movies", lambda: (fake_movie_ids, fake_texts))

    build_module.build_hnsw_artifacts()

    vi = VectorIndex().load(vec_dir=str(vec_dir), hnsw_dir=str(hnsw_dir))

    v = vi.get_vector(101)
    assert v is not None
    assert v.ndim == 1
    assert len(v) == vi.dim

    missing = vi.get_vector(999999)
    assert missing is None


def test_vector_index_search_returns_results_for_valid_query(tmp_path, monkeypatch):
    vec_dir = tmp_path / "vectors"
    hnsw_dir = tmp_path / "hnsw"

    monkeypatch.setattr(build_module, "VEC_DIR", str(vec_dir))
    monkeypatch.setattr(build_module, "HNSW_DIR", str(hnsw_dir))

    fake_movie_ids = np.array([201, 202, 203], dtype=np.int32)
    fake_texts = [
        "batman dark knight gotham hero action",
        "superman hero metropolis action flying",
        "love romance drama heartbreak relationship",
    ]
    monkeypatch.setattr(build_module, "load_movies", lambda: (fake_movie_ids, fake_texts))

    build_module.build_hnsw_artifacts()

    vi = VectorIndex().load(vec_dir=str(vec_dir), hnsw_dir=str(hnsw_dir))
    query_vec = vi.get_vector(201)

    results = vi.search(query_vec, k=2)

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(isinstance(mid, int) for mid, _ in results)
    assert all(isinstance(score, float) for _, score in results)
    assert results[0][0] == 201


def test_vector_index_rejects_mismatched_movie_ids_and_vectors(tmp_path):
    vec_dir = tmp_path / "vectors"
    hnsw_dir = tmp_path / "hnsw"
    vec_dir.mkdir()
    hnsw_dir.mkdir()

    np.save(vec_dir / "movie_ids.npy", np.array([1, 2, 3], dtype=np.int32))
    np.save(vec_dir / "vectors.npy", np.random.rand(2, 4).astype(np.float32))
    (hnsw_dir / "movies_hnsw.bin").write_bytes(b"dummy")

    vi = VectorIndex()

    with pytest.raises(ValueError, match="row count mismatch"):
        vi._load_from_dirs(str(vec_dir), str(hnsw_dir))


def test_vector_index_rejects_duplicate_movie_ids(tmp_path):
    vec_dir = tmp_path / "vectors"
    hnsw_dir = tmp_path / "hnsw"
    vec_dir.mkdir()
    hnsw_dir.mkdir()

    np.save(vec_dir / "movie_ids.npy", np.array([1, 1, 2], dtype=np.int32))
    np.save(vec_dir / "vectors.npy", np.random.rand(3, 4).astype(np.float32))
    (hnsw_dir / "movies_hnsw.bin").write_bytes(b"dummy")

    vi = VectorIndex()

    with pytest.raises(ValueError, match="duplicate movie IDs"):
        vi._load_from_dirs(str(vec_dir), str(hnsw_dir))


def test_vector_index_search_rejects_non_1d_query():
    vi = VectorIndex()
    vi.index = object()
    vi.vectors = np.array([[1.0, 0.0]], dtype=np.float32)
    vi.movie_ids = np.array([1], dtype=np.int32)

    with pytest.raises(ValueError, match="must be 1D"):
        vi.search(np.array([[1.0, 0.0]], dtype=np.float32), k=1)