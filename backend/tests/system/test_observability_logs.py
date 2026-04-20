import pytest

from app.ml.scripts import run_worker_once as worker_module
from app.services import startup as startup_module


class StopLoop(Exception):
    pass


def test_worker_logs_key_events(monkeypatch, capsys, tmp_path):
    worker_dir = tmp_path / "worker"
    lock_path = worker_dir / "worker.lock"
    latest_path = worker_dir / "latest_worker_run.json"

    monkeypatch.setattr(worker_module, "WORKER_DIR", str(worker_dir))
    monkeypatch.setattr(worker_module, "LOCK_PATH", str(lock_path))
    monkeypatch.setattr(worker_module, "LATEST_WORKER_RUN_PATH", str(latest_path))
    monkeypatch.setattr(worker_module, "utc_run_id", lambda: "worker-run-obs-001")
    monkeypatch.setattr(worker_module, "utc_now_iso", lambda: "2026-04-20T12:00:00+00:00")
    monkeypatch.setattr(worker_module, "AUTO_PROMOTE_IF_VALID", False)

    monkeypatch.setattr(
        worker_module,
        "run_pipeline",
        lambda config: {
            "run_id": "run-123",
            "status": "success",
            "finished_at_utc": "2026-04-20T12:01:00+00:00",
            "latest_pointer": "latest.json",
            "run_snapshot": {"k": 20},
            "errors": [],
            "metrics_summary": {
                "Hybrid_Service": {
                    "hitrate_at_20": 0.90,
                    "ndcg_at_20": 0.82,
                    "coverage_rate": 1.0,
                },
                "Hybrid_Model": {"hitrate_at_20": 0.88},
                "ALS_FullCatalog": {"hitrate_at_20": 0.70},
            },
        },
    )

    monkeypatch.setattr(
        worker_module,
        "publish_run",
        lambda run_id, set_as_candidate: {
            "run_id": run_id,
            "remote_prefix": f"runs/{run_id}",
            "file_count": 8,
        },
    )

    monkeypatch.setattr(
        worker_module,
        "download_run_into_cache",
        lambda run_id: {
            "run_id": run_id,
            "local_run_dir": str(tmp_path / "cache" / run_id),
        },
    )

    monkeypatch.setattr(
        worker_module,
        "validate_cached_run_dir",
        lambda local_run_dir: {"valid": True, "checked_dir": local_run_dir},
    )
    monkeypatch.setattr(
        worker_module,
        "validate_cached_run_for_restore",
        lambda run_id: {"ok": True, "run_id": run_id},
    )
    monkeypatch.setattr(
        worker_module,
        "run_smoke_checks",
        lambda run_id, cached_run_dir: {"ok": True, "run_id": run_id},
    )
    monkeypatch.setattr(worker_module, "upload_json", lambda key, payload: None)

    worker_module.run_worker_once()

    captured = capsys.readouterr()
    out = captured.out

    assert "=== WORKER START: worker-run-obs-001 ===" in out
    assert "[worker] Starting pipeline..." in out
    assert "[worker] Publishing run to R2: run-123" in out
    assert "[worker] Downloading candidate into cache for validation: run-123" in out
    assert "=== WORKER FINISHED ===" in out
    assert "status: success" in out


def test_refresh_logs_no_change(monkeypatch, capsys):
    class FakeSettings:
        use_r2_artifacts = True

    monkeypatch.setattr(startup_module, "settings", FakeSettings())
    monkeypatch.setattr(
        startup_module,
        "ensure_production_run_restored",
        lambda force=False: {"status": "noop", "run_id": "run-123"},
    )

    def fake_sleep(seconds):
        raise StopLoop()

    monkeypatch.setattr(startup_module.time, "sleep", fake_sleep)

    with pytest.raises(StopLoop):
        startup_module._refresh_loop()

    captured = capsys.readouterr()
    out = captured.out

    assert "Background refresh loop started" in out
    assert "Background refresh: no change (run-123)" in out


def test_refresh_logs_detected_change(monkeypatch, capsys):
    class FakeSettings:
        use_r2_artifacts = True

    monkeypatch.setattr(startup_module, "settings", FakeSettings())
    monkeypatch.setattr(
        startup_module,
        "ensure_production_run_restored",
        lambda force=False: {"status": "restored", "run_id": "run-456"},
    )

    def fake_sleep(seconds):
        raise StopLoop()

    monkeypatch.setattr(startup_module.time, "sleep", fake_sleep)

    with pytest.raises(StopLoop):
        startup_module._refresh_loop()

    captured = capsys.readouterr()
    out = captured.out

    assert "Background refresh detected change:" in out
    assert "run-456" in out


def test_refresh_logs_failure(monkeypatch, capsys):
    class FakeSettings:
        use_r2_artifacts = True

    monkeypatch.setattr(startup_module, "settings", FakeSettings())

    def boom(force=False):
        raise RuntimeError("restore failed")

    monkeypatch.setattr(startup_module, "ensure_production_run_restored", boom)

    def fake_sleep(seconds):
        raise StopLoop()

    monkeypatch.setattr(startup_module.time, "sleep", fake_sleep)

    with pytest.raises(StopLoop):
        startup_module._refresh_loop()

    captured = capsys.readouterr()
    out = captured.out

    assert "Background refresh failed: restore failed" in out