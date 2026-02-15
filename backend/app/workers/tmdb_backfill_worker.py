# app/workers/tmdb_backfill_worker.py
import os
import time
import logging
from datetime import datetime, timezone, timedelta, date

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import MovieMetadata
from app.services.tmdb_client import tmdb_client

logger = logging.getLogger("tmdb_backfill_worker")
logging.basicConfig(level=logging.INFO)

REQUESTS_PER_BATCH = int(os.getenv("TMDB_REQUESTS_PER_BATCH", "35"))
BATCH_SLEEP_SECONDS = int(os.getenv("TMDB_BATCH_SLEEP_SECONDS", "10"))
COOLDOWN_HOURS = int(os.getenv("TMDB_COOLDOWN_HOURS", "24"))
BACKFILL_LIMIT = int(os.getenv("TMDB_BACKFILL_LIMIT", "2000"))
COMMIT_EVERY = int(os.getenv("TMDB_COMMIT_EVERY", "25"))

SLEEP_WHEN_EMPTY_SECONDS = int(os.getenv("TMDB_EMPTY_SLEEP_SECONDS", "30"))


def parse_release_date(rd: str | None) -> date | None:
    if not rd:
        return None
    try:
        return date.fromisoformat(rd)
    except Exception:
        return None


def pick_batch(db: Session, limit: int) -> list[MovieMetadata]:
    return (
        db.query(MovieMetadata)
        .filter(MovieMetadata.status.in_(["pending", "error"]))
        .order_by(
            MovieMetadata.last_checked_at.is_(None).desc(),
            MovieMetadata.last_checked_at.asc(),
        )
        .limit(limit)
        .all()
    )


def run_once(pick_limit: int):
    db: Session = SessionLocal()
    try:
        metas = pick_batch(db, pick_limit)
        if not metas:
            logger.info("No pending/error rows found.")
            return 0

        logger.info(f"Picked {len(metas)} rows to process")

        calls = 0
        processed = 0
        found = 0
        errors = 0
        skipped_cooldown = 0
        marked_not_found = 0
        changed_since_commit = 0

        for i, meta in enumerate(metas, start=1):
            processed += 1
            now = datetime.now(timezone.utc)

            # must have tmdb_id for this worker
            if not meta.tmdb_id:
                meta.status = "not_found"
                meta.last_checked_at = now
                marked_not_found += 1
                changed_since_commit += 1
                continue

            if meta.last_checked_at and (now - meta.last_checked_at) < timedelta(hours=COOLDOWN_HOURS):
                skipped_cooldown += 1
                continue

            meta.last_checked_at = now
            changed_since_commit += 1

            code, details = tmdb_client.movie_details(int(meta.tmdb_id))
            calls += 1

            if not details:
                if code == 404:
                    meta.status = "not_found"
                    marked_not_found += 1
                else:
                    meta.status = "error"
                    errors += 1
                changed_since_commit += 1
            else:
                meta.overview = details.get("overview")
                meta.poster_path = details.get("poster_path")
                meta.backdrop_path = details.get("backdrop_path")
                meta.release_date = parse_release_date(details.get("release_date"))
                meta.fetched_at = now
                meta.status = "found"
                found += 1
                changed_since_commit += 1

            logger.info(f"[{i}/{len(metas)}] movie_id={meta.movie_id} tmdb_id={meta.tmdb_id} status={meta.status}")

            if calls % REQUESTS_PER_BATCH == 0:
                logger.info(f"Rate-limit sleep: {BATCH_SLEEP_SECONDS}s")
                time.sleep(BATCH_SLEEP_SECONDS)

            if changed_since_commit >= COMMIT_EVERY:
                db.commit()
                changed_since_commit = 0

        if changed_since_commit:
            db.commit()

        logger.info(
            f"Batch done: picked={len(metas)} processed={processed} calls={calls} "
            f"found={found} errors={errors} skipped_cooldown={skipped_cooldown} marked_not_found={marked_not_found}"
        )
        return processed

    finally:
        db.close()


def main():
    logger.info(f"TMDb backfill worker started (pick_limit={BACKFILL_LIMIT})")
    while True:
        processed = run_once(BACKFILL_LIMIT)
        if processed == 0:
            time.sleep(SLEEP_WHEN_EMPTY_SECONDS)


if __name__ == "__main__":
    main()
