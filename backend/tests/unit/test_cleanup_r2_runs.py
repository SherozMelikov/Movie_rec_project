from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import app.ml.scripts.cleanup_r2_runs as cleanup


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def fixed_time(monkeypatch):
    monkeypatch.setattr(cleanup, "datetime", FixedDateTime)


def test_parse_iso_datetime_returns_none_for_invalid_value():
    assert cleanup.parse_iso_datetime(None) is None
    assert cleanup.parse_iso_datetime("") is None
    assert cleanup.parse_iso_datetime("not-a-date") is None


def test_cleanup_r2_runs_skips_when_cleanup_delay_not_elapsed(monkeypatch, fixed_time):
    monkeypatch.setattr(
        cleanup,
        "load_registry",
        lambda: {
            "cleanup_not_before_utc": "2026-04-21T12:00:00+00:00",
        },
    )

    result = cleanup.cleanup_r2_runs(dry_run=True, ignore_cleanup_delay=False)

    assert result["status"] == "skipped"
    assert result["reason"] == "cleanup delay window has not elapsed"
    assert result["cleanup_not_before_utc"] == "2026-04-21T12:00:00+00:00"
    assert result["seconds_until_cleanup_allowed"] > 0


def test_cleanup_r2_runs_identifies_deletable_runs_in_dry_run_mode(monkeypatch, fixed_time):
    monkeypatch.setattr(
        cleanup,
        "load_registry",
        lambda: {
            "production": {"run_id": "run-300"},
            "candidate": {"run_id": "run-250"},
            "previous_production": {"run_id": "run-200"},
            "previous": {"run_id": "run-200"},
            "cleanup_not_before_utc": "2026-04-19T12:00:00+00:00",
        },
    )
    monkeypatch.setattr(cleanup, "list_run_ids", lambda: ["run-100", "run-200", "run-250", "run-300"])
    monkeypatch.setattr(
        cleanup,
        "list_run_keys",
        lambda run_id: [f"hybrid-recommender/runs/{run_id}/file1", f"hybrid-recommender/runs/{run_id}/file2"],
    )

    result = cleanup.cleanup_r2_runs(dry_run=True, ignore_cleanup_delay=False)

    assert result["status"] == "success"
    assert result["dry_run"] is True
    assert result["keep_run_ids"] == ["run-200", "run-250", "run-300"]
    assert result["delete_run_ids"] == ["run-100"]
    assert result["total_runs_to_delete"] == 1
    assert result["total_keys_to_delete"] == 2
    assert result["deleted"] == []
    assert result["deleted_key_count"] == 0


def test_cleanup_r2_runs_keeps_protected_runs(monkeypatch, fixed_time):
    monkeypatch.setattr(
        cleanup,
        "load_registry",
        lambda: {
            "production": {"run_id": "run-prod"},
            "previous_production": {"run_id": "run-prev"},
            "previous": {"run_id": "run-prev"},
            "candidate": {"run_id": "run-cand"},
        },
    )
    monkeypatch.setattr(cleanup, "list_run_ids", lambda: ["run-old", "run-prev", "run-cand", "run-prod"])
    monkeypatch.setattr(cleanup, "list_run_keys", lambda run_id: [f"{run_id}/a"])

    result = cleanup.cleanup_r2_runs(dry_run=True, ignore_cleanup_delay=True)

    assert result["protected_slots"] == {
        "production": "run-prod",
        "previous_production": "run-prev",
        "previous": "run-prev",
        "candidate": "run-cand",
    }
    assert result["keep_run_ids"] == ["run-cand", "run-prev", "run-prod"]
    assert result["delete_run_ids"] == ["run-old"]


def test_cleanup_r2_runs_deletes_runs_when_apply_mode_enabled(monkeypatch, fixed_time):
    monkeypatch.setattr(
        cleanup,
        "load_registry",
        lambda: {
            "production": {"run_id": "run-prod"},
            "cleanup_not_before_utc": "2026-04-19T12:00:00+00:00",
        },
    )
    monkeypatch.setattr(cleanup, "list_run_ids", lambda: ["run-old-1", "run-old-2", "run-prod"])
    monkeypatch.setattr(
        cleanup,
        "list_run_keys",
        lambda run_id: [f"hybrid-recommender/runs/{run_id}/a", f"hybrid-recommender/runs/{run_id}/b"],
    )

    deleted_calls = []

    def fake_delete_keys(keys):
        deleted_calls.append(list(keys))
        return {"deleted": len(keys), "keys": keys}

    monkeypatch.setattr(cleanup, "delete_keys", fake_delete_keys)

    result = cleanup.cleanup_r2_runs(dry_run=False, ignore_cleanup_delay=False)

    assert result["status"] == "success"
    assert result["dry_run"] is False
    assert set(result["delete_run_ids"]) == {"run-old-1", "run-old-2"}
    assert result["total_runs_to_delete"] == 2
    assert result["deleted_key_count"] == 4
    assert len(result["deleted"]) == 2
    assert len(deleted_calls) == 2


def test_cleanup_r2_runs_can_ignore_cleanup_delay(monkeypatch, fixed_time):
    monkeypatch.setattr(
        cleanup,
        "load_registry",
        lambda: {
            "production": {"run_id": "run-prod"},
            "cleanup_not_before_utc": "2026-04-21T12:00:00+00:00",
        },
    )
    monkeypatch.setattr(cleanup, "list_run_ids", lambda: ["run-old", "run-prod"])
    monkeypatch.setattr(cleanup, "list_run_keys", lambda run_id: [f"{run_id}/a"])
    monkeypatch.setattr(cleanup, "delete_keys", lambda keys: {"deleted": len(keys), "keys": keys})

    result = cleanup.cleanup_r2_runs(dry_run=True, ignore_cleanup_delay=True)

    assert result["status"] == "success"
    assert result["ignore_cleanup_delay"] is True
    assert result["delete_run_ids"] == ["run-old"]