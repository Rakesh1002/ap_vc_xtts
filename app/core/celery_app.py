from celery import Celery
from app.core.config import get_settings

settings = get_settings()

# Ensure model paths are accessible to workers
celery_app = Celery(
    "worker",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
    include=[
        "app.workers.translation_tasks",
        "app.workers.voice_tasks"
    ]
)

# Configure Celery
celery_app.conf.update(
    task_routes={
        "app.workers.translation_tasks.*": {"queue": "translation-queue"},
        "app.workers.voice_tasks.*": {"queue": "voice-queue"}
    },
    task_time_limit=settings.TASK_TIMEOUT,
    task_soft_time_limit=settings.TASK_TIMEOUT - 30,
    worker_max_tasks_per_child=50,
    worker_prefetch_multiplier=1,
    task_ignore_result=False,
    task_track_started=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC'
) 