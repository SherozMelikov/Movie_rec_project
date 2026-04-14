from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import app.services.r2_restore_service as svc


def _write_dummy_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".json":
        path.write_text("{}", encoding="utf-8")
    else:
        path.write_bytes(b"dummy")


def _create_cached_run(run_root: Path, run_id: str, required_files: list[str] | None = None) -> Path:
    run_dir = run_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    files = required_files or svc.REQUIRED_RUNTIME_FILES
    for rel_path in files:
        _write_dummy_file(run_dir / rel_path)

    return run_dir


@pytest.fixture
def isolated_paths(tmp_path, monkeypatch):
    artifacts_root = tmp_path / "artifacts"

    cache_root = artifacts_root / "r2_cache"
    staging_root = artifacts_root / "restore_staging"
    backup_root = artifacts_root / "restore_backup"

    live_als = artifacts_root / "als"
    live_vectors = artifacts_root / "vectors"
    live_hnsw = artifacts_root / "hnsw"

    latest_restore_log = artifacts_root / "latest_r2_restore.json"
    local_active_run = artifacts_root / "active_production_run.json"

    monkeypatch.setattr(svc, "CACHE_ROOT", str(cache_root))
    monkeypatch.setattr(svc, "STAGING_ROOT", str(staging_root))
    monkeypatch.setattr(svc, "BACKUP_ROOT", str(backup_root))
    monkeypatch.setattr(svc, "LIVE_ALS_DIR", str(live_als))
    monkeypatch.setattr(svc, "LIVE_VECTORS_DIR", str(live_vectors))
    monkeypatch.setattr(svc, "LIVE_HNSW_DIR", str(live_hnsw))
    monkeypatch.setattr(svc, "LOCAL_R2_RESTORE_LOG_PATH", str(latest_restore_log))
    monkeypatch.setattr(svc, "LOCAL_ACTIVE_RUN_PATH", str(local_active_run))

    return {
        "artifacts_root": artifacts_root,
        "cache_root": cache_root,
        "staging_root": staging_root,
        "backup_root": backup_root,
        "live_als": live_als,
        "live_vectors": live_vectors,
        "live_hnsw": live_hnsw,
        "latest_restore_log": latest_restore_log,
        "local_active_run": local_active_run,
    }


def test_validate_cached_run_dir_reports_missing_files(isolated_paths):
    run_dir = isolated_paths["cache_root"] / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Create only one required file, leave the rest missing
    _write_dummy_file(run_dir / svc.REQUIRED_RUNTIME_FILES[0])

    result = svc.validate_cached_run_dir(str(run_dir))

    assert result["valid"] is False
    assert len(result["missing_files"]) == len(svc.REQUIRED_RUNTIME_FILES) - 1
    assert svc.REQUIRED_RUNTIME_FILES[0] not in result["missing_files"]


def test_validate_cached_run_for_restore_returns_runtime_validation_failed(isolated_paths, monkeypatch):
    _create_cached_run(isolated_paths["cache_root"], "run-1")

    def fake_validate_dir(_path: str):
        raise ValueError("bad als dir")

    monkeypatch.setattr(svc.als_store, "validate_dir", fake_validate_dir)

    result = svc.validate_cached_run_for_restore("run-1")

    assert result["ok"] is False
    assert result["run_id"] == "run-1"
    assert result["reason"] == "runtime_validation_failed"
    assert result["error_type"] == "ValueError"
    assert "bad als dir" in result["error_message"]


def test_prepare_staging_from_cache_copies_and_validates(isolated_paths, monkeypatch):
    _create_cached_run(isolated_paths["cache_root"], "run-1")

    calls = {"als": [], "vectors": []}

    def fake_als_validate(path: str):
        calls["als"].append(path)
        return {"ok": True}

    def fake_vector_validate(vectors_dir: str, hnsw_dir: str):
        calls["vectors"].append((vectors_dir, hnsw_dir))
        return {"ok": True}

    monkeypatch.setattr(svc.als_store, "validate_dir", fake_als_validate)
    monkeypatch.setattr(svc.vector_index, "validate_dirs", fake_vector_validate)

    result = svc.prepare_staging_from_cache("run-1")

    stage_root = Path(result["stage_root"])

    assert (stage_root / "als" / "user_factors.npy").exists()
    assert (stage_root / "vectors" / "vectors.npy").exists()
    assert (stage_root / "hnsw" / "movies_hnsw.bin").exists()

    assert len(calls["als"]) == 1
    assert len(calls["vectors"]) == 1


