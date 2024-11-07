from typing import Optional, Dict, Any
import torch
import psutil
import gc
from functools import wraps
import time
import logging
from app.core.metrics import MODEL_INFERENCE_TIME
from app.core.device import get_device_manager
from app.core.errors import AudioProcessingError, ErrorCodes, ErrorSeverity, ErrorCategory

logger = logging.getLogger(__name__)

class PerformanceOptimizer:
    def __init__(self):
        self.device_manager = get_device_manager()
        self.memory_threshold = 0.85  # 85% memory usage threshold
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes
        
    def check_resources(self) -> Dict[str, float]:
        """Check system resource usage"""
        stats = {
            "cpu_percent": psutil.cpu_percent(),
            "ram_percent": psutil.virtual_memory().percent,
        }
        
        if self.device_manager.is_gpu_available:
            for i in range(torch.cuda.device_count()):
                allocated = torch.cuda.memory_allocated(i) / torch.cuda.get_device_properties(i).total_memory
                stats[f"gpu_{i}_memory_percent"] = allocated * 100
                
        return stats
    
    def optimize_memory(self):
        """Perform memory optimization if needed"""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
            
        stats = self.check_resources()
        needs_cleanup = any(
            v > self.memory_threshold * 100 for k, v in stats.items() 
            if k.endswith("_percent")
        )
        
        if needs_cleanup:
            logger.info("Performing memory cleanup")
            self._cleanup_memory()
            self.last_cleanup = current_time
    
    def _cleanup_memory(self):
        """Perform thorough memory cleanup"""
        # Python garbage collection
        gc.collect()
        
        # Clear CUDA cache if available
        if self.device_manager.is_gpu_available:
            torch.cuda.empty_cache()
            
        # Clear any model-specific caches
        # Add model-specific cache clearing here
        
        # Log memory stats after cleanup
        stats = self.check_resources()
        logger.info(f"Memory stats after cleanup: {stats}")

def optimize_performance(timeout: Optional[float] = None):
    """Decorator for optimizing performance of resource-intensive operations"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            optimizer = PerformanceOptimizer()
            
            # Check resources before execution
            pre_stats = optimizer.check_resources()
            logger.debug(f"Resource stats before {func.__name__}: {pre_stats}")
            
            # Optimize memory if needed
            optimizer.optimize_memory()
            
            start_time = time.time()
            try:
                # Execute the function with timeout if specified
                if timeout:
                    # Implement timeout logic here
                    pass
                
                result = await func(*args, **kwargs)
                
                # Record metrics
                execution_time = time.time() - start_time
                MODEL_INFERENCE_TIME.labels(
                    model_name=func.__name__
                ).observe(execution_time)
                
                return result
                
            except Exception as e:
                # Check if error is resource-related
                post_stats = optimizer.check_resources()
                if any(v > 95 for v in post_stats.values()):
                    raise AudioProcessingError(
                        message="Resource exhaustion during processing",
                        error_code=ErrorCodes.RESOURCE_EXHAUSTED,
                        details={"resource_stats": post_stats},
                        severity=ErrorSeverity.HIGH,
                        category=ErrorCategory.SYSTEM,
                        original_error=e
                    )
                raise
                
            finally:
                # Log resource usage
                post_stats = optimizer.check_resources()
                logger.debug(f"Resource stats after {func.__name__}: {post_stats}")
                
                # Cleanup if necessary
                optimizer.optimize_memory()
                
        return wrapper
    return decorator

# Example usage in voice cloning service:
@optimize_performance(timeout=300)
async def process_voice_cloning(self, voice_file_path: str, text: str) -> str:
    # Existing voice cloning logic
    pass 