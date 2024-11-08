"""Core optimization and resource management"""
import torch
import gc
import logging
from typing import Dict, Any
from app.core.metrics import MEMORY_USAGE, GPU_MEMORY_USAGE, GPU_UTILIZATION

logger = logging.getLogger(__name__)

class ResourceOptimizer:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.is_gpu_available = torch.cuda.is_available()

    def optimize_for_inference(self):
        """Optimize system for model inference"""
        if self.is_gpu_available:
            # Clear GPU cache
            torch.cuda.empty_cache()
            
            # Set memory growth
            torch.cuda.set_per_process_memory_fraction(0.7)
            
            # Update GPU metrics
            self._update_gpu_metrics()
        
        # Run garbage collection
        gc.collect()
        
        # Update memory metrics
        self._update_memory_metrics()

    def cleanup(self):
        """Cleanup resources after processing"""
        if self.is_gpu_available:
            torch.cuda.empty_cache()
        gc.collect()
        self._update_all_metrics()

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get current memory statistics"""
        stats = {
            'ram_used': self._get_ram_usage(),
            'ram_available': self._get_ram_available()
        }
        
        if self.is_gpu_available:
            stats.update({
                'gpu_used': self._get_gpu_memory_used(),
                'gpu_available': self._get_gpu_memory_available(),
                'gpu_utilization': self._get_gpu_utilization()
            })
            
        return stats

    def _update_memory_metrics(self):
        """Update RAM memory metrics"""
        MEMORY_USAGE.labels(type="used").set(self._get_ram_usage())
        MEMORY_USAGE.labels(type="available").set(self._get_ram_available())

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
        return 0  # TODO: Implement actual RAM usage tracking

    def _get_ram_available(self) -> int:
        """Get available RAM in bytes"""
        return 0  # TODO: Implement actual RAM availability tracking

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

resource_optimizer = ResourceOptimizer()