def test_restore_run_from_cache_success_swaps_live_dirs_and_writes_logs(isolated_paths, monkeypatch):
    _create_cached_run(isolated_paths["cache_root"], "run-1")

    # Existing live runtime state that should be backed up
    (isolated_paths["live_als"]).mkdir(parents=True, exist_ok=True)
    (isolated_paths["live_vectors"]).mkdir(parents=True, exist_ok=True)
    (isolated_paths["live_hnsw"]).mkdir(parents=True, exist_ok=True)

    (isolated_paths["live_als"] / "old_als.txt").write_text("old", encoding="utf-8")
    (isolated_paths["live_vectors"] / "old_vectors.txt").write_text("old", encoding="utf-8")
    (isolated_paths["live_hnsw"] / "old_hnsw.txt").write_text("old", encoding="utf-8")

    monkeypatch.setattr(svc.als_store, "validate_dir", lambda _path: {"ok": True})
    monkeypatch.setattr(svc.vector_index, "validate_dirs", lambda _v, _h: {"ok": True})

    load_calls = {"als": [], "vectors": []}

    monkeypatch.setattr(svc.als_store, "load", lambda path: load_calls["als"].append(path))
    monkeypatch.setattr(
        svc.vector_index,
        "load",
        lambda vectors_dir, hnsw_dir: load_calls["vectors"].append((vectors_dir, hnsw_dir)),
    )

    fixed_now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(svc, "utc_now", lambda: fixed_now)

    result = svc.restore_run_from_cache("run-1")

    assert result["status"] == "success"
    assert result["run_id"] == "run-1"
    assert result["rollback_performed"] is False

    # New live files are now active
    assert (isolated_paths["live_als"] / "user_factors.npy").exists()
    assert (isolated_paths["live_vectors"] / "vectors.npy").exists()
    assert (isolated_paths["live_hnsw"] / "movies_hnsw.bin").exists()

    # Loaders called on live dirs
    assert load_calls["als"] == [str(isolated_paths["live_als"])]
    assert load_calls["vectors"] == [(str(isolated_paths["live_vectors"]), str(isolated_paths["live_hnsw"]))]

    # Backup preserved old live state
    backup_root = Path(result["backup_root"])
    assert (backup_root / "als" / "old_als.txt").exists()
    assert (backup_root / "vectors" / "old_vectors.txt").exists()
    assert (backup_root / "hnsw" / "old_hnsw.txt").exists()

    # Logs written
    assert isolated_paths["latest_restore_log"].exists()
    restore_log = json.loads(isolated_paths["latest_restore_log"].read_text(encoding="utf-8"))
    assert restore_log["restored_run_id"] == "run-1"

    assert isolated_paths["local_active_run"].exists()
    active_run = json.loads(isolated_paths["local_active_run"].read_text(encoding="utf-8"))
    assert active_run["run_id"] == "run-1"

    # Stage cleaned up
    assert not (isolated_paths["staging_root"] / "run-1").exists()


