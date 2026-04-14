from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

ENV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
)
load_dotenv(ENV_PATH)

from app.ml.storage.r2_artifacts import (
    load_registry,
    save_registry,
    key_exists,
    download_json,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_ref(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "remote_prefix": f"hybrid-recommender/runs/{run_id}",
    }


def load_validation_report(run_id: str) -> dict:
    validation_key = f"hybrid-recommender/runs/{run_id}/validation_report.json"
    if not key_exists(validation_key):
        raise RuntimeError(
            f"Cannot promote run {run_id}: validation report not found in R2 at {validation_key}"
        )

    report = download_json(validation_key)
    if not report.get("eligible_for_promotion"):
        raise RuntimeError(
            f"Cannot promote run {run_id}: validation report exists but eligible_for_promotion=false"
        )
    return report


def promote_run(
    run_id: str,
    require_validation: bool = True,
    cleanup_delay_hours: int = 24,
) -> dict:
    manifest_key = f"hybrid-recommender/runs/{run_id}/r2_publish_manifest.json"
    if not key_exists(manifest_key):
        raise RuntimeError(
            f"Cannot promote run {run_id}: publish manifest not found in R2 at {manifest_key}"
        )

    validation_report = None
    if require_validation:
        validation_report = load_validation_report(run_id)

    registry = load_registry()
    now = utc_now_iso()

    old_production = registry.get("production")
    new_production = make_run_ref(run_id)
    new_production["promoted_at_utc"] = now

    if validation_report:
        new_production["validated_at_utc"] = validation_report.get("validated_at_utc")
        new_production["validation_summary"] = {
            "required_artifacts_ok": validation_report.get("required_artifacts_ok"),
            "eval_thresholds_ok": validation_report.get("eval_thresholds_ok"),
            "restore_validation_ok": validation_report.get("restore_validation_ok"),
            "smoke_checks_ok": validation_report.get("smoke_checks_ok"),
        }

    if old_production and old_production.get("run_id") == run_id:
        registry["production"] = new_production
        registry["updated_at_utc"] = now
        save_registry(registry)
        return registry

    if old_production is not None:
        previous = dict(old_production)
        previous["replaced_at_utc"] = now
        registry["previous_production"] = previous
        registry["previous"] = previous  # backward compatibility
    else:
        registry["previous_production"] = None
        registry["previous"] = None

    registry["production"] = new_production

    candidate = registry.get("candidate")
    if candidate and candidate.get("run_id") == run_id:
        registry["candidate"] = None

    history = registry.get("promotion_history") or []
    history.append(
        {
            "run_id": run_id,
            "promoted_at_utc": now,
            "replaced_run_id": old_production.get("run_id") if old_production else None,
        }
    )
    registry["promotion_history"] = history[-20:]

    registry["cleanup_not_before_utc"] = (
        datetime.now(timezone.utc) + timedelta(hours=cleanup_delay_hours)
    ).isoformat()

    registry["updated_at_utc"] = now
    save_registry(registry)
    return registry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--allow-unvalidated", action="store_true")
    parser.add_argument("--cleanup-delay-hours", type=int, default=24)
    args = parser.parse_args()

    result = promote_run(
        run_id=args.run_id,
        require_validation=not args.allow_unvalidated,
        cleanup_delay_hours=args.cleanup_delay_hours,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()