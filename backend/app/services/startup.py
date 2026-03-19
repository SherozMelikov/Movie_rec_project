from __future__ import annotations

from app.config import settings
from app.services.als_store import als_store
from app.services.vector_index import vector_index


def run_startup() -> None:
    if settings.use_r2_artifacts:
        from app.services.r2_sync import sync_artifacts_from_r2
        sync_artifacts_from_r2(force=False)
        print("Artifacts synced from R2.")
    else:
        print("Using local artifacts for development.")

    als_store.load()
    vector_index.load()
    print("Artifacts loaded successfully.")