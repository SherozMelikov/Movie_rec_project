# backend/app/ml/scripts/run_pipeline.py
# Run:
#   python -m app.ml.scripts.run_pipeline

from __future__ import annotations

import json
import os
import shutil
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone

from app.ml.scripts.train_als import train_als
from app.ml.scripts.build_hnsw_artifacts import build_hnsw_artifacts
from app.ml.scripts.eval_all_models import evaluate, save_metrics


PIPELINE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "artifacts", "pipeline")
)
ARTIFACTS_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "artifacts")
)
RUNS_DIR = os.path.join(ARTIFACTS_ROOT, "runs")
LATEST_RUN_PATH = os.path.join(ARTIFACTS_ROOT, "latest_run.json")

os.makedirs(PIPELINE_DIR, exist_ok=True)
os.makedirs(RUNS_DIR, exist_ok=True)


@dataclass
class PipelineConfig:
    run_eval: bool = True
    min_hybrid_service_hitrate_at_20: float = 0.80
    require_full_coverage: bool = True
    fail_on_quality_gate: bool = True


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


def copy_file(src: str, dst: str) -> None:
    ensure_dir(os.path.dirname(dst))
    shutil.copy2(src, dst)


def copy_tree_contents(src_dir: str, dst_dir: str) -> None:
    if not os.path.exists(src_dir):
        raise FileNotFoundError(f"Source directory does not exist: {src_dir}")

    ensure_dir(dst_dir)

    for name in os.listdir(src_dir):
        src_path = os.path.join(src_dir, name)
        dst_path = os.path.join(dst_dir, name)

        if os.path.isdir(src_path):
            if os.path.exists(dst_path):
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)


def read_latest_metrics_summary(metrics: dict) -> dict:
    overall = metrics.get("overall_models", {})
    hybrid_service = overall.get("Hybrid_Service", {})
    hybrid_model = overall.get("Hybrid_Model", {})
    als = overall.get("ALS_FullCatalog", {})
    cbf = overall.get("CBF_Seeded", {})

    return {
        "ALS_FullCatalog": {
            "hitrate_at_20": als.get("hitrate_at_k"),
            "ndcg_at_20": als.get("ndcg_at_k"),
            "coverage_rate": als.get("coverage_rate"),
        },
        "CBF_Seeded": {
            "hitrate_at_20": cbf.get("hitrate_at_k"),
            "ndcg_at_20": cbf.get("ndcg_at_k"),
            "coverage_rate": cbf.get("coverage_rate"),
        },
        "Hybrid_Model": {
            "hitrate_at_20": hybrid_model.get("hitrate_at_k"),
            "ndcg_at_20": hybrid_model.get("ndcg_at_k"),
            "coverage_rate": hybrid_model.get("coverage_rate"),
        },
        "Hybrid_Service": {
            "hitrate_at_20": hybrid_service.get("hitrate_at_k"),
            "ndcg_at_20": hybrid_service.get("ndcg_at_k"),
            "coverage_rate": hybrid_service.get("coverage_rate"),
        },
    }


def evaluate_quality_gates(metrics: dict, config: PipelineConfig) -> tuple[bool, list[str]]:
    failures: list[str] = []

    overall = metrics.get("overall_models", {})
    hybrid_service = overall.get("Hybrid_Service", {})

    hs_hr = hybrid_service.get("hitrate_at_k")
    hs_cov = hybrid_service.get("coverage_rate")

    if hs_hr is None:
        failures.append("Hybrid_Service hitrate_at_k is missing")
    elif hs_hr < config.min_hybrid_service_hitrate_at_20:
        failures.append(
            f"Hybrid_Service HitRate@20 {hs_hr:.4f} < required {config.min_hybrid_service_hitrate_at_20:.4f}"
        )

    if config.require_full_coverage:
        if hs_cov is None:
            failures.append("Hybrid_Service coverage_rate is missing")
        elif hs_cov < 1.0:
            failures.append(f"Hybrid_Service coverage_rate {hs_cov:.4f} < required 1.0000")

    return len(failures) == 0, failures


