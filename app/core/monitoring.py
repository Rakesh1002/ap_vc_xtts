from prometheus_client import Counter, Histogram, Gauge
import psutil
import logging
from typing import Dict, Any
import time
from functools import wraps
from app.core.memory import memory_manager
import asyncio

logger = logging.getLogger(__name__)

# Metrics
REQUEST_COUNT = Counter('api_request_total', 'Total API requests', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('api_request_latency_seconds', 'Request latency', ['endpoint'])
TASK_PROCESSING_TIME = Histogram('task_processing_seconds', 'Task processing time', ['task_type'])
QUEUE_SIZE = Gauge('task_queue_size', 'Current queue size', ['queue_name'])
MEMORY_USAGE = Gauge('memory_usage_bytes', 'Memory usage in bytes')
GPU_MEMORY_USAGE = Gauge('gpu_memory_usage_bytes', 'GPU memory usage in bytes')
ERROR_COUNT = Counter('error_total', 'Total errors', ['type', 'severity'])

class PerformanceMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.memory_manager = memory_manager

    def track_request(self, method: str, endpoint: str):
        """Track API request metrics"""
        REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()

    def track_latency(self, endpoint: str, duration: float):
        """Track request latency"""
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)

    def update_queue_metrics(self, queue_stats: Dict[str, int]):
        """Update queue metrics"""
        for queue_name, size in queue_stats.items():
            QUEUE_SIZE.labels(queue_name=queue_name).set(size)

    def update_resource_metrics(self):
        """Update resource usage metrics"""
        # Memory usage
        memory_stats = self.memory_manager.get_memory_stats()
        MEMORY_USAGE.set(psutil.Process().memory_info().rss)
        
        # GPU metrics if available
        if 'gpu_allocated' in memory_stats:
            GPU_MEMORY_USAGE.set(float(memory_stats['gpu_allocated'].replace('MB', '')))

    def track_error(self, error_type: str, severity: str):
        """Track error metrics"""
        ERROR_COUNT.labels(type=error_type, severity=severity).inc()

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        return {
            'uptime_seconds': time.time() - self.start_time,
            'memory_stats': self.memory_manager.get_memory_stats(),
            'cpu_percent': psutil.cpu_percent(),
            'open_files': len(psutil.Process().open_files()),
            'thread_count': psutil.Process().num_threads()
        }

def track_performance(task_type: str = None):
    """Decorator to track task performance"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                if task_type:
                    TASK_PROCESSING_TIME.labels(task_type=task_type).observe(duration)
                return result
            except Exception as e:
                monitor.track_error(type(e).__name__, 'high')
                raise
                
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                if task_type:
                    TASK_PROCESSING_TIME.labels(task_type=task_type).observe(duration)
                return result
            except Exception as e:
                monitor.track_error(type(e).__name__, 'high')
                raise
                
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

monitor = PerformanceMonitor() 