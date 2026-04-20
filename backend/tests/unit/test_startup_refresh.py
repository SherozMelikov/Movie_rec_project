import pytest

from app.services import startup as startup_module


class StopLoop(Exception):
    pass


def test_start_background_refresh_thread_does_nothing_when_r2_disabled(monkeypatch):
    class FakeSettings:
        use_r2_artifacts = False

    started = {"called": False}

    class FakeThread:
        def __init__(self, *args, **kwargs):
            started["called"] = True

        def start(self):
            started["called"] = True

    monkeypatch.setattr(startup_module, "settings", FakeSettings())
    monkeypatch.setattr(startup_module.threading, "Thread", FakeThread)

    startup_module._start_background_refresh_thread()

    assert started["called"] is False


def test_start_background_refresh_thread_starts_daemon_thread_when_r2_enabled(monkeypatch):
    class FakeSettings:
        use_r2_artifacts = True

    captured = {}

    class FakeThread:
        def __init__(self, target, name, daemon):
            captured["target"] = target
            captured["name"] = name
            captured["daemon"] = daemon

        def start(self):
            captured["started"] = True

    monkeypatch.setattr(startup_module, "settings", FakeSettings())
    monkeypatch.setattr(startup_module.threading, "Thread", FakeThread)

    startup_module._start_background_refresh_thread()

    assert captured["target"] == startup_module._refresh_loop
    assert captured["name"] == "artifact-refresh-loop"
    assert captured["daemon"] is True
    assert captured["started"] is True


def test_refresh_loop_skips_when_r2_disabled(monkeypatch, capsys):
    class FakeSettings:
        use_r2_artifacts = False

    monkeypatch.setattr(startup_module, "settings", FakeSettings())

    def fake_sleep(seconds):
        raise StopLoop()

    monkeypatch.setattr(startup_module.time, "sleep", fake_sleep)

    with pytest.raises(StopLoop):
        startup_module._refresh_loop()

    captured = capsys.readouterr()
    assert "Background refresh loop started" in captured.out
    assert "Background refresh skipped: USE_R2_ARTIFACTS is false" in captured.out


def test_refresh_loop_reports_no_change_when_restore_returns_noop(monkeypatch, capsys):
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
    assert "Background refresh loop started" in captured.out
    assert "Background refresh: no change (run-123)" in captured.out


def test_refresh_loop_reports_detected_change(monkeypatch, capsys):
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
    assert "Background refresh detected change:" in captured.out
    assert "run-456" in captured.out


def test_refresh_loop_catches_exception_and_continues_iteration(monkeypatch, capsys):
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
    assert "Background refresh failed: restore failed" in captured.out


def test_run_startup_starts_background_thread_when_r2_enabled(monkeypatch):
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