def test_restore_run_from_cache_rolls_back_if_live_activation_fails(isolated_paths, monkeypatch):
    _create_cached_run(isolated_paths["cache_root"], "run-1")

    # Existing live runtime state
    (isolated_paths["live_als"]).mkdir(parents=True, exist_ok=True)
    (isolated_paths["live_vectors"]).mkdir(parents=True, exist_ok=True)
    (isolated_paths["live_hnsw"]).mkdir(parents=True, exist_ok=True)

    (isolated_paths["live_als"] / "old_als.txt").write_text("old", encoding="utf-8")
    (isolated_paths["live_vectors"] / "old_vectors.txt").write_text("old", encoding="utf-8")
    (isolated_paths["live_hnsw"] / "old_hnsw.txt").write_text("old", encoding="utf-8")

    monkeypatch.setattr(svc.als_store, "validate_dir", lambda _path: {"ok": True})
    monkeypatch.setattr(svc.vector_index, "validate_dirs", lambda _v, _h: {"ok": True})

    monkeypatch.setattr(svc.als_store, "load", lambda _path: None)

    vector_load_calls = {"count": 0}

    def flaky_vector_load(_vectors_dir: str, _hnsw_dir: str):
        vector_load_calls["count"] += 1
        if vector_load_calls["count"] == 1:
            raise RuntimeError("simulated live activation failure")

    monkeypatch.setattr(svc.vector_index, "load", flaky_vector_load)

    with pytest.raises(RuntimeError, match="rollback performed=True"):
        svc.restore_run_from_cache("run-1")

    # Old live state restored
    assert (isolated_paths["live_als"] / "old_als.txt").exists()
    assert (isolated_paths["live_vectors"] / "old_vectors.txt").exists()
    assert (isolated_paths["live_hnsw"] / "old_hnsw.txt").exists()

    # Staging cleaned up even after failure
    assert not (isolated_paths["staging_root"] / "run-1").exists()


def test_download_run_into_cache_uses_manifest_and_downloads_files(isolated_paths, monkeypatch):
    manifest = {
        "files": [
            {
                "relative_path": "als/user_factors.npy",
                "key": "hybrid-recommender/runs/run-1/als/user_factors.npy",
            },
            {
                "relative_path": "vectors/vectors.npy",
                "key": "hybrid-recommender/runs/run-1/vectors/vectors.npy",
            },
        ]
    }

    def fake_download_json(key: str):
        assert key == "hybrid-recommender/runs/run-1/r2_publish_manifest.json"
        return manifest

    def fake_download_file(key: str, local_path: str):
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_bytes(key.encode("utf-8"))

    monkeypatch.setattr(svc, "download_json", fake_download_json)
    monkeypatch.setattr(svc, "download_file", fake_download_file)

    result = svc.download_run_into_cache("run-1")

    assert result["run_id"] == "run-1"
    assert result["file_count"] == 2
    assert Path(result["local_run_dir"]).exists()
    assert (Path(result["local_run_dir"]) / "r2_publish_manifest.json").exists()
    assert (Path(result["local_run_dir"]) / "als" / "user_factors.npy").exists()
    assert (Path(result["local_run_dir"]) / "vectors" / "vectors.npy").exists()


def test_ensure_production_run_restored_returns_noop_when_local_matches(monkeypatch):
    monkeypatch.setattr(svc, "get_production_pointer", lambda: {"run_id": "run-1"})
    monkeypatch.setattr(svc, "get_local_active_run_id", lambda: "run-1")
    monkeypatch.setattr(
        svc,
        "restore_run",
        lambda _run_id: pytest.fail("restore_run should not be called when active run already matches"),
    )

    result = svc.ensure_production_run_restored(force=False)

    assert result == {
        "status": "noop",
        "reason": "local active run already matches production",
        "run_id": "run-1",
    }

def test_read_json_reads_written_json(isolated_paths):
    path = isolated_paths["artifacts_root"] / "sample.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"a": 1, "b": "x"}), encoding="utf-8")

    result = svc.read_json(str(path))

    assert result == {"a": 1, "b": "x"}


def test_clear_dir_contents_removes_files_and_directories(isolated_paths):
    target_dir = isolated_paths["artifacts_root"] / "to_clear"
    target_dir.mkdir(parents=True, exist_ok=True)

    (target_dir / "file.txt").write_text("hello", encoding="utf-8")
    nested_dir = target_dir / "nested"
    nested_dir.mkdir(parents=True, exist_ok=True)
    (nested_dir / "inner.txt").write_text("world", encoding="utf-8")

    svc.clear_dir_contents(str(target_dir))

    assert target_dir.exists()
    assert list(target_dir.iterdir()) == []


