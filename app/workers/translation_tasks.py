from app.core.celery_app import celery_app
from app.services.translation import TranslationService
from app.models.audio import ProcessingStatus
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.models.audio import TranslationJob
from app.core.metrics import ACTIVE_JOBS, JOB_DURATION, JOB_STATUS
import logging
from datetime import datetime
import time

logger = logging.getLogger(__name__)

@celery_app.task(
    name="translate_audio",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
async def translate_audio(self, job_id: int):
    translation_service = TranslationService()
    job_start_time = time.time()
    
    # Track active jobs
    ACTIVE_JOBS.labels(job_type="translation").inc()
    
    async with AsyncSessionLocal() as db:
        try:
            # Get job
            job = await db.execute(
                select(TranslationJob).where(TranslationJob.id == job_id)
            )
            job = job.scalar_one()
            
            # Update status to processing
            job.status = ProcessingStatus.PROCESSING
            await db.commit()
            
            # Process translation
            transcript_path, detected_language = await translation_service.translate_audio(
                audio_path=job.input_path,
                target_language=job.target_language,
                source_language=job.source_language
            )
            
            # Update job with success
            job.status = ProcessingStatus.COMPLETED
            job.transcript_path = transcript_path
            if not job.source_language:
                job.source_language = detected_language
            job.completed_at = datetime.utcnow()
            await db.commit()
            
            # Record success metrics
            JOB_STATUS.labels(
                job_type="translation",
                status="success"
            ).inc()
            
        except Exception as e:
            error_msg = f"Translation failed for job {job_id}: {str(e)}"
            logger.exception(error_msg)
            
            # Update job status
            job.status = ProcessingStatus.FAILED
            job.completed_at = datetime.utcnow()
            await db.commit()
            
            # Record failure metrics
            JOB_STATUS.labels(
                job_type="translation",
                status="failure"
            ).inc()
            
            # Retry if appropriate
            if self.request.retries < self.max_retries:
                raise self.retry(exc=e)
            raise Exception(error_msg)
            
        finally:
            # Record job duration
            job_duration = time.time() - job_start_time
            JOB_DURATION.labels(job_type="translation").observe(job_duration)
            
            # Decrement active jobs
            ACTIVE_JOBS.labels(job_type="translation").dec()