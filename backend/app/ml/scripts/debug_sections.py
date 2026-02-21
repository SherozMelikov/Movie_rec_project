from __future__ import annotations

from collections import defaultdict
from sqlalchemy import text

from app.db.database import SessionLocal
from app.services.recommend_service import recommend_service


def _get_seeds(db, user_id: int):
    # same logic as service uses (quick view)
    rows = db.execute(text("""
        SELECT movie_id, MAX(ts) AS last_ts
        FROM interactions_all
        WHERE user_id=:uid
          AND (event_type='like' OR (event_type='rate' AND rating_value >= 4))
        GROUP BY movie_id
        ORDER BY last_ts DESC
        LIMIT 10;
    """), {"uid": user_id}).fetchall()
    return [int(r[0]) for r in rows]


def _get_exclude_ids(db, user_id: int):
    rows = db.execute(text("""
        SELECT DISTINCT movie_id
        FROM interactions_all
        WHERE user_id=:uid
        LIMIT 20000;
    """), {"uid": user_id}).fetchall()
    return {int(r[0]) for r in rows}


def _get_trending_truth(db, days: int = 7, limit: int = 20):
    rows = db.execute(text("""
        SELECT movie_id
        FROM interactions_all
        WHERE ts >= NOW() - (:days || ' days')::interval
        GROUP BY movie_id
        ORDER BY COUNT(*) DESC
        LIMIT :limit;
    """), {"days": days, "limit": limit}).fetchall()
    return [int(r[0]) for r in rows]


def main(user_id: int = 1, limit_per_section: int = 12):
    db = SessionLocal()
    try:
        print(f"\n=== Debug sections for user_id={user_id} ===")

        seeds = _get_seeds(db, user_id)
        exclude_ids = _get_exclude_ids(db, user_id)
        print("Seeds (recent likes / >=4 ratings):", seeds[:5])
        print("Exclude count:", len(exclude_ids))

        sections = recommend_service.get_sections_for_user(
            db=db,
            user_id=user_id,
            limit_per_section=limit_per_section,
            as_of_ts=None,
        )

        all_ids = []
        by_section = defaultdict(list)

        for s in sections:
            ids = [it.movie_id for it in s.items]
            by_section[s.title] = ids
            all_ids.extend(ids)
            print(f"\n[{s.title}] ({len(ids)} items)")
            print("First 6 ids:", ids[:6])
            # basic violations
            seen_violations = [mid for mid in ids if mid in exclude_ids]
            if seen_violations:
                print("❌ VIOLATION: contains already-interacted ids:", seen_violations[:10])

        # duplicates across sections
        dupes = {mid for mid in all_ids if all_ids.count(mid) > 1}
        if dupes:
            print("\n❌ VIOLATION: duplicates across sections:", list(dupes)[:20])
        else:
            print("\n✅ No duplicates across sections")

        # check trending overlaps "truth"
        trending_ids = by_section.get("Trending Now", [])
        if trending_ids:
            truth = _get_trending_truth(db, days=7, limit=50)
            overlap = len(set(trending_ids) & set(truth))
            print(f"\nTrending overlap with SQL top (7 days): {overlap}/{len(trending_ids)}")
            if overlap == 0:
                print("⚠️ Trending seems off (maybe low data or timestamps not recent).")

        # check Because You Liked doesn't include seed
        because = by_section.get("Because You Liked", [])
        if because and seeds:
            if seeds[0] in because:
                print("\n❌ VIOLATION: Because You Liked contains the seed movie:", seeds[0])
            else:
                print("\n✅ Because You Liked does not include the seed movie")

        print("\nDone.\n")

    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--user_id", type=int, default=1)
    p.add_argument("--limit", type=int, default=12)
    args = p.parse_args()
    main(user_id=args.user_id, limit_per_section=args.limit)
