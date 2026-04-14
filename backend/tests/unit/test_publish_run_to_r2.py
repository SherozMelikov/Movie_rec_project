from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import app.ml.scripts.publish_run_to_r2 as publish


def test_utc_now_iso_returns_string():
    result = publish.utc_now_iso()
    assert isinstance(result, str)
    assert "T" in result


@pytest.fixture
def isolated_runs_dir(tmp_path, monkeypatch):
    runs_dir = tmp_path / "artifacts" / "runs"
    monkeypatch.setattr(publish, "RUNS_DIR", str(runs_dir))
    return {"runs_dir": runs_dir}


def test_publish_run_raises_when_local_run_dir_missing(isolated_runs_dir):
    with pytest.raises(FileNotFoundError, match="Run directory not found"):
        publish.publish_run("run-missing")


def test_publish_run_uploads_manifest_and_updates_candidate_registry(isolated_runs_dir, monkeypatch):
    run_id = "run-1"
    local_run_dir = isolated_runs_dir["runs_dir"] / run_id
    local_run_dir.mkdir(parents=True, exist_ok=True)

    fixed_times = iter(
        [
            "2026-04-10T12:00:00+00:00",  # published_at_utc
            "2026-04-10T12:00:01+00:00",  # candidate.uploaded_at_utc
            "2026-04-10T12:00:02+00:00",  # registry.updated_at_utc
        ]
    )
    monkeypatch.setattr(publish, "utc_now_iso", lambda: next(fixed_times))

    uploads = []
    json_uploads = []
    saved_registries = []

    upload_files = [
        {
            "relative_path": "als/user_factors.npy",
            "key": "hybrid-recommender/runs/run-1/als/user_factors.npy",
        },
        {
            "relative_path": "vectors/vectors.npy",
            "key": "hybrid-recommender/runs/run-1/vectors/vectors.npy",
        },
    ]

    def fake_upload_run_directory(local_dir, remote_prefix):
        uploads.append((local_dir, remote_prefix))
        return {"files": upload_files}

    def fake_upload_json(key, payload):
        json_uploads.append((key, payload))

    def fake_load_registry():
        return {"production": {"run_id": "prod-1"}}

    def fake_save_registry(registry):
        saved_registries.append(registry)

    monkeypatch.setattr(publish, "upload_run_directory", fake_upload_run_directory)
    monkeypatch.setattr(publish, "upload_json", fake_upload_json)
    monkeypatch.setattr(publish, "load_registry", fake_load_registry)
    monkeypatch.setattr(publish, "save_registry", fake_save_registry)

    result = publish.publish_run(run_id=run_id, set_as_candidate=True)

    assert uploads == [
        (str(local_run_dir), "hybrid-recommender/runs/run-1")
    ]

    assert len(json_uploads) == 1
    manifest_key, manifest_payload = json_uploads[0]
    assert manifest_key == "hybrid-recommender/runs/run-1/r2_publish_manifest.json"
    assert manifest_payload == {
        "run_id": "run-1",
        "published_at_utc": "2026-04-10T12:00:00+00:00",
        "remote_prefix": "hybrid-recommender/runs/run-1",
        "file_count": 2,
        "files": upload_files,
    }

    assert len(saved_registries) == 1
    assert saved_registries[0] == {
        "production": {"run_id": "prod-1"},
        "candidate": {
            "run_id": "run-1",
            "remote_prefix": "hybrid-recommender/runs/run-1",
            "uploaded_at_utc": "2026-04-10T12:00:01+00:00",
        },
        "updated_at_utc": "2026-04-10T12:00:02+00:00",
    }

    assert result == {
        "run_id": "run-1",
        "remote_prefix": "hybrid-recommender/runs/run-1",
        "file_count": 2,
        "files": upload_files,
        "registry": saved_registries[0],
    }


def test_publish_run_uploads_manifest_without_registry_update_when_candidate_disabled(
    isolated_runs_dir, monkeypatch
):
    run_id = "run-2"
    local_run_dir = isolated_runs_dir["runs_dir"] / run_id
    local_run_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(publish, "utc_now_iso", lambda: "2026-04-10T12:00:00+00:00")

    json_uploads = []
    upload_files = [
        {
            "relative_path": "manifest.json",
            "key": "hybrid-recommender/runs/run-2/manifest.json",
        }
    ]

    monkeypatch.setattr(
        publish,
        "upload_run_directory",
        lambda local_dir, remote_prefix: {"files": upload_files},
    )
    monkeypatch.setattr(publish, "upload_json", lambda key, payload: json_uploads.append((key, payload)))
    monkeypatch.setattr(
        publish,
        "load_registry",
        lambda: pytest.fail("load_registry should not be called when set_as_candidate=False"),
    )
    monkeypatch.setattr(
        publish,
        "save_registry",
        lambda registry: pytest.fail("save_registry should not be called when set_as_candidate=False"),
    )

    result = publish.publish_run(run_id=run_id, set_as_candidate=False)

    assert len(json_uploads) == 1
    assert json_uploads[0][0] == "hybrid-recommender/runs/run-2/r2_publish_manifest.json"

    assert result == {
        "run_id": "run-2",
        "remote_prefix": "hybrid-recommender/runs/run-2",
        "file_count": 1,
        "files": upload_files,
        "registry": None,
    }


def test_main_parses_args_and_prints_result(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "publish_run_to_r2.py",
            "--run-id",
            "run-9",
            "--no-set-candidate",
        ],
    )

    calls = {}

    def fake_publish_run(run_id, set_as_candidate):
        calls["run_id"] = run_id
        calls["set_as_candidate"] = set_as_candidate
        return {"status": "ok", "run_id": run_id}

    monkeypatch.setattr(publish, "publish_run", fake_publish_run)

    publish.main()

    captured = capsys.readouterr()

    assert calls == {
        "run_id": "run-9",
        "set_as_candidate": False,
    }
    assert json.loads(captured.out) == {"status": "ok", "run_id": "run-9"}