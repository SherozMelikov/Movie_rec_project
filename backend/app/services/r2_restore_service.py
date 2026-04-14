from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone

from app.ml.storage.r2_artifacts import download_json, download_file
from app.services.als_store import als_store
from app.services.vector_index import vector_index


APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ARTIFACTS_ROOT = os.path.join(APP_DIR, "ml", "artifacts")

CACHE_ROOT = os.path.join(ARTIFACTS_ROOT, "r2_cache")
STAGING_ROOT = os.path.join(ARTIFACTS_ROOT, "restore_staging")
BACKUP_ROOT = os.path.join(ARTIFACTS_ROOT, "restore_backup")

LIVE_ALS_DIR = os.path.join(ARTIFACTS_ROOT, "als")
LIVE_VECTORS_DIR = os.path.join(ARTIFACTS_ROOT, "vectors")
LIVE_HNSW_DIR = os.path.join(ARTIFACTS_ROOT, "hnsw")

LOCAL_R2_RESTORE_LOG_PATH = os.path.join(ARTIFACTS_ROOT, "latest_r2_restore.json")
LOCAL_ACTIVE_RUN_PATH = os.path.join(ARTIFACTS_ROOT, "active_production_run.json")

REQUIRED_RUNTIME_FILES = [
    "als/user_factors.npy",
    "als/item_factors.npy",
    "als/user_id_to_idx.json",
    "als/movie_id_to_idx.json",
    "vectors/movie_ids.npy",
    "vectors/vectors.npy",
    "hnsw/movies_hnsw.bin",
    "manifest.json",
    "r2_publish_manifest.json",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json(path: str, data: dict) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def remove_path_if_exists(path: str) -> None:
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)


def validate_cached_run_dir(run_dir: str) -> dict:
    file_checks = []
    missing_files = []

    for rel_path in REQUIRED_RUNTIME_FILES:
        abs_path = os.path.join(run_dir, rel_path)
        exists = os.path.exists(abs_path)
        file_checks.append(
            {
                "relative_path": rel_path,
                "path": abs_path,
                "exists": exists,
            }
        )
        if not exists:
            missing_files.append(rel_path)

    return {
        "run_dir": run_dir,
        "file_checks": file_checks,
        "missing_files": missing_files,
        "valid": len(missing_files) == 0,
    }


def validate_cached_run_for_restore(run_id: str) -> dict:
    cached_run_dir = os.path.join(CACHE_ROOT, run_id)
    validation = validate_cached_run_dir(cached_run_dir)

    if not validation["valid"]:
        return {
            "ok": False,
            "run_id": run_id,
            "reason": "missing_required_files",
            "missing_files": validation.get("missing_files", []),
        }

    als_dir = os.path.join(cached_run_dir, "als")
    vectors_dir = os.path.join(cached_run_dir, "vectors")
    hnsw_dir = os.path.join(cached_run_dir, "hnsw")

    try:
        als_summary = als_store.validate_dir(als_dir)
        vector_summary = vector_index.validate_dirs(vectors_dir, hnsw_dir)

        return {
            "ok": True,
            "run_id": run_id,
            "als": als_summary,
            "vectors": vector_summary,
        }
    except Exception as e:
        return {
            "ok": False,
            "run_id": run_id,
            "reason": "runtime_validation_failed",
            "error_type": type(e).__name__,
            "error_message": str(e),
        }


def get_registry() -> dict:
    return download_json("hybrid-recommender/registry.json")


def get_production_pointer() -> dict:
    registry = get_registry()
    production = registry.get("production")

    if not production or not production.get("run_id"):
        raise RuntimeError("registry.json does not contain a valid production run")

    return production


def get_local_active_run_id() -> str | None:
    if not os.path.exists(LOCAL_ACTIVE_RUN_PATH):
        return None

    try:
        data = read_json(LOCAL_ACTIVE_RUN_PATH)
        return data.get("run_id")
    except Exception:
        return None


