import json
from pathlib import Path

import pytest

from app.ml.scripts import publish_run_to_r2 as publish_module
from app.ml.storage import r2_artifacts as r2_module


def test_publish_run_uploads_run_directory_to_versioned_prefix(tmp_path, monkeypatch):
    runs_dir = tmp_path / "runs"
    run_id = "run-123"
    local_run_dir = runs_dir / run_id
    local_run_dir.mkdir(parents=True)

    (local_run_dir / "meta.json").write_text('{"ok": true}', encoding="utf-8")
    (local_run_dir / "metrics.json").write_text('{"score": 0.9}', encoding="utf-8")

    monkeypatch.setattr(publish_module, "RUNS_DIR", str(runs_dir))
    monkeypatch.setattr(publish_module, "utc_now_iso", lambda: "2026-04-20T12:00:00+00:00")

    uploaded = {}

    def fake_upload_run_directory(local_dir, remote_prefix):
        uploaded["local_dir"] = local_dir
        uploaded["remote_prefix"] = remote_prefix
        return {
            "remote_prefix": remote_prefix,
            "files": [
                {"relative_path": "meta.json", "key": f"{remote_prefix}/meta.json", "size": 12, "sha256": "aaa"},
                {"relative_path": "metrics.json", "key": f"{remote_prefix}/metrics.json", "size": 15, "sha256": "bbb"},
            ],
        }

    monkeypatch.setattr(publish_module, "upload_run_directory", fake_upload_run_directory)
    monkeypatch.setattr(publish_module, "upload_json", lambda key, data: None)
    monkeypatch.setattr(publish_module, "load_registry", lambda: r2_module.default_registry())
    monkeypatch.setattr(publish_module, "save_registry", lambda registry: None)

    result = publish_module.publish_run(run_id=run_id, set_as_candidate=True)

    assert uploaded["local_dir"] == str(local_run_dir)
    assert uploaded["remote_prefix"] == f"hybrid-recommender/runs/{run_id}"
    assert result["run_id"] == run_id
    assert result["remote_prefix"] == f"hybrid-recommender/runs/{run_id}"
    assert result["file_count"] == 2


def test_publish_run_uploads_publish_manifest(tmp_path, monkeypatch):
    runs_dir = tmp_path / "runs"
    run_id = "run-456"
    local_run_dir = runs_dir / run_id
    local_run_dir.mkdir(parents=True)

    (local_run_dir / "artifact.bin").write_bytes(b"abc")

    monkeypatch.setattr(publish_module, "RUNS_DIR", str(runs_dir))
    monkeypatch.setattr(publish_module, "utc_now_iso", lambda: "2026-04-20T12:05:00+00:00")

    monkeypatch.setattr(
        publish_module,
        "upload_run_directory",
        lambda local_dir, remote_prefix: {
            "remote_prefix": remote_prefix,
            "files": [
                {"relative_path": "artifact.bin", "key": f"{remote_prefix}/artifact.bin", "size": 3, "sha256": "hash1"},
            ],
        },
    )

    uploaded_json = {}

    def fake_upload_json(key, data):
        uploaded_json["key"] = key
        uploaded_json["data"] = data

    monkeypatch.setattr(publish_module, "upload_json", fake_upload_json)
    monkeypatch.setattr(publish_module, "load_registry", lambda: r2_module.default_registry())
    monkeypatch.setattr(publish_module, "save_registry", lambda registry: None)

    result = publish_module.publish_run(run_id=run_id, set_as_candidate=True)

    expected_prefix = f"hybrid-recommender/runs/{run_id}"

    assert uploaded_json["key"] == f"{expected_prefix}/r2_publish_manifest.json"
    assert uploaded_json["data"]["run_id"] == run_id
    assert uploaded_json["data"]["remote_prefix"] == expected_prefix
    assert uploaded_json["data"]["file_count"] == 1
    assert result["file_count"] == 1