def artifact_file_status() -> dict:
    expected = {
        "als_user_factors": os.path.join(ARTIFACTS_ROOT, "als", "user_factors.npy"),
        "als_item_factors": os.path.join(ARTIFACTS_ROOT, "als", "item_factors.npy"),
        "als_user_id_to_idx": os.path.join(ARTIFACTS_ROOT, "als", "user_id_to_idx.json"),
        "als_movie_id_to_idx": os.path.join(ARTIFACTS_ROOT, "als", "movie_id_to_idx.json"),
        "als_meta": os.path.join(ARTIFACTS_ROOT, "als", "meta.json"),
        "vectors_movie_ids": os.path.join(ARTIFACTS_ROOT, "vectors", "movie_ids.npy"),
        "vectors_vectors": os.path.join(ARTIFACTS_ROOT, "vectors", "vectors.npy"),
        "vectors_tfidf": os.path.join(ARTIFACTS_ROOT, "vectors", "tfidf.joblib"),
        "vectors_svd": os.path.join(ARTIFACTS_ROOT, "vectors", "svd.joblib"),
        "hnsw_index": os.path.join(ARTIFACTS_ROOT, "hnsw", "movies_hnsw.bin"),
        "hnsw_meta": os.path.join(ARTIFACTS_ROOT, "hnsw", "meta.json"),
    }

    return {
        key: {
            "path": path,
            "exists": os.path.exists(path),
        }
        for key, path in expected.items()
    }


def snapshot_run_artifacts(run_id: str, metrics_path: str | None = None) -> dict:
    run_dir = os.path.join(RUNS_DIR, run_id)
    ensure_dir(run_dir)

    live_als_dir = os.path.join(ARTIFACTS_ROOT, "als")
    live_vectors_dir = os.path.join(ARTIFACTS_ROOT, "vectors")
    live_hnsw_dir = os.path.join(ARTIFACTS_ROOT, "hnsw")

    run_als_dir = os.path.join(run_dir, "als")
    run_vectors_dir = os.path.join(run_dir, "vectors")
    run_hnsw_dir = os.path.join(run_dir, "hnsw")

    copy_tree_contents(live_als_dir, run_als_dir)
    copy_tree_contents(live_vectors_dir, run_vectors_dir)
    copy_tree_contents(live_hnsw_dir, run_hnsw_dir)

    copied = {
        "run_dir": run_dir,
        "als_dir": run_als_dir,
        "vectors_dir": run_vectors_dir,
        "hnsw_dir": run_hnsw_dir,
        "metrics_path": None,
    }

    if metrics_path and os.path.exists(metrics_path):
        dst_metrics = os.path.join(run_dir, "metrics.json")
        copy_file(metrics_path, dst_metrics)
        copied["metrics_path"] = dst_metrics

    return copied


def write_run_manifest(run_id: str, manifest: dict) -> str:
    run_dir = os.path.join(RUNS_DIR, run_id)
    ensure_dir(run_dir)

    run_manifest_path = os.path.join(run_dir, "manifest.json")
    write_json(run_manifest_path, manifest)
    return run_manifest_path


def update_latest_run_pointer(
    run_id: str,
    manifest: dict,
    metrics_summary: dict | None,
) -> dict:
    pointer = {
        "run_id": run_id,
        "updated_at_utc": utc_now_iso(),
        "status": manifest.get("status"),
        "metrics_summary": metrics_summary,
        "paths": {
            "run_dir": os.path.join(RUNS_DIR, run_id),
            "als_dir": os.path.join(RUNS_DIR, run_id, "als"),
            "vectors_dir": os.path.join(RUNS_DIR, run_id, "vectors"),
            "hnsw_dir": os.path.join(RUNS_DIR, run_id, "hnsw"),
            "manifest_path": os.path.join(RUNS_DIR, run_id, "manifest.json"),
            "metrics_path": os.path.join(RUNS_DIR, run_id, "metrics.json"),
        },
    }
    write_json(LATEST_RUN_PATH, pointer)
    return pointer


