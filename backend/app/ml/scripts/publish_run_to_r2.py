# backend/app/ml/scripts/publish_run_to_r2.py
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
    upload_run_directory,
    upload_json,
    load_registry,
    save_registry,
)

ARTIFACTS_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "artifacts")
)
RUNS_DIR = os.path.join(ARTIFACTS_ROOT, "runs")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def publish_run(run_id: str, set_as_candidate: bool = True) -> dict:
    local_run_dir = os.path.join(RUNS_DIR, run_id)
    if not os.path.exists(local_run_dir):
        raise FileNotFoundError(f"Run directory not found: {local_run_dir}")

    remote_prefix = f"hybrid-recommender/runs/{run_id}"
    upload_result = upload_run_directory(local_run_dir, remote_prefix)

    publish_manifest = {
        "run_id": run_id,
        "published_at_utc": utc_now_iso(),
        "remote_prefix": remote_prefix,
        "file_count": len(upload_result["files"]),
        "files": upload_result["files"],
    }

    upload_json(f"{remote_prefix}/r2_publish_manifest.json", publish_manifest)

    registry_update = None

    if set_as_candidate:
        registry = load_registry()
        registry["candidate"] = {
            "run_id": run_id,
            "remote_prefix": remote_prefix,
            "uploaded_at_utc": utc_now_iso(),
        }
        registry["updated_at_utc"] = utc_now_iso()
        save_registry(registry)
        registry_update = registry

    return {
        "run_id": run_id,
        "remote_prefix": remote_prefix,
        "file_count": len(upload_result["files"]),
        "files": upload_result["files"],
        "registry": registry_update,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--no-set-candidate", action="store_true")
    args = parser.parse_args()

    result = publish_run(run_id=args.run_id, set_as_candidate=not args.no_set_candidate)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()