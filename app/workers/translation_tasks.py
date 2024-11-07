from app.core.celery_app import celery_app
from app.core.task_processor import task_processor
from app.core.constants import CeleryTasks, CeleryQueues

@celery_app.task(
    name=CeleryTasks.TRANSLATE_AUDIO,
    queue=CeleryQueues.TRANSLATION,
    bind=True,
    max_retries=3,
    soft_time_limit=1700,
    time_limit=1800
)
@task_processor.process_task("audio_translation")
def translate_audio(self, job_id: int):
    """Audio translation task"""
    # Rest of the code remains the same