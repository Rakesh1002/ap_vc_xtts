"""Unified task processing and monitoring"""
from typing import Dict, Any, Optional, Callable
from app.core.metrics import (
    TASK_PROCESSING_TIME,
    ACTIVE_JOBS,
    JOB_STATUS,
    MODEL_INFERENCE_TIME,
    QUEUE_SIZE
)
from app.core.monitoring_registry import MetricsRegistry
from app.core.service_registry import ServiceRegistry
from app.core.optimization import resource_optimizer
from app.core.memory import memory_manager
import logging
import time
from functools import wraps
from app.db.session import AsyncSessionLocal
from app.models.audio import ProcessingStatus, CloningJob, TranslationJob
from app.core.errors import AudioProcessingError
from datetime import datetime
import asyncio
from sqlalchemy import select

logger = logging.getLogger(__name__)

class TaskProcessor:
    def __init__(self):
        self.memory_manager = memory_manager
        self.resource_optimizer = resource_optimizer

    def prepare_for_task(self, task_type: str):
        """Prepare system for task execution"""
        # Update queue metrics
        QUEUE_SIZE.labels(queue_name=task_type).inc()
        
        # Optimize resources
        self.resource_optimizer.optimize_for_inference()
        
        # Track active jobs
        ACTIVE_JOBS.labels(job_type=task_type).inc()

    def cleanup_after_task(self, task_type: str):
        """Cleanup after task execution"""
        # Update queue metrics
        QUEUE_SIZE.labels(queue_name=task_type).dec()
        
        # Cleanup memory
        self.memory_manager.cleanup()
        
        # Track completed jobs
        ACTIVE_JOBS.labels(job_type=task_type).dec()

    async def update_job_status(
        self,
        job_id: int,
        status: ProcessingStatus,
        error_message: Optional[str] = None,
        job_type: str = "voice"
    ):
        """Update job status with metrics tracking"""
        async with AsyncSessionLocal() as db:
            try:
                # Select appropriate model based on job type
                model = CloningJob if job_type == "voice" else TranslationJob
                
                # Get job using select
                result = await db.execute(
                    select(model).where(model.id == job_id)
                )
                job = result.scalar_one_or_none()
                
                if job:
                    job.status = status
                    job.error_message = error_message
                    job.updated_at = datetime.utcnow()
                    if status == ProcessingStatus.COMPLETED:
                        job.completed_at = datetime.utcnow()
                    await db.commit()
                    
                    # Update metrics
                    JOB_STATUS.labels(
                        job_type=job.__class__.__name__,
                        status=status.value
                    ).inc()
                else:
                    logger.error(f"Job {job_id} not found")
                    
            except Exception as e:
                logger.error(f"Failed to update job status: {e}")
                await db.rollback()
                raise

    def process_task(self, task_type: str):
        """Decorator for task processing with metrics and error handling"""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                self.prepare_for_task(task_type)
                
                try:
                    result = await func(*args, **kwargs)
                    
                    # Record success metrics
                    duration = time.time() - start_time
                    TASK_PROCESSING_TIME.labels(
                        task_type=task_type,
                        status="success"
                    ).observe(duration)
                    
                    JOB_STATUS.labels(
                        job_type=task_type,
                        status="success"
                    ).inc()
                    
                    return result
                    
                except Exception as e:
                    # Record failure metrics
                    JOB_STATUS.labels(
                        job_type=task_type,
                        status="failure"
                    ).inc()
                    
                    logger.exception(f"Task failed: {task_type}")
                    raise
                    
                finally:
                    self.cleanup_after_task(task_type)
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                self.prepare_for_task(task_type)
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Record success metrics
                    duration = time.time() - start_time
                    TASK_PROCESSING_TIME.labels(
                        task_type=task_type,
                        status="success"
                    ).observe(duration)
                    
                    JOB_STATUS.labels(
                        job_type=task_type,
                        status="success"
                    ).inc()
                    
                    return result
                    
                except Exception as e:
                    # Record failure metrics
                    JOB_STATUS.labels(
                        job_type=task_type,
                        status="failure"
                    ).inc()
                    
                    logger.exception(f"Task failed: {task_type}")
                    raise
                    
                finally:
                    self.cleanup_after_task(task_type)
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        return decorator

task_processor = TaskProcessor()