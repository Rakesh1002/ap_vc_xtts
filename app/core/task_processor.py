"""Unified task processing and monitoring"""
from typing import Dict, Any, Optional, Callable
from app.core.metrics import (
    TASK_PROCESSING_TIME,
    ACTIVE_JOBS,
    JOB_STATUS,
    MODEL_INFERENCE_TIME,
    QUEUE_SIZE,
    SPEAKER_DIARIZATION_TIME,
    SPEAKER_EXTRACTION_TIME,
    SPEAKER_COUNT,
    SPEAKER_CONFIDENCE,
    DENOISING_PROCESSING_TIME,
    NOISE_REDUCTION_LEVEL,
    VAD_CONFIDENCE,
    SPECTRAL_DENOISING_TIME,
    SPECTRAL_NOISE_REDUCTION
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
from app.services.speaker_diarization import SpeakerDiarizationService
from app.services.speaker_extraction import SpeakerExtractionService
from app.services.denoiser_service import DenoiserService
import tempfile
from pathlib import Path
from app.services.storage_service import StorageService
from app.models.audio import DenoiseJob
from app.services.spectral_denoiser_service import SpectralDenoiserService

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

    async def process_speaker_task(
        self,
        job_id: int,
        task_type: str,
        num_speakers: Optional[int] = None
    ):
        """Process speaker analysis tasks with proper metrics"""
        metric = (SPEAKER_DIARIZATION_TIME if task_type == "diarization" 
                 else SPEAKER_EXTRACTION_TIME)
        
        start_time = time.time()
        try:
            # Get appropriate service
            if task_type == "diarization":
                service = SpeakerDiarizationService()
                result = await service.process_audio(job_id, num_speakers=num_speakers)
            else:
                service = SpeakerExtractionService()
                result = await service.process_audio(job_id)

            # Record metrics
            duration = time.time() - start_time
            metric.labels(status="success").observe(duration)
            
            if "num_speakers" in result:
                SPEAKER_COUNT.labels(job_type=task_type).observe(result["num_speakers"])

            return result

        except Exception as e:
            metric.labels(status="failure").observe(time.time() - start_time)
            logger.exception(f"Speaker {task_type} task failed")
            raise

    async def process_denoising_task(
        self,
        job_id: int
    ) -> Dict[str, Any]:
        """Process audio denoising with metrics tracking"""
        start_time = time.time()
        try:
            async with AsyncSessionLocal() as db:
                job = await db.get(DenoiseJob, job_id)
                if not job:
                    raise ValueError(f"Job {job_id} not found")
                    
                service = DenoiserService()
                storage_service = StorageService()
                
                # Create temporary files
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as input_temp, \
                     tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as output_temp:
                    
                    try:
                        # Download input file
                        await storage_service.download_file(job.input_path, input_temp.name)
                        
                        # Process audio
                        result = await service.process_audio(
                            input_path=input_temp.name,
                            output_path=output_temp.name
                        )
                        
                        # Record metrics
                        duration = time.time() - start_time
                        DENOISING_PROCESSING_TIME.labels(status="success").observe(duration)
                        
                        if "noise_reduction_db" in result["stats"]:
                            NOISE_REDUCTION_LEVEL.labels(status="success").observe(
                                result["stats"]["noise_reduction_db"]
                            )
                            
                        return result
                        
                    finally:
                        # Cleanup temp files
                        for temp_file in [input_temp.name, output_temp.name]:
                            try:
                                Path(temp_file).unlink(missing_ok=True)
                            except Exception as e:
                                logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")
                                
        except Exception as e:
            DENOISING_PROCESSING_TIME.labels(status="failure").observe(
                time.time() - start_time
            )
            logger.exception("Denoising task failed")
            raise

    async def process_spectral_denoising_task(
        self,
        job_id: int
    ) -> Dict[str, Any]:
        """Process audio denoising with spectral gating"""
        start_time = time.time()
        try:
            async with AsyncSessionLocal() as db:
                job = await db.get(DenoiseJob, job_id)
                if not job:
                    raise ValueError(f"Job {job_id} not found")
                    
                service = SpectralDenoiserService()
                storage_service = StorageService()
                
                # Create temporary files
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as input_temp, \
                     tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as output_temp:
                    
                    try:
                        # Download input file
                        await storage_service.download_file(job.input_path, input_temp.name)
                        
                        # Process audio with parameters from job
                        result = await service.process_audio(
                            input_path=input_temp.name,
                            output_path=output_temp.name,
                            **job.parameters
                        )
                        
                        # Record metrics
                        duration = time.time() - start_time
                        SPECTRAL_DENOISING_TIME.labels(status="success").observe(duration)
                        
                        if "noise_reduction_db" in result["stats"]:
                            SPECTRAL_NOISE_REDUCTION.labels(status="success").observe(
                                result["stats"]["noise_reduction_db"]
                            )
                            
                        return result
                        
                    finally:
                        # Cleanup temp files
                        for temp_file in [input_temp.name, output_temp.name]:
                            try:
                                Path(temp_file).unlink(missing_ok=True)
                            except Exception as e:
                                logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")
                                
        except Exception as e:
            SPECTRAL_DENOISING_TIME.labels(status="failure").observe(
                time.time() - start_time
            )
            logger.exception("Spectral denoising task failed")
            raise

task_processor = TaskProcessor()