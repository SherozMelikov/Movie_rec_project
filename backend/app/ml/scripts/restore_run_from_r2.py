# backend/app/ml/scripts/restore_run_from_r2.py
# Run:
#   python -m app.ml.scripts.restore_run_from_r2 --run-id 2026-04-03T09-55-18Z
#   python -m app.ml.scripts.restore_run_from_r2 --production

from __future__ import annotations

import argparse
import json
import os

from dotenv import load_dotenv

ENV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
)
load_dotenv(ENV_PATH)

from app.ml.storage.r2_artifacts import download_json
from app.services.r2_restore_service import restore_run, restore_production_run


def resolve_run_id(run_id: str | None, use_production: bool) -> str:
    if use_production:
        production = download_json("hybrid-recommender/production.json")
        production_run_id = production.get("run_id")

        if not production_run_id:
            raise RuntimeError("production.json does not contain run_id")

        return production_run_id

    if not run_id:
        raise RuntimeError("Provide --run-id <RUN_ID> or use --production")

    return run_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore a saved artifact run from R2 into the live artifact folders."
    )
    parser.add_argument("--run-id", type=str, default=None, help="Specific run ID to restore from R2")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Restore the run pointed to by hybrid-recommender/production.json in R2",
    )

    args = parser.parse_args()

    if args.production:
        result = restore_production_run()
    else:
        run_id = resolve_run_id(args.run_id, args.production)
        result = restore_run(run_id)

    print("\n=== R2 RESTORE COMPLETE ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()