"""Centralized metrics configuration"""
from prometheus_client import Counter, Gauge, Histogram, Summary
from app.core.monitoring_registry import MetricsRegistry

# API Metrics
REQUEST_COUNT = MetricsRegistry.register_metric(
    'api_request_total',
    Counter,
    'Total API requests',
    ['method', 'endpoint']
)

REQUEST_LATENCY = MetricsRegistry.register_metric(
    'api_request_latency_seconds',
    Histogram,
    'Request latency',
    ['endpoint'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)

# Task Metrics
TASK_PROCESSING_TIME = MetricsRegistry.register_metric(
    'task_processing_seconds',
    Histogram,
    'Task processing time',
    ['task_type', 'status'],
    buckets=[1, 5, 15, 30, 60, 300, 600]
)

ACTIVE_JOBS = MetricsRegistry.register_metric(
    'active_jobs',
    Gauge,
    'Number of active jobs',
    ['job_type']
)

JOB_STATUS = MetricsRegistry.register_metric(
    'job_status_total',
    Counter,
    'Job completion status',
    ['job_type', 'status']
)

# Resource Metrics
RESOURCE_USAGE = MetricsRegistry.register_metric(
    'resource_usage',
    Gauge,
    'Resource usage percentage',
    ['resource', 'type']
)

MEMORY_USAGE = MetricsRegistry.register_metric(
    'memory_usage_bytes',
    Gauge,
    'Memory usage in bytes',
    ['type']
)

GPU_METRICS = MetricsRegistry.register_metric(
    'gpu_metrics',
    Gauge,
    'GPU metrics',
    ['device', 'metric']
)

# Model Metrics
MODEL_INFERENCE_TIME = MetricsRegistry.register_metric(
    'model_inference_seconds',
    Histogram,
    'Model inference time',
    ['model_name', 'operation'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

MODEL_BATCH_SIZE = MetricsRegistry.register_metric(
    'model_batch_size',
    Histogram,
    'Model batch size',
    ['model_name']
)

# Cache Metrics
CACHE_HITS = MetricsRegistry.register_metric(
    'cache_hits_total',
    Counter,
    'Cache hit count',
    ['cache_type']
)

CACHE_MISSES = MetricsRegistry.register_metric(
    'cache_misses_total',
    Counter,
    'Cache miss count',
    ['cache_type']
)

# Storage Metrics
STORAGE_OPERATIONS = MetricsRegistry.register_metric(
    'storage_operations_total',
    Counter,
    'Storage operations count',
    ['operation', 'status']
)

STORAGE_LATENCY = MetricsRegistry.register_metric(
    'storage_operation_seconds',
    Histogram,
    'Storage operation latency',
    ['operation'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)

# Database Metrics
DB_CONNECTIONS = MetricsRegistry.register_metric(
    'db_connections',
    Gauge,
    'Database connections',
    ['state']
)

DB_OPERATION_LATENCY = MetricsRegistry.register_metric(
    'db_operation_seconds',
    Histogram,
    'Database operation latency',
    ['operation'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)

# Queue Metrics
QUEUE_SIZE = MetricsRegistry.register_metric(
    'queue_size',
    Gauge,
    'Queue size',
    ['queue_name']
)

QUEUE_LATENCY = MetricsRegistry.register_metric(
    'queue_latency_seconds',
    Histogram,
    'Time spent in queue',
    ['queue_name'],
    buckets=[1, 5, 15, 30, 60, 300]
)

# Error Metrics
ERROR_COUNT = MetricsRegistry.register_metric(
    'error_total',
    Counter,
    'Error count',
    ['type', 'severity', 'component']
)

# Custom Business Metrics
VOICE_CLONING_SUCCESS_RATE = MetricsRegistry.register_metric(
    'voice_cloning_success_rate',
    Gauge,
    'Voice cloning success rate',
    ['model_version']
)

TRANSLATION_ACCURACY = MetricsRegistry.register_metric(
    'translation_accuracy',
    Gauge,
    'Translation accuracy score',
    ['source_lang', 'target_lang']
)

# Speaker Analysis Metrics
SPEAKER_DIARIZATION_TIME = MetricsRegistry.register_metric(
    'speaker_diarization_seconds',
    Histogram,
    'Speaker diarization processing time',
    ['status'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

SPEAKER_EXTRACTION_TIME = MetricsRegistry.register_metric(
    'speaker_extraction_seconds',
    Histogram,
    'Speaker extraction processing time',
    ['status'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

SPEAKER_COUNT = MetricsRegistry.register_metric(
    'speaker_count',
    Histogram,
    'Number of speakers detected',
    ['job_type']
)

SPEAKER_CONFIDENCE = MetricsRegistry.register_metric(
    'speaker_confidence',
    Histogram,
    'Speaker detection confidence',
    ['job_type']
)

SPEAKER_PROCESSING_ERRORS = MetricsRegistry.register_metric(
    'speaker_processing_errors_total',
    Counter,
    'Speaker processing errors',
    ['job_type', 'error_type']
)

SPEAKER_QUEUE_SIZE = MetricsRegistry.register_metric(
    'speaker_queue_size',
    Gauge,
    'Speaker processing queue size',
    ['job_type']
)

GPU_MEMORY_USAGE = MetricsRegistry.register_metric(
    'gpu_memory_usage_bytes',
    Gauge,
    'GPU memory usage in bytes',
    ['device']
)

GPU_UTILIZATION = MetricsRegistry.register_metric(
    'gpu_utilization_percent',
    Gauge,
    'GPU utilization percentage',
    ['device']
)

# Add denoising metrics
DENOISING_PROCESSING_TIME = MetricsRegistry.register_metric(
    'denoising_processing_seconds',
    Histogram,
    'Audio denoising processing time',
    ['status'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

NOISE_REDUCTION_LEVEL = MetricsRegistry.register_metric(
    'noise_reduction_db',
    Histogram,
    'Noise reduction level in dB',
    ['status']
)

VAD_CONFIDENCE = MetricsRegistry.register_metric(
    'vad_confidence',
    Histogram,
    'Voice Activity Detection confidence',
    []
)

# Add new metrics for spectral denoising
SPECTRAL_DENOISING_TIME = MetricsRegistry.register_metric(
    'spectral_denoising_seconds',
    Histogram,
    'Spectral denoising processing time',
    ['status'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

SPECTRAL_NOISE_REDUCTION = MetricsRegistry.register_metric(
    'spectral_noise_reduction_db',
    Histogram,
    'Spectral noise reduction level in dB',
    ['status']
)

# Add these metrics
DENOISER_PROCESSING_TIME = Histogram(
    'denoiser_processing_time_seconds',
    'Time spent processing audio with denoiser',
    ['status']
)

DENOISER_MEMORY_USAGE = Gauge(
    'denoiser_memory_usage_bytes',
    'Memory usage of denoiser service',
    ['device']
)

DENOISER_BATCH_SIZE = Histogram(
    'denoiser_batch_size_seconds',
    'Audio length being processed',
    ['status']
)

DENOISER_ERROR_COUNT = Counter(
    'denoiser_error_count',
    'Number of denoiser errors',
    ['error_type']
)