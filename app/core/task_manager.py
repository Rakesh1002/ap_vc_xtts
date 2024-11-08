"""Task management and orchestration"""
from typing import Dict, Any, List, Optional
from app.core.config import get_settings
from app.core.metrics import QUEUE_SIZE, ACTIVE_JOBS, JOB_STATUS
import logging
from datetime import datetime, timedelta
from app.models.audio import ProcessingStatus, CloningJob, TranslationJob, BaseJob, DenoiseJob
from sqlalchemy import and_, select, func
from app.db.session import AsyncSessionLocal
from app.core.celery_app import celery_app
from app.core.constants import CeleryQueues, CeleryTasks
from celery.result import AsyncResult
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)
settings = get_settings()

class TaskManager:
    def __init__(self):
        self.settings = get_settings()
        self.active_tasks: Dict[str, Any] = {}
        self.task_history: List[Dict[str, Any]] = []
        self.queue_limits = {
            CeleryQueues.VOICE: settings.VOICE_QUEUE_CONCURRENCY,
            CeleryQueues.TRANSLATION: settings.TRANSLATION_QUEUE_CONCURRENCY,
            CeleryQueues.DENOISER: settings.DENOISER_QUEUE_CONCURRENCY,
            CeleryQueues.SPECTRAL: settings.DENOISER_QUEUE_CONCURRENCY
        }

    async def can_accept_task(self, queue_name: str) -> bool:
        """Check if queue can accept more tasks"""
        try:
            async with AsyncSessionLocal() as db:
                # Count active tasks in queue
                result = await db.execute(
                    select(func.count(BaseJob.id)).where(
                        and_(
                            BaseJob.queue == queue_name,
                            BaseJob.status.in_([
                                ProcessingStatus.PENDING,
                                ProcessingStatus.PROCESSING
                            ])
                        )
                    )
                )
                active_count = result.scalar()
                
                # Check against limit
                queue_limit = self.queue_limits.get(queue_name, settings.MAX_QUEUE_SIZE)
                return active_count < queue_limit
                
        except Exception as e:
            logger.error(f"Error checking queue capacity: {e}")
            return False

    async def cleanup_stale_jobs(self):
        """Cleanup jobs that have been stuck for too long"""
        try:
            threshold = datetime.utcnow() - timedelta(hours=self.settings.STALE_JOB_THRESHOLD)
            
            async with AsyncSessionLocal() as db:
                # Find stale jobs
                for model in [CloningJob, TranslationJob, DenoiseJob]:
                    result = await db.execute(
                        select(model).where(
                            and_(
                                model.status.in_([ProcessingStatus.PENDING, ProcessingStatus.PROCESSING]),
                                model.created_at < threshold
                            )
                        )
                    )
                    stale_jobs = result.scalars().all()
                    
                    for job in stale_jobs:
                        try:
                            # Cancel Celery task if exists
                            if job.task_id:
                                celery_app.control.revoke(job.task_id, terminate=True)
                            
                            # Clean up any associated files
                            if hasattr(job, 'output_path') and job.output_path:
                                try:
                                    storage_service = StorageService()
                                    await storage_service.delete_file(job.output_path)
                                except Exception as e:
                                    logger.warning(f"Failed to delete output file for job {job.id}: {e}")
                            
                            # Update job status
                            job.status = ProcessingStatus.FAILED
                            job.error_message = "Job timed out"
                            job.updated_at = datetime.utcnow()
                            
                            # Update metrics
                            ACTIVE_JOBS.labels(job_type=job.__class__.__name__).dec()
                            JOB_STATUS.labels(
                                job_type=job.__class__.__name__,
                                status="failed"
                            ).inc()
                            
                            logger.warning(f"Cleaned up stale job: {job.id}")
                            
                        except Exception as e:
                            logger.error(f"Failed to cleanup job {job.id}: {e}")
                            continue
                    
                    await db.commit()
                    
        except Exception as e:
            logger.error(f"Failed to cleanup stale jobs: {e}")

    async def get_queue_metrics(self) -> Dict[str, Dict[str, int]]:
        """Get detailed queue metrics"""
        metrics = {}
        try:
            async with AsyncSessionLocal() as db:
                for queue in [CeleryQueues.VOICE, CeleryQueues.TRANSLATION]:
                    # Get counts for different statuses
                    queue_metrics = {}
                    for status in ProcessingStatus:
                        result = await db.execute(
                            select(func.count(BaseJob.id)).where(
                                and_(
                                    BaseJob.queue == queue,
                                    BaseJob.status == status
                                )
                            )
                        )
                        count = result.scalar()
                        queue_metrics[status.value] = count
                    
                    # Calculate total and update Prometheus metrics
                    total = sum(queue_metrics.values())
                    queue_metrics['total'] = total
                    metrics[queue] = queue_metrics
                    
                    QUEUE_SIZE.labels(queue_name=queue).set(total)
                    
        except Exception as e:
            logger.error(f"Failed to get queue metrics: {e}")
            
        return metrics

    async def requeue_failed_jobs(self, max_age_hours: int = 24) -> Dict[str, int]:
        """Requeue failed jobs within age limit"""
        results = {'attempted': 0, 'succeeded': 0, 'failed': 0}
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            async with AsyncSessionLocal() as db:
                # Find failed jobs for both job types
                for model, task_name, queue in [
                    (CloningJob, CeleryTasks.CLONE_VOICE, CeleryQueues.VOICE),
                    (TranslationJob, CeleryTasks.TRANSLATE_AUDIO, CeleryQueues.TRANSLATION),
                    (DenoiseJob, CeleryTasks.DENOISE_AUDIO, CeleryQueues.DENOISER),
                    (DenoiseJob, CeleryTasks.SPECTRAL_DENOISE_AUDIO, CeleryQueues.SPECTRAL)
                ]:
                    result = await db.execute(
                        select(model).where(
                            and_(
                                model.status == ProcessingStatus.FAILED,
                                model.created_at >= cutoff_time,
                                model.retries < self.settings.MAX_RETRIES_PER_JOB
                            )
                        )
                    )
                    failed_jobs = result.scalars().all()
                    
                    for job in failed_jobs:
                        results['attempted'] += 1
                        try:
                            # Reset job status
                            job.status = ProcessingStatus.PENDING
                            job.error_message = None
                            job.retries += 1
                            job.updated_at = datetime.utcnow()
                            
                            # Create new task
                            task = celery_app.send_task(
                                task_name,
                                args=[job.id],
                                queue=queue
                            )
                            
                            # Update task ID
                            job.task_id = task.id
                            results['succeeded'] += 1
                            
                        except Exception as e:
                            logger.error(f"Failed to retry job {job.id}: {str(e)}")
                            results['failed'] += 1
                            continue
                    
                await db.commit()
                
        except Exception as e:
            logger.error(f"Failed to requeue jobs: {e}")
            
        return results

    async def get_job_status(self, job_id: int, job_type: str) -> Dict[str, Any]:
        """Get detailed job status including Celery task status"""
        try:
            async with AsyncSessionLocal() as db:
                # Select appropriate model
                model = CloningJob if job_type == "voice" else TranslationJob
                
                result = await db.execute(
                    select(model).where(model.id == job_id)
                )
                job = result.scalar_one_or_none()
                
                if not job:
                    return {"error": "Job not found"}
                
                status_info = {
                    "job_id": job.id,
                    "status": job.status.value,
                    "created_at": job.created_at,
                    "updated_at": job.updated_at,
                    "completed_at": job.completed_at,
                    "error_message": job.error_message,
                    "retries": job.retries
                }
                
                # Get Celery task status if available
                if job.task_id:
                    task_result = AsyncResult(job.task_id)
                    status_info["task_status"] = {
                        "state": task_result.state,
                        "info": task_result.info,
                        "error": str(task_result.result) if task_result.failed() else None
                    }
                
                return status_info
                
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return {"error": "Failed to get job status"}

    async def handle_failed_job(self, job_id: int, error_message: str, db: AsyncSession):
        """Handle failed job by updating its status and error message"""
        try:
            # Find job in either table
            for model in [CloningJob, TranslationJob]:
                result = await db.execute(
                    select(model).where(model.id == job_id)
                )
                job = result.scalar_one_or_none()
                if job:
                    job.status = ProcessingStatus.FAILED
                    job.error_message = error_message
                    job.updated_at = datetime.utcnow()
                    
                    # Update metrics
                    JOB_STATUS.labels(
                        job_type=job.__class__.__name__,
                        status="failed"
                    ).inc()
                    
                    await db.commit()
                    logger.error(f"Job {job_id} failed: {error_message}")
                    return
                    
            logger.error(f"Failed job {job_id} not found")
        except Exception as e:
            logger.error(f"Error handling failed job {job_id}: {e}")
            await db.rollback()
            raise

task_manager = TaskManager()