def run_pipeline(config: PipelineConfig | None = None) -> dict:
    config = config or PipelineConfig()
    run_id = utc_run_id()
    started_at = utc_now_iso()

    manifest: dict = {
        "run_id": run_id,
        "started_at_utc": started_at,
        "finished_at_utc": None,
        "status": "running",
        "config": {
            "run_eval": config.run_eval,
            "min_hybrid_service_hitrate_at_20": config.min_hybrid_service_hitrate_at_20,
            "require_full_coverage": config.require_full_coverage,
            "fail_on_quality_gate": config.fail_on_quality_gate,
        },
        "steps": {
            "train_als": {"status": "pending", "details": None},
            "build_hnsw_artifacts": {"status": "pending", "details": None},
            "evaluate": {"status": "pending", "details": None},
            "quality_gate": {"status": "pending", "details": None},
        },
        "artifacts": {},
        "metrics_summary": None,
        "run_snapshot": None,
        "latest_pointer": None,
        "errors": [],
    }

    pipeline_manifest_path = os.path.join(PIPELINE_DIR, f"pipeline_run_{run_id}.json")
    latest_pipeline_manifest_path = os.path.join(PIPELINE_DIR, "latest_pipeline_run.json")

    metrics = None
    metrics_path = None

    try:
        print(f"=== PIPELINE START: {run_id} ===")

        print("\n[1/4] Training ALS artifacts...")
        manifest["steps"]["train_als"]["status"] = "running"
        als_info = train_als()
        manifest["steps"]["train_als"]["status"] = "ok"
        manifest["steps"]["train_als"]["details"] = als_info

        print("\n[2/4] Building vector + HNSW artifacts...")
        manifest["steps"]["build_hnsw_artifacts"]["status"] = "running"
        hnsw_info = build_hnsw_artifacts()
        manifest["steps"]["build_hnsw_artifacts"]["status"] = "ok"
        manifest["steps"]["build_hnsw_artifacts"]["details"] = hnsw_info

        manifest["artifacts"] = artifact_file_status()

        if config.run_eval:
            print("\n[3/4] Running evaluation...")
            manifest["steps"]["evaluate"]["status"] = "running"
            metrics = evaluate()
            metrics_path = save_metrics(metrics)
            manifest["steps"]["evaluate"]["status"] = "ok"
            manifest["steps"]["evaluate"]["details"] = {
                "saved_metrics_path": metrics_path,
            }
            manifest["metrics_summary"] = read_latest_metrics_summary(metrics)
        else:
            manifest["steps"]["evaluate"]["status"] = "skipped"
            manifest["steps"]["evaluate"]["details"] = {"reason": "run_eval=False"}

        print("\n[4/4] Checking quality gates...")
        manifest["steps"]["quality_gate"]["status"] = "running"
        if metrics is not None:
            passed, failures = evaluate_quality_gates(metrics, config)
            manifest["steps"]["quality_gate"]["status"] = "ok" if passed else "failed"
            manifest["steps"]["quality_gate"]["details"] = {
                "passed": passed,
                "failures": failures,
            }

            if not passed and config.fail_on_quality_gate:
                raise RuntimeError("Quality gate failed: " + " | ".join(failures))
        else:
            manifest["steps"]["quality_gate"]["status"] = "skipped"
            manifest["steps"]["quality_gate"]["details"] = {"reason": "no metrics available"}

        print("\n[artifact snapshot] Saving versioned run artifacts...")
        snapshot_info = snapshot_run_artifacts(run_id=run_id, metrics_path=metrics_path)
        manifest["run_snapshot"] = snapshot_info

        # IMPORTANT: mark success before writing run manifest and latest pointer
        manifest["status"] = "success"

        run_manifest_path_in_run = write_run_manifest(run_id=run_id, manifest=manifest)

        latest_pointer = update_latest_run_pointer(
            run_id=run_id,
            manifest=manifest,
            metrics_summary=manifest["metrics_summary"],
        )
        manifest["latest_pointer"] = latest_pointer

        # rewrite run manifest after latest pointer is attached
        write_json(run_manifest_path_in_run, manifest)

        return manifest

    except Exception as e:
        manifest["status"] = "failed"
        manifest["errors"].append(
            {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc(),
            }
        )
        return manifest

    finally:
        manifest["finished_at_utc"] = utc_now_iso()
        write_json(pipeline_manifest_path, manifest)
        write_json(latest_pipeline_manifest_path, manifest)

        print("\n=== PIPELINE FINISHED ===")
        print("status:", manifest["status"])
        print("manifest:", pipeline_manifest_path)

        if manifest["metrics_summary"] is not None:
            print("\nMetrics summary:")
            print(json.dumps(manifest["metrics_summary"], indent=2))


if __name__ == "__main__":
    result = run_pipeline()
    if result["status"] != "success":
        raise SystemExit(1)