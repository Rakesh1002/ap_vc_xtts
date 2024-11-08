import os
import multiprocessing
from app.core.celery_app import celery_app
from app.core.memory import memory_manager
from app.core.task_manager import task_manager
from app.db.session import AsyncSessionLocal
import logging
from app.core.config import get_settings
import asyncio
from celery.signals import (
    worker_init, worker_process_init,
    worker_ready, worker_shutting_down,
    task_prerun, task_postrun,
    task_success, task_failure,
    task_retry, task_revoked
)
from app.core.constants import CeleryTasks
from app.core.optimization import ResourceOptimizer

# Initialize settings and logging
logger = logging.getLogger(__name__)
settings = get_settings()

# Set up memory monitoring
memory_manager.start_monitoring()

# Configure worker pool
if os.name != 'nt' and multiprocessing.get_start_method(allow_none=True) != 'spawn':
    multiprocessing.set_start_method('spawn')

# Disable MPS on macOS
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'

# Signal handlers
@worker_init.connect
def init_worker(**kwargs):
    """Initialize worker process"""
    logger.info("Initializing worker process...")

@task_prerun.connect
def task_prerun_handler(task_id, task, args, kwargs, **_):
    """Handler called before task execution"""
    logger.info(f"Starting task: {task.name}[{task_id}]")
    
    # Optimize for denoising tasks
    if task.name in [CeleryTasks.DENOISE_AUDIO, CeleryTasks.SPECTRAL_DENOISE_AUDIO]:
        resource_optimizer.optimize_for_denoising()
    else:
        resource_optimizer.optimize_for_inference()

@task_success.connect
def task_success_handler(sender=None, **kwargs):
    """Handle successful task completion"""
    logger.info(f"Task {sender.request.id} completed successfully")

@task_failure.connect
def task_failure_handler(task_id, exception, args, kwargs, traceback, **_):
    """Handle task failure"""
    logger.error(f"Task {task_id} failed: {str(exception)}")
    if args:
        job_id = args[0]
        async def update_failed_job():
            async with AsyncSessionLocal() as db:
                await task_manager.handle_failed_job(job_id, str(exception), db)
        
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(update_failed_job())
        finally:
            loop.close()

if __name__ == '__main__':
    try:
        logger.info("Starting Celery worker...")
        celery_app.worker_main()
    except Exception as e:
        logger.error(f"Failed to start Celery worker: {e}")
        raise
    finally:
        memory_manager.stop_monitoring()