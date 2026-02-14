import random
from sqlalchemy import text
from app.db.database import SessionLocal

GENRES = [
    "Action", "Adventure", "Animation", "Children", "Comedy", "Crime",
    "Documentary", "Drama", "Fantasy", "Film-Noir", "Horror", "Mystery",
    "Romance", "Sci-Fi", "Thriller", "War", "Western"
]

# tweak
MIN_GENRES = 3
MAX_GENRES = 5
MIN_MOVIES = 5
MAX_MOVIES = 10

# cap how many movies we sample per genre (performance guard)
MAX_POOL_PER_GENRE = 5000


def get_synthetic_user_ids(db):
    rows = db.execute(text("""
        SELECT user_id
        FROM users
        WHERE username LIKE 'synthetic_%'
    """)).fetchall()
    return [int(r[0]) for r in rows]


def fetch_movie_pool_for_genre(db, genre: str, limit: int):
    rows = db.execute(text("""
        SELECT movie_id
        FROM movies
        WHERE genres ILIKE :pattern
        LIMIT :limit
    """), {"pattern": f"%{genre}%", "limit": limit}).fetchall()
    return [int(r[0]) for r in rows]


def upsert_onboarding(db, user_id: int, favorite_genres: list[str]):
    # Insert or update onboarding row
    db.execute(text("""
        INSERT INTO user_onboarding (user_id, favorite_genres, completed_at)
        VALUES (:user_id, :favorite_genres, NOW())
        ON CONFLICT (user_id)
        DO UPDATE SET favorite_genres = EXCLUDED.favorite_genres,
                      completed_at = NOW();
    """), {"user_id": user_id, "favorite_genres": favorite_genres})


def replace_onboarding_movies(db, user_id: int, picked_movie_ids: list[int]):
    # Clear and insert (simple & safe for dev)
    db.execute(text("""
        DELETE FROM user_onboarding_movies WHERE user_id = :user_id
    """), {"user_id": user_id})

    # Insert picks
    for mid in picked_movie_ids:
        db.execute(text("""
            INSERT INTO user_onboarding_movies (user_id, movie_id, created_at)
            VALUES (:user_id, :movie_id, NOW())
            ON CONFLICT (user_id, movie_id) DO NOTHING;
        """), {"user_id": user_id, "movie_id": mid})


def main():
    random.seed(42)
    db = SessionLocal()

    try:
        user_ids = get_synthetic_user_ids(db)
        print(f"Found synthetic users: {len(user_ids)}")

        # Cache pools per genre so we don’t query 2000 times
        pools = {}

        created = 0
        for user_id in user_ids:
            gcount = random.randint(MIN_GENRES, MAX_GENRES)
            favorite_genres = random.sample(GENRES, k=gcount)

            # Build candidate pool from those genres
            candidate_ids = set()
            for g in favorite_genres:
                if g not in pools:
                    pools[g] = fetch_movie_pool_for_genre(db, g, MAX_POOL_PER_GENRE)
                candidate_ids.update(pools[g])

            candidate_ids = list(candidate_ids)
            if len(candidate_ids) < MIN_MOVIES:
                # skip if not enough candidates (rare)
                continue

            mcount = random.randint(MIN_MOVIES, MAX_MOVIES)
            picked_movie_ids = random.sample(candidate_ids, k=min(mcount, len(candidate_ids)))

            upsert_onboarding(db, user_id, favorite_genres)
            replace_onboarding_movies(db, user_id, picked_movie_ids)

            created += 1

            # commit in chunks
            if created % 200 == 0:
                db.commit()
                print(f"Processed {created} users...")

        db.commit()
        print(f"Done. Created/updated onboarding for {created} users.")

        print("Verify with:")
        print("  SELECT COUNT(*) FROM user_onboarding;")
        print("  SELECT COUNT(*) FROM user_onboarding_movies;")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
