import os
from celery import Celery
from app.core.config import get_settings
from app.core.constants import CeleryQueues, CeleryTasks

settings = get_settings()

# Initialize Celery app
celery_app = Celery(
    'app',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        'app.workers.voice_tasks',
        'app.workers.translation_tasks',
        'app.workers.speaker_tasks',
        'app.workers.denoiser_tasks',
        'app.workers.spectral_denoiser_tasks'
    ]
)

# Start worker command:
"""
# Start dedenoiser worker
celery -A app.workers.celery_worker worker -Q denoiser-queue --concurrency=2

# Start spectral denoiser worker
celery -A app.workers.celery_worker worker -Q denoiser-queue --concurrency=2
""" 