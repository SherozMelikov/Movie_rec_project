from app.celery_app import celery_app
from app.services.recommendation_service import RecommendationService
from app.core.model_loader import ModelLoader

model_loader = ModelLoader()
recommendation_service = RecommendationService(model_loader)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def recompute_recommendations(self, user_id: int):
    try:
        recommendation_service._recompute(user_id)
    except Exception as e:
        raise self.retry(exc=e)