def set_local_active_run(run_id: str) -> None:
    write_json(
        LOCAL_ACTIVE_RUN_PATH,
        {
            "run_id": run_id,
            "updated_at_utc": utc_now_iso(),
        },
    )


def download_run_into_cache(run_id: str) -> dict:
    remote_prefix = f"hybrid-recommender/runs/{run_id}"
    publish_manifest = download_json(f"{remote_prefix}/r2_publish_manifest.json")

    local_run_dir = os.path.join(CACHE_ROOT, run_id)
    ensure_dir(local_run_dir)
    clear_dir_contents(local_run_dir)

    write_json(os.path.join(local_run_dir, "r2_publish_manifest.json"), publish_manifest)

    downloaded_files: list[dict] = []

    for item in publish_manifest.get("files", []):
        relative_path = item["relative_path"]
        key = item["key"]
        local_path = os.path.join(local_run_dir, relative_path)

        download_file(key, local_path)

        downloaded_files.append(
            {
                "relative_path": relative_path,
                "key": key,
                "local_path": local_path,
            }
        )

    return {
        "run_id": run_id,
        "remote_prefix": remote_prefix,
        "local_run_dir": local_run_dir,
        "file_count": len(downloaded_files),
        "downloaded_files": downloaded_files,
        "publish_manifest": publish_manifest,
    }


def prepare_staging_from_cache(run_id: str) -> dict:
    cached_run_dir = os.path.join(CACHE_ROOT, run_id)
    validation = validate_cached_run_dir(cached_run_dir)

    if not validation["valid"]:
        raise RuntimeError(
            f"Cached R2 run directory is incomplete or invalid: {cached_run_dir}\n"
            f"Missing files: {json.dumps(validation['missing_files'], indent=2)}"
        )

    stage_root = os.path.join(STAGING_ROOT, run_id)
    remove_path_if_exists(stage_root)
    ensure_dir(stage_root)

    stage_als_dir = os.path.join(stage_root, "als")
    stage_vectors_dir = os.path.join(stage_root, "vectors")
    stage_hnsw_dir = os.path.join(stage_root, "hnsw")

    copy_tree_contents(os.path.join(cached_run_dir, "als"), stage_als_dir)
    copy_tree_contents(os.path.join(cached_run_dir, "vectors"), stage_vectors_dir)
    copy_tree_contents(os.path.join(cached_run_dir, "hnsw"), stage_hnsw_dir)

    # Validate from staging without touching live runtime state
    als_store.validate_dir(stage_als_dir)
    vector_index.validate_dirs(stage_vectors_dir, stage_hnsw_dir)

    return {
        "cached_run_dir": cached_run_dir,
        "stage_root": stage_root,
        "stage_als_dir": stage_als_dir,
        "stage_vectors_dir": stage_vectors_dir,
        "stage_hnsw_dir": stage_hnsw_dir,
    }


