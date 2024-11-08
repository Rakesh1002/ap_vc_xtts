from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import redis
from app.core.config import get_settings
import time
import logging
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY

settings = get_settings()
logger = logging.getLogger(__name__)

# Update rate limits
RATE_LIMITS = {
    # ... existing limits ...
    'denoiser': {
        'requests_per_minute': 15,
        'burst_size': 30
    }
}

class RateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.rate_limit = 100  # requests per minute
        self.window = 60  # seconds

    async def check_rate_limit(self, key: str) -> bool:
        current = int(time.time())
        window_key = f"{key}:{current // self.window}"
        
        count = self.redis.incr(window_key)
        if count == 1:
            self.redis.expire(window_key, self.window)
        
        return count <= self.rate_limit

async def rate_limit_middleware(request: Request, call_next):
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True
    )
    
    limiter = RateLimiter(redis_client)
    
    # Use IP address as rate limit key
    client_ip = request.client.host
    
    if not await limiter.check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests"}
        )
    
    response = await call_next(request)
    return response 

async def metrics_middleware(request: Request, call_next):
    """Middleware to collect request metrics"""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        
        # Record request count with method and endpoint
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path
        ).inc()
        
        # Record latency
        duration = time.time() - start_time
        REQUEST_LATENCY.labels(
            endpoint=request.url.path
        ).observe(duration)
        
        return response
        
    except Exception as e:
        # Record error count
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path
        ).inc()
        
        logger.exception("Error in request processing")
        raise