from app.core.celery_app import celery_app
from app.core.task_processor import task_processor
from app.core.constants import CeleryTasks, CeleryQueues
from app.services.speaker_diarization import SpeakerDiarizationService
from app.services.speaker_extraction import SpeakerExtractionService
from app.db.session import AsyncSessionLocal
from app.models.audio import SpeakerJob, ProcessingStatus
import logging
from app.core.device import get_device_manager
import torch
from datetime import datetime
import asyncio
from app.core.errors import AudioProcessingError, ErrorCodes
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

def init_worker():
    """Initialize worker process"""
    device_manager = get_device_manager()
    if device_manager.is_gpu_available:
        torch.cuda.empty_cache()
        torch.cuda.set_per_process_memory_fraction(0.7)

def run_async(coro):
    """Run async function in sync context"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)

@asynccontextmanager
async def get_job_session(job_id: int) -> AsyncGenerator[tuple[AsyncSession, SpeakerJob], None]:
    """Get long-running async session with job"""
    async with AsyncSessionLocal() as session:
        try:
            # Get job with FOR UPDATE lock
            stmt = select(SpeakerJob).where(SpeakerJob.id == job_id).with_for_update()
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            yield session, job
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            await session.close()

@celery_app.task(
    name=CeleryTasks.EXTRACT_SPEAKERS,
    queue=CeleryQueues.SPEAKER,
    bind=True,
    max_retries=3,
    soft_time_limit=1700,
    time_limit=1800,
    acks_late=True,
    reject_on_worker_lost=True
)
@task_processor.process_task("speaker_extraction")
def extract_speakers(self, job_id: int):
    """Speaker extraction task"""
    try:
        init_worker()
        
        async def process_job():
            async with get_job_session(job_id) as (session, job):
                try:
                    # Get input path
                    input_path = job.input_path
                    
                    # Update status to processing
                    job.status = ProcessingStatus.PROCESSING
                    await session.commit()
                    
                    # Process audio
                    service = SpeakerExtractionService()
                    result = await service.process_audio(input_path)
                    
                    # Update job with results
                    job.result = result
                    job.status = ProcessingStatus.COMPLETED
                    job.completed_at = datetime.utcnow()
                    await session.commit()
                    
                    logger.info(f"Speaker extraction completed for job {job_id}")
                    return result
                    
                except AudioProcessingError as e:
                    job.status = ProcessingStatus.FAILED
                    job.error_message = str(e)
                    job.error_code = e.error_code
                    await session.commit()
                    logger.error(f"Speaker extraction failed for job {job_id}: {str(e)}")
                    return {
                        "status": "failed",
                        "error": str(e),
                        "error_code": e.error_code
                    }
                    
                except Exception as e:
                    job.status = ProcessingStatus.FAILED
                    job.error_message = f"Unexpected error: {str(e)}"
                    job.error_code = ErrorCodes.UNKNOWN_ERROR
                    await session.commit()
                    logger.error(f"Speaker extraction failed for job {job_id}: {str(e)}")
                    raise
        
        return run_async(process_job())
        
    except Exception as e:
        logger.error(f"Speaker extraction failed for job {job_id}: {str(e)}")
        raise
    finally:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

@celery_app.task(
    name=CeleryTasks.DIARIZE_SPEAKERS,
    queue=CeleryQueues.SPEAKER,
    bind=True,
    max_retries=3,
    soft_time_limit=1700,
    time_limit=1800,
    acks_late=True,
    reject_on_worker_lost=True
)
@task_processor.process_task("speaker_diarization")
def diarize_speakers(self, job_id: int, num_speakers: int = None):
    """Speaker diarization task"""
    try:
        init_worker()
        
        async def process_job():
            async with get_job_session(job_id) as (session, job):
                try:
                    # Get input path
                    input_path = job.input_path
                    
                    # Update status to processing
                    job.status = ProcessingStatus.PROCESSING
                    await session.commit()
                    
                    # Process audio
                    service = SpeakerDiarizationService()
                    result = await service.process_audio(input_path, num_speakers=num_speakers)
                    
                    # Update job with results
                    job.result = result
                    job.status = ProcessingStatus.COMPLETED
                    job.completed_at = datetime.utcnow()
                    await session.commit()
                    
                    logger.info(f"Speaker diarization completed for job {job_id}")
                    return result
                    
                except AudioProcessingError as e:
                    job.status = ProcessingStatus.FAILED
                    job.error_message = str(e)
                    job.error_code = e.error_code
                    await session.commit()
                    logger.error(f"Speaker diarization failed for job {job_id}: {str(e)}")
                    return {
                        "status": "failed",
                        "error": str(e),
                        "error_code": e.error_code
                    }
                    
                except Exception as e:
                    job.status = ProcessingStatus.FAILED
                    job.error_message = f"Unexpected error: {str(e)}"
                    job.error_code = ErrorCodes.UNKNOWN_ERROR
                    await session.commit()
                    logger.error(f"Speaker diarization failed for job {job_id}: {str(e)}")
                    raise
        
        return run_async(process_job())
        
    except Exception as e:
        logger.error(f"Speaker diarization failed for job {job_id}: {str(e)}")
        raise
    finally:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()