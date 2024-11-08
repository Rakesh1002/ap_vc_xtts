"""Centralized monitoring configuration"""
from prometheus_client import Counter, Histogram, Gauge
from typing import Dict, Any, List, Optional, Type, Union
import logging

logger = logging.getLogger(__name__)

DEFAULT_BUCKETS = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]

class MetricsRegistry:
    _metrics: Dict[str, Any] = {}
    
    @classmethod
    def register_metric(
        cls,
        name: str,
        metric_type: Type[Union[Counter, Histogram, Gauge]],
        description: str,
        labels: Optional[List[str]] = None,
        **kwargs
    ):
        """Register a Prometheus metric with additional configuration"""
        if name not in cls._metrics:
            if metric_type == Counter:
                cls._metrics[name] = Counter(
                    name,
                    description,
                    labels or []
                )
            elif metric_type == Histogram:
                buckets = kwargs.get('buckets', DEFAULT_BUCKETS)
                cls._metrics[name] = Histogram(
                    name,
                    description,
                    labels or [],
                    buckets=buckets
                )
            elif metric_type == Gauge:
                cls._metrics[name] = Gauge(
                    name,
                    description,
                    labels or []
                )
        return cls._metrics[name]
    
    @classmethod
    def get_metric(cls, name: str):
        """Get registered metric by name"""
        return cls._metrics.get(name)

    @classmethod
    def clear_metrics(cls):
        """Clear all registered metrics"""
        cls._metrics.clear()

    @classmethod
    def get_all_metrics(cls) -> Dict[str, Any]:
        """Get all registered metrics"""
        return cls._metrics.copy()

    @classmethod
    def metric_exists(cls, name: str) -> bool:
        """Check if a metric exists"""
        return name in cls._metrics

# Register base metrics with default buckets
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
    buckets=DEFAULT_BUCKETS
)

TASK_PROCESSING_TIME = MetricsRegistry.register_metric(
    'task_processing_seconds',
    Histogram,
    'Task processing time',
    ['task_type', 'status'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

ACTIVE_JOBS = MetricsRegistry.register_metric(
    'active_jobs',
    Gauge,
    'Currently active jobs',
    ['job_type']
)

JOB_STATUS = MetricsRegistry.register_metric(
    'job_status_total',
    Counter,
    'Job completion status',
    ['job_type', 'status']
)

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

MODEL_INFERENCE_TIME = MetricsRegistry.register_metric(
    'model_inference_seconds',
    Histogram,
    'Model inference time',
    ['model_name', 'operation'],
    buckets=[1, 5, 10, 30, 60, 120]
)

MODEL_BATCH_SIZE = MetricsRegistry.register_metric(
    'model_batch_size',
    Histogram,
    'Model batch size',
    ['model_name']
)

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

ERROR_COUNT = MetricsRegistry.register_metric(
    'error_total',
    Counter,
    'Error count',
    ['type', 'severity', 'component']
)

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