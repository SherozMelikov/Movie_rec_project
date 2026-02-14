# backend/app/workers/simulate_data.py
import random
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import User, Movie, Rating, Like

NUM_USERS = 10   # number of users to simulate
NUM_MOVIES = 15  # number of movies to simulate

def simulate_users_and_movies(db: Session):
    # --- Add users ---
    for i in range(1, NUM_USERS + 1):
        db.add(User(name=f"User {i}"))

    # --- Add movies ---
    for i in range(1, NUM_MOVIES + 1):
        db.add(Movie(title=f"Movie {i}"))

    db.commit()  # commit to generate IDs

    # Fetch the real IDs
    users = db.query(User).all()
    movies = db.query(Movie).all()

    # --- Simulate ratings and likes ---
    for user in users:
        for movie in movies:
            # 50% chance user rated the movie
            if random.random() > 0.5:
                score = random.randint(1, 5)
                db.add(Rating(user_id=user.id, movie_id=movie.id, score=score))
            # 30% chance user liked the movie
            if random.random() > 0.7:
                db.add(Like(user_id=user.id, movie_id=movie.id))

    db.commit()
    print(f"✅ Simulated {len(users)} users and {len(movies)} movies with ratings & likes.")


if __name__ == "__main__":
    db = SessionLocal()
    simulate_users_and_movies(db)
