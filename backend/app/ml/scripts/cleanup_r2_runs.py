from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

ENV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
)
load_dotenv(ENV_PATH)

from app.ml.storage.r2_artifacts import (
    load_registry,
    list_run_ids,
    list_run_keys,
    delete_keys,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def cleanup_r2_runs(
    dry_run: bool = True,
    ignore_cleanup_delay: bool = False,
) -> dict:
    registry = load_registry()
    now = utc_now()

    cleanup_not_before_utc = registry.get("cleanup_not_before_utc")
    cleanup_not_before_dt = parse_iso_datetime(cleanup_not_before_utc)

    if cleanup_not_before_dt and now < cleanup_not_before_dt and not ignore_cleanup_delay:
        return {
            "dry_run": dry_run,
            "executed_at_utc": utc_now_iso(),
            "status": "skipped",
            "reason": "cleanup delay window has not elapsed",
            "cleanup_not_before_utc": cleanup_not_before_utc,
            "seconds_until_cleanup_allowed": int((cleanup_not_before_dt - now).total_seconds()),
        }

    keep_run_ids = set()
    protected_slots: dict[str, str | None] = {
        "production": None,
        "previous_production": None,
        "previous": None,
        "candidate": None,
    }

    for slot in ("production", "previous_production", "previous", "candidate"):
        entry = registry.get(slot)
        if entry and entry.get("run_id"):
            run_id = entry["run_id"]
            keep_run_ids.add(run_id)
            protected_slots[slot] = run_id

    all_run_ids = sorted(list_run_ids(), reverse=True)
    delete_run_ids = [run_id for run_id in all_run_ids if run_id not in keep_run_ids]

    runs_to_delete: list[dict] = []
    total_keys_to_delete = 0

    for run_id in delete_run_ids:
        keys = list_run_keys(run_id)
        runs_to_delete.append(
            {
                "run_id": run_id,
                "key_count": len(keys),
                "keys": keys,
            }
        )
        total_keys_to_delete += len(keys)

    deleted = []
    deleted_key_count = 0

    if not dry_run:
        for item in runs_to_delete:
            result = delete_keys(item["keys"])
            deleted.append(
                {
                    "run_id": item["run_id"],
                    "deleted_key_count": result["deleted"],
                }
            )
            deleted_key_count += result["deleted"]

    return {
        "dry_run": dry_run,
        "executed_at_utc": utc_now_iso(),
        "status": "success",
        "cleanup_not_before_utc": cleanup_not_before_utc,
        "ignore_cleanup_delay": ignore_cleanup_delay,
        "protected_slots": protected_slots,
        "keep_run_ids": sorted(keep_run_ids),
        "all_run_ids": all_run_ids,
        "delete_run_ids": delete_run_ids,
        "total_runs_to_delete": len(delete_run_ids),
        "total_keys_to_delete": total_keys_to_delete,
        "runs_to_delete": runs_to_delete,
        "deleted": deleted,
        "deleted_key_count": deleted_key_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually delete runs in R2")
    parser.add_argument(
        "--ignore-cleanup-delay",
        action="store_true",
        help="Ignore cleanup_not_before_utc and allow cleanup immediately",
    )
    args = parser.parse_args()

    result = cleanup_r2_runs(
        dry_run=not args.apply,
        ignore_cleanup_delay=args.ignore_cleanup_delay,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()