def restore_run_from_cache(run_id: str) -> dict:
    stage_info = prepare_staging_from_cache(run_id)

    ensure_dir(BACKUP_ROOT)
    backup_tag = f"{run_id}_{utc_now().strftime('%Y%m%dT%H%M%SZ')}"

    backup_root = os.path.join(BACKUP_ROOT, backup_tag)
    ensure_dir(backup_root)

    backup_als_dir = os.path.join(backup_root, "als")
    backup_vectors_dir = os.path.join(backup_root, "vectors")
    backup_hnsw_dir = os.path.join(backup_root, "hnsw")

    had_live_als = os.path.exists(LIVE_ALS_DIR)
    had_live_vectors = os.path.exists(LIVE_VECTORS_DIR)
    had_live_hnsw = os.path.exists(LIVE_HNSW_DIR)

    rollback_performed = False

    try:
        # Move current live dirs aside
        if had_live_als:
            os.rename(LIVE_ALS_DIR, backup_als_dir)
        if had_live_vectors:
            os.rename(LIVE_VECTORS_DIR, backup_vectors_dir)
        if had_live_hnsw:
            os.rename(LIVE_HNSW_DIR, backup_hnsw_dir)

        # Move staged dirs into live locations
        os.rename(stage_info["stage_als_dir"], LIVE_ALS_DIR)
        os.rename(stage_info["stage_vectors_dir"], LIVE_VECTORS_DIR)
        os.rename(stage_info["stage_hnsw_dir"], LIVE_HNSW_DIR)

        # Final live runtime load
        als_store.load(LIVE_ALS_DIR)
        vector_index.load(LIVE_VECTORS_DIR, LIVE_HNSW_DIR)

    except Exception as e:
        rollback_performed = True

        remove_path_if_exists(LIVE_ALS_DIR)
        remove_path_if_exists(LIVE_VECTORS_DIR)
        remove_path_if_exists(LIVE_HNSW_DIR)

        if had_live_als and os.path.exists(backup_als_dir):
            os.rename(backup_als_dir, LIVE_ALS_DIR)
        if had_live_vectors and os.path.exists(backup_vectors_dir):
            os.rename(backup_vectors_dir, LIVE_VECTORS_DIR)
        if had_live_hnsw and os.path.exists(backup_hnsw_dir):
            os.rename(backup_hnsw_dir, LIVE_HNSW_DIR)

        if had_live_als and had_live_vectors and had_live_hnsw:
            als_store.load(LIVE_ALS_DIR)
            vector_index.load(LIVE_VECTORS_DIR, LIVE_HNSW_DIR)

        raise RuntimeError(
            f"Failed to activate restored run {run_id}; rollback performed={rollback_performed}. "
            f"Original error: {type(e).__name__}: {e}"
        ) from e

    finally:
        remove_path_if_exists(stage_info["stage_root"])

    restore_log = {
        "restored_run_id": run_id,
        "restored_at_utc": utc_now_iso(),
        "source": "r2",
        "source_cached_run_dir": stage_info["cached_run_dir"],
        "live_paths": {
            "als": LIVE_ALS_DIR,
            "vectors": LIVE_VECTORS_DIR,
            "hnsw": LIVE_HNSW_DIR,
        },
        "backup_root": backup_root,
        "rollback_performed": rollback_performed,
    }

    write_json(LOCAL_R2_RESTORE_LOG_PATH, restore_log)

    cached_restore_log_path = os.path.join(stage_info["cached_run_dir"], "restore_log.json")
    write_json(cached_restore_log_path, restore_log)

    set_local_active_run(run_id)

    return {
        "status": "success",
        "run_id": run_id,
        "source": "r2",
        "source_cached_run_dir": stage_info["cached_run_dir"],
        "restore_log_path": cached_restore_log_path,
        "latest_restore_log_path": LOCAL_R2_RESTORE_LOG_PATH,
        "live_paths": restore_log["live_paths"],
        "backup_root": backup_root,
        "rollback_performed": rollback_performed,
    }


def restore_run(run_id: str) -> dict:
    download_info = download_run_into_cache(run_id)
    restore_result = restore_run_from_cache(run_id)

    return {
        "status": restore_result["status"],
        "run_id": run_id,
        "download": {
            "remote_prefix": download_info["remote_prefix"],
            "local_run_dir": download_info["local_run_dir"],
            "file_count": download_info["file_count"],
        },
        "restore": restore_result,
    }


def restore_production_run() -> dict:
    production = get_production_pointer()
    production_run_id = production["run_id"]
    return restore_run(production_run_id)


def ensure_production_run_restored(force: bool = False) -> dict:
    production = get_production_pointer()
    production_run_id = production["run_id"]
    local_run_id = get_local_active_run_id()

    if not force and local_run_id == production_run_id:
        return {
            "status": "noop",
            "reason": "local active run already matches production",
            "run_id": production_run_id,
        }

    return restore_run(production_run_id)