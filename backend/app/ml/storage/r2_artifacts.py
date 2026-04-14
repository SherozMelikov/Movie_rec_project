from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from botocore.exceptions import ClientError

from app.ml.storage.r2_client import get_r2_client, get_r2_bucket


REGISTRY_KEY = "hybrid-recommender/registry.json"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_files(root: str):
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            yield os.path.join(dirpath, filename)


def upload_json(key: str, data: dict) -> None:
    s3 = get_r2_client()
    bucket = get_r2_bucket()
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def download_json(key: str) -> dict:
    s3 = get_r2_client()
    bucket = get_r2_bucket()
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read().decode("utf-8"))


def key_exists(key: str) -> bool:
    s3 = get_r2_client()
    bucket = get_r2_bucket()
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def download_json_if_exists(key: str) -> dict | None:
    if not key_exists(key):
        return None
    return download_json(key)


def default_registry() -> dict:
    return {
        "production": None,
        "previous": None,
        "candidate": None,
        "updated_at_utc": None,
    }


def load_registry() -> dict:
    registry = download_json_if_exists(REGISTRY_KEY)
    if registry is None:
        return default_registry()
    return registry


def save_registry(registry: dict) -> None:
    upload_json(REGISTRY_KEY, registry)


def upload_run_directory(local_run_dir: str, remote_prefix: str) -> dict:
    s3 = get_r2_client()
    bucket = get_r2_bucket()

    uploaded_files = []

    for abs_path in iter_files(local_run_dir):
        rel_path = os.path.relpath(abs_path, local_run_dir).replace("\\", "/")
        key = f"{remote_prefix.rstrip('/')}/{rel_path}"

        s3.upload_file(abs_path, bucket, key)

        uploaded_files.append({
            "relative_path": rel_path,
            "key": key,
            "size": os.path.getsize(abs_path),
            "sha256": sha256_file(abs_path),
        })

    return {
        "remote_prefix": remote_prefix,
        "files": uploaded_files,
    }


def download_file(key: str, local_path: str) -> None:
    s3 = get_r2_client()
    bucket = get_r2_bucket()
    ensure_dir(os.path.dirname(local_path))
    s3.download_file(bucket, key, local_path)


def list_keys(prefix: str) -> list[str]:
    s3 = get_r2_client()
    bucket = get_r2_bucket()

    keys: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            keys.append(item["Key"])

    return keys


def delete_keys(keys: list[str]) -> dict:
    if not keys:
        return {"deleted": 0, "keys": []}

    s3 = get_r2_client()
    bucket = get_r2_bucket()

    deleted: list[str] = []

    for i in range(0, len(keys), 1000):
        batch = keys[i:i + 1000]
        s3.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": k} for k in batch]},
        )
        deleted.extend(batch)

    return {
        "deleted": len(deleted),
        "keys": deleted,
    }


def list_run_ids(prefix: str = "hybrid-recommender/runs/") -> list[str]:
    keys = list_keys(prefix)
    run_ids = set()

    for key in keys:
        remainder = key[len(prefix):]
        parts = remainder.split("/", 1)
        if parts and parts[0]:
            run_ids.add(parts[0])

    return sorted(run_ids)


def list_run_keys(run_id: str) -> list[str]:
    return list_keys(f"hybrid-recommender/runs/{run_id}/")