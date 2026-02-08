from celery import Celery

# Redis broker
celery_app = Celery(
    "recommendation_tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

# Optional: retry settings / serialization
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
