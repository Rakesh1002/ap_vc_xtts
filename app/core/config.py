from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Dict, Any
import torch

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
    
    # Model Paths
    WHISPER_MODEL_PATH: str = "models/model.bin"
    WHISPER_CONFIG_PATH: str = "models/config.json"
    
    # XTTS model paths - fixed paths
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
    
    # SSL Settings
    SSL: str = "require"
    SSL_CA_CERTS: str = "/etc/ssl/certs/ca-certificates.crt"
    
    class Config:
        case_sensitive = True
        env_file = ".env"

    @property
    def database_url(self) -> str:
        if self.SQLALCHEMY_DATABASE_URI:
            return self.SQLALCHEMY_DATABASE_URI
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"

@lru_cache
def get_settings() -> Settings:
    return Settings() 