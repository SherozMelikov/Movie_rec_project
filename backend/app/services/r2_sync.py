from pathlib import Path
import boto3
from botocore.config import Config

from app.config import settings

APP_DIR = Path(__file__).resolve().parents[1]
LOCAL_ARTIFACTS_DIR = APP_DIR / "ml" / "artifacts"

ARTIFACTS = [
    ("artifacts/als/item_factors.npy", LOCAL_ARTIFACTS_DIR / "als" / "item_factors.npy"),
    ("artifacts/als/meta.json", LOCAL_ARTIFACTS_DIR / "als" / "meta.json"),
    ("artifacts/als/movie_id_to_idx.json", LOCAL_ARTIFACTS_DIR / "als" / "movie_id_to_idx.json"),
    ("artifacts/als/user_factors.npy", LOCAL_ARTIFACTS_DIR / "als" / "user_factors.npy"),
    ("artifacts/als/user_id_to_idx.json", LOCAL_ARTIFACTS_DIR / "als" / "user_id_to_idx.json"),

    ("artifacts/hnsw/meta.json", LOCAL_ARTIFACTS_DIR / "hnsw" / "meta.json"),
    ("artifacts/hnsw/movies_hnsw.bin", LOCAL_ARTIFACTS_DIR / "hnsw" / "movies_hnsw.bin"),

    ("artifacts/vectors/movie_ids.npy", LOCAL_ARTIFACTS_DIR / "vectors" / "movie_ids.npy"),
    ("artifacts/vectors/svd.joblib", LOCAL_ARTIFACTS_DIR / "vectors" / "svd.joblib"),
    ("artifacts/vectors/tfidf.joblib", LOCAL_ARTIFACTS_DIR / "vectors" / "tfidf.joblib"),
    ("artifacts/vectors/vectors.npy", LOCAL_ARTIFACTS_DIR / "vectors" / "vectors.npy"),
]

s3 = boto3.client(
    "s3",
    endpoint_url=settings.r2_endpoint,
    aws_access_key_id=settings.r2_access_key,
    aws_secret_access_key=settings.r2_secret_key,
    region_name="auto",
    config=Config(signature_version="s3v4"),
)


def sync_artifacts_from_r2(force: bool = False):
    print("Starting R2 sync...")

    for r2_key, local_path in ARTIFACTS:
        if not local_path.exists() or force:
            print(f"Downloading {r2_key} → {local_path}")
            local_path.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(settings.r2_bucket, r2_key, str(local_path))
        else:
            print(f"Skipping existing {local_path}")

    print("R2 sync completed.")