def test_publish_run_updates_candidate_registry_when_enabled(tmp_path, monkeypatch):
    runs_dir = tmp_path / "runs"
    run_id = "run-789"
    local_run_dir = runs_dir / run_id
    local_run_dir.mkdir(parents=True)
    (local_run_dir / "artifact.txt").write_text("hello", encoding="utf-8")

    monkeypatch.setattr(publish_module, "RUNS_DIR", str(runs_dir))
    monkeypatch.setattr(publish_module, "utc_now_iso", lambda: "2026-04-20T12:10:00+00:00")

    monkeypatch.setattr(
        publish_module,
        "upload_run_directory",
        lambda local_dir, remote_prefix: {
            "remote_prefix": remote_prefix,
            "files": [
                {"relative_path": "artifact.txt", "key": f"{remote_prefix}/artifact.txt", "size": 5, "sha256": "hash2"},
            ],
        },
    )
    monkeypatch.setattr(publish_module, "upload_json", lambda key, data: None)

    saved = {}

    monkeypatch.setattr(publish_module, "load_registry", lambda: r2_module.default_registry())

    def fake_save_registry(registry):
        saved["registry"] = registry

    monkeypatch.setattr(publish_module, "save_registry", fake_save_registry)

    result = publish_module.publish_run(run_id=run_id, set_as_candidate=True)

    assert result["registry"] is not None
    assert saved["registry"]["candidate"]["run_id"] == run_id
    assert saved["registry"]["candidate"]["remote_prefix"] == f"hybrid-recommender/runs/{run_id}"
    assert saved["registry"]["updated_at_utc"] == "2026-04-20T12:10:00+00:00"


def test_publish_run_does_not_update_registry_when_candidate_disabled(tmp_path, monkeypatch):
    runs_dir = tmp_path / "runs"
    run_id = "run-999"
    local_run_dir = runs_dir / run_id
    local_run_dir.mkdir(parents=True)
    (local_run_dir / "artifact.txt").write_text("hello", encoding="utf-8")

    monkeypatch.setattr(publish_module, "RUNS_DIR", str(runs_dir))
    monkeypatch.setattr(publish_module, "utc_now_iso", lambda: "2026-04-20T12:15:00+00:00")

    monkeypatch.setattr(
        publish_module,
        "upload_run_directory",
        lambda local_dir, remote_prefix: {
            "remote_prefix": remote_prefix,
            "files": [
                {"relative_path": "artifact.txt", "key": f"{remote_prefix}/artifact.txt", "size": 5, "sha256": "hash3"},
            ],
        },
    )
    monkeypatch.setattr(publish_module, "upload_json", lambda key, data: None)

    load_called = {"called": False}
    save_called = {"called": False}

    def fake_load_registry():
        load_called["called"] = True
        return r2_module.default_registry()

    def fake_save_registry(registry):
        save_called["called"] = True

    monkeypatch.setattr(publish_module, "load_registry", fake_load_registry)
    monkeypatch.setattr(publish_module, "save_registry", fake_save_registry)

    result = publish_module.publish_run(run_id=run_id, set_as_candidate=False)

    assert result["registry"] is None
    assert load_called["called"] is False
    assert save_called["called"] is False


def test_publish_run_raises_when_local_run_directory_missing(tmp_path, monkeypatch):
    runs_dir = tmp_path / "runs"
    monkeypatch.setattr(publish_module, "RUNS_DIR", str(runs_dir))

    with pytest.raises(FileNotFoundError, match="Run directory not found"):
        publish_module.publish_run(run_id="missing-run", set_as_candidate=True)


def test_upload_run_directory_returns_uploaded_file_metadata(tmp_path, monkeypatch):
    local_run_dir = tmp_path / "local_run"
    local_run_dir.mkdir()

    (local_run_dir / "a.txt").write_text("alpha", encoding="utf-8")
    nested = local_run_dir / "subdir"
    nested.mkdir()
    (nested / "b.txt").write_text("beta", encoding="utf-8")

    uploaded = []

    class FakeS3:
        def upload_file(self, abs_path, bucket, key):
            uploaded.append((abs_path, bucket, key))

    monkeypatch.setattr(r2_module, "get_r2_client", lambda: FakeS3())
    monkeypatch.setattr(r2_module, "get_r2_bucket", lambda: "test-bucket")

    result = r2_module.upload_run_directory(
        local_run_dir=str(local_run_dir),
        remote_prefix="hybrid-recommender/runs/run-abc",
    )

    assert result["remote_prefix"] == "hybrid-recommender/runs/run-abc"
    assert len(result["files"]) == 2

    relative_paths = sorted(f["relative_path"] for f in result["files"])
    assert relative_paths == ["a.txt", "subdir/b.txt"]

    keys = sorted(f["key"] for f in result["files"])
    assert keys == [
        "hybrid-recommender/runs/run-abc/a.txt",
        "hybrid-recommender/runs/run-abc/subdir/b.txt",
    ]

    assert len(uploaded) == 2
    assert all(item[1] == "test-bucket" for item in uploaded)