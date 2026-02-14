# from app.db.database import get_db
# from app.db.models import Like
# from app.tasks.recommendation_tasks import recompute_recommendations


# class LikeService:
#     def add_like(self, like_data):
#         with get_db() as db:
#             existing = db.query(Like).filter_by(
#                 user_id=like_data.user_id,
#                 movie_id=like_data.movie_id
#             ).first()

#             if existing:
#                 return existing

#             like = Like(
#                 user_id=like_data.user_id,
#                 movie_id=like_data.movie_id
#             )
#             db.add(like)
#             db.commit()
#             db.refresh(like)

#         # trigger celery AFTER db is closed
#         recompute_recommendations.delay(like.user_id)
#         return like
