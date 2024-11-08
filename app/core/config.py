from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Dict, Any, List
import torch
from app.core.constants import CeleryQueues

class Settings(BaseSettings):
    # Basic settings
    PROJECT_NAME: str = "Audio Processing API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    
    # Database
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    SQLALCHEMY_DATABASE_URI: str | None = None
    
    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: list[str] = ["*"]
    
    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    
    # S3 Storage
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str
    S3_REGION: str
    MULTIPART_THRESHOLD: int = 8 * 1024 * 1024  # 8MB
    MULTIPART_CHUNKSIZE: int = 8 * 1024 * 1024  # 8MB
    MAX_CONCURRENCY: int = 10
    DOWNLOAD_DIR: str = "/tmp/downloads"
    UPLOAD_DIR: str = "/tmp/uploads"
    
    # Model Paths
    WHISPER_MODEL_PATH: str = "models/model.bin"
    WHISPER_CONFIG_PATH: str = "models/config.json"
    
    # XTTS model paths
    XTTS_BASE_DIR: str = "models/XTTS-v2"
    XTTS_MODEL_PATH: str = "models/XTTS-v2/model.pth"
    XTTS_CONFIG_PATH: str = "models/XTTS-v2/config.json"
    XTTS_VOCAB_PATH: str = "models/XTTS-v2/vocab.json"
    XTTS_SPEAKERS_PATH: str = "models/XTTS-v2/speakers.pth"
    
    # Worker Settings
    WORKER_CONCURRENCY: int = 2
    TASK_TIMEOUT: int = 600
    MAX_RETRIES: int = 3
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    LOG_LEVEL: str = "INFO"
    
    # HashiCorp Vault
    VAULT_ADDR: str = "http://vault:8200"
    VAULT_TOKEN: str = "your_vault_token"
    
    # GPU Settings
    CUDA_VISIBLE_DEVICES: str = "0"
    DEVICE_STRATEGY: str = "auto"
    
    # Database SSL Settings
    SSL_MODE: str = "require"
    SSL_CA_CERTS: str | None = None
    
    # Celery Settings
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: List[str] = ["json"]
    CELERY_TIMEZONE: str = "UTC"
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 3600
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1
    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = 50
    CELERY_WORKER_MAX_MEMORY_PER_CHILD: int = 400000
    CELERY_DEFAULT_QUEUE: str = CeleryQueues.VOICE
    
    # Queue Settings
    VOICE_QUEUE_CONCURRENCY: int = 2
    TRANSLATION_QUEUE_CONCURRENCY: int = 4
    VOICE_QUEUE_TIME_LIMIT: int = 3600
    TRANSLATION_QUEUE_TIME_LIMIT: int = 1800
    
    # Memory Management
    MEMORY_CLEANUP_INTERVAL: int = 5  # Minutes
    MAX_MEMORY_USAGE: int = 90  # Percentage
    FORCE_GC_THRESHOLD: int = 85  # Percentage
    MIN_FREE_MEMORY: int = 2000  # MB
    
    # Queue Management
    MAX_QUEUE_SIZE: int = 100
    QUEUE_TIMEOUT: int = 3600  # 1 hour
    STALE_JOB_THRESHOLD: int = 24  # Hours
    MAX_RETRIES_PER_JOB: int = 3
    RETRY_BACKOFF: int = 60  # Seconds
    
    # Task Processing
    BATCH_SIZE: int = 10
    MAX_CONCURRENT_JOBS: int = 5
    JOB_PRIORITY_LEVELS: int = 3
    TASK_SOFT_TIMEOUT: int = 3300  # 55 minutes
    TASK_HARD_TIMEOUT: int = 3600  # 60 minutes

    # Database Pool Settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800  # 30 minutes
    DB_ECHO: bool = False
    DB_ECHO_POOL: bool = False
    DB_PRE_PING: bool = True
    DB_POOL_RESET_ON_RETURN: str = "rollback"

    # Connection Pool Settings
    ASYNC_POOL_SIZE: int = 20
    ASYNC_MAX_OVERFLOW: int = 10
    ASYNC_POOL_TIMEOUT: int = 30
    ASYNC_MAX_CONNECTIONS: int = 100
    ASYNC_POOL_RECYCLE: int = 300  # 5 minutes

    # Redis Pool Settings
    REDIS_POOL_SIZE: int = 10
    REDIS_POOL_TIMEOUT: int = 20
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_RETRY_ON_TIMEOUT: bool = True
    REDIS_SOCKET_KEEPALIVE: bool = True

    # Speaker Analysis Models
    SPEAKER_MODELS_DIR: str = "models/speaker"
    DIARIZATION_MODEL_PATH: str = "models/speaker/diarization"
    SEPARATION_MODEL_PATH: str = "models/speaker/separation"
    
    # HuggingFace Settings
    HF_TOKEN: str  # Required for pyannote models
    HF_CACHE_DIR: str = "models/huggingface"
    
    # Speaker Analysis Settings
    MAX_SPEAKERS: int = 10
    MIN_SPEAKER_TIME: float = 1.0  # Minimum speaking time in seconds
    SPEAKER_OVERLAP_THRESHOLD: float = 0.5  # Overlap threshold for diarization
    
    # Queue Settings
    SPEAKER_QUEUE_CONCURRENCY: int = 2
    SPEAKER_QUEUE_TIME_LIMIT: int = 1800  # 30 minutes
    
    # Processing Settings
    AUDIO_SAMPLE_RATE: int = 16000
    MAX_AUDIO_DURATION: int = 7200  # 2 hours
    MIN_AUDIO_DURATION: int = 1  # 1 second
    
    # Storage Settings for Speaker Analysis
    SPEAKER_UPLOAD_DIR: str = "uploads/speaker"
    SPEAKER_PROCESSED_DIR: str = "processed/speaker"
    DIARIZATION_OUTPUT_DIR: str = "processed/diarization"
    EXTRACTION_OUTPUT_DIR: str = "processed/extraction"

    # Model-specific Settings
    DIARIZATION_MIN_SPEAKERS: int = 1
    DIARIZATION_MAX_SPEAKERS: int = 20
    EXTRACTION_MAX_SPEAKERS: int = 10
    SPEAKER_MIN_DURATION: float = 0.5  # Minimum duration for speaker segments

    # Denoiser Settings
    DENOISER_MAX_DURATION: int = 600  # 10 minutes
    DENOISER_SAMPLE_RATE: int = 48000

    # Denoiser queue settings
    DENOISER_QUEUE_CONCURRENCY: int = 2
    DENOISER_QUEUE_TIME_LIMIT: int = 1000
    DENOISER_RATE_LIMIT: str = "15/m"
    DENOISER_PRIORITY: int = 5
    DENOISER_MAX_RETRIES: int = 3

    # Denoiser settings
    DENOISER_MODEL: str = "dns64"  # dns48 or dns64
    DENOISER_CHUNK_SIZE: int = 10  # seconds
    DENOISER_MAX_MEMORY: int = 4096  # MB
    DENOISER_USE_CUDA: bool = True
    DENOISER_NUM_THREADS: int = 4

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields in environment variables

    @property
    def database_url(self) -> str:
        """Base database URL without SSL parameters"""
        if self.SQLALCHEMY_DATABASE_URI:
            return self.SQLALCHEMY_DATABASE_URI.split('?')[0]  # Remove any existing parameters
            
        # Build URL from environment variables
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"

    @property
    def async_database_url(self) -> str:
        """Async database URL (for FastAPI) with SSL parameter"""
        base_url = self.database_url.replace('postgresql://', 'postgresql+asyncpg://')
        return f"{base_url}?ssl=require"  # asyncpg uses ssl=require

    @property
    def sync_database_url(self) -> str:
        """Sync database URL (for Alembic) with SSL parameter"""
        base_url = self.database_url.replace('postgresql://', 'postgresql+psycopg2://')
        return f"{base_url}?sslmode=require"  # psycopg2 uses sslmode=require

@lru_cache
def get_settings() -> Settings:
    return Settings()