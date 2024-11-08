"""Task registration and configuration"""
from typing import Any, Callable, Dict, Optional
from functools import wraps
from app.core.config import get_settings
from app.core.constants import CeleryTasks, CeleryQueues
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

class TaskRegistry:
    _tasks: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register_task(
        cls,
        name: str,
        queue: str,
        max_retries: int = 3,
        soft_time_limit: Optional[int] = None,
        hard_time_limit: Optional[int] = None,
        priority: int = 0
    ):
        """Register a Celery task with configuration"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            # Store task configuration
            cls._tasks[name] = {
                'queue': queue,
                'max_retries': max_retries,
                'soft_time_limit': soft_time_limit or settings.TASK_SOFT_TIMEOUT,
                'hard_time_limit': hard_time_limit or settings.TASK_HARD_TIMEOUT,
                'priority': priority,
                'function': wrapper
            }

            # Add task metadata
            wrapper.name = name
            wrapper.queue = queue
            wrapper.max_retries = max_retries

            return wrapper
        return decorator

    # Register speaker tasks
    register_task(
        CeleryTasks.DIARIZE_SPEAKERS,
        CeleryQueues.SPEAKER,
        soft_time_limit=1700,
        hard_time_limit=1800
    )

    register_task(
        CeleryTasks.EXTRACT_SPEAKERS,
        CeleryQueues.SPEAKER,
        soft_time_limit=1700,
        hard_time_limit=1800
    )

    # Add to existing task registrations
    register_task(
        CeleryTasks.DENOISE_AUDIO,
        CeleryQueues.DENOISER,
        soft_time_limit=900,
        hard_time_limit=1000
    )

    # Add spectral denoiser task registration
    register_task(
        CeleryTasks.SPECTRAL_DENOISE_AUDIO,
        CeleryQueues.SPECTRAL,
        soft_time_limit=900,
        hard_time_limit=1000,
        priority=5
    )

    @classmethod
    def get_task(cls, name: str) -> Optional[Dict[str, Any]]:
        """Get task configuration by name"""
        return cls._tasks.get(name)

    @classmethod
    def get_all_tasks(cls) -> Dict[str, Dict[str, Any]]:
        """Get all registered tasks"""
        return cls._tasks.copy()

    @classmethod
    def get_queue_tasks(cls, queue: str) -> Dict[str, Dict[str, Any]]:
        """Get all tasks for a specific queue"""
        return {
            name: config for name, config in cls._tasks.items()
            if config['queue'] == queue
        }