from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.ml.scripts.run_worker_once as worker


@pytest.fixture
def isolated_worker_paths(tmp_path, monkeypatch):
    worker_dir = tmp_path / "artifacts" / "worker"
    lock_path = worker_dir / "worker.lock"
    latest_worker_run_path = worker_dir / "latest_worker_run.json"

    monkeypatch.setattr(worker, "WORKER_DIR", str(worker_dir))
    monkeypatch.setattr(worker, "LOCK_PATH", str(lock_path))
    monkeypatch.setattr(worker, "LATEST_WORKER_RUN_PATH", str(latest_worker_run_path))
    monkeypatch.setattr(worker, "utc_now_iso", lambda: "2026-04-09T12:00:00+00:00")
    monkeypatch.setattr(worker, "utc_run_id", lambda: "2026-04-09T12-00-00Z")

    return {
        "worker_dir": worker_dir,
        "lock_path": lock_path,
        "latest_worker_run_path": latest_worker_run_path,
        "worker_log_path": worker_dir / "worker_run_2026-04-09T12-00-00Z.json",
    }


def test_acquire_lock_creates_lock_file(isolated_worker_paths):
    result = worker.acquire_lock()

    assert result["created_at_utc"] == "2026-04-09T12:00:00+00:00"
    assert result["script"] == "run_worker_once.py"
    assert "pid" in result

    lock_data = json.loads(isolated_worker_paths["lock_path"].read_text(encoding="utf-8"))
    assert lock_data == result


