from app.core.celery_app import celery_app
from app.core.task_processor import task_processor
from app.core.constants import CeleryTasks, CeleryQueues
from app.services.denoiser_service import DenoiserService, DenoiserError
from app.services.storage_service import StorageService
from app.models.audio import DenoiseJob, ProcessingStatus
from app.core.errors import AudioProcessingError, ErrorCodes
from datetime import datetime
import logging
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any
from app.db.session import AsyncSessionLocal
import tempfile
import os
from app.core.optimization import resource_optimizer, optimize_array_processing

logger = logging.getLogger(__name__)

def init_worker():
    """Initialize worker process"""
    resource_optimizer.optimize_for_denoising()

def run_async(coro):
    """Run async function in sync context"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)

@asynccontextmanager
async def get_job_session(job_id: int) -> AsyncGenerator[tuple[AsyncSession, DenoiseJob], None]:
    """Get long-running async session with job"""
    async with AsyncSessionLocal() as session:
        try:
            stmt = select(DenoiseJob).where(DenoiseJob.id == job_id).with_for_update()
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

@optimize_array_processing
async def process_denoising(
    job: DenoiseJob,
    input_temp: str,
    output_temp: str
) -> Dict[str, Any]:
    """Process audio denoising with Denoiser"""
    try:
        denoiser_service = DenoiserService()
        
        # Validate input file
        audio_info = denoiser_service.validate_audio_file(input_temp)
        
        # Process audio
        result = await denoiser_service.process_audio(
            input_path=input_temp,
            output_path=output_temp
        )
        
        # Add audio info to stats
        result["stats"].update(audio_info)
        
        return result
        
    except DenoiserError as e:
        logger.error(f"Denoising error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in denoising: {str(e)}")
        raise DenoiserError(
            message="Failed to process audio",
            error_code=ErrorCodes.PROCESSING_ERROR,
            details={"error": str(e)}
        )

@celery_app.task(
    name=CeleryTasks.DENOISE_AUDIO,
    queue=CeleryQueues.DENOISER,
    bind=True,
    max_retries=3,
    soft_time_limit=900,
    time_limit=1000,
    acks_late=True,
    reject_on_worker_lost=True
)
@task_processor.process_task("denoising")
def denoise_audio(self, job_id: int):
    """Audio denoising task using Denoiser"""
    try:
        init_worker()
        
        # Check if denoiser service is initialized
        denoiser_service = DenoiserService()
        if not denoiser_service.initialized:
            raise DenoiserError(
                message="Denoiser service not initialized",
                error_code=ErrorCodes.INIT_ERROR
            )
            
        async def process_job():
            input_temp = None
            output_temp = None
            
            try:
                async with get_job_session(job_id) as (session, job):
                    try:
                        # Update status to processing
                        job.status = ProcessingStatus.PROCESSING
                        await session.commit()
                        
                        # Create temporary files for processing
                        input_temp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                        output_temp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                        
                        try:
                            # Download from S3 to temp file
                            storage_service = StorageService()
                            await storage_service.download_file(
                                job.input_path,
                                input_temp.name
                            )
                            input_temp.flush()
                            
                            # Process audio
                            result = await process_denoising(
                                job=job,
                                input_temp=input_temp.name,
                                output_temp=output_temp.name
                            )
                            
                            # Upload processed file to S3
                            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                            filename = Path(job.input_path).stem
                            output_key = f"processed/denoiser/{job_id}/{timestamp}_{filename}_denoised.wav"
                            
                            await storage_service.upload_file(
                                output_temp.name,
                                output_key
                            )
                            
                            # Update job with results
                            job.output_path = output_key
                            job.stats = result["stats"]
                            job.status = ProcessingStatus.COMPLETED
                            job.completed_at = datetime.utcnow()
                            await session.commit()
                            
                            return result
                            
                        except Exception as e:
                            logger.error(f"Processing failed: {str(e)}")
                            job.status = ProcessingStatus.FAILED
                            job.error_message = str(e)
                            await session.commit()
                            raise
                            
                    except Exception as e:
                        if self.request.retries < self.max_retries:
                            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
                        raise
                        
            finally:
                # Cleanup temp files
                for temp_file in [input_temp, output_temp]:
                    if temp_file:
                        try:
                            temp_file.close()
                            if os.path.exists(temp_file.name):
                                os.unlink(temp_file.name)
                        except Exception as e:
                            logger.warning(f"Failed to cleanup temp file: {e}")
                
        return run_async(process_job())
        
    except Exception as e:
        logger.error(f"Denoising failed for job {job_id}: {str(e)}")
        raise
    finally:
        resource_optimizer.cleanup()