def test_copy_tree_contents_raises_if_source_missing(isolated_paths):
    missing_src = isolated_paths["artifacts_root"] / "does_not_exist"
    dst = isolated_paths["artifacts_root"] / "dst"

    with pytest.raises(FileNotFoundError, match="Source directory does not exist"):
        svc.copy_tree_contents(str(missing_src), str(dst))


def test_copy_tree_contents_copies_files_and_subdirectories(isolated_paths):
    src = isolated_paths["artifacts_root"] / "src"
    dst = isolated_paths["artifacts_root"] / "dst"

    src.mkdir(parents=True, exist_ok=True)
    (src / "root.txt").write_text("root", encoding="utf-8")
    (src / "nested").mkdir(parents=True, exist_ok=True)
    (src / "nested" / "child.txt").write_text("child", encoding="utf-8")

    dst.mkdir(parents=True, exist_ok=True)
    (dst / "old.txt").write_text("old", encoding="utf-8")

    svc.copy_tree_contents(str(src), str(dst))

    assert not (dst / "old.txt").exists()
    assert (dst / "root.txt").read_text(encoding="utf-8") == "root"
    assert (dst / "nested" / "child.txt").read_text(encoding="utf-8") == "child"


def test_remove_path_if_exists_removes_file(isolated_paths):
    file_path = isolated_paths["artifacts_root"] / "temp.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("temp", encoding="utf-8")

    svc.remove_path_if_exists(str(file_path))

    assert not file_path.exists()


def test_validate_cached_run_for_restore_returns_missing_required_files(isolated_paths):
    run_dir = isolated_paths["cache_root"] / "run-missing"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_dummy_file(run_dir / svc.REQUIRED_RUNTIME_FILES[0])

    result = svc.validate_cached_run_for_restore("run-missing")

    assert result["ok"] is False
    assert result["run_id"] == "run-missing"
    assert result["reason"] == "missing_required_files"
    assert len(result["missing_files"]) == len(svc.REQUIRED_RUNTIME_FILES) - 1


def test_validate_cached_run_for_restore_returns_success(isolated_paths, monkeypatch):
    _create_cached_run(isolated_paths["cache_root"], "run-ok")

    monkeypatch.setattr(svc.als_store, "validate_dir", lambda path: {"validated_als_dir": path})
    monkeypatch.setattr(
        svc.vector_index,
        "validate_dirs",
        lambda vectors_dir, hnsw_dir: {"vectors_dir": vectors_dir, "hnsw_dir": hnsw_dir},
    )

    result = svc.validate_cached_run_for_restore("run-ok")

    assert result["ok"] is True
    assert result["run_id"] == "run-ok"
    assert result["als"]["validated_als_dir"].endswith(r"run-ok\als") or result["als"]["validated_als_dir"].endswith("run-ok/als")
    assert result["vectors"]["vectors_dir"].endswith(r"run-ok\vectors") or result["vectors"]["vectors_dir"].endswith("run-ok/vectors")


def test_get_registry_downloads_expected_key(monkeypatch):
    calls = []

    def fake_download_json(key: str):
        calls.append(key)
        return {"production": {"run_id": "run-1"}}

    monkeypatch.setattr(svc, "download_json", fake_download_json)

    result = svc.get_registry()

    assert result == {"production": {"run_id": "run-1"}}
    assert calls == ["hybrid-recommender/registry.json"]


def test_get_production_pointer_returns_production(monkeypatch):
    monkeypatch.setattr(svc, "get_registry", lambda: {"production": {"run_id": "run-123", "slot": "production"}})

    result = svc.get_production_pointer()

    assert result == {"run_id": "run-123", "slot": "production"}


def test_get_production_pointer_raises_when_registry_missing_valid_production(monkeypatch):
    monkeypatch.setattr(svc, "get_registry", lambda: {"production": {}})

    with pytest.raises(RuntimeError, match="does not contain a valid production run"):
        svc.get_production_pointer()


def test_get_local_active_run_id_returns_none_when_file_missing(isolated_paths):
    result = svc.get_local_active_run_id()
    assert result is None


