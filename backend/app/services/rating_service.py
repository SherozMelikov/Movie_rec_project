# from app.db.database import get_db
# from app.db.models import Rating
# from app.tasks.recommendation_tasks import recompute_recommendations


# class RatingService:
#     def add_rating(self, rating_data):
#         with get_db() as db:
#             rating = Rating(
#                 user_id=rating_data.user_id,
#                 movie_id=rating_data.movie_id,
#                 rating=rating_data.rating
#             )
#             db.add(rating)
#             db.commit()
#             db.refresh(rating)

#         # trigger celery AFTER db is closed
#         recompute_recommendations.delay(rating.user_id)
#         return rating
