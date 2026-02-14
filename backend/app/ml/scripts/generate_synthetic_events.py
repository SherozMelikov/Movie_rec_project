import random
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import SessionLocal
from app.db.models import User, Movie
from app.core.security import hash_password

# Tweak these
NUM_USERS = 200
EVENTS_PER_USER = 60
LIKE_PROB = 0.12
RATE_PROB = 0.10
VIEW_PROB = 0.78  # should sum to 1 with others (approx)
MAX_MOVIES_PER_GENRE_POOL = 5000  # per genre candidates

GENRES = [
    "Action", "Adventure", "Animation", "Children", "Comedy", "Crime",
    "Documentary", "Drama", "Fantasy", "Film-Noir", "Horror", "Mystery",
    "Romance", "Sci-Fi", "Thriller", "War", "Western"
]

def pick_genres():
    return random.sample(GENRES, k=3)

def ensure_fake_users(db: Session, n: int) -> list[int]:
    # Create users synthetic_0001 ... synthetic_n
    ids = []
    for i in range(1, n + 1):
        username = f"synthetic_{i:04d}"
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            ids.append(existing.user_id)
            continue

        u = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=hash_password("password123"),
        )
        db.add(u)
        db.flush()  # get user_id without commit
        ids.append(u.user_id)
    db.commit()
    return ids

def fetch_movie_pool_for_genre(db: Session, genre: str, limit: int) -> list[int]:
    # Uses ILIKE on genres column
    rows = (
        db.query(Movie.movie_id)
        .filter(Movie.genres.ilike(f"%{genre}%"))
        .limit(limit)
        .all()
    )
    return [int(r[0]) for r in rows]

def insert_event(db: Session, user_id: int, movie_id: int, event_type: str, rating_value=None):
    db.execute(
        text("""
            INSERT INTO events (user_id, movie_id, event_type, rating_value)
            VALUES (:user_id, :movie_id, :event_type, :rating_value)
        """),
        {
            "user_id": user_id,
            "movie_id": movie_id,
            "event_type": event_type,
            "rating_value": rating_value,
        }
    )

def biased_rating() -> int:
    # More 4–5 than 1–2 (common in real apps)
    return random.choices([1,2,3,4,5], weights=[3,6,15,35,41], k=1)[0]

def main():
    random.seed(42)
    db = SessionLocal()

    try:
        user_ids = ensure_fake_users(db, NUM_USERS)

        # Precompute pools for a handful of genres to avoid repeated DB scans
        # (3 genres per user; this keeps it manageable)
        pools = {}

        total_events = 0

        for user_id in user_ids:
            fav_genres = pick_genres()

            # Build candidate pool = union of genre pools
            candidate_ids = []
            for g in fav_genres:
                if g not in pools:
                    pools[g] = fetch_movie_pool_for_genre(db, g, MAX_MOVIES_PER_GENRE_POOL)
                candidate_ids.extend(pools[g])

            candidate_ids = list(set(candidate_ids))
            if not candidate_ids:
                continue

            # For each user, simulate a session of events
            for _ in range(EVENTS_PER_USER):
                movie_id = random.choice(candidate_ids)

                r = random.random()
                if r < VIEW_PROB:
                    insert_event(db, user_id, movie_id, "view", None)
                elif r < VIEW_PROB + LIKE_PROB:
                    insert_event(db, user_id, movie_id, "like", None)
                else:
                    insert_event(db, user_id, movie_id, "rate", biased_rating())

                total_events += 1

            # Commit per user (safer for large runs)
            db.commit()

        print(f"Done. Inserted ~{total_events} synthetic events for {len(user_ids)} users.")
        print("Verify with: SELECT COUNT(*) FROM events;")

    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
