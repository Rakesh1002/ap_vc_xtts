"""Core optimization and resource management"""
import torch
import gc
import logging
import psutil
import os
from typing import Dict, Any
from app.core.metrics import MEMORY_USAGE, GPU_MEMORY_USAGE, GPU_UTILIZATION
from functools import wraps

logger = logging.getLogger(__name__)

class ResourceOptimizer:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.is_gpu_available = torch.cuda.is_available()
        self.process = psutil.Process(os.getpid())

    def optimize_for_inference(self):
        """Optimize system for model inference"""
        if self.is_gpu_available:
            # Clear GPU cache
            torch.cuda.empty_cache()
            
            # Set memory growth
            torch.cuda.set_per_process_memory_fraction(0.7)
            
            # Reset peak memory stats
            torch.cuda.reset_peak_memory_stats()
            
            # Update GPU metrics
            self._update_gpu_metrics()
        
        # Run garbage collection
        gc.collect()
        
        # Update memory metrics
        self._update_memory_metrics()

    def optimize_for_denoising(self):
        """Optimize system resources for denoising tasks"""
        try:
            if torch.cuda.is_available():
                # Set optimal CUDA settings
                torch.backends.cudnn.benchmark = True
                torch.backends.cudnn.deterministic = False
                
                # Clear GPU cache
                torch.cuda.empty_cache()
                
                # Set device specific optimizations
                device = torch.cuda.current_device()
                torch.cuda.set_device(device)
                
                # Log optimization status
                logger.info(f"Optimized CUDA settings for denoising on device {device}")
                
            # Set CPU thread optimizations
            torch.set_num_threads(4)  # Limit CPU threads for better memory usage
            
        except Exception as e:
            logger.error(f"Failed to optimize resources: {str(e)}")

    def cleanup(self):
        """Cleanup resources after processing"""
        if self.is_gpu_available:
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
        
        # Multiple GC passes
        for _ in range(3):
            gc.collect()
        
        self._update_all_metrics()

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get current memory statistics"""
        stats = {
            'ram_used': self._get_ram_usage(),
            'ram_available': self._get_ram_available(),
            'process_memory': self.process.memory_info().rss
        }
        
        if self.is_gpu_available:
            stats.update({
                'gpu_used': self._get_gpu_memory_used(),
                'gpu_available': self._get_gpu_memory_available(),
                'gpu_utilization': self._get_gpu_utilization(),
                'gpu_peak_memory': torch.cuda.max_memory_allocated()
            })
            
        return stats

    def _update_memory_metrics(self):
        """Update RAM memory metrics"""
        MEMORY_USAGE.labels(type="used").set(self._get_ram_usage())
        MEMORY_USAGE.labels(type="available").set(self._get_ram_available())
        MEMORY_USAGE.labels(type="process").set(self.process.memory_info().rss)

    def _update_gpu_metrics(self):
        """Update GPU metrics"""
        if self.is_gpu_available:
            GPU_MEMORY_USAGE.labels(device="cuda:0").set(self._get_gpu_memory_used())
            GPU_UTILIZATION.labels(device="cuda:0").set(self._get_gpu_utilization())

    def _update_all_metrics(self):
        """Update all resource metrics"""
        self._update_memory_metrics()
        if self.is_gpu_available:
            self._update_gpu_metrics()

    def _get_ram_usage(self) -> int:
        """Get RAM usage in bytes"""
        return self.process.memory_info().rss

    def _get_ram_available(self) -> int:
        """Get available RAM in bytes"""
        return psutil.virtual_memory().available

    def _get_gpu_memory_used(self) -> int:
        """Get GPU memory usage in bytes"""
        if self.is_gpu_available:
            return torch.cuda.memory_allocated()
        return 0

    def _get_gpu_memory_available(self) -> int:
        """Get available GPU memory in bytes"""
        if self.is_gpu_available:
            return torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated()
        return 0

    def _get_gpu_utilization(self) -> float:
        """Get GPU utilization percentage"""
        if self.is_gpu_available:
            return torch.cuda.utilization()
        return 0.0

def optimize_array_processing(func):
    """Decorator to optimize array processing functions"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            # Clear memory before processing
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
            
            # Run function
            result = await func(*args, **kwargs)
            
            # Clear memory after processing
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
            
            return result
            
        except Exception as e:
            logger.error(f"Error in array processing: {e}")
            raise
            
    return wrapper

resource_optimizer = ResourceOptimizer()