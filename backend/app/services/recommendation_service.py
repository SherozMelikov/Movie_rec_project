from sqlalchemy.orm import Session
from app.db.models import Movie, Rating, UserRecommendationCache
from app.db.database import SessionLocal
import threading
import pandas as pd
import logging
import json

logging.basicConfig(level=logging.INFO)

class RecommendationService:
    def __init__(self, model_loader):
        self.model_loader = model_loader

    def get_top_picks(self, user_id: int):
        db: Session = SessionLocal()
        cache = db.query(UserRecommendationCache).filter_by(user_id=user_id).first()
        db.close()

        if cache:
            logging.info(f"✅ Returning cached recommendations for user {user_id}")
            return {"user_id": user_id, "recommendations": cache.recommendations}  # ✅ no json.loads
        else:
            logging.info(f"⚠️ No cache found for user {user_id}, recomputing in background")
            threading.Thread(target=self._recompute, args=(user_id,), daemon=True).start()
            return {"user_id": user_id, "recommendations": []}


    def _recompute(self, user_id: int):
        print(f"🟢 Starting recomputation for user {user_id}")
        db: Session = SessionLocal()

        # Fetch user ratings
        ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
        if not ratings:
            print(f"⚠️ No ratings found for user {user_id}, skipping recomputation")
            db.close()
            return

        user_ratings = pd.DataFrame([{
            "user_id": r.user_id,
            "movie_id": r.movie_id,
            "rating": r.rating
        } for r in ratings])

        # Refresh CF model
        self.model_loader.refresh_cf_model()

        # Get hybrid recommendations
        recs = self.model_loader.hybrid.recommend(user_id=user_id, user_ratings=user_ratings, top_n=10)
        print(f"✅ Hybrid recommendations (movie_id: score): {recs}")

        # Fetch movies
        movie_ids = list(recs.keys())
        movies = db.query(Movie).filter(Movie.movie_id.in_(movie_ids)).all()

        rec_list = [{
            "movie_id": m.movie_id,
            "title": m.title,
            "genres": m.genres,
            "score": float(recs[m.movie_id])
        } for m in movies]

        print(f"✅ Final rec_list ready to cache: {rec_list}")

        # Update cache
        cache = db.query(UserRecommendationCache).filter_by(user_id=user_id).first()
        if cache:
            cache.recommendations = rec_list
            cache.is_stale = False
        else:
            cache = UserRecommendationCache(
                user_id=user_id,
                recommendations=rec_list,
                is_stale=False
            )
            db.add(cache)

        db.commit()
        db.close()
        print(f"✅ Cached recommendations updated for user {user_id}")
