from app.services import startup as startup_module


def test_artifact_recovery_on_restart(monkeypatch):
    calls = []

    class FakeSettings:
        use_r2_artifacts = True

    def fake_restore(force=False):
        calls.append("restore_called")
        return {"status": "restored", "run_id": "run-123"}

    def fake_reload():
        calls.append("reload_called")

    def fake_start_bg():
        calls.append("start_bg_called")

    monkeypatch.setattr(startup_module, "settings", FakeSettings())
    monkeypatch.setattr(
        startup_module,
        "ensure_production_run_restored",
        fake_restore,
    )
    monkeypatch.setattr(
        startup_module,
        "_reload_runtime_artifacts",
        fake_reload,
    )
    monkeypatch.setattr(
        startup_module,
        "_start_background_refresh_thread",
        fake_start_bg,
    )

    startup_module.run_startup()

    assert "restore_called" in calls
    assert "start_bg_called" in calls
    assert "reload_called" not in calls