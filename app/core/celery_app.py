from celery import Celery
from app.core.config import get_settings
from app.core.constants import CeleryQueues, CeleryTasks, TaskTimeouts

settings = get_settings()

celery_app = Celery(
    "app",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[  # Add task modules here
        'app.workers.voice_tasks',
        'app.workers.translation_tasks',
        'app.workers.speaker_tasks',
        'app.workers.denoiser_tasks',
        'app.workers.spectral_denoiser_tasks'
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    timezone=settings.CELERY_TIMEZONE,
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
    worker_max_tasks_per_child=settings.CELERY_WORKER_MAX_TASKS_PER_CHILD,
    worker_max_memory_per_child=settings.CELERY_WORKER_MAX_MEMORY_PER_CHILD,
    
    # Queue routing
    task_routes={
        CeleryTasks.CLONE_VOICE: {'queue': CeleryQueues.VOICE},
        CeleryTasks.TRANSLATE_AUDIO: {'queue': CeleryQueues.TRANSLATION},
        CeleryTasks.DIARIZE_SPEAKERS: {'queue': CeleryQueues.SPEAKER},
        CeleryTasks.EXTRACT_SPEAKERS: {'queue': CeleryQueues.SPEAKER},
        CeleryTasks.DENOISE_AUDIO: {'queue': CeleryQueues.DENOISER},
        CeleryTasks.SPECTRAL_DENOISE_AUDIO: {'queue': CeleryQueues.SPECTRAL},
        'voice_cleanup': {'queue': CeleryQueues.VOICE},
        'translation_cleanup': {'queue': CeleryQueues.TRANSLATION},
        'speaker_cleanup': {'queue': CeleryQueues.SPEAKER},
        'denoiser_cleanup': {'queue': CeleryQueues.DENOISER},
    },
    
    # Queue-specific settings
    task_queues={
        CeleryQueues.VOICE: {
            'exchange': CeleryQueues.VOICE,
            'routing_key': 'voice.clone',
        },
        CeleryQueues.TRANSLATION: {
            'exchange': CeleryQueues.TRANSLATION,
            'routing_key': 'translation.process',
        },
        CeleryQueues.SPEAKER: {
            'exchange': CeleryQueues.SPEAKER,
            'routing_key': 'speaker.process',
        },
        CeleryQueues.DENOISER: {
            'exchange': CeleryQueues.DENOISER,
            'routing_key': 'denoiser.process',
            'queue_arguments': {
                'x-max-priority': 10,
                'x-message-ttl': 3600000  # 1 hour
            }
        },
        CeleryQueues.SPECTRAL: {
            'exchange': CeleryQueues.SPECTRAL,
            'routing_key': 'denoiser.spectral',
            'queue_arguments': {
                'x-max-priority': 10,
                'x-message-ttl': 3600000  # 1 hour
            }
        }
    },
    
    # Task timeouts
    task_soft_time_limit=TaskTimeouts.VOICE_SOFT_TIMEOUT,
    task_time_limit=TaskTimeouts.VOICE_HARD_TIMEOUT,
    
    # Default queue
    task_default_queue=CeleryQueues.VOICE,
    task_create_missing_queues=True,
    
    # Additional settings
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_annotations={
        '*': {
            'rate_limit': '10/m'
        },
        CeleryTasks.DENOISE_AUDIO: {
            'rate_limit': '15/m',
            'time_limit': 1000,
            'soft_time_limit': 900,
            'priority': 5
        },
        'app.workers.denoiser_tasks.denoise_audio': {
            'rate_limit': '15/m',
            'time_limit': 1000,
            'soft_time_limit': 900,
            'priority': 5
        },
        'app.workers.spectral_denoiser_tasks.denoise_audio': {
            'rate_limit': '15/m',
            'time_limit': 1000,
            'soft_time_limit': 900,
            'priority': 5
        }
    }
)

# Queue-specific time limits
celery_app.conf.task_time_limit = {
    CeleryQueues.VOICE: settings.VOICE_QUEUE_TIME_LIMIT,
    CeleryQueues.TRANSLATION: settings.TRANSLATION_QUEUE_TIME_LIMIT,
    CeleryQueues.SPEAKER: settings.SPEAKER_QUEUE_TIME_LIMIT,
    CeleryQueues.DENOISER: 1000,  # 1000 seconds hard limit
}

# Queue-specific concurrency
celery_app.conf.worker_concurrency = {
    CeleryQueues.VOICE: settings.VOICE_QUEUE_CONCURRENCY,
    CeleryQueues.TRANSLATION: settings.TRANSLATION_QUEUE_CONCURRENCY,
    CeleryQueues.SPEAKER: settings.SPEAKER_QUEUE_CONCURRENCY,
    CeleryQueues.DENOISER: 2  # 2 concurrent denoising tasks
} 