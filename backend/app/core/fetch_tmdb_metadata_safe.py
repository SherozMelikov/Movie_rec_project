import os
import time
from datetime import datetime, timezone, date, timedelta

import requests
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import MovieMetadata

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = os.getenv("TMDB_BASE_URL", "https://api.themoviedb.org/3")

if not TMDB_API_KEY:
    raise ValueError("TMDB_API_KEY is missing. Set it in Railway Variables.")

# -------------------------------
# Controls (can override via Railway Variables)
# -------------------------------
REQUESTS_PER_BATCH = int(os.getenv("TMDB_REQUESTS_PER_BATCH", "35"))
BATCH_SLEEP_SECONDS = int(os.getenv("TMDB_BATCH_SLEEP_SECONDS", "10"))
COOLDOWN_HOURS = int(os.getenv("TMDB_COOLDOWN_HOURS", "24"))
TIMEOUT_SECONDS = int(os.getenv("TMDB_TIMEOUT_SECONDS", "10"))

BACKFILL_LIMIT = int(os.getenv("TMDB_BACKFILL_LIMIT", "5000"))
COMMIT_EVERY = int(os.getenv("TMDB_COMMIT_EVERY", "25"))
SLEEP_ON_429_SECONDS = int(os.getenv("TMDB_429_SLEEP_SECONDS", "60"))


def parse_release_date(rd: str | None) -> date | None:
    if not rd:
        return None
    try:
        return date.fromisoformat(rd)
    except Exception:
        return None


def tmdb_movie_details(tmdb_id: int) -> tuple[int, dict | None]:
    """Return (status_code, json_or_none)."""
    url = f"{TMDB_BASE_URL}/movie/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY, "language": "en-US"}

    try:
        r = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
        if r.status_code != 200:
            return r.status_code, None
        return 200, r.json()
    except Exception:
        return 0, None


def backfill(limit: int):
    db: Session = SessionLocal()
    try:
        metas = (
            db.query(MovieMetadata)
            .filter(MovieMetadata.status.in_(["pending", "error"]))
            .order_by(
                MovieMetadata.last_checked_at.is_(None).desc(),
                MovieMetadata.last_checked_at.asc(),
            )
            .limit(limit)
            .all()
        )

        total = len(metas)
        print(f"🟢 Rows to process: {total}")

        calls = 0
        processed = 0
        found = 0
        skipped_cooldown = 0
        changed = 0

        for meta in metas:
            processed += 1
            now = datetime.now(timezone.utc)  # ✅ update timestamp per row

            if not meta.tmdb_id:
                meta.status = "not_found"
                meta.last_checked_at = now
                changed += 1
                continue

            if meta.last_checked_at and (now - meta.last_checked_at) < timedelta(hours=COOLDOWN_HOURS):
                skipped_cooldown += 1
                continue

            meta.last_checked_at = now
            changed += 1

            status_code, details = tmdb_movie_details(int(meta.tmdb_id))
            calls += 1

            # ✅ handle 429 (rate limit) properly
            if status_code == 429:
                print(f"⏳ 429 rate limit. Sleeping {SLEEP_ON_429_SECONDS}s then retrying once...")
                time.sleep(SLEEP_ON_429_SECONDS)
                status_code, details = tmdb_movie_details(int(meta.tmdb_id))
                calls += 1

            if not details:
                if status_code == 404:
                    meta.status = "not_found"
                else:
                    meta.status = "error"
                changed += 1
            else:
                meta.overview = details.get("overview")
                meta.poster_path = details.get("poster_path")
                meta.backdrop_path = details.get("backdrop_path")
                meta.release_date = parse_release_date(details.get("release_date"))
                meta.fetched_at = now
                meta.status = "found"
                found += 1
                changed += 1

            print(f"✅ [{processed}/{total}] movie_id={meta.movie_id} tmdb_id={meta.tmdb_id} status={meta.status}")

            if calls % REQUESTS_PER_BATCH == 0:
                print(f"💤 Sleeping {BATCH_SLEEP_SECONDS}s (batch pacing)...")
                time.sleep(BATCH_SLEEP_SECONDS)

            # ✅ commit in chunks (faster)
            if changed >= COMMIT_EVERY:
                db.commit()
                changed = 0

        if changed:
            db.commit()

        print("🎉 Done.")
        print(f"processed={processed} calls={calls} found={found} skipped_cooldown={skipped_cooldown}")

    finally:
        db.close()


if __name__ == "__main__":
    backfill(limit=BACKFILL_LIMIT)
