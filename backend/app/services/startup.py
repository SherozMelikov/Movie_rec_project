from __future__ import annotations

import threading
import time

from app.config import settings
from app.services.als_store import als_store
from app.services.vector_index import vector_index
from app.services.r2_restore_service import ensure_production_run_restored

_REFRESH_INTERVAL_SECONDS = 30  # use 300 on Render later


def _reload_runtime_artifacts() -> None:
    als_store.load()
    vector_index.load()
    print("Artifacts loaded successfully.")


def _refresh_loop() -> None:
    print(f"Background refresh loop started. Interval={_REFRESH_INTERVAL_SECONDS}s")

    while True:
        try:
            if settings.use_r2_artifacts:
                result = ensure_production_run_restored(force=False)

                if result.get("status") != "noop":
                    print(f"Background refresh detected change: {result}")
                else:
                    print(f"Background refresh: no change ({result.get('run_id')})")
            else:
                print("Background refresh skipped: USE_R2_ARTIFACTS is false")

        except Exception as e:
            print(f"Background refresh failed: {e}")

        time.sleep(_REFRESH_INTERVAL_SECONDS)


def _start_background_refresh_thread() -> None:
    if not settings.use_r2_artifacts:
        return

    thread = threading.Thread(
        target=_refresh_loop,
        name="artifact-refresh-loop",
        daemon=True,
    )
    thread.start()
    print("Background artifact refresh thread started.")


def run_startup() -> None:
    if settings.use_r2_artifacts:
        result = ensure_production_run_restored(force=False)
        print(f"Production artifacts restore result: {result}")

        # Only load manually if restore service did not perform a restore
        if result.get("status") == "noop":
            _reload_runtime_artifacts()
    else:
        print("Using local artifacts for development.")
        _reload_runtime_artifacts()

    _start_background_refresh_thread()