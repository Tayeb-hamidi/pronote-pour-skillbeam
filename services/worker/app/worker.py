"""Celery app entrypoint for worker service."""

from shared.celery_app import create_celery

celery_app = create_celery("worker")

# Ensure task modules are imported for registration.
import app.tasks  # noqa: F401,E402
