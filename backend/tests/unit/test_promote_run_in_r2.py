from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pytest

import app.ml.scripts.promote_run_in_r2 as promote


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def fixed_time(monkeypatch):
    monkeypatch.setattr(promote, "datetime", FixedDateTime)
    monkeypatch.setattr(promote, "utc_now_iso", lambda: "2026-04-10T12:00:00+00:00")


def test_make_run_ref():
    result = promote.make_run_ref("run-1")

    assert result == {
        "run_id": "run-1",
        "remote_prefix": "hybrid-recommender/runs/run-1",
    }


def test_load_validation_report_raises_when_key_missing(monkeypatch):
    monkeypatch.setattr(promote, "key_exists", lambda key: False)

    with pytest.raises(RuntimeError, match="validation report not found"):
        promote.load_validation_report("run-1")


def test_load_validation_report_raises_when_not_eligible(monkeypatch):
    monkeypatch.setattr(promote, "key_exists", lambda key: True)
    monkeypatch.setattr(
        promote,
        "download_json",
        lambda key: {"eligible_for_promotion": False},
    )

    with pytest.raises(RuntimeError, match="eligible_for_promotion=false"):
        promote.load_validation_report("run-1")


def test_load_validation_report_returns_report_when_valid(monkeypatch):
    report = {
        "eligible_for_promotion": True,
        "validated_at_utc": "2026-04-10T11:00:00+00:00",
    }

    monkeypatch.setattr(promote, "key_exists", lambda key: True)
    monkeypatch.setattr(promote, "download_json", lambda key: report)

    result = promote.load_validation_report("run-1")

    assert result == report


def test_promote_run_raises_when_publish_manifest_missing(monkeypatch):
    monkeypatch.setattr(promote, "key_exists", lambda key: False)

    with pytest.raises(RuntimeError, match="publish manifest not found"):
        promote.promote_run("run-1")


def test_promote_run_calls_validation_when_required(monkeypatch, fixed_time):
    saved = []

    monkeypatch.setattr(promote, "key_exists", lambda key: True)
    monkeypatch.setattr(
        promote,
        "load_validation_report",
        lambda run_id: {
            "validated_at_utc": "2026-04-10T11:00:00+00:00",
            "required_artifacts_ok": True,
            "eval_thresholds_ok": True,
            "restore_validation_ok": True,
            "smoke_checks_ok": True,
        },
    )
    monkeypatch.setattr(
        promote,
        "load_registry",
        lambda: {
            "production": {"run_id": "run-old", "remote_prefix": "hybrid-recommender/runs/run-old"},
            "candidate": {"run_id": "run-1", "remote_prefix": "hybrid-recommender/runs/run-1"},
        },
    )
    monkeypatch.setattr(promote, "save_registry", lambda registry: saved.append(registry))

    result = promote.promote_run("run-1", require_validation=True, cleanup_delay_hours=24)

    assert result["production"]["run_id"] == "run-1"
    assert result["production"]["promoted_at_utc"] == "2026-04-10T12:00:00+00:00"
    assert result["production"]["validated_at_utc"] == "2026-04-10T11:00:00+00:00"
    assert result["production"]["validation_summary"] == {
        "required_artifacts_ok": True,
        "eval_thresholds_ok": True,
        "restore_validation_ok": True,
        "smoke_checks_ok": True,
    }
    assert len(saved) == 1


def test_promote_run_skips_validation_when_not_required(monkeypatch, fixed_time):
    saved = []

    monkeypatch.setattr(promote, "key_exists", lambda key: True)
    monkeypatch.setattr(
        promote,
        "load_validation_report",
        lambda run_id: pytest.fail("load_validation_report should not be called"),
    )
    monkeypatch.setattr(promote, "load_registry", lambda: {"production": None})
    monkeypatch.setattr(promote, "save_registry", lambda registry: saved.append(registry))

    result = promote.promote_run("run-1", require_validation=False, cleanup_delay_hours=24)

    assert result["production"]["run_id"] == "run-1"
    assert "validated_at_utc" not in result["production"]
    assert "validation_summary" not in result["production"]
    assert len(saved) == 1


