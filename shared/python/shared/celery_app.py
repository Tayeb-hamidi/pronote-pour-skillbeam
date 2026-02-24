"""Celery application factory."""

from celery import Celery

from shared.config import get_settings

settings = get_settings()


def create_celery(name: str) -> Celery:
    """Create configured Celery app."""

    celery_app = Celery(name, broker=settings.redis_url, backend=settings.redis_url)
    celery_app.conf.task_track_started = True
    celery_app.conf.result_expires = 3600
    celery_app.conf.task_serializer = "json"
    celery_app.conf.result_serializer = "json"
    celery_app.conf.accept_content = ["json"]
    return celery_app
