# fetch_tmdb_metadata_safe.py
import os
import time
import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from backend.app.db.database import SessionLocal
from backend.app.db.models import MovieMetadata, Link

# -------------------------------
# Load .env
# -------------------------------
dotenv_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
)
load_dotenv(dotenv_path)

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not TMDB_API_KEY:
    raise ValueError("TMDB_API_KEY not found! Check your .env file path.")

TMDB_BASE_URL = "https://api.themoviedb.org/3/movie/{}"
REQUESTS_PER_BATCH = 40
BATCH_SLEEP_SECONDS = 10

# -------------------------------
# Fetch single movie metadata
# -------------------------------
def fetch_movie_metadata(tmdb_id: int) -> dict | None:
    """Fetch metadata for a single movie from TMDB."""
    url = TMDB_BASE_URL.format(tmdb_id)
    params = {"api_key": TMDB_API_KEY, "language": "en-US"}
    try:
        response = requests.get(url, params=params)
        if response.status_code != 200:
            print(f"⚠️ Failed to fetch TMDB ID {tmdb_id}: {response.status_code}")
            return None
        data = response.json()
        metadata = {
            "year": int(data["release_date"][:4]) if data.get("release_date") else None,
            "poster_url": f"https://image.tmdb.org/t/p/w500{data['poster_path']}" if data.get("poster_path") else None,
            "backdrop_url": f"https://image.tmdb.org/t/p/w780{data['backdrop_path']}" if data.get("backdrop_path") else None,
            "plot": data.get("overview"),
            "popularity": data.get("popularity"),
            "vote_average": data.get("vote_average")
        }
        return metadata
    except Exception as e:
        print(f"⚠️ Exception fetching TMDB ID {tmdb_id}: {e}")
        return None

# -------------------------------
# Update all movie metadata safely
# -------------------------------
def update_movie_metadata_safe():
    db: Session = SessionLocal()
    try:
        # Fetch all movies with TMDB IDs
        links = db.query(Link).filter(Link.tmdb_id.isnot(None)).all()
        total = len(links)
        print(f"🟢 Total movies to update: {total}")

        for i, link in enumerate(links, start=1):
            tmdb_id = link.tmdb_id
            movie_id = link.movie_id

            metadata = fetch_movie_metadata(tmdb_id)
            if metadata:
                # Upsert MovieMetadata
                obj = db.query(MovieMetadata).filter(MovieMetadata.movie_id == movie_id).first()
                if obj:
                    for k, v in metadata.items():
                        setattr(obj, k, v)
                else:
                    obj = MovieMetadata(movie_id=movie_id, **metadata)
                    db.add(obj)
                db.commit()
                print(f"✅ [{i}/{total}] Updated movie_id={movie_id} (TMDB {tmdb_id})")

            # Rate limiting: max 40 requests per 10 seconds
            if i % REQUESTS_PER_BATCH == 0:
                print(f"💤 Sleeping {BATCH_SLEEP_SECONDS}s to respect TMDB rate limit...")
                time.sleep(BATCH_SLEEP_SECONDS)

        print("🎉 All movie metadata updated successfully!")
    finally:
        db.close()

# -------------------------------
# Run script
# -------------------------------
if __name__ == "__main__":
    update_movie_metadata_safe()
