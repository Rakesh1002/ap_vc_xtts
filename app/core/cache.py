from typing import Any, Optional
import json
import redis
from app.core.config import get_settings
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)
settings = get_settings()

# Add to cache configuration
DENOISED_AUDIO_CACHE_TTL = 3600  # 1 hour

class CacheManager:
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=1,  # Use different DB than Celery
            decode_responses=True
        )
        self.default_ttl = 3600  # 1 hour

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = self.redis.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        nx: bool = False
    ) -> bool:
        """Set value in cache"""
        try:
            return self.redis.set(
                key,
                json.dumps(value),
                ex=ttl or self.default_ttl,
                nx=nx
            )
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            return bool(self.redis.delete(key))
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter"""
        try:
            return self.redis.incr(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error: {e}")
            return 0

    async def get_or_set(
        self,
        key: str,
        func: callable,
        ttl: Optional[int] = None
    ) -> Any:
        """Get from cache or compute and store"""
        try:
            value = await self.get(key)
            if value is not None:
                return value
                
            value = await func()
            await self.set(key, value, ttl)
            return value
            
        except Exception as e:
            logger.error(f"Cache get_or_set error: {e}")
            return await func()

cache_manager = CacheManager() 