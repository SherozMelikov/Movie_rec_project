# backend/app/ml/scripts/restore_run.py
# Run:
#   python -m app.ml.scripts.restore_run --run-id 2026-04-03T09-55-18Z
#   python -m app.ml.scripts.restore_run --latest

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone


ARTIFACTS_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "artifacts")
)

RUNS_DIR = os.path.join(ARTIFACTS_ROOT, "runs")
LATEST_RUN_PATH = os.path.join(ARTIFACTS_ROOT, "latest_run.json")

LIVE_ALS_DIR = os.path.join(ARTIFACTS_ROOT, "als")
LIVE_VECTORS_DIR = os.path.join(ARTIFACTS_ROOT, "vectors")
LIVE_HNSW_DIR = os.path.join(ARTIFACTS_ROOT, "hnsw")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: dict) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def clear_dir_contents(path: str) -> None:
    ensure_dir(path)
    for name in os.listdir(path):
        target = os.path.join(path, name)
        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)


def copy_tree_contents(src_dir: str, dst_dir: str) -> None:
    if not os.path.exists(src_dir):
        raise FileNotFoundError(f"Source directory does not exist: {src_dir}")

    clear_dir_contents(dst_dir)

    for name in os.listdir(src_dir):
        src_path = os.path.join(src_dir, name)
        dst_path = os.path.join(dst_dir, name)

        if os.path.isdir(src_path):
            shutil.copytree(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)


def validate_run_dir(run_dir: str) -> dict:
    paths = {
        "run_dir": run_dir,
        "als_dir": os.path.join(run_dir, "als"),
        "vectors_dir": os.path.join(run_dir, "vectors"),
        "hnsw_dir": os.path.join(run_dir, "hnsw"),
        "manifest_path": os.path.join(run_dir, "manifest.json"),
        "metrics_path": os.path.join(run_dir, "metrics.json"),
    }

    checks = {
        key: {
            "path": path,
            "exists": os.path.exists(path),
        }
        for key, path in paths.items()
    }

    valid = (
        checks["als_dir"]["exists"]
        and checks["vectors_dir"]["exists"]
        and checks["hnsw_dir"]["exists"]
        and checks["manifest_path"]["exists"]
    )

    return {
        "paths": paths,
        "checks": checks,
        "valid": valid,
    }


def resolve_run_id(run_id: str | None, use_latest: bool) -> str:
    if use_latest:
        if not os.path.exists(LATEST_RUN_PATH):
            raise FileNotFoundError(f"latest_run.json not found: {LATEST_RUN_PATH}")

        latest = read_json(LATEST_RUN_PATH)
        latest_run_id = latest.get("run_id")

        if not latest_run_id:
            raise RuntimeError("latest_run.json does not contain run_id")

        return latest_run_id

    if not run_id:
        raise RuntimeError("Provide --run-id <RUN_ID> or use --latest")

    return run_id


def restore_run(run_id: str) -> dict:
    run_dir = os.path.join(RUNS_DIR, run_id)
    validation = validate_run_dir(run_dir)

    if not validation["valid"]:
        raise RuntimeError(
            f"Run directory is incomplete or invalid: {run_dir}\n"
            f"Checks: {json.dumps(validation['checks'], indent=2)}"
        )

    src_als_dir = validation["paths"]["als_dir"]
    src_vectors_dir = validation["paths"]["vectors_dir"]
    src_hnsw_dir = validation["paths"]["hnsw_dir"]

    ensure_dir(LIVE_ALS_DIR)
    ensure_dir(LIVE_VECTORS_DIR)
    ensure_dir(LIVE_HNSW_DIR)

    copy_tree_contents(src_als_dir, LIVE_ALS_DIR)
    copy_tree_contents(src_vectors_dir, LIVE_VECTORS_DIR)
    copy_tree_contents(src_hnsw_dir, LIVE_HNSW_DIR)

    restore_log = {
        "restored_run_id": run_id,
        "restored_at_utc": utc_now_iso(),
        "source_run_dir": run_dir,
        "live_paths": {
            "als": LIVE_ALS_DIR,
            "vectors": LIVE_VECTORS_DIR,
            "hnsw": LIVE_HNSW_DIR,
        },
    }

    restore_log_path = os.path.join(run_dir, "restore_log.json")
    write_json(restore_log_path, restore_log)

    return {
        "status": "success",
        "run_id": run_id,
        "source_run_dir": run_dir,
        "restore_log_path": restore_log_path,
        "live_paths": restore_log["live_paths"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore a saved artifact run into the live artifact folders."
    )
    parser.add_argument("--run-id", type=str, default=None, help="Specific run ID to restore")
    parser.add_argument("--latest", action="store_true", help="Restore the run pointed to by latest_run.json")

    args = parser.parse_args()

    run_id = resolve_run_id(args.run_id, args.latest)
    result = restore_run(run_id)

    print("\n=== RESTORE COMPLETE ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()