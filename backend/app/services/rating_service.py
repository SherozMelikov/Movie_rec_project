from backend.app.db.database import SessionLocal
from backend.app.db.models import Rating
import threading

class RatingService:
    def __init__(self, recommendation_service):
        self.recommendation_service = recommendation_service

    def add_rating(self, rating_data):
        """
        Save rating and trigger recomputation in the background.
        """
        db = SessionLocal()

        rating = Rating(
            user_id=rating_data.user_id,
            movie_id=rating_data.movie_id,
            rating=rating_data.rating
        )

        db.add(rating)
        db.commit()
        db.refresh(rating)
        db.close()

        # 🔥 Trigger background recomputation
        threading.Thread(
            target=self.recommendation_service._recompute,
            args=(rating.user_id,),
            daemon=True
        ).start()

        return rating