def test_acquire_lock_raises_when_lock_already_exists(isolated_worker_paths):
    isolated_worker_paths["lock_path"].parent.mkdir(parents=True, exist_ok=True)
    isolated_worker_paths["lock_path"].write_text(
        json.dumps({"created_at_utc": "old", "pid": 999}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Worker lock already exists"):
        worker.acquire_lock()


def test_acquire_lock_raises_with_fallback_when_existing_lock_is_invalid_json(isolated_worker_paths):
    isolated_worker_paths["lock_path"].parent.mkdir(parents=True, exist_ok=True)
    isolated_worker_paths["lock_path"].write_text("{not valid json", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Failed to read existing lock file"):
        worker.acquire_lock()


def test_release_lock_removes_existing_lock_file(isolated_worker_paths):
    isolated_worker_paths["lock_path"].parent.mkdir(parents=True, exist_ok=True)
    isolated_worker_paths["lock_path"].write_text("{}", encoding="utf-8")

    worker.release_lock()

    assert not isolated_worker_paths["lock_path"].exists()


def test_summarize_pipeline_result_extracts_key_metrics():
    pipeline_result = {
        "status": "success",
        "run_id": "run-1",
        "metrics_summary": {
            "Hybrid_Service": {
                "hitrate_at_20": 0.91,
                "ndcg_at_20": 0.77,
                "coverage_rate": 1.0,
            },
            "Hybrid_Model": {
                "hitrate_at_20": 0.88,
            },
            "ALS_FullCatalog": {
                "hitrate_at_20": 0.66,
            },
        },
    }

    result = worker.summarize_pipeline_result(pipeline_result)

    assert result == {
        "pipeline_status": "success",
        "run_id": "run-1",
        "hybrid_service_hitrate_at_20": 0.91,
        "hybrid_service_ndcg_at_20": 0.77,
        "hybrid_service_coverage_rate": 1.0,
        "hybrid_model_hitrate_at_20": 0.88,
        "als_hitrate_at_20": 0.66,
    }


def test_build_validation_report_marks_candidate_eligible(monkeypatch):
    monkeypatch.setattr(worker, "utc_now_iso", lambda: "2026-04-09T12:00:00+00:00")

    result = worker.build_validation_report(
        run_id="run-1",
        pipeline_result={"status": "success"},
        artifact_validation={"valid": True},
        restore_validation={"ok": True},
        smoke_checks={"ok": True},
    )

    assert result["run_id"] == "run-1"
    assert result["validated_at_utc"] == "2026-04-09T12:00:00+00:00"
    assert result["eligible_for_promotion"] is True
    assert result["required_artifacts_ok"] is True
    assert result["restore_validation_ok"] is True
    assert result["smoke_checks_ok"] is True


def test_build_validation_report_marks_candidate_ineligible(monkeypatch):
    monkeypatch.setattr(worker, "utc_now_iso", lambda: "2026-04-09T12:00:00+00:00")

    result = worker.build_validation_report(
        run_id="run-1",
        pipeline_result={"status": "success"},
        artifact_validation={"valid": False},
        restore_validation={"ok": True},
        smoke_checks={"ok": True},
    )

    assert result["eligible_for_promotion"] is False
    assert result["required_artifacts_ok"] is False


def test_run_worker_once_returns_failed_when_pipeline_fails(isolated_worker_paths, monkeypatch):
    def fake_run_pipeline(config):
        return {
            "run_id": "run-1",
            "status": "failed",
            "finished_at_utc": "2026-04-09T12:01:00+00:00",
            "latest_pointer": None,
            "run_snapshot": None,
            "errors": [{"message": "quality gate failed"}],
            "metrics_summary": {},
        }

    monkeypatch.setattr(worker, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(worker, "publish_run", lambda **kwargs: pytest.fail("publish_run should not be called"))

    result = worker.run_worker_once()

    assert result["status"] == "failed"
    assert result["pipeline_result"]["status"] == "failed"
    assert result["r2_publish"] is None
    assert result["validation_report"] is None
    assert not isolated_worker_paths["lock_path"].exists()
    assert isolated_worker_paths["worker_log_path"].exists()
    assert isolated_worker_paths["latest_worker_run_path"].exists()


def test_run_worker_once_fails_when_pipeline_success_has_no_run_id(isolated_worker_paths, monkeypatch):
    monkeypatch.setattr(
        worker,
        "run_pipeline",
        lambda config: {
            "run_id": None,
            "status": "success",
            "finished_at_utc": "2026-04-09T12:01:00+00:00",
            "latest_pointer": None,
            "run_snapshot": None,
            "errors": [],
            "metrics_summary": {},
        },
    )

    result = worker.run_worker_once()

    assert result["status"] == "failed"
    assert len(result["errors"]) == 1
    assert result["errors"][0]["type"] == "RuntimeError"
    assert "run_id is missing" in result["errors"][0]["message"]
    assert not isolated_worker_paths["lock_path"].exists()


def test_run_worker_once_returns_failed_when_candidate_is_not_eligible(isolated_worker_paths, monkeypatch):
    uploads = []

    pipeline_result = {
        "run_id": "run-1",
        "status": "success",
        "finished_at_utc": "2026-04-09T12:01:00+00:00",
        "latest_pointer": {"run_id": "run-1"},
        "run_snapshot": {"run_id": "run-1"},
        "errors": [],
        "metrics_summary": {
            "Hybrid_Service": {"hitrate_at_20": 0.9, "ndcg_at_20": 0.8, "coverage_rate": 1.0},
            "Hybrid_Model": {"hitrate_at_20": 0.85},
            "ALS_FullCatalog": {"hitrate_at_20": 0.7},
        },
    }

    monkeypatch.setattr(worker, "AUTO_PROMOTE_IF_VALID", False)
    monkeypatch.setattr(worker, "run_pipeline", lambda config: pipeline_result)
    monkeypatch.setattr(
        worker,
        "publish_run",
        lambda run_id, set_as_candidate: {
            "run_id": run_id,
            "remote_prefix": f"hybrid-recommender/runs/{run_id}",
            "file_count": 9,
        },
    )
    monkeypatch.setattr(
        worker,
        "download_run_into_cache",
        lambda run_id: {
            "run_id": run_id,
            "local_run_dir": f"/tmp/{run_id}",
            "remote_prefix": f"hybrid-recommender/runs/{run_id}",
            "file_count": 9,
        },
    )
    monkeypatch.setattr(worker, "validate_cached_run_dir", lambda _path: {"valid": False})
    monkeypatch.setattr(worker, "validate_cached_run_for_restore", lambda _run_id: {"ok": True})
    monkeypatch.setattr(worker, "run_smoke_checks", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(worker, "upload_json", lambda key, payload: uploads.append((key, payload)))
    monkeypatch.setattr(worker, "promote_run", lambda **kwargs: pytest.fail("promote_run should not be called"))

    result = worker.run_worker_once()

    assert result["status"] == "failed"
    assert result["validation_report"]["eligible_for_promotion"] is False
    assert result["auto_promotion"] == {
        "status": "skipped",
        "reason": "candidate_not_eligible_for_promotion",
        "validation_key": "hybrid-recommender/runs/run-1/validation_report.json",
    }

    assert len(uploads) == 1
    assert uploads[0][0] == "hybrid-recommender/runs/run-1/validation_report.json"


def test_run_worker_once_success_skips_auto_promotion_when_flag_is_false(isolated_worker_paths, monkeypatch):
    uploads = []
    calls = {}

    pipeline_result = {
        "run_id": "run-1",
        "status": "success",
        "finished_at_utc": "2026-04-09T12:01:00+00:00",
        "latest_pointer": {"run_id": "run-1"},
        "run_snapshot": {"run_id": "run-1"},
        "errors": [],
        "metrics_summary": {
            "Hybrid_Service": {"hitrate_at_20": 0.9, "ndcg_at_20": 0.8, "coverage_rate": 1.0},
            "Hybrid_Model": {"hitrate_at_20": 0.85},
            "ALS_FullCatalog": {"hitrate_at_20": 0.7},
        },
    }

    def fake_run_pipeline(config):
        calls["pipeline_config"] = config
        return pipeline_result

    monkeypatch.setattr(worker, "AUTO_PROMOTE_IF_VALID", False)
    monkeypatch.setattr(worker, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(
        worker,
        "publish_run",
        lambda run_id, set_as_candidate: {
            "run_id": run_id,
            "remote_prefix": f"hybrid-recommender/runs/{run_id}",
            "file_count": 9,
        },
    )
    monkeypatch.setattr(
        worker,
        "download_run_into_cache",
        lambda run_id: {
            "run_id": run_id,
            "local_run_dir": f"/tmp/{run_id}",
            "remote_prefix": f"hybrid-recommender/runs/{run_id}",
            "file_count": 9,
        },
    )
    monkeypatch.setattr(worker, "validate_cached_run_dir", lambda _path: {"valid": True})
    monkeypatch.setattr(worker, "validate_cached_run_for_restore", lambda _run_id: {"ok": True})
    monkeypatch.setattr(worker, "run_smoke_checks", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(worker, "upload_json", lambda key, payload: uploads.append((key, payload)))
    monkeypatch.setattr(worker, "promote_run", lambda **kwargs: pytest.fail("promote_run should not be called"))

    result = worker.run_worker_once()

    assert result["status"] == "success"
    assert result["pipeline_result"]["run_id"] == "run-1"
    assert result["validation_report"]["eligible_for_promotion"] is True
    assert result["auto_promotion"] == {
        "status": "skipped",
        "run_id": "run-1",
        "reason": "AUTO_PROMOTE_IF_VALID is false",
        "eligible_for_promotion": True,
    }

    assert calls["pipeline_config"].run_eval is True
    assert calls["pipeline_config"].min_hybrid_service_hitrate_at_20 == 0.80
    assert calls["pipeline_config"].require_full_coverage is True
    assert calls["pipeline_config"].fail_on_quality_gate is True

    assert len(uploads) == 1
    assert uploads[0][0] == "hybrid-recommender/runs/run-1/validation_report.json"
    assert not isolated_worker_paths["lock_path"].exists()
    assert isolated_worker_paths["worker_log_path"].exists()
    assert isolated_worker_paths["latest_worker_run_path"].exists()


def test_run_worker_once_success_auto_promotes_when_flag_is_true(isolated_worker_paths, monkeypatch):
    promotions = []

    pipeline_result = {
        "run_id": "run-1",
        "status": "success",
        "finished_at_utc": "2026-04-09T12:01:00+00:00",
        "latest_pointer": {"run_id": "run-1"},
        "run_snapshot": {"run_id": "run-1"},
        "errors": [],
        "metrics_summary": {
            "Hybrid_Service": {"hitrate_at_20": 0.9, "ndcg_at_20": 0.8, "coverage_rate": 1.0},
            "Hybrid_Model": {"hitrate_at_20": 0.85},
            "ALS_FullCatalog": {"hitrate_at_20": 0.7},
        },
    }

    monkeypatch.setattr(worker, "AUTO_PROMOTE_IF_VALID", True)
    monkeypatch.setattr(worker, "run_pipeline", lambda config: pipeline_result)
    monkeypatch.setattr(
        worker,
        "publish_run",
        lambda run_id, set_as_candidate: {
            "run_id": run_id,
            "remote_prefix": f"hybrid-recommender/runs/{run_id}",
            "file_count": 9,
        },
    )
    monkeypatch.setattr(
        worker,
        "download_run_into_cache",
        lambda run_id: {
            "run_id": run_id,
            "local_run_dir": f"/tmp/{run_id}",
            "remote_prefix": f"hybrid-recommender/runs/{run_id}",
            "file_count": 9,
        },
    )
    monkeypatch.setattr(worker, "validate_cached_run_dir", lambda _path: {"valid": True})
    monkeypatch.setattr(worker, "validate_cached_run_for_restore", lambda _run_id: {"ok": True})
    monkeypatch.setattr(worker, "run_smoke_checks", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(worker, "upload_json", lambda key, payload: None)

    def fake_promote_run(run_id, require_validation, cleanup_delay_hours):
        promotions.append(
            {
                "run_id": run_id,
                "require_validation": require_validation,
                "cleanup_delay_hours": cleanup_delay_hours,
            }
        )
        return {"production": {"run_id": run_id}}

    monkeypatch.setattr(worker, "promote_run", fake_promote_run)

    result = worker.run_worker_once()

    assert result["status"] == "success"
    assert result["auto_promotion"] == {
        "status": "success",
        "run_id": "run-1",
        "registry": {"production": {"run_id": "run-1"}},
    }
    assert promotions == [
        {
            "run_id": "run-1",
            "require_validation": True,
            "cleanup_delay_hours": 24,
        }
    ]


def test_run_worker_once_captures_unexpected_exception_and_releases_lock(isolated_worker_paths, monkeypatch):
    monkeypatch.setattr(
        worker,
        "run_pipeline",
        lambda config: {
            "run_id": "run-1",
            "status": "success",
            "finished_at_utc": "2026-04-09T12:01:00+00:00",
            "latest_pointer": {"run_id": "run-1"},
            "run_snapshot": {"run_id": "run-1"},
            "errors": [],
            "metrics_summary": {},
        },
    )
    monkeypatch.setattr(worker, "publish_run", lambda **kwargs: (_ for _ in ()).throw(ValueError("publish boom")))

    result = worker.run_worker_once()

    assert result["status"] == "failed"
    assert len(result["errors"]) == 1
    assert result["errors"][0]["type"] == "ValueError"
    assert "publish boom" in result["errors"][0]["message"]
    assert not isolated_worker_paths["lock_path"].exists()
    assert isolated_worker_paths["worker_log_path"].exists()
    assert isolated_worker_paths["latest_worker_run_path"].exists()


def test_main_exits_zero_when_worker_succeeds(monkeypatch):
    monkeypatch.setattr(worker, "run_worker_once", lambda: {"status": "success"})

    with pytest.raises(SystemExit) as exc:
        worker.main()

    assert exc.value.code == 0


def test_main_exits_one_when_worker_fails(monkeypatch):
    monkeypatch.setattr(worker, "run_worker_once", lambda: {"status": "failed"})

    with pytest.raises(SystemExit) as exc:
        worker.main()

    assert exc.value.code == 1

def test_utc_now_iso_returns_string():
    result = worker.utc_now_iso()
    assert isinstance(result, str)
    assert "T" in result


def test_utc_run_id_returns_string():
    result = worker.utc_run_id()
    assert isinstance(result, str)
    assert result.endswith("Z")