# backend/app/workers/tmdb_backfill_worker.py

import os
import time
import logging
from datetime import datetime, timezone, date, timedelta
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import MovieMetadata
from app.services.tmdb_client import tmdb_client

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("tmdb_backfill_worker")

# -------------------------------
# Worker settings (env-configurable)
# -------------------------------
REQUESTS_PER_BATCH = int(os.getenv("TMDB_REQ_BATCH", "35"))      # keep under 40
BATCH_SLEEP_SECONDS = int(os.getenv("TMDB_BATCH_SLEEP", "10"))   # sleep after each batch

COOLDOWN_HOURS = int(os.getenv("TMDB_COOLDOWN_HOURS", "24"))     # don't retry too often
PICK_LIMIT = int(os.getenv("TMDB_PICK_LIMIT", "2000"))           # rows per loop
LOOP_SLEEP_SECONDS = int(os.getenv("TMDB_LOOP_SLEEP", "30"))     # when no work


def parse_release_date(rd: str | None) -> date | None:
    if not rd:
        return None
    try:
        return date.fromisoformat(rd)
    except Exception:
        return None


def should_skip_due_to_cooldown(meta: MovieMetadata, now: datetime) -> bool:
    if not meta.last_checked_at:
        return False
    return (now - meta.last_checked_at) < timedelta(hours=COOLDOWN_HOURS)


def pick_batch(db: Session, limit: int):
    return (
        db.query(MovieMetadata)
        .filter(MovieMetadata.status.in_(["pending", "error"]))
        .order_by(
            MovieMetadata.last_checked_at.is_(None).desc(),
            MovieMetadata.last_checked_at.asc()
        )
        .limit(limit)
        .all()
    )


def run_once(limit: int = 2000) -> int:
    """
    Process one batch.
    Returns number of rows picked (0 => nothing to do).
    """
    db: Session = SessionLocal()
    try:
        metas = pick_batch(db, limit)
        total = len(metas)

        if total == 0:
            return 0

        log.info("Picked %d rows to process", total)

        now = datetime.now(timezone.utc)
        calls = 0
        processed = 0
        found = 0
        errors = 0
        skipped_cooldown = 0
        marked_not_found = 0

        for meta in metas:
            processed += 1

            # must have tmdb_id for this worker
            if not meta.tmdb_id:
                meta.status = "not_found"
                meta.last_checked_at = now
                db.commit()
                marked_not_found += 1
                continue

            # cooldown gate
            if should_skip_due_to_cooldown(meta, now):
                skipped_cooldown += 1
                continue

            # set last_checked_at BEFORE calling TMDb (prevents rapid retries)
            meta.last_checked_at = now
            db.commit()

            try:
                details = tmdb_client.movie_details(int(meta.tmdb_id))
                calls += 1

                meta.overview = details.get("overview")
                meta.poster_path = details.get("poster_path")
                meta.backdrop_path = details.get("backdrop_path")
                meta.release_date = parse_release_date(details.get("release_date"))
                meta.fetched_at = now
                meta.status = "found"
                db.commit()
                found += 1

            except Exception:
                meta.status = "error"
                db.commit()
                errors += 1

            log.info(
                "[%d/%d] movie_id=%s tmdb_id=%s status=%s",
                processed, total, meta.movie_id, meta.tmdb_id, meta.status
            )

            # rate limiting
            if calls % REQUESTS_PER_BATCH == 0:
                log.info("Rate-limit sleep: %ds", BATCH_SLEEP_SECONDS)
                time.sleep(BATCH_SLEEP_SECONDS)

        log.info(
            "Batch done: picked=%d processed=%d calls=%d found=%d errors=%d skipped_cooldown=%d marked_not_found=%d",
            total, processed, calls, found, errors, skipped_cooldown, marked_not_found
        )
        return total

    finally:
        db.close()


def main():
    log.info("TMDb backfill worker started (pick_limit=%d)", PICK_LIMIT)
    while True:
        n = run_once(limit=PICK_LIMIT)
        if n == 0:
            log.info("No pending/error rows. Sleeping %ds...", LOOP_SLEEP_SECONDS)
            time.sleep(LOOP_SLEEP_SECONDS)


if __name__ == "__main__":
    main()