def test_promote_run_when_same_run_already_in_production_updates_and_returns(monkeypatch, fixed_time):
    saved = []

    monkeypatch.setattr(promote, "key_exists", lambda key: True)
    monkeypatch.setattr(
        promote,
        "load_validation_report",
        lambda run_id: {
            "validated_at_utc": "2026-04-10T11:00:00+00:00",
            "required_artifacts_ok": True,
            "eval_thresholds_ok": True,
            "restore_validation_ok": True,
            "smoke_checks_ok": True,
        },
    )
    monkeypatch.setattr(
        promote,
        "load_registry",
        lambda: {
            "production": {
                "run_id": "run-1",
                "remote_prefix": "hybrid-recommender/runs/run-1",
                "promoted_at_utc": "old-time",
            },
            "candidate": {"run_id": "run-1"},
        },
    )
    monkeypatch.setattr(promote, "save_registry", lambda registry: saved.append(registry))

    result = promote.promote_run("run-1", require_validation=True)

    assert result["production"]["run_id"] == "run-1"
    assert result["production"]["promoted_at_utc"] == "2026-04-10T12:00:00+00:00"
    assert result["updated_at_utc"] == "2026-04-10T12:00:00+00:00"
    assert len(saved) == 1


def test_promote_run_moves_old_production_to_previous_and_clears_candidate(monkeypatch, fixed_time):
    saved = []

    history = [{"run_id": f"old-{i}", "promoted_at_utc": f"t{i}", "replaced_run_id": None} for i in range(25)]

    monkeypatch.setattr(promote, "key_exists", lambda key: True)
    monkeypatch.setattr(
        promote,
        "load_validation_report",
        lambda run_id: {
            "validated_at_utc": "2026-04-10T11:00:00+00:00",
            "required_artifacts_ok": True,
            "eval_thresholds_ok": True,
            "restore_validation_ok": True,
            "smoke_checks_ok": True,
        },
    )
    monkeypatch.setattr(
        promote,
        "load_registry",
        lambda: {
            "production": {
                "run_id": "run-old",
                "remote_prefix": "hybrid-recommender/runs/run-old",
                "promoted_at_utc": "2026-04-09T10:00:00+00:00",
            },
            "candidate": {
                "run_id": "run-1",
                "remote_prefix": "hybrid-recommender/runs/run-1",
            },
            "promotion_history": history,
        },
    )
    monkeypatch.setattr(promote, "save_registry", lambda registry: saved.append(registry))

    result = promote.promote_run("run-1", require_validation=True, cleanup_delay_hours=24)

    assert result["production"]["run_id"] == "run-1"
    assert result["previous_production"]["run_id"] == "run-old"
    assert result["previous_production"]["replaced_at_utc"] == "2026-04-10T12:00:00+00:00"
    assert result["previous"]["run_id"] == "run-old"
    assert result["candidate"] is None
    assert result["updated_at_utc"] == "2026-04-10T12:00:00+00:00"
    assert result["cleanup_not_before_utc"] == "2026-04-11T12:00:00+00:00"
    assert len(result["promotion_history"]) == 20
    assert result["promotion_history"][-1] == {
        "run_id": "run-1",
        "promoted_at_utc": "2026-04-10T12:00:00+00:00",
        "replaced_run_id": "run-old",
    }
    assert len(saved) == 1


def test_promote_run_sets_previous_fields_to_none_when_no_old_production(monkeypatch, fixed_time):
    saved = []

    monkeypatch.setattr(promote, "key_exists", lambda key: True)
    monkeypatch.setattr(
        promote,
        "load_validation_report",
        lambda run_id: {
            "validated_at_utc": "2026-04-10T11:00:00+00:00",
            "required_artifacts_ok": True,
            "eval_thresholds_ok": True,
            "restore_validation_ok": True,
            "smoke_checks_ok": True,
        },
    )
    monkeypatch.setattr(promote, "load_registry", lambda: {})
    monkeypatch.setattr(promote, "save_registry", lambda registry: saved.append(registry))

    result = promote.promote_run("run-1", require_validation=True)

    assert result["production"]["run_id"] == "run-1"
    assert result["previous_production"] is None
    assert result["previous"] is None
    assert len(saved) == 1


def test_main_parses_args_and_prints_result(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "promote_run_in_r2.py",
            "--run-id",
            "run-1",
            "--cleanup-delay-hours",
            "48",
            "--allow-unvalidated",
        ],
    )

    calls = {}

    def fake_promote_run(run_id, require_validation, cleanup_delay_hours):
        calls["run_id"] = run_id
        calls["require_validation"] = require_validation
        calls["cleanup_delay_hours"] = cleanup_delay_hours
        return {"status": "ok", "run_id": run_id}

    monkeypatch.setattr(promote, "promote_run", fake_promote_run)

    promote.main()

    captured = capsys.readouterr()

    assert calls == {
        "run_id": "run-1",
        "require_validation": False,
        "cleanup_delay_hours": 48,
    }
    assert json.loads(captured.out) == {"status": "ok", "run_id": "run-1"}

def test_utc_now_iso_returns_string():
    result = promote.utc_now_iso()
    assert isinstance(result, str)
    assert "T" in result    