def test_get_local_active_run_id_returns_none_for_invalid_json(isolated_paths):
    isolated_paths["local_active_run"].parent.mkdir(parents=True, exist_ok=True)
    isolated_paths["local_active_run"].write_text("{not valid json", encoding="utf-8")

    result = svc.get_local_active_run_id()

    assert result is None


def test_set_local_active_run_writes_expected_json(isolated_paths, monkeypatch):
    monkeypatch.setattr(svc, "utc_now_iso", lambda: "2026-04-09T12:00:00+00:00")

    svc.set_local_active_run("run-55")

    data = json.loads(isolated_paths["local_active_run"].read_text(encoding="utf-8"))
    assert data == {
        "run_id": "run-55",
        "updated_at_utc": "2026-04-09T12:00:00+00:00",
    }


def test_prepare_staging_from_cache_raises_when_cached_run_is_incomplete(isolated_paths):
    run_dir = isolated_paths["cache_root"] / "run-bad"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_dummy_file(run_dir / "als" / "user_factors.npy")

    with pytest.raises(RuntimeError, match="Cached R2 run directory is incomplete or invalid"):
        svc.prepare_staging_from_cache("run-bad")


def test_restore_run_combines_download_and_restore_results(monkeypatch):
    monkeypatch.setattr(
        svc,
        "download_run_into_cache",
        lambda run_id: {
            "run_id": run_id,
            "remote_prefix": f"hybrid-recommender/runs/{run_id}",
            "local_run_dir": f"/tmp/{run_id}",
            "file_count": 9,
        },
    )
    monkeypatch.setattr(
        svc,
        "restore_run_from_cache",
        lambda run_id: {
            "status": "success",
            "run_id": run_id,
            "source": "r2",
        },
    )

    result = svc.restore_run("run-9")

    assert result == {
        "status": "success",
        "run_id": "run-9",
        "download": {
            "remote_prefix": "hybrid-recommender/runs/run-9",
            "local_run_dir": "/tmp/run-9",
            "file_count": 9,
        },
        "restore": {
            "status": "success",
            "run_id": "run-9",
            "source": "r2",
        },
    }


def test_restore_production_run_uses_production_run_id(monkeypatch):
    monkeypatch.setattr(svc, "get_production_pointer", lambda: {"run_id": "prod-1"})
    monkeypatch.setattr(svc, "restore_run", lambda run_id: {"status": "success", "run_id": run_id})

    result = svc.restore_production_run()

    assert result == {"status": "success", "run_id": "prod-1"}


def test_ensure_production_run_restored_calls_restore_when_local_differs(monkeypatch):
    monkeypatch.setattr(svc, "get_production_pointer", lambda: {"run_id": "run-prod"})
    monkeypatch.setattr(svc, "get_local_active_run_id", lambda: "run-old")
    monkeypatch.setattr(svc, "restore_run", lambda run_id: {"status": "success", "run_id": run_id})

    result = svc.ensure_production_run_restored(force=False)

    assert result == {"status": "success", "run_id": "run-prod"}


def test_ensure_production_run_restored_force_true_restores_even_when_local_matches(monkeypatch):
    monkeypatch.setattr(svc, "get_production_pointer", lambda: {"run_id": "run-prod"})
    monkeypatch.setattr(svc, "get_local_active_run_id", lambda: "run-prod")
    monkeypatch.setattr(svc, "restore_run", lambda run_id: {"status": "success", "run_id": run_id, "forced": True})

    result = svc.ensure_production_run_restored(force=True)

    assert result == {"status": "success", "run_id": "run-prod", "forced": True}#

def test_get_local_active_run_id_returns_run_id_when_json_is_valid(isolated_paths):
    isolated_paths["local_active_run"].parent.mkdir(parents=True, exist_ok=True)
    isolated_paths["local_active_run"].write_text(
        json.dumps({"run_id": "run-123"}),
        encoding="utf-8",
    )

    result = svc.get_local_active_run_id()

    assert result == "run-123"