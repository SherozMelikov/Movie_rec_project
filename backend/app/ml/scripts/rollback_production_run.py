from __future__ import annotations

import json
from datetime import datetime, timezone

from app.ml.storage.r2_artifacts import load_registry, save_registry


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def rollback_to_previous() -> dict:
    registry = load_registry()

    current = registry.get("production")
    previous = registry.get("previous_production")

    if not previous or not previous.get("run_id"):
        raise RuntimeError("No previous_production available for rollback")

    now = utc_now_iso()

    # swap production ↔ previous
    new_production = dict(previous)
    new_production["rolled_back_at_utc"] = now

    new_previous = dict(current) if current else None
    if new_previous:
        new_previous["replaced_at_utc"] = now

    registry["production"] = new_production
    registry["previous_production"] = new_previous
    registry["previous"] = new_previous  # backward compatibility

    history = registry.get("promotion_history") or []
    history.append(
        {
            "run_id": new_production["run_id"],
            "rolled_back_at_utc": now,
            "replaced_run_id": current.get("run_id") if current else None,
        }
    )
    registry["promotion_history"] = history[-20:]

    registry["updated_at_utc"] = now

    save_registry(registry)
    return registry


def main():
    result = rollback_to_previous()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()