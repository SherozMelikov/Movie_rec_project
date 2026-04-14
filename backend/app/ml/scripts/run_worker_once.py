# backend/app/ml/scripts/run_worker_once.py
# Run:
#   python -m app.ml.scripts.run_worker_once

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone

from app.ml.scripts.publish_run_to_r2 import publish_run
from app.ml.scripts.promote_run_in_r2 import promote_run
from app.ml.scripts.run_pipeline import run_pipeline, PipelineConfig
from app.ml.storage.r2_artifacts import upload_json
from app.services.smoke_checks import run_smoke_checks
from app.services.r2_restore_service import (
    download_run_into_cache,
    validate_cached_run_dir,
    validate_cached_run_for_restore,
)

AUTO_PROMOTE_IF_VALID = os.getenv("AUTO_PROMOTE_IF_VALID", "false").lower() == "true"

ARTIFACTS_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "artifacts")
)
WORKER_DIR = os.path.join(ARTIFACTS_ROOT, "worker")
LOCK_PATH = os.path.join(WORKER_DIR, "worker.lock")
LATEST_WORKER_RUN_PATH = os.path.join(WORKER_DIR, "latest_worker_run.json")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json(path: str, data: dict) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def acquire_lock() -> dict:
    ensure_dir(WORKER_DIR)

    if os.path.exists(LOCK_PATH):
        try:
            existing = read_json(LOCK_PATH)
        except Exception:
            existing = {"error": "Failed to read existing lock file"}

        raise RuntimeError(
            f"Worker lock already exists: {LOCK_PATH}\n"
            f"Existing lock info: {json.dumps(existing, indent=2)}"
        )

    lock_data = {
        "created_at_utc": utc_now_iso(),
        "pid": os.getpid(),
        "script": "run_worker_once.py",
    }
    write_json(LOCK_PATH, lock_data)
    return lock_data


def release_lock() -> None:
    if os.path.exists(LOCK_PATH):
        os.remove(LOCK_PATH)


def summarize_pipeline_result(result: dict) -> dict:
    metrics_summary = result.get("metrics_summary") or {}
    hs = metrics_summary.get("Hybrid_Service") or {}
    hm = metrics_summary.get("Hybrid_Model") or {}
    als = metrics_summary.get("ALS_FullCatalog") or {}

    return {
        "pipeline_status": result.get("status"),
        "run_id": result.get("run_id"),
        "hybrid_service_hitrate_at_20": hs.get("hitrate_at_20"),
        "hybrid_service_ndcg_at_20": hs.get("ndcg_at_20"),
        "hybrid_service_coverage_rate": hs.get("coverage_rate"),
        "hybrid_model_hitrate_at_20": hm.get("hitrate_at_20"),
        "als_hitrate_at_20": als.get("hitrate_at_20"),
    }


def build_validation_report(
    run_id: str,
    pipeline_result: dict,
    artifact_validation: dict,
    restore_validation: dict,
    smoke_checks: dict,
) -> dict:
    report = {
        "run_id": run_id,
        "validated_at_utc": utc_now_iso(),
        "pipeline_status": pipeline_result.get("status"),
        "required_artifacts_ok": artifact_validation.get("valid") is True,
        "eval_thresholds_ok": pipeline_result.get("status") == "success",
        "restore_validation_ok": restore_validation.get("ok") is True,
        "smoke_checks_ok": smoke_checks.get("ok") is True,
        "artifact_validation": artifact_validation,
        "restore_validation": restore_validation,
        "smoke_checks": smoke_checks,
    }
    report["eligible_for_promotion"] = all(
        [
            report["pipeline_status"] == "success",
            report["required_artifacts_ok"],
            report["eval_thresholds_ok"],
            report["restore_validation_ok"],
            report["smoke_checks_ok"],
        ]
    )
    return report


def run_worker_once() -> dict:
    worker_run_id = utc_run_id()
    started_at = utc_now_iso()

    worker_manifest = {
        "worker_run_id": worker_run_id,
        "started_at_utc": started_at,
        "finished_at_utc": None,
        "status": "running",
        "lock": None,
        "pipeline_result": None,
        "pipeline_summary": None,
        "r2_publish": None,
        "artifact_validation": None,
        "restore_validation": None,
        "smoke_checks": None,
        "validation_report": None,
        "auto_promotion": None,
        "errors": [],
    }

    worker_log_path = os.path.join(WORKER_DIR, f"worker_run_{worker_run_id}.json")

    try:
        print(f"=== WORKER START: {worker_run_id} ===")

        lock_info = acquire_lock()
        worker_manifest["lock"] = lock_info

        pipeline_config = PipelineConfig(
            run_eval=True,
            min_hybrid_service_hitrate_at_20=0.80,
            require_full_coverage=True,
            fail_on_quality_gate=True,
        )

        print("\n[worker] Starting pipeline...")
        pipeline_result = run_pipeline(config=pipeline_config)

        worker_manifest["pipeline_result"] = {
            "run_id": pipeline_result.get("run_id"),
            "status": pipeline_result.get("status"),
            "finished_at_utc": pipeline_result.get("finished_at_utc"),
            "latest_pointer": pipeline_result.get("latest_pointer"),
            "run_snapshot": pipeline_result.get("run_snapshot"),
            "errors": pipeline_result.get("errors", []),
        }
        worker_manifest["pipeline_summary"] = summarize_pipeline_result(pipeline_result)

        if pipeline_result.get("status") != "success":
            worker_manifest["status"] = "failed"
            return worker_manifest

        run_id = pipeline_result.get("run_id")
        if not run_id:
            raise RuntimeError("Pipeline succeeded but run_id is missing")

        print(f"\n[worker] Publishing run to R2: {run_id}")
        publish_result = publish_run(run_id=run_id, set_as_candidate=True)
        worker_manifest["r2_publish"] = publish_result

        print(f"\n[worker] Downloading candidate into cache for validation: {run_id}")
        download_info = download_run_into_cache(run_id)

        artifact_validation = validate_cached_run_dir(download_info["local_run_dir"])
        worker_manifest["artifact_validation"] = artifact_validation

        restore_validation = validate_cached_run_for_restore(run_id)
        worker_manifest["restore_validation"] = restore_validation

        smoke_checks = run_smoke_checks(
            run_id=run_id,
            cached_run_dir=download_info["local_run_dir"],
        )
        worker_manifest["smoke_checks"] = smoke_checks

        validation_report = build_validation_report(
            run_id=run_id,
            pipeline_result=pipeline_result,
            artifact_validation=artifact_validation,
            restore_validation=restore_validation,
            smoke_checks=smoke_checks,
        )
        worker_manifest["validation_report"] = validation_report

        validation_key = f"hybrid-recommender/runs/{run_id}/validation_report.json"
        upload_json(validation_key, validation_report)

        if not validation_report["eligible_for_promotion"]:
            worker_manifest["status"] = "failed"
            worker_manifest["auto_promotion"] = {
                "status": "skipped",
                "reason": "candidate_not_eligible_for_promotion",
                "validation_key": validation_key,
            }
            return worker_manifest

        if AUTO_PROMOTE_IF_VALID:
            print(f"\n[worker] Auto-promoting validated candidate: {run_id}")
            promotion_result = promote_run(
                run_id=run_id,
                require_validation=True,
                cleanup_delay_hours=24,
            )
            worker_manifest["auto_promotion"] = {
                "status": "success",
                "run_id": run_id,
                "registry": promotion_result,
            }
        else:
            worker_manifest["auto_promotion"] = {
                "status": "skipped",
                "run_id": run_id,
                "reason": "AUTO_PROMOTE_IF_VALID is false",
                "eligible_for_promotion": True,
            }

        worker_manifest["status"] = "success"
        return worker_manifest

    except Exception as e:
        worker_manifest["status"] = "failed"
        worker_manifest["errors"].append(
            {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc(),
            }
        )
        return worker_manifest

    finally:
        worker_manifest["finished_at_utc"] = utc_now_iso()
        write_json(worker_log_path, worker_manifest)
        write_json(LATEST_WORKER_RUN_PATH, worker_manifest)

        release_lock()

        print("\n=== WORKER FINISHED ===")
        print("status:", worker_manifest["status"])
        print("worker log:", worker_log_path)

        summary = worker_manifest.get("pipeline_summary")
        if summary:
            print("\nPipeline summary:")
            print(json.dumps(summary, indent=2))

        r2_publish = worker_manifest.get("r2_publish")
        if r2_publish:
            print("\nR2 publish summary:")
            print(
                json.dumps(
                    {
                        "run_id": r2_publish.get("run_id"),
                        "remote_prefix": r2_publish.get("remote_prefix"),
                        "file_count": r2_publish.get("file_count"),
                    },
                    indent=2,
                )
            )

        auto_promotion = worker_manifest.get("auto_promotion")
        if auto_promotion:
            print("\nAuto-promotion summary:")
            print(json.dumps(auto_promotion, indent=2))


def main() -> None:
    result = run_worker_once()
    if result.get("status") != "success":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()