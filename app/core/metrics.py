from prometheus_client import Counter, Histogram, Gauge
import time

# Request metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint']
)

# Job metrics
ACTIVE_JOBS = Gauge(
    'active_jobs',
    'Number of currently active jobs',
    ['job_type']
)

JOB_DURATION = Histogram(
    'job_duration_seconds',
    'Job processing duration in seconds',
    ['job_type']
)

JOB_STATUS = Counter(
    'job_status_total',
    'Total number of jobs by status',
    ['job_type', 'status']
)

# Model metrics
MODEL_INFERENCE_TIME = Histogram(
    'model_inference_seconds',
    'Model inference time in seconds',
    ['model_name']
)

class MetricsMiddleware:
    async def __call__(self, request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        return response

def track_job_metrics():
    def decorator(func):
        async def wrapper(*args, **kwargs):
            job_type = func.__name__
            
            ACTIVE_JOBS.labels(job_type=job_type).inc()
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                JOB_STATUS.labels(
                    job_type=job_type,
                    status='success'
                ).inc()
                return result
            except Exception as e:
                JOB_STATUS.labels(
                    job_type=job_type,
                    status='failure'
                ).inc()
                raise e
            finally:
                duration = time.time() - start_time
                JOB_DURATION.labels(job_type=job_type).observe(duration)
                ACTIVE_JOBS.labels(job_type=job_type).dec()
                
        return wrapper